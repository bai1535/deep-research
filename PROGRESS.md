# PROGRESS.md — 当前进度

> 更新日期：2026-09-03。每次会话结束前更新“进行中 / 阻塞 / 下一步”三节。

## 已完成（部分在 working tree，尚未 commit）

- 三阶段研究流水线：Research(+Alignment/Reflect/Augment) → Verify(三轮对抗核查) → Synthesis，
  支持 graph checkpoint / resume。
- `core/` 基础设施：Agent 循环、BuildTool、StateGraph、Blackboard、FileCache、Compressor、EventBus。
- Web API + SSE + Docker Compose 部署；当前容器 `healthy`。
- 经验层、`qwen_patch`、`response_parser`、`safe_construct`、trace_id 日志。
- **P0 搜索可靠性**：Baidu/Bing 免费引擎优先；Firecrawl/Tavily 按 key 门控；DDG 移除；
  不可恢复错误进程级禁用；429 进程级 60s cooldown（search 与 web_fetch 共享）。
- **结构化输出**：12 个 JSON agent 启用 `response_format={"type":"json_object"}`；
  实测带工具 agent 仍正常 tool_calls；解析失败从 8 次降到 0–2 次。
- **空返回修复**：`tools-failed` 提前终止返回 `_tool_error_summary`，不再产生 Empty input。
- **研究对象对齐门**：Orchestrator 铁律 + 字符粗筛 + `alignment-checker`（DeepSeek）
  修正跑题子问题；最新 run 视角已围绕“个人 PC”而非“AI PC”。
- **搜索调用可观测性**：`core/call_log.py` 写 `logs/search_calls.jsonl`；
  最新 run 记录 128 次调用（bing 51 / web_fetch 37 / baidu 25 / firecrawl 9 / tavily 4 / sqlite 2）。
- **Web 日志查看器**：`GET /logs` + `/api/logs/*`，支持文本日志实时尾随、全文搜索、
  级别过滤，以及 search_calls 按 run/tool/status 筛选；可选 `LOG_VIEWER_TOKEN` 保护。
- **来源分级接入评分**：Scorer 按 `web_fetch` 的 `[来源: ★]` 标签给来源可靠性打分。
- **测试体系修复**：`tests/test_db.py` 改为 asyncpg/PostgreSQL 真实库测试，
  `tests/test_config.py` 适配当前 Config；Makefile 增加 pytest-asyncio 的
  `asyncio_mode=auto` 与 session 级 event loop 配置；`make test` 当前 **35 passed**。
- **效果评估体系**：新增 `scripts/search_eval.py`（可用率、延迟、Hit@k、nDCG@k），
  `agent.py` 日志开始记录 `result_urls`，`Makefile` 增加 `make eval`。
- **解析器引号修复**：`response_parser.py` 解析前归一化全角双引号 `“”`，
  新增 `tests/test_response_parser.py`，降低 `ALL parse strategies failed` 概率。
- **公开基准接入**：新增 `scripts/eval_benchmarks.py`，支持 DeepResearch Bench（100 任务）
  和 BrowseComp-Plus（830 题），`Makefile` 增加 `make eval-bench`。
- **搜索策略优化**：Bing 英文 query 使用 `mkt=en-US&setlang=en&ensearch=1`；
  给带搜索工具的 Agent 注入拆解锚点/精确短语/`site:`/避免重复查询的策略提示。
- **日志过滤与 Scorer 容错**：日志查看器 ERROR 过滤改为正则匹配带 padding 的级别；
  `ScoreResult.overall_score` 增加默认值 0，避免 Total failure。
- **日志查看器可读性**：强制 `color-scheme: dark`，日志行默认浅色文字，避免黑字黑底。
- **Wikipedia/Wikidata 工具 + 最终答案抽取器**：新增 `wikipedia_search` / `wikidata_lookup`
  供研究员/反驳者查询百科与结构化事实；报告生成后用 `final_answer.py` 抽取简洁最终答案，
  写入 `evidence.json` / `answer.txt`，并新增 `/research/{run_id}/answer` 接口与评测字段。
- **ModSearch 借鉴：Firecrawl keyless 桥接**：`wikipedia_search` / `wikidata_lookup` 改走
  Firecrawl keyless 搜索/抓取，绕开 CN 被墙的 wikipedia.org/wikidata.org 直连；
  `FirecrawlSearchTool` / `WebFetchTool` 无 key 时也自动走 keyless 免费通道。
- **Firecrawl 省额度策略**：默认研究只注册 Baidu/Bing（完全不消耗 Firecrawl）；
  Wikipedia/Wikidata/Firecrawl/Tavily 只在 Reflector 质量门不达标触发 augment 时，
  通过 `get_quality_search_tools()` 启用。
- **轻量每轮搜索质量门**：研究员某轮 Baidu/Bing 结果全错/为空/少于 2 条 URL 时，
  Agent 自动解锁保留的 `firecrawl_search`/`wikipedia_search`/`wikidata_lookup`，
  不用等整轮 Reflector 才补救。
- **查询规划器**：研究开始前先分析问题类型，生成按类型区分的搜索方案
  （实体事实/多跳线索/对比/实时/技术/学术/政策/商业/历史/通用），
  并把子查询、优先源、验证步骤注入 Orchestrator 和 Researcher。
- **日志页面稳定性与对比度修复**：请求增加超时、防重叠/防过期响应、
  回到前台自动刷新；日志区背景更黑、文字更亮，级别颜色提高对比度；
  增量追加日志行，避免每次全量重绘导致页面卡住。
- **候选答案验证循环**：仅对 entity_fact / multi_hop_clue / historical_archive
  等离散答案题型启用；对候选逐条验证，输出 final_candidate 并写入 evidence。
- **Wayback Machine 历史档案接入**：新增 `wayback_lookup`，通过 Firecrawl keyless
  查询 archive.org 历史快照并抓取旧页面，用于 2002/2003 等旧事件验证。
- **自动评测 Judge**：新增 `scripts/eval_judge.py` 和 `make judge`，用 DeepSeek
  对比 `final_answer` 与 gold，输出 yes/partial/no 和 0-100 分数。
- **Verifier 主动搜索 + 矛盾裁决器**：Verifier 增加搜索工具可主动找反证；
  跨视角出现矛盾时由专门 Agent 裁决并写入 cross-check。
- **候选验证结果归一化**：兼容 LLM 返回单个候选对象而非 `candidates` 数组，
  避免 candidates=0 导致候选被忽略；并增加置信度门槛，低分候选不强制作为最终答案。
- **事件溯源 Phase 1**：新增事件模型与 JSONL 事件存储，Agent 工具调用和 LLM 调用
  开始记录不可变事件，支持基础因果链查询与 rollback_to 前缀回滚。
- **因果回溯引擎**：从最终声明沿事件 DAG 反向定位污染源，输出可疑事件链和污染评分。
- **确定性缓存与重放**：新增 OutputCache 和 ReplayEngine，可复用已缓存输出生成重放计划。
- **分支级回滚与 API**：可计算受影响/未受影响分支，新增 `/events`、`/rollback`、`/trace` 接口。
- **实际执行 rollback**：清除受影响分支缓存、写入 rollback_state.json，`/rollback` 支持 execute。
- **重放受影响分支**：回滚后可自动重放受影响的外部工具调用，记录 replay_output.jsonl 并更新状态。
- **重放 LLM + 重新生成报告**：回滚+重放工具后重新运行合成阶段，更新报告和 evidence。
- **日志/前端事件查看和回滚入口**：日志页新增“事件/回滚”页签，可查看事件、执行回滚/重放/重新生成。
- **Verifier 状态容错 + Researcher JSON 约束**：Verifier 状态自动归一化（verfied→verified 等）；
  Researcher 输出 JSON 的提示和重试提示强化。
- **Claim 级溯源 Phase A**：新增 ClaimNode/AnswerDocument 数据模型与 ClaimAnnotator，
  从最终报告抽取可追溯 claims 并写入 claims.json，不改写报告原文；已接入 Synthesis 阶段。
- **Claim 级溯源 Phase B**：新增 AtomicClaimVerifier，对未覆盖/未验证的 claim 逐条
  使用质量搜索工具做原子验证，更新 claims.json 的状态、置信度、证据、推理和事件 ID。
- **Claim 级溯源 Phase C**：新增 `/research/{run_id}/claims` 与
  `/research/{run_id}/claims/{claim_id}/trace` API，以及 `/report/{run_id}` 报告证据
  双视图页面（流畅版/证据版），支持点击 claim 查看证据链与事件回溯。
- **Claim 级溯源 Phase D**：新增 `scripts/eval_claims.py` 评估 Claim 溯源指标
  （覆盖率/证据覆盖率/可追溯性/验证通过率/粒度审计），新增黄金拆分样例
  `data/claim_golden.json`，并增加 `make eval-claims` 目标。
- **主报告页证据可视化修复（F25）**：在报告正文中按 claim 位置插入彩色上标
  （不同可信度不同颜色），点击上标跳转到对应证据注释；`report.html` 同样支持
  上标跳转到证据版；裸 URL 自动可点击。
- **Verifier 独立二次核查（F26）**：新增独立二次核查员，不参考第一轮结论，
  使用质量工具重新验证；区分 `fact_status` 与 `presentation_issues`，
  可将“事实正确但因表述/口径被降级”的 claim 恢复为 verified。
- **日志页自动刷新增强（F27）**：autoTail 开启时无论 tail/search 都持续刷新，
  增加看门狗强制重载，回到前台时重置 busy 并重启定时器。
- **Researcher 输出救捞（F28）**：当 Researcher 多次输出非 JSON 后，
  用无工具格式化 Agent 将 Markdown/散文转换为标准 JSON 研究卡，减少 all attempts exhausted。
- **Agent 独立性治理 Phase 1（F29）**：新增 AgentPolicy 数据模型与默认策略，
  `create_agent` 自动为每个 Agent 附加 Policy（仅元数据，不改变行为）。
- **Agent 独立性治理 Phase 2（F30）**：新增 ScopedBlackboard 按 ContextPolicy
  限制 Blackboard 读写；Agent 工具调用前按 ToolPolicy 检查允许/禁止/配额。
- **Agent 独立性治理 Phase 3（F31）**：ResourceBudget 真正限制工具/LLM/token/成本，
  策略拒绝写入 `logs/policy_audit.jsonl`。
- **Agent 独立性治理 Phase 4（F32）**：VerificationStandard 渲染为系统提示中的
  验证标准块，不同 Agent 使用 Policy 定义的评分 rubric。
- **Agent 独立性治理 Phase 5（F33）**：second-opinion/contradiction-adjudicator
  的 ContextPolicy 限制 Blackboard 读写，运行时无法读取第一轮结论等 run 数据。
- **自适应计算分配（F34）**：新增 `adaptive.py` 纯确定性调度模块；按问题类型/
  角色/关键词宽度为每个视角生成 `ComputeAllocation`，写入 `compute_plan` 并映射为
  Researcher 的 ResourceBudget；质量门补强阶段改为“弱卡优先 + 按 weakness 动态预算”，
  不再无差别重跑全部卡片。
- **Bing 解析优化**：`bing_search` 现在会先反转义 HTML 实体，再解码 `bing.com/ck`
  跳转链接为真实 URL；标题/摘要统一清理 HTML 标签与实体；解码失败时回退到
  `cite` 显示的可见域名，并补充单元测试。
- 项目地图：`AGENTS.md` + 各模块 ARCHITECTURE/CONSTRAINTS + `Makefile`。

## 最新运行基线（run `20260824-034524`）

- 最近一次已完成 run：score 68，findings 36，verified 5；143 次搜索调用。
- 日志中仍见 Tavily 配额、Firecrawl 限流、少量 httpx 403/521 和一次 asyncio Unclosed client session。
- 旧基线（run `20260820-072235`）：0 ERROR / 4 WARNING；score 74；25 findings；
  verified 13 / suspect 4 / disputed 7 / false 1。

## 进行中 / 风险

- **新机制测试待补**：`_is_unrecoverable` / `_is_rate_limited` / `_DISABLED_TOOLS` /
  `call_log` / `_check_alignment` 还没有专门 pytest（注意模块级注册表需要 fixture 清理）。
- **效果评估依赖新日志**：历史 `search_calls.jsonl` 没有 `result_urls`，Hit@k/nDCG@k
  需要新 run 积累数据后才有值；当前 `make eval` 会先输出可用率/延迟。
- **付费 API 配额**：Tavily plan limit、Firecrawl 免费档限流仍在，但已被禁用/冷却机制控制住。
- **Qwen 端点不可达**：`QWEN_BASE_URL=http://192.168.91.66/v1` 超时；
  对齐门已改用 DeepSeek，Qwen 暂不承担关键路径。
- **Baidu 来源分级偏差**：Baidu 跳转 URL 被 `_classify_url` 判成商业网站 ★★，
  会低估 Baidu 来源的可靠性评分。
- **Firecrawl keyless 额度**：Wikipedia/Wikidata 桥接依赖 Firecrawl keyless 免费额度
  （每月约 1000 credits），高并发/长任务需关注用量；可配 FIRECRAWL_API_KEY 提升额度。
- `.gitignore` 缺 `logs/`（含新的 `search_calls.jsonl`）、`pgdata/`、`run.log`。
- `smoke_test.py` 是 CrewAI 时代旧文件，已无法运行。
- 整目录覆盖上传（VS Code）会使运行容器的 bind mount 指向 deleted inode，
  `GET /` 500；上传后必须 `make restart`（已写入 `web/ARCHITECTURE.md`）。
- 日志查看器默认无鉴权；服务暴露在公网时应在容器环境设置 `LOG_VIEWER_TOKEN`。

## 下一步（按优先级）

1. **补新机制测试**：给 `_is_unrecoverable` / `_is_rate_limited` / `_DISABLED_TOOLS` /
   `call_log` / `_check_alignment` 补 pytest（注意模块级注册表需要 fixture 清理）。
2. **修 `.gitignore`**：加入 `logs/`、`pgdata/`、`run.log`，避免 search_calls 等噪声进入 git。
3. **Baidu 来源分级修正**：`web_fetch` 落地后按最终域名分类，或解析 Baidu 跳转 URL 的目标域。
4. 删除或重写 `smoke_test.py`，然后按逻辑分块 commit（重构 → P0 → 对齐/日志 → 评分）。
