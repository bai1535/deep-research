# Spec: 事件溯源（Event Sourcing）——确定性回滚与因果推理

## 一、背景与问题

当前 DeepResearch 是“流水线 + checkpoint”模型：
- 发生幻觉/注入污染时只能人工看日志，无法自动定位污染源
- 无法只回滚受污染的分支，只能整轮重跑
- Agent 的原子动作（搜索、抓取、摘录）没有统一、可追溯的事件记录

## 二、目标

1. 将 DeepResearch 的每个原子动作封装为**不可变事件**并持久化
2. 实现**因果链追踪**：从最终报告中的一条声明，反向定位到导致污染的来源事件
3. 实现**确定性回滚**：`rollback_to(event_id)` 只重放受影响分支，不整轮重跑

## 三、核心概念

### 1. 事件（Event）

每个原子动作都是一个不可变事件：

```
event_id: uuid
run_id: string
parent_event_id: uuid | null
seq: int
agent: string
action: search | fetch | read_paragraph | extract_sentence | llm_call | decision | ...
input_hash: string
output_hash: string
payload: json
created_at: timestamp
```

- `parent_event_id` 构成因果 DAG
- `input_hash` / `output_hash` 用于确定性重放和污染定位

### 2. 事件存储（Event Store）

- 按 run 追加写，不可修改
- 可落 PostgreSQL 表或 JSONL 文件
- 提供按 `run_id + seq` 查询、按 `parent_event_id` 遍历

### 3. 因果链（Provenance Graph）

每个下游事件记录“我来自哪些上游事件”：

- 搜索事件 → 产生 URL 列表，每个 URL 带 source_event_id
- 抓取事件 → 引用搜索事件的 URL + source_event_id
- 摘录事件 → 引用抓取事件的段落
- LLM 生成声明 → 引用它依据的摘录/证据事件

最终形成一张有向无环图（DAG）。

## 四、技术方案

### Phase 1：事件埋点与持久化

- 在 Agent 工具调用层统一发出事件：
  - search / fetch / read / extract / llm_call
- 在 `core/agent.py` 的 tool 执行处和 LLM 调用处埋点
- 事件写入 Event Store，兼容现有 `search_calls.jsonl`
- 不改变现有业务流程，只增加旁路记录

### Phase 2：因果回溯引擎

输入：一条最终声明（claim_text）或一个可疑来源 URL

输出：导致该声明产生的完整事件链

算法：
1. 从最终声明的 `provenance_event_id` 出发
2. 沿 `parent_event_id` 反向 BFS/DFS
3. 标记每条链上的“污染候选事件”
4. 对候选事件做污染评分：
   - 来源域名可信度
   - 是否来自被注入/异常的搜索结果
   - 是否与最终声明文本高度重合

### Phase 3：确定性回滚与重放

`rollback_to(event_id)`：

1. 找到 `event_id` 之后、且属于受影响分支的事件集合
2. 生成“回滚后的目标状态”
3. 基于缓存重放：
   - 工具结果缓存：相同 `input_hash` 直接复用
   - LLM 响应缓存：相同 prompt/上下文 hash 直接复用
4. 只重放受影响分支，未受影响分支保留原状态
5. 更新 checkpoint / 数据库 / 报告

对应分布式系统的 **State Machine Replication**：
- 每个 run 是一个确定性状态机
- 事件是命令
- 快照 + 事件日志支持任意点回放

### Phase 4：与现有系统集成

- 与 checkpoint/resume 共存
- 提供 `POST /research/{run_id}/rollback?event_id=...` API
- 在报告中标注污染来源和回滚记录

## 五、成功标准

1. 给定一个“被污染的最终答案”，能自动回溯到污染源事件
2. `rollback_to(event_id)` 能只重放受影响分支，结果与整轮重跑一致
3. 现有 `make test` 全绿
4. 不影响正常研究流程的性能（事件写入为异步/旁路）


## 六、存储策略（已确定：分层存储方案 E）

### 热数据（最近 N 次 run）
- 保存完整事件日志
- 保存输入哈希 / 输出哈希
- 保存原始输出缓存（搜索结果、页面正文、LLM 响应）
- 支持完整确定性回滚

### 冷数据（超过保留期的旧 run）
- 只保存事件元数据 + 输入/输出哈希 + 摘要
- 不保存原始全文和 LLM 响应
- 回滚旧 run 时：
  - 哈希仍在，可定位事件
  - 原始输出缺失时重新抓取 / 重新生成
  - 确定性降级为“近似重放”，但节省存储

### 保留策略
- 默认保留最近 50 个可完整回放的 run（可配置）
- 更早的 run 自动降级为冷数据
- 冷数据可进一步归档或清理

### 容量估算
- 热数据：单 run 最坏约 50–200 MB
- 50 个热 run：约 2.5–10 GB，当前 31G 可用可承受
- 冷数据：只保留哈希和摘要，单 run 约 1–2 MB

## 七、风险与难点

| 难点 | 说明 | 对策 |
|---|---|---|
| LLM 非确定性 | 同一输入可能不同输出 | 对 LLM 请求做 hash 缓存，回放时复用 |
| 外部工具副作用 | 搜索/抓取结果可能变化 | 工具结果按 query/url 缓存，回放时用缓存 |
| 事件量过大 | 一次研究可能上千事件 | 只保留结构化摘要 + 大 payload 外置 |
| DAG 复杂度 | 分支多 | 先做单分支回滚，再扩展多分支 |

## 八、建议 Sprint 切分

1. F19-1：事件模型 + 埋点 + 存储
2. F19-2：因果回溯引擎
3. F19-3：确定性缓存与重放
4. F19-4：rollback API + 集成验证
