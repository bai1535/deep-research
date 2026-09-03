# MCTS-RAG 2.0 开发路线

> 目标：在 1.0 多智能体深度研究系统之上，引入 MCTS-RAG 风格的自适应“推理 × 检索”搜索，提升高难多跳问题的精确回答能力。

## 背景

1.0 当前使用固定多 Agent 流水线：拆解视角 → 并行研究 → 反思 → 验证 → 合成。

2.0 参考论文《MCTS-RAG: Enhance Retrieval-Augmented Generation with Monte Carlo Tree Search》，将“检索”与“推理”交织成树搜索：

- 节点 = 推理状态
- 动作 = 直接回答 / 快速推理 / 拆解问题 / 检索后推理 / 检索并拆解 / 汇总答案
- 选择 = UCT
- 检索 = 现有 Bing/Baidu/WebFetch 等工具
- 奖励 = 检索有用性 + 答案一致性 + 验证结果
- 最终答案 = 多条轨迹按 reward 加权投票

## 当前状态（2026-09-03）

已完成 **纯算法脚手架**，尚未接 LLM/工具：

- `deep_research.mcts_rag.actions`：A1–A6 动作空间定义
- `deep_research.mcts_rag.tree`：MCTSNode、UCT、backpropagate
- `deep_research.mcts_rag.voting`：候选答案归一化、分组、加权投票
- 单元测试：`tests/test_mcts_rag.py`

## 里程碑

### M1 纯算法脚手架 ✅
- 动作空间
- MCTS 树结构与 UCT
- 答案投票
- 单元测试

### M2 LLM 动作执行器
- 为 A1–A6 编写 Prompt 模板
- 用现有 `Agent` / litellm 执行动作
- 用现有搜索/抓取工具实现 R2 检索
- 输出结构化中间状态

### M3 简单 MCTS 循环
- selection / expansion / rollout / backpropagation
- 深度与 rollout 预算
- 简单奖励：检索是否有用 + 答案是否一致

### M4 BrowseComp 实验入口
- 写一个可独立运行的 CLI/脚本
- 输入 BrowseComp-Plus 问题
- 输出候选答案和最终答案
- 用现有 `eval_judge.py` 评测

### M5 接入正式流水线
- 对 `multi_hop_clue` / `historical_archive` / 精确答案类问题路由到 MCTS-RAG
- 保留普通开放题走 1.0 流水线

## 验证指标

- BrowseComp-Plus 3 题基线：0/3
- 2.0 目标：先在 3 题上产生正确/部分正确，再扩大样本
- DeepResearch Bench 中文开放题保持不退化（当前平均 71.3）

## 设计原则

1. 不破坏 1.0 稳定流水线
2. 先做可独立运行的原型，验证有效后再接入
3. 所有搜索/推理动作保持可追溯（事件日志）
4. 控制成本：深度/rollout 预算可配置
