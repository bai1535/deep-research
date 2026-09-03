# web/ — FastAPI 服务

## 运行

容器命令：`python -m uvicorn web.api:app --host 0.0.0.0 --port 8000`。
`web/index.html` 是单页前端，由 `/` 返回；主题文件在 `web/themes/`，不参与后端逻辑。

## API

| 方法/路径 | 用途 |
|---|---|
| `GET /` | 前端页面（读 `/app/web/index.html`） |
| `GET /health` | 健康检查，docker healthcheck 依赖它 |
| `POST /research` | 提交问题，202 立即返回 run_id，后台执行 |
| `POST /research/{run_id}/resume` | 从 checkpoint 恢复失败/中断的 run |
| `GET /research/{run_id}` | 状态与结果摘要 |
| `GET /research/{run_id}/stream` | SSE 实时进度 |
| `GET /research/{run_id}/report` | 最终 Markdown 报告 |
| `GET /research/{run_id}/evidence` | evidence JSON |
| `GET /research/{run_id}/answer` | 抽取出的简洁最终答案（纯文本） |
| `GET /research/{run_id}/claims` | Claim 级溯源文档 claims.json |
| `GET /research/{run_id}/claims/{claim_id}/trace` | 单条 claim 的事件链与祖先事件 |
| `GET /report/{run_id}` | 报告证据双视图页面（`web/report.html`） |
| `GET /research` | 最近 run 列表（limit ≤ 100） |
| `GET /logs` | 只读日志查看器页面（`web/logs.html`） |
| `GET /api/logs/files` | 列出 `logs/` 下的 .log / .jsonl 文件 |
| `GET /api/logs/text` | 文本日志 tail（默认 current.log）或全文搜索（q / level 过滤） |
| `GET /api/logs/calls` | 读取 `logs/search_calls.jsonl` 最近记录，支持 run_id / tool / status / q 过滤 |

日志查看器安全：容器环境可设 `LOG_VIEWER_TOKEN`；设置后 `/logs` 及三个 API 都要求 `?token=`
匹配，否则 403。默认未设置（开放），公网部署时应设置。

## 关键机制

- 并发门：`MAX_CONCURRENT_RESEARCH`（默认 20）信号量，超出排队不并发爆炸。
- startup 时 `init_db()` 建表；`deep_research.qwen_patch` 必须先 import。
- SSE 从 pipeline 的 `_event_buses` 取 EventBus；EventBus 在 run 结束后 TTL 300s 释放，
  晚连接客户端靠事件历史回放。
- run 的后台任务在 FastAPI 进程内执行；容器重启会丢未持久化的运行状态，checkpoint 负责恢复。

## ⚠️ bind mount 覆盖上传陷阱（已实际发生过）

`docker-compose.yml` 把宿主机 `./web:/app/web:ro`、`./src:/app/src:ro` 挂进容器。
如果上传方式是**删除整个目录再重建**（VS Code 覆盖上传常见），运行中的容器会继续指向
被删除目录的旧 inode（`/proc/self/mountinfo` 里显示 `//deleted`），表现为容器内目录变空，
`GET /` 报 `FileNotFoundError: /app/web/index.html` 500。

规则：**整目录覆盖上传后必须 `make restart`（或 `make setup`）**，让容器重新绑定当前路径。
重启后验证：`curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/` 应为 200。

## 约束

1. 新接口不要直接调 crew/pipeline 的私有细节；通过 `pipeline.run_research` 和 `Repository`。
2. SSE 事件形状与 `core/events.py` 保持同步；前端 JS 按 `event.type` 分支。
3. 路由参数必须校验（run_id 格式、question 长度），保持 202/404 的语义。
4. 改 `api.py` 后需要 `make restart`；只改 `index.html`/主题同样建议重启，避免 deleted-inode 空目录问题。
