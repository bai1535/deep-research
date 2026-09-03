# Makefile — Deep Research 标准操作入口
# 用法: make help

SHELL := /bin/bash
.DEFAULT_GOAL := help
COMPOSE := docker compose
SERVICE := deep-research

.PHONY: help setup up down ps logs restart shell check test compare eval eval-bench eval-claims judge

help: ## 列出所有命令
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sed -E 's/:[^#]*## /: /'

setup: ## 构建并启动整套服务
	$(COMPOSE) up -d --build

up: ## 启动服务（不重建）
	$(COMPOSE) up -d

down: ## 停止服务
	$(COMPOSE) down

ps: ## 查看容器状态
	$(COMPOSE) ps

logs: ## 跟踪应用日志
	$(COMPOSE) logs -f $(SERVICE)

restart: ## 代码变更后重启（uvicorn 无 --reload）
	$(COMPOSE) restart $(SERVICE)

shell: ## 进入应用容器
	$(COMPOSE) exec $(SERVICE) bash

check: ## 验证 compose 配置、服务健康、关键模块导入
	$(COMPOSE) config --quiet
	@curl -fsS http://127.0.0.1:8000/health >/dev/null && echo "health: OK"
	@$(COMPOSE) exec $(SERVICE) python -c "import deep_research.pipeline, deep_research.tools, web.api; print('imports: OK')"

test: ## 跑 pytest（当前应全绿）
	$(COMPOSE) run --rm --no-deps --user root -v "$(PWD)/tests:/app/tests:ro" $(SERVICE) sh -c "pip install -q pytest pytest-asyncio pytest-mock && pytest -q -o asyncio_mode=auto -o asyncio_default_test_loop_scope=session -o asyncio_default_fixture_loop_scope=session tests"

compare: ## 对比最近 10 次研究的质量指标
	$(COMPOSE) run --rm --no-deps -v "$(PWD)/scripts:/app/scripts:ro" $(SERVICE) python scripts/compare_runs.py

eval: ## 运行搜索/效果评估（可用率、延迟、Hit@k、nDCG@k）
	$(COMPOSE) run --rm --no-deps -v "$(PWD)/scripts:/app/scripts:ro" $(SERVICE) python scripts/search_eval.py

eval-bench: ## 运行公开基准评测（DeepResearch Bench / BrowseComp-Plus）
	python3 scripts/eval_benchmarks.py --benchmark all --limit 2

eval-claims: ## 评估已运行 run 的 Claim 溯源指标（claims.json）
	PYTHONPATH="$(PWD)/src" python3 scripts/eval_claims.py --runs-dir runs --limit 20

judge: ## 用 DeepSeek 裁判评测结果（对比 final_answer 与 gold）
	docker compose run --rm --no-deps --user root -v "$(PWD)/scripts:/app/scripts:ro" -v "$(PWD)/eval_results:/app/eval_results" $(SERVICE) python scripts/eval_judge.py --input eval_results/run-browsecomp_plus.jsonl
