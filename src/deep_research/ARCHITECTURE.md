# deep_research 顶层架构

> 只讲数据流、组件边界和关键契约。细节进各模块自己的文档：
> `core/` `tools/` `crews/` `agents/` `db/` `models/`。

## 运行链路

```
用户问题
  │  Web: POST /research          CLI: python -m deep_research.main
  ▼
pipeline.run_research(question)
  │  创建 Blackboard + FileCache + EventBus + Repository，StateGraph 驱动
  ▼
research ──► reflect ──(不合格, 预算内)──► augment ──► reflect ...
  │               │
  │               └──(合格)──► verify ──► synthesize ──► complete
  └──(0 findings, 预算耗尽)──────────────────────────► empty_result ──► complete
```

Research 节点内部：

```
Orchestrator（动态 3-6 视角，带研究对象铁律）
  → 字符重叠粗筛（_check_alignment）
  → Alignment Checker（DeepSeek，无工具，json_object，跑题则改写）
  → N 个 Researcher 并行（搜索 + web_fetch）
```

## 组件职责

| 包 | 职责 | 关键类/模块 |
|---|---|---|
| `pipeline.py` | 组装 StateGraph、checkpoint、resume、成本汇总 | `run_research`, `build_graph` |
| `core/` | 无外部编排依赖的基础设施：Agent 循环、Tool 管道、Graph、并发原语、事件、调用日志 | `Agent`, `BuildTool`, `StateGraph`, `Blackboard`, `call_log` |
| `tools/` | Web 搜索/抓取/知识库/数据库读取工具 | `BingSearchTool`, `BaiduSearchTool`, `TavilySearchTool`, `FirecrawlSearchTool`, `WikipediaSearchTool`, `WikidataLookupTool`, `WebFetchTool`, `SQLiteReadTool` |
| `crews/` | 三个阶段的可执行编排 + 研究对象对齐门 | `ResearchCrewRunner`, `ReflectionCrewRunner`, `VerificationCrewRunner`, `SynthesisCrewRunner` |
| `agents/` | 声明式 Agent 配置与工厂 | `create_agent`, `RESEARCHER_CONFIGS`, `ORCHESTRATOR_CONFIG` |
| `db/` | PostgreSQL asyncpg 连接池 + Repository | `init_db`, `get_pool`, `Repository` |
| `models/` | Pydantic 数据契约与枚举 | `ResearchCard`, `VerifiedCard`, `ScoreResult`, `ResearchRun` |
| `experience.py` | 跨 run 可教性：静态经验 + 从 evidence.json 学习 | `ExperienceStore` |
| `response_parser.py` / `safe_construct.py` | LLM JSON 输出的多策略解析 | `parse_json_response`, `safe_construct_*` |
| `claim_annotator.py` | 最终答案的非破坏式 Claim 标注层 | `ClaimAnnotator` |
| `claim_verifier.py` | 未覆盖 claim 的原子验证 | `AtomicClaimVerifier` |
| `trace.py` | 日志 trace_id 注入 | `trace_logger` |

## 关键契约与阈值

- 质量门：`MIN_FINDINGS = 3`、`MAX_AUGMENTS = 2`、`QUALITY_THRESHOLD = 60`（`pipeline.py`）。
  反射器只负责打分，是否合格由 pipeline 确定性判定。
- 对齐门（`crews/research_crew.py`）：字符重叠阈值 `ALIGNMENT_MIN_OVERLAP = 0.2` 只做粗筛；
  语义对齐由 `alignment-checker` 完成。**对齐失败不得阻塞研究**，一律回退原始 briefs。
- JSON 输出 agent 通过 `create_agent(response_format={"type":"json_object"})` 启用；
  实测 DeepSeek 在带工具时仍会正常 tool_calls。
- 每个 run 产物：`runs/<run_id>/report.md`、`evidence.json`（含 `final_answer`）、`answer.txt`、`claims.json`、`audit.jsonl`。
- 每次工具调用产物：`logs/search_calls.jsonl`（run_id/trace_id/agent/tool/query/status/duration_ms/error）。
- `audit.jsonl` 只记录最终产物事件（run_start/research_card/verified_card/score/insights）。
- Checkpoint：每个 graph 节点完成后把可序列化 state 存进 `run_checkpoints`；
  完成时清除。resume 只恢复 JSON 子集，Blackboard/Repo/EventBus 重建。

## 硬约束（跨模块）

1. 所有 LLM 入口必须 `import deep_research.qwen_patch`，否则 Qwen 工具调用可能失败。
2. 工具实例必须**按 agent 深拷贝**（`agents/registry.py::create_agent`），
   避免 WebFetchTool 的实例状态跨并行 run 互相污染；
   但**不可恢复禁用和 429 cooldown 是进程级共享的**（`core/tool.py`），两者语义不同，勿混。
3. 严格 JSON 输出统一走 `response_parser.py`；Agent 层可用 `response_format` 辅助，
   但解析仍要保留多策略兜底。
4. 成本统计通过 Blackboard 的 `usage:<agent_name>` 键；新增 agent 后沿用该约定。
5. Scorer 的来源可靠性评分依赖 `web_fetch` 输出的 `[来源: 标签 ★]`；
   修改来源分类 pattern 会直接影响最终 score，见 `tools/CONSTRAINTS.md`。
