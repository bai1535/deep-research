# Deep Research 多智能体深度研究系统

一个面向复杂问题的多智能体深度研究系统：输入一个研究问题，系统会自动拆解视角、并行联网检索、质量门反思、对抗式事实核查，并生成带引用来源的中文研究报告。

## 项目简介

本项目通过多个具有独立角色、独立权限和独立资源预算的 AI Agent 协作完成深度研究：

- **Orchestrator**：把研究问题拆成多个互补视角
- **Researcher**：按视角联网检索并产出带来源的发现
- **Reflector**：对研究质量打分，不达标则触发补强
- **Verifier / Refuter**：对抗式事实核查与反证搜索
- **Scorer / Extractor / Editor**：评分、提炼并生成最终报告

技术栈：

- Python 3.11
- FastAPI + SSE
- PostgreSQL 16 / asyncpg
- Docker Compose
- LiteLLM / DeepSeek

## 核心特性

### 1. 三阶段研究流水线

```text
Research(+Alignment/Reflect/Augment)
  → Verification(三轮对抗核查 + 独立二次核查)
  → Synthesis(评分 + 提炼 + 报告生成)
```

支持 checkpoint / resume，研究过程中断后可恢复。

### 2. Claim 级溯源

- 从最终报告中抽取原子 Claim
- 将 Claim 映射到研究阶段证据
- 对未验证 Claim 做原子验证
- 提供报告证据双视图、Claim 点击溯源、事件回滚入口
- 产物：`report.md`、`evidence.json`、`claims.json`、`audit.jsonl`

### 3. Agent 独立性治理

每个 Agent 都具备：

- 独立上下文读写边界（ScopedBlackboard）
- 独立工具权限（ToolPolicy）
- 独立资源预算（ResourceBudget）
- 独立验证标准（VerificationStandard）
- 运行时信息隔离（如二次核查员无法读取第一轮结论）

所有策略拒绝都会写入 `logs/policy_audit.jsonl`，可审计。

### 4. 自适应计算分配

- 根据问题类型、角色、关键词宽度为每个视角分配研究深度与工具预算
- 质量门补强时按“卡片弱点”动态选择需要补强的视角
- 避免强卡浪费预算、弱卡不够深

### 5. 多搜索后端

- 百度搜索（免费，中文新内容强）
- Bing 搜索（免费，英文/技术文档/论文强）
- Wikipedia / Wikidata（Firecrawl keyless 桥接）
- Firecrawl / Tavily（按 Key 门控，用于质量门补强）
- Wayback Machine（历史档案）

### 6. 事件溯源与回滚

- Agent 的工具调用和 LLM 调用记录为不可变事件
- 支持因果回溯、分支级回滚、确定性重放、重新生成报告

### 7. Web 日志与报告

- 实时研究进度 SSE
- 日志查看器（tail / 搜索 / 级别过滤 / 事件回滚）
- 报告证据双视图
- 支持多套展示主题

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
```

在 `.env` 中填入真实 Key：

```dotenv
DEEPSEEK_API_KEY=sk-your-deepseek-key
TAVILY_API_KEY=tvly-your-tavily-key
FIRECRAWL_API_KEY=fc-your-firecrawl-key
```

`.env` 已被 `.gitignore` 忽略，不会提交到仓库。

### 2. Docker 启动

```bash
make setup        # docker compose up -d --build
make check        # 健康检查
```

### 3. 发起一次研究

Web API：

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"question":"你的研究问题"}'

curl http://127.0.0.1:8000/research/<run_id>
curl http://127.0.0.1:8000/research/<run_id>/report
```

CLI：

```bash
docker compose run --rm deep-research \
  python -m deep_research.main "你的研究问题"
```

## 常用命令

| 命令 | 说明 |
|---|---|
| `make setup` | 构建并启动服务 |
| `make restart` | 代码变更后重启 |
| `make check` | 健康检查 |
| `make test` | 运行 pytest |
| `make eval` | 搜索效果评估 |
| `make eval-bench` | 公开基准评测 |
| `make eval-claims` | Claim 溯源指标 |
| `make judge` | DeepSeek 裁判评测 |

## API 主要端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/research` | 提交研究问题 |
| GET | `/research/{run_id}` | 查询研究状态 |
| GET | `/research/{run_id}/report` | 获取报告 Markdown |
| GET | `/research/{run_id}/evidence` | 获取证据 JSON |
| GET | `/research/{run_id}/claims` | 获取 Claim 列表 |
| GET | `/research/{run_id}/claims/{claim_id}/trace` | 查询 Claim 证据链 |
| GET | `/research` | 最近研究列表 |
| GET | `/logs` | 日志查看器 |

## 目录结构

```text
src/deep_research/
  agents/       # Agent 配置与策略
  core/         # Agent 循环、Blackboard、工具、图执行
  crews/        # Research / Reflect / Verify / Synthesis
  tools/        # 搜索、抓取、知识库、历史档案
  db/           # PostgreSQL 数据访问
web/            # FastAPI + 前端页面
tests/          # pytest 测试
scripts/        # 评测、harness、辅助脚本
docs/           # 架构与设计文档
features.json   # 功能清单与验证状态
```

## 评测与基准

- `make test`：单元测试
- `make eval-claims`：Claim 溯源覆盖率/证据覆盖率/可追溯性
- `make eval-bench`：DeepResearch Bench / BrowseComp-Plus
- `docs/baseline-20260903.md`：当前基线记录

## 版本说明

| 版本 | 说明 |
|---|---|
| `v1.0` | 当前稳定版：多智能体深度研究 + Claim 溯源 + Agent 治理 + 自适应计算分配 |
| `v2.0-mcts` | 2.0 开发分支：基于 MCTS-RAG 的高难问题推理与自适应研究规划 |

## 安全说明

- 所有真实密钥只放在本地 `.env`，不进入 Git
- `.env`、`logs/`、`runs/`、`pgdata/`、`eval_results/`、`.backup-*` 均已加入 `.gitignore`
- 仓库中的 `.env.example` 只包含占位符

## 文档索引

- `AGENTS.md`：项目知识入口
- `docs/agent-independence-policy.md`：Agent 独立性治理设计
- `docs/claim-level-provenance.md`：Claim 级溯源设计
- `docs/baseline-20260903.md`：评测基线
- `src/deep_research/ARCHITECTURE.md`：顶层架构
