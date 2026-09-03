# Architecture

多智能体深度研究系统：Orchestrator → 并行 Researchers → Reflect/Augment 质量门 → Verifier/Refuter → Scorer/Extractor → Editor。

## 模块
- `src/deep_research/core` — Agent 循环、BuildTool、StateGraph、checkpoint
- `src/deep_research/crews` — 三阶段 crew runner
- `src/deep_research/tools` — 搜索/抓取/知识库工具（含 Wikipedia/Wikidata）
- `src/deep_research/db` — asyncpg/PostgreSQL
- `web/` — FastAPI + SSE + 日志查看器

## 关键接口
- `POST /research`、`GET /research/{run_id}`、`/report`、`/evidence`、`/answer`
- `make test` / `make check` / `make eval` / `make eval-bench`

## 约束
- 详细见 `AGENTS.md`、`src/deep_research/ARCHITECTURE.md`、`src/deep_research/tools/CONSTRAINTS.md`
