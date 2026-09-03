# crews/ 架构 — 三阶段编排

`pipeline.py` 决定“什么时候跑什么”，本包决定“每个阶段具体怎么跑”。

## 四个 Runner + 一个对齐检查器

| Runner | 阶段 | 模式 | 输入 → 输出 |
|---|---|---|---|
| `ResearchCrewRunner` | Research / Augment | Orchestrator → 对齐检查 → N 个研究员并行 | question → `list[ResearchCard]` |
| `ReflectionCrewRunner` | Reflect | 单人评审 | cards → `ReflectionResult(quality_score, feedback)` |
| `VerificationCrewRunner` | Verify | 每卡 3 轮对抗辩论 + 跨卡分析 | cards → `list[VerifiedCard]` |
| `SynthesisCrewRunner` | Synthesize | Scorer ∥ Extractor（barrier）→ Editor | verified cards → score + insights + report 文件 |
| `alignment-checker`（Research 内部） | 对齐门 | 无工具，DeepSeek，json_object | 跑题子问题 → 修正后 briefs |

## ResearchCrewRunner 细节

### 查询规划器（新增，先于 Orchestrator）

- 输入问题，输出：`question_type`、`key_constraints`、`search_plan`。
- `search_plan` 包含：策略摘要、优先来源、具体子查询、验证步骤、是否允许质量工具。
- 问题类型：entity_fact / multi_hop_clue / comparative / news_current / technical / academic / policy_legal / business_market / historical_archive / general。
- 规划器失败时回退通用方案，绝不阻塞研究。

### Orchestrator

- `ORCHESTRATOR_TASK` 第一条是**研究对象铁律**：sub_question 不得替换研究对象、
  不得擅自收窄/扩大范围；明确用“个人 PC → AI PC”作为反例。
- 动态生成 3–6 个视角；`_DEFAULT_PERSPECTIVES` 只在 Orchestrator 失败/旧格式时回退。
- `_normalise_role()` 把自由角色名映射回固定池，避免 experience 统计碎片化。

### 对齐门（新增，防跑题）

1. `_check_alignment()`：字符重叠粗筛，`ALIGNMENT_MIN_OVERLAP=0.2`，只告警不丢弃；
   抓不住“个人 PC → AI PC”这种前缀替换。
2. `_align_perspectives()`：调用 `alignment-checker`（DeepSeek，无工具，
   `response_format={"type":"json_object"}`），逐条输出 `aligned` 和修正版 `sub_question`。
3. **任何失败都回退原始 briefs，绝不阻塞研究**。

### Researcher 重试

- `MAX_RETRIES=2`；每次失败用“严格只输出 JSON”重试。
- 全部失败返回空卡（gap 说明失败）；augment 重跑用 `replace=True` 写 DB。
- 重试耗尽后若最后输出非 JSON，会调用 `researcher-salvage-*` 无工具格式化 Agent，
  把 Markdown/散文转换为标准 JSON 研究卡，降低 all attempts exhausted。
- `response_format={"type":"json_object"}` 由 `agents/registry.py` 注入，
  已实测带工具 agent 仍会正常调用搜索工具。

### 自适应计算分配（Adaptive Compute Allocation）

- `adaptive.py` 是纯确定性模块，不调 LLM：输入问题类型、视角列表、search_plan，
  输出每个视角的 `ComputeAllocation(depth, max_tool_calls, max_tool_rounds)`。
- `ResearchCrewRunner.run()` 在 Orchestrator 之后计算 `compute_plan`，
  写入 blackboard `compute_plan` 并推送到事件流；每个 Researcher 的
  `ResourceBudget.max_tool_calls` 与 `max_tool_rounds` 来自该视角的分配。
- `augment()` 不再无差别重跑所有卡片：用 `card_weakness_score()` 给每张卡打分
  （发现数少、低置信度占比高、缺来源、盲区多），只选弱卡补强；
  若全部都不弱但质量门仍失败，则补最弱的一半，避免空转。
- 每张被补强的卡按 weakness 获得动态预算：弱卡 depth 3，普通卡 depth 2，
  强卡 depth 1；后续 augment 轮次预算递增 15%。
- 预算只限制工具调用轮数和次数，不限制 LLM 调用次数，避免把“还能收敛”的
  研究任务变成空回复。

## Reflect 是质量门，不是决策者

- 0 findings 直接返回 `quality_score=0, skipped=True`，不调 LLM。
- reflector 只打分/给 feedback；`pipeline.py` 用 `QUALITY_THRESHOLD=60` + `MIN_FINDINGS=3` 做确定性判定。
- feedback 必须具体到“搜什么关键词、补什么证据”。
- **Firecrawl/知识库只在质量门失败后的 augment 轮启用**：`research_crew.augment()`
  收到 feedback 时用 `get_quality_search_tools()`（含 Wikipedia/Wikidata/Firecrawl/Tavily），
  平时研究只用 `get_search_tools()`（Baidu/Bing，完全不消耗 Firecrawl）。

## Verification 三轮协议

1. verifier 查证每条 claim（web_fetch + sqlite_read）；
2. refuter 搜索反证，生成 refutations；
3. verifier 回应反驳，给出最终 entries 和 resolved 状态。
4. 若第一轮结果非全 verified，运行**独立二次核查员**（不参考前序结论，使用质量工具），
   区分 `fact_status` 与 `presentation_issues`，并与第一轮结果合并。
- 零 findings 的卡片跳过；跨卡分析结果写 `blackboard["run:<run_id>:cross_checks"]`。

## Candidate Verification（新增，仅适合题型）

- 适合：entity_fact / multi_hop_clue / historical_archive。
- 不适合：technical / academic / news_current / business_market / general 等开放题。
- 在 Synthesis 前运行，使用 `get_quality_search_tools()` 对候选逐条验证。
- 输出 `final_candidate` / `confidence` / `candidates[]`，写入 evidence 并注入 Editor。

## Synthesis：来源分级已接入评分

- `SCORER_TASK` 现在按 `web_fetch` 的 `[来源: 标签 ★]` 打分：
  ★★★★=5、★★★=4、★★=2、★=1；无 ★★★★ 来源的声明来源可靠性最多 3。
- Editor 读 `_build_data_summary()` 的编号声明摘要（“视角 + 声明#N”），**不再自己调工具**。
- Editor 产出报告后，`ClaimAnnotator` 生成 `claims.json`（Phase A，非破坏式标注，不改写报告）；
  随后 `AtomicClaimVerifier` 对未覆盖 claim 做原子验证（Phase B）。
- 产物：`report.md`、`evidence.json`、`claims.json`、`audit.jsonl`。

## 约束

1. LLM JSON 解析统一用 `response_parser.parse_json_response` + `safe_construct_*`。
2. Agent 创建统一走 `agents.registry.create_agent()`；对齐检查器是唯一的 ad-hoc agent，
   保持无工具 + json_object + 失败可回退。
3. 新增阶段先更新本文件，再到 `pipeline.py` 加节点/边。
4. 并行任务用 `core.orchestrator.parallel`（异常容忍）。
