# agents/ 架构 — 声明式 Agent 配置

本目录包含 `registry.py`、`policy.py` 和 `__init__.py`。旧 agent 模块已删除，职责迁移到
`crews/` 的 task 模板和 `core/agent.py` 的通用循环。

## 职责

- 声明每个 agent 的 role / goal / backstory / tools / llm / response_format。
- `policy.py` 定义 AgentPolicy 数据模型（独立性治理 Phase 1，仅元数据）。
- `create_agent()` 组装 system prompt 并实例化 `core.agent.Agent`，自动附加默认 Policy。

## 配置清单（`registry.py`）

| 配置 | 工具 | LLM | response_format |
|---|---|---|---|
| `ORCHESTRATOR_CONFIG` | 无 | deepseek | json_object |
| `RESEARCHER_CONFIGS`（4 个静态角色模板） | `get_search_tools()`（含 wikipedia_search/wikidata_lookup）+ `WebFetchTool()` | deepseek | json_object |
| `VERIFIER_CONFIG` | `WebFetchTool()` + `SQLiteReadTool()` | deepseek | json_object |
| `REFUTER_CONFIG` | `get_refuter_tools()` | deepseek | json_object |
| `SCORER_CONFIG` / `EXTRACTOR_CONFIG` | `SQLiteReadTool()` | deepseek | json_object |
| `EDITOR_CONFIG` | `SQLiteReadTool()`（`synthesis_crew.py` 运行时覆盖为 `tools=[]`，直接读注入的数据摘要） | deepseek | **无**（输出 Markdown） |
| `REFLECTOR_CONFIG` | 无 | deepseek | json_object |

实际研究视角由 `crews/research_crew.py::ORCHESTRATOR_TASK` 动态生成；
`RESEARCHER_CONFIGS` 只是 fallback/角色模板。`alignment-checker` 在
`research_crew.py` 里 ad-hoc 创建（DeepSeek，无工具，json_object），不在此注册表。

## create_agent 的关键行为

1. `_deepseek()` / `_qwen()` 把 config 转成 litellm 的 `openai/<model>` 形式。
2. **深拷贝工具列表**：同类工具实例绝不跨 agent 共享（WebFetchTool 实例状态依赖此约定）。
3. system prompt = role + goal + backstory + 当前时间 + “输出语言：中文”。
4. 注入 `experience.py` 的跨 run 经验（按 agent 名和工具名匹配）。
5. 传递 `response_format`；`core/agent.py` 每次 LLM 调用都会带上它。
6. 支持 `max_tool_rounds / stall_limit / tool_error_limit` 可编程终止参数。
7. 自动附加 `AgentPolicy`（默认全放行；后续阶段再强制）。

## AgentPolicy 强制（Phase 2）

- `create_agent()` 会用 `ScopedBlackboard` 包装共享 Blackboard：
  - 读只允许 `ContextPolicy.read_blackboard_keys`
  - 写只允许 `ContextPolicy.write_blackboard_keys`
- `core/agent.py` 在执行工具前调用 `_tool_allowed()`：
  - 检查 denied_tools
  - 检查 allowed_tools（为 None 表示全部允许）
  - 检查 per_tool_max_calls
- 默认 Policy 全放行；后续收紧时只需修改 `agents/policy.py` 的默认策略。

## AgentPolicy 强制（Phase 3：资源预算与审计）

- `ResourceBudget` 在 Agent 运行时生效：
  - `max_tool_calls`：工具总调用次数达到后拒绝新工具调用
  - `max_llm_calls` / `max_tokens` / `max_cost_usd`：LLM 调用前检查，超限直接终止该 Agent 的 LLM 调用
- 所有策略拒绝会写入 `logs/policy_audit.jsonl`：
  - ScopedBlackboard 拒绝读写
  - 工具被 denied / 不在 allowed / per-tool 超限 / 总工具次数超限
  - LLM 预算超限
- 默认 Policy 无预算限制，行为不变。

## AgentPolicy 强制（Phase 4：验证标准独立化）

- `VerificationStandard.render_prompt()` 会把 Policy 中的 rubric 渲染成一段中文标准文本。
- `create_agent()` 在组装 system prompt 时自动追加这段“验证标准块”。
- 不同角色默认使用不同标准：
  - verifier/refuter：`verifier_rubric_v1`
  - second-opinion：`independent_review_v1`（不可见第一轮）
  - researcher：`researcher_confidence_v1`
  - scorer：`scorer_rubric_v1`
- 以后调整评分规则只需改 `agents/policy.py`，不用改各 task prompt。

## AgentPolicy 强制（Phase 5：运行时信息隔离）

- second-opinion / contradiction-adjudicator 的 ContextPolicy：
  - 可读：`run_id`、`trace_id`、`event_bus`、`search_plan`、`usage:*`
  - 可写：`usage:*`
  - 不可读：`run:*`（第一轮卡片、验证结果等）
- 该限制由 ScopedBlackboard 在运行时强制，不只是提示词约束。

## response_format 注意事项

- 给带工具的 agent 设 `json_object` 是**实测可行**的（DeepSeek 仍会先 tool_calls 再输出 JSON）；
- 但换模型（尤其本地 Qwen）后必须重新跑一次工具调用探针；
- Editor 必须保持无 `response_format`，否则 Markdown 报告会被破坏。

## 约束

- 不要在 `registry.py` 里手写新的 Agent 子类；新增角色 = 加配置字典 + 在 crews 里写 task 模板。
- 工具集合变化会影响 `experience.py::_SEARCH_TOOLS` 和经验注入，必须同步检查。
- LLM 配置只从 `Config` 读；不要在 registry 里硬编码 base_url/model。
- 对齐检查器必须保留“失败回退原始 briefs”的语义，不要给它加会阻塞流程的依赖。
