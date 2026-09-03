# AGENTS.md — Deep Research 着陆页

> 这是本项目的知识入口。详细知识放在各模块目录下的 ARCHITECTURE.md / CONSTRAINTS.md / README.md，
> 本文件只回答三个问题：这是什么项目、怎么跑、怎么验证。
> **代码变更后必须同步更新对应模块文档和 PROGRESS.md。**

## 1. 这是什么项目

多智能体深度研究系统：输入一个研究问题，自动拆分视角 → 研究对象对齐检查 → 并行联网检索 →
反思质量门（不足则反馈重搜）→ 三轮对抗式事实核查 → 评分/提炼 → 输出带引用的中文研究报告。

- 技术栈：Python 3.11、litellm（DeepSeek / Qwen）、FastAPI + SSE、PostgreSQL 16、Docker Compose
- 对外形式：Web API（`http://<host>:8000`）+ CLI（`python -m deep_research.main "问题"`）
- 三阶段流水线：Research(+Alignment/Reflect/Augment) → Verification → Synthesis

## 2. 项目地图

| 你想了解 | 去这里 |
|---|---|
| 顶层架构、数据流、checkpoint/resume | `src/deep_research/ARCHITECTURE.md` |
| Agent 循环 / response_format / 终止策略 | `src/deep_research/core/ARCHITECTURE.md` |
| BuildTool 禁用与 cooldown / 调用日志 | `src/deep_research/core/ARCHITECTURE.md`、`core/call_log.py` |
| 搜索与抓取后端、故障约束 | `src/deep_research/tools/CONSTRAINTS.md` |
| 四个 Crew、对齐门、来源评分 | `src/deep_research/crews/ARCHITECTURE.md` |
| Agent 注册表与 prompt 构造 | `src/deep_research/agents/ARCHITECTURE.md` |
| 数据库硬约束 | `src/deep_research/db/CONSTRAINTS.md` |
| 数据模型（Pydantic 契约） | `src/deep_research/models/README.md` |
| Web API 与 SSE | `web/ARCHITECTURE.md` |
| 日志查看器 | 浏览器打开 `http://<host>:8000/logs`（实现见 `web/api.py` + `web/logs.html`） |
| 当前进度 / 已知阻塞 / 下一步 | `PROGRESS.md` |
| 操作命令入口 | `Makefile`（`make help`） |
| 每次搜索/抓取调用的结构化记录 | `logs/search_calls.jsonl`（由 `core/call_log.py` 写入） |

## 3. 怎么跑

```bash
# 推荐：Docker
make setup            # docker compose up -d --build
make check            # 健康检查

# Web API
curl -X POST http://127.0.0.1:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"question":"你的研究问题"}'
curl http://127.0.0.1:8000/research/<run_id>
curl http://127.0.0.1:8000/research/<run_id>/report

# Web 日志查看器（滚动/搜索/筛选/实时尾随，替代 tmux）
# 浏览器打开 http://<host>:8000/logs
# 可选保护：在 .env 或容器环境设 LOG_VIEWER_TOKEN=xxx，访问时页面会要求输入

# CLI（单次任务）
docker compose run --rm deep-research python -m deep_research.main "你的研究问题"

# 改完代码后
make restart
```

**重要**：如果上传时是“删除旧文件夹再放新文件夹”（VS Code 覆盖上传常见），Docker 的
`./web:/app/web`、`./src:/app/src` bind mount 会指向已删除的旧 inode，容器里会看到空目录，
`GET /` 报 `FileNotFoundError: /app/web/index.html`。上传后必须 `make restart`（或 `make setup`）。

## 4. 怎么验证

```bash
make check     # compose 配置 + /health + 关键模块导入，应全绿
make test      # pytest；当前有 13 个陈旧用例失败（见 PROGRESS.md），修复前不视为绿灯
make compare   # 对比最近 10 次研究的 cards/claims/sources/verified 和 score

# 搜索调用可观测性（新）
grep '"run_id": "<run_id>"' logs/search_calls.jsonl   # 每个引擎调用次数/成功/延迟/错误
grep "alignment-checker\|Alignment" logs/current.log   # 对齐门是否执行、是否修正
```

验证硬规则：

- 任何代码变更先跑 `make check`；测试修复后 `make test` 必须全绿才能合并。
- 搜索/抓取工具改动前先读 `tools/CONSTRAINTS.md`，并用真实查询探测免费引擎。
- 改了 Agent prompt 或 `response_format`，必须验证带工具 agent 仍能正常发起 tool_calls。

## 5. 硬约束（违反即返工）

1. `.env` 含真实密钥，禁止提交、禁止把 key 写入日志或报告。
2. 搜索后端不可恢复错误（配额/计费/auth）必须走 `core/tool.py` 的进程级禁用；
   429 限流走 60s 进程级 cooldown。不得恢复“每个 agent 实例独立重试”的旧行为。
3. 数据库只允许走 `src/deep_research/db` 的 asyncpg 连接池（`get_pool()`），禁止旁路连接。
4. `src/`、`web/` 在容器内是只读挂载；改代码在宿主机改，再 `make restart`。
5. `deep_research.qwen_patch` 必须在任何 litellm 调用前导入（`main.py`、`web/api.py` 已处理）。
6. 对齐门当前使用 `llm="deepseek"`；`QWEN_BASE_URL`（192.168.91.66）已被验证不可达，
   不要切回 qwen，除非先验证连通性。
7. `logs/`（含 `search_calls.jsonl`）、`runs/`、`pgdata/`、`run.log` 不应提交；
   `.gitignore` 尚未覆盖的项见 PROGRESS.md。
8. 改代码时同步改对应模块文档；完成证据只能是命令输出、测试结果或对比数据。

## 6. 关键运行事实（2026-08-20）

- 最新 run `20260820-072235`：0 ERROR / 4 WARNING，score 74，25 findings；
- `search_calls.jsonl` 已记录该 run 的 128 次工具调用；
- alignment-checker 成功把跑题子问题拉回“个人 PC”研究对象。
