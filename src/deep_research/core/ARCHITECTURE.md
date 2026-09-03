# core/ 架构与约束

本包是无外部编排依赖的基础设施，供 crews 和 pipeline 使用。

## 模块清单

| 模块 | 职责 | 关键接口 |
|---|---|---|
| `agent.py` | LLM agent 循环：调模型 → 并行执行工具 → 注入结果 → 再调模型 | `Agent.run(task)`, `LLMConfig` |
| `tool.py` | 工具四阶段管道 + 进程级禁用/冷却注册表 | `BuildTool.run(args)`, `disable_tool_key`, `set_backend_cooldown` |
| `graph.py` | 零依赖 StateGraph：节点返回部分 state，支持条件边/循环/resume | `StateGraph.add_node/add_edge/add_conditional_edges/run` |
| `orchestrator.py` | 并发原语：`parallel`（异常容忍）、`pipeline`、`barrier` | `parallel(*coros)` |
| `blackboard.py` | 跨 agent 共享 KV 槽位 | `Blackboard.read/write` |
| `file_cache.py` | URL → 内容缓存，TTL 300s | `FileCache.get_or_fetch` |
| `compressor.py` | 消息超阈值时滑动窗口 + LLM 摘要压缩 | `Compressor` |
| `events.py` | 进度事件总线，SSE 消费，保留最近 1000 条历史 | `EventBus` |
| `call_log.py` | 每次工具调用追加一行 JSON 到 `logs/search_calls.jsonl` | `log_call(record)` |

## Agent 循环的关键约束

- `MAX_TOOL_ROUNDS = 20` 绝对上限。
- 连续 3 轮完全相同的 `(tool, query)` 签名 → stall 提前停；连续 2 轮所有工具返回 ERROR/空 → 提前停。
- **`tools-failed` 提前停不再返回空字符串**，而是返回 `_tool_error_summary(results)`，
  让上层 parser 看到具体错误而不是 `Empty input`。
- `Agent.run()` 每次任务重置 `messages/token_usage/cost`；一个 Agent 实例不要复用来连续跑多个任务。
- 支持 `response_format`（如 `{"type":"json_object"}`）：每次 `_call_llm()` 都会传该参数。
  **已验证 DeepSeek 在带 tools 时仍会正常产生 tool_calls**；换模型后要重新验证。
- 每次 `_call_llm()` 都会重新过滤 `is_disabled()` 的工具；全部禁用时 `tools=None`，
  不传空 schema 给 litellm。
- 每次工具调用通过 `_log_call()` 写 `logs/search_calls.jsonl`（best-effort，绝不抛异常）。
- **轻量每轮搜索质量门**：`Agent` 可带 `reserved_tools`；某轮 Baidu/Bing
  全错/为空/少于 2 条 URL 时自动解锁保留工具（Firecrawl/Wikipedia/Wikidata），
  并追加一条 user 提示，避免等整轮 Reflector 才补救。
- token/cost 统计写入 Blackboard `usage:<agent_name>`，由 pipeline 汇总。

## BuildTool 管道与进程级状态

- 子类必须提供 `name`、`description`、`parameters`，实现 `execute()`。
- 管道：`validate_input → check_permissions → execute → format_result`。
- `_is_unrecoverable()`：配额/计费/过期/credit/payment/401/403 → **进程级永久禁用**；
- `_is_rate_limited()`：429 / rate limit → **进程级 60s cooldown**（`RATE_LIMIT_COOLDOWN`）；
- 其他瞬时错误：只返回 ERROR，本调用降级。

两个注册表都在 `tool.py` 模块级：

| 注册表 | key | 语义 | 恢复方式 |
|---|---|---|---|
| `_DISABLED_TOOLS` | 工具名或 backend 名 | 不可恢复，全进程所有实例共享 | 重启进程 |
| `_COOLDOWN_UNTIL` | backend 名 | 瞬时限流，并行 agent 一起退避 | 到期自动恢复 |

辅助函数：`disable_tool_key / is_tool_key_disabled / set_backend_cooldown / in_backend_cooldown`。
`web_fetch.py` 和 `search.py` 都用同一套 key（`"tavily"` / `"firecrawl"`），保证搜索和抓取一起退避。

## Graph / Blackboard / Events

- 节点是 `async (state: dict) -> dict`，返回 partial update；循环终止由条件函数负责，
  `DEFAULT_MAX_STEPS = 200` 是兜底。
- `__visited__` 集合支持崩溃恢复：已访问节点不重跑，但从其出边继续路由。
- Blackboard 只是内存 KV，无锁无持久化；跨 agent 的卡片/verified/usage 槽位约定见顶层架构。
- EventBus 按 run 注册在 pipeline 的 `_event_buses`，run 结束后 TTL 300s 释放；
  SSE 晚连接靠保留历史回放。

## 改这里的检查清单

1. 改动是否影响所有 agent 的公共行为？先跑 `make check`。
2. 新工具是否实现了四个管道阶段的最小必要逻辑？
3. 新增的禁用/冷却是否与 `_DISABLED_TOOLS` / `_COOLDOWN_UNTIL` 的语义一致：
   不可恢复=永久、429=短冷却、其他瞬时=单次降级。
4. 修改 `response_format` 逻辑后，必须用带工具的 agent 实测 tool_calls 仍能触发。
5. 新增事件类型要同步 `events.py` 顶部注释和 `web/ARCHITECTURE.md`。
6. 修改 `call_log.py` 字段时，保持 JSONL 单行、best-effort，并更新 AGENTS.md 的验证命令。
