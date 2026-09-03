# Claim 级溯源与原子验证 — 设计方案

> 目标：在不改写最终答案的前提下，为答案叠加一层“证据标注层”，让每个可独立验证的事实单元都能追溯到来源、验证状态和事件链。
> 原则：**拆的是验证单元，不是答案本身。**

---

## 1. 背景与问题

当前系统已经有：

- 研究阶段的结构化 Claims（`ResearchCard.key_findings`）
- 三轮对抗验证（`VerifiedCard.entries`）
- 候选答案验证（`CandidateVerifier`）
- 事件溯源、因果回溯、分支回滚、重放

但最终 `report.md` 和 `final_answer` 与这些证据之间缺少**可点击的绑定**：

- 用户看到一句结论，不知道它对应哪条研究 claim、哪些 URL、哪个事件
- `trace_claim` 只能靠文本模糊匹配事件，无法精确到“这句话的证据链”
- 验证状态停留在研究数据层，没有反映到最终答案上

本方案要解决的是：**把“答案文本”和“已有证据体系”用一张可追溯的 Claim 图谱连起来。**

---

## 2. 设计原则

1. **非破坏式标注**
   - 最终答案原文一个字都不改
   - 拆分结果作为旁路数据（`claims.json`）保存，不参与答案文本生成

2. **粒度适中**
   - 按“可独立验证的事实单元”拆分
   - 不拆到短语级，不拆修饰语、时间状语、逻辑连接词
   - Claim 必须是原文的连续子串，不允许改写或凭空细分

3. **层级化**
   - 结论 claim → 支撑 claim → 证据
   - 保留“因此 / 但是 / 首先”等逻辑关系，不让答案变成扁平碎片

4. **聚合而非碎片**
   - 每个 claim 有自己的置信度
   - 段落置信度 = 该段 claims 加权聚合
   - 答案整体置信度 = 各段聚合
   - 用户看到的是整体分数，不是一堆零散分数

5. **失败不删原文**
   - 低置信 claim 不删除，只标记为“存疑 / 待确认”
   - 只有核心 claim 被证伪时才触发答案修订流程

6. **双视图**
   - 流畅版：纯答案文章，默认展示
   - 证据版：按 claims 展开，每个 claim 带证据链

---

## 3. 数据模型

核心是三个概念：`AnswerDocument`、`ClaimNode`、`EvidenceLink`。

```json
{
  "run_id": "20260902-123456",
  "original_text": "……最终答案原文，与 report.md 完全一致……",
  "overall_confidence": 78,
  "claims": [
    {
      "claim_id": "c1",
      "text": "Queen Arwa University 成立于 1999 年",
      "claim_type": "direct_answer",
      "span": { "start": 12, "end": 48 },
      "parent_claim_id": null,
      "source_claim_ref": {
        "research_card_id": "card-3",
        "claim_index": 0
      },
      "status": "verified",
      "confidence": 82,
      "evidence_links": [
        {
          "url": "https://example.org/...",
          "tool": "web_fetch",
          "event_id": "evt_xxx",
          "snippet": "Founded in 1999...",
          "source_reliability": 4,
          "support": "support"
        }
      ],
      "event_ids": ["evt_xxx", "evt_yyy"]
    }
  ]
}
```

字段说明：

| 字段 | 含义 |
|---|---|
| `claim_id` | 稳定 ID，供 UI、API、回滚引用 |
| `span` | 在原文中的字符区间（Markdown 渲染时用） |
| `source_claim_ref` | 尽量复用研究阶段已有的 claim，避免重复验证 |
| `status` | `verified / suspect / disputed / unverifiable` |
| `confidence` | 0-100，由证据聚合得出 |
| `evidence_links` | 每条证据的来源、工具、事件 ID、摘要、支持/反对 |
| `event_ids` | 关联的事件 ID 列表，用于精确溯源 |

---

## 4. 生成流程

```
SynthesisCrewRunner 现有流程
  └─ Editor 产出 report.md（原文不动）
       └─ ClaimAnnotator（新增）
            ├─ 输入：question、data_summary、report.md、verified cards、search_plan
            ├─ 输出：claims.json（含 span、source_claim_ref、status、evidence_links）
            └─ 写 runs/<run_id>/claims.json
                └─ evidence.json 增加 claims 摘要（不替换原有字段）
```

关键约束：

- **ClaimAnnotator 只读 report.md，不修改 report.md**
- ClaimAnnotator 失败时静默跳过，不影响主流程和已有产物
- `final_answer` 仍从 report.md 提取，不因 claims 改变

---

## 5. Claim 提取与粒度控制

> 粒度适中的保证不是靠“感觉”，而是靠：**抽取规则 + 原文子串约束 + 自动校验 + 层级兜底 + 评测反馈**。

### 5.1 从哪里提取

优先从这些区域提取：

- “直接回答”段落
- “关键证据”段落中的结论句
- 每段的主题句 / 结论句

不对所有背景陈述、行动建议、成本附录做 claim 化。

### 5.2 一个 claim 的三条件

一个 claim 必须同时满足：

1. **可独立验证**：单独拿出来能判断真伪
2. **原子事实**：只含一个主谓宾事实，不包含并列事实
3. **对答案有支撑作用**：删掉它会影响答案的完整性

### 5.3 原文子串约束

- Claim 文本必须是原文的**连续子串**，不允许 LLM 自己改写或概括
- 这样能防止把一句话拆成“看起来更细但原文没有”的碎片
- 如果 LLM 想表达原文没有的细分，说明那不是拆分，而是新增内容，应丢弃

### 5.4 可拆 / 不可拆自测

| 原文 | 处理 | 判断依据 |
|---|---|---|
| “XX 成立于 1999 年” | 拆 | 一个可独立验证的事实 |
| “成立于 1999 年，位于也门” | 拆成两个 | 两个并列事实，各自可独立验证 |
| “1999 年” | 不拆 | 只是时间状语，不能独立判断真伪 |
| “但是目前缺乏官方档案” | 不拆 | 是限定/转折，不是独立事实 |
| “根据多个来源” | 不拆 | 元话语，不是事实 |
| “XX 大学是位于也门的一所高校” | 不拆 | 主干 + 必要限定语，拆开反而丢失语义 |

判断口诀：

- **能独立验证？** 不能 → 不拆
- **拆开后每块都还对答案有意义？** 不是 → 不拆
- **只是修饰/限定/连接？** 是 → 不拆
- **两个并列事实？** 是 → 拆

### 5.5 自动校验：过细 / 过粗检测

**过细检测**

| 检查 | 规则 | 处理 |
|---|---|---|
| 子串包含 | claim A 是 claim B 的子串，且表达同一事实 | 合并 |
| 相邻重复 | 相邻 claim 的主语+谓语几乎相同 | 合并 |
| 过短 | 长度过短且不是专有名词 | 标记为过细，合并到父 claim |

**过粗检测**

| 检查 | 规则 | 处理 |
|---|---|---|
| 并列词 | claim 中出现“并且 / 同时 / 以及 / 也 / 此外” | 提示可能含多个事实，交回模型二次拆分 |
| 多主题 | 一条 claim 的证据 URL 横跨多个不相关主题 | 提示可能过粗 |

### 5.6 层级兜底（最重要）

- 拿不准时，**不要拆成多个平级 claim**，而是保留一个父 claim + 若干子 claim
- 例如：

```
父：XX 大学的基本信息
  ├─ 子：成立于 1999 年
  └─ 子：位于也门
```

- 即使“拆细了”，展示层仍然是一段完整内容，不会显得支离破碎
- 验证时子 claim 各自独立验证，父 claim 置信度由子 claim 聚合

### 5.7 复用已有 claim

- 优先把最终答案句子映射到 `ResearchCard.key_findings` 或 `VerifiedCard.entries`
- 能映射的就继承 `claim_id`、验证状态、来源 URL
- 映射不上的才新建 claim，并在 `source_claim_ref` 中标记为空
- 复用本身也是一种粒度约束：**研究阶段已经是一个事实单元的，不要因为出现在答案里就拆得更碎**

---

## 6. 验证策略

### 6.1 分层验证

| 场景 | 处理 |
|---|---|
| 已有 VerifiedCard 覆盖 | 直接继承状态，不额外搜索 |
| 已有研究 claim 但未验证 | 按 claim 粒度做一次原子验证 |
| 新提取的 claim | 按 claim 粒度做一次原子验证 |
| 低风险/常识性 claim | 可标记 `unverifiable`，不强制搜索 |

### 6.2 原子验证

复用现有 `CandidateVerifier` 的思路，但改为 claim 粒度：

- 输入：一个 claim + 问题约束 + 已有线索
- 工具：`get_quality_search_tools()`
- 输出：支持/反对/中性证据、置信度、状态

### 6.3 聚合

- 一个 claim 有多条证据时，支持证据 > 反对证据 → 置信度上调
- 存在反对证据 → 状态降为 `disputed` 或 `suspect`
- 段落置信度 = 该段 claims 的加权平均（可按重要程度加权）
- 整体置信度 = 各段加权平均

---

## 7. 与事件溯源 / 回滚的关系

这是本方案最能体现技术深度的地方。

### 7.1 精确溯源

- 每个 `EvidenceLink.event_id` 直接指向事件 DAG 中的节点
- 新增 API：`GET /research/{run_id}/claims/{claim_id}/trace`
  - 返回该 claim 的证据事件链
  - 比现在 `trace_claim` 的文本模糊匹配更精确

### 7.2 回滚联动

- 回滚某个污染事件后，`ReplayEngine` 重放并重新生成报告
- 重新生成后自动重跑 `ClaimAnnotator`
- `claims.json` 记录 `generated_at`，可对比回滚前后的 claim 变化
- UI 可以展示“这条 claim 在回滚后状态从 X 变成 Y”

### 7.3 版本化

- 每次重新生成保留 `claims.<version>.json`（或写入 `claims_history.jsonl`）
- 便于审计：哪个版本、哪个事件导致 claim 状态变化

---

## 8. UI 设计

### 8.1 入口

- 日志页新增“报告证据”页签，或独立页面 `/report/{run_id}`
- 保持现有 `/logs` 入口不变

### 8.2 双视图

**流畅版（默认）**

- 展示原始 report.md，不显示任何标注
- 用户无感知

**证据版**

- 左侧：原文，claim 文本高亮/下划线
- 右侧：claim 列表
  - 状态徽标（verified / suspect / disputed / unverifiable）
  - 置信度
  - 证据 URL 列表
  - 事件链入口
- 点击右侧 claim → 左侧高亮对应 span
- 点击左侧高亮 → 右侧展开证据

### 8.3 操作

- 每条证据可点击打开原始 URL
- 有 `event_id` 的证据可查看事件链
- 有可回滚事件时提供“回滚到此证据”入口（复用现有 rollback API）

---

## 9. 评估指标

在 `eval_benchmarks.py` / `eval_judge.py` 中增加：

| 指标 | 含义 |
|---|---|
| Claim 覆盖率 | 最终答案中可映射到 claim 的比例 |
| 证据覆盖率 | 有至少一条 evidence 的 claim 比例 |
| 可追溯性 | 有 `event_id` 的 claim 比例 |
| 验证通过率 | status=verified 的 claim 比例 |
| 连贯性 | LLM 或人工评分（1-5），确保拆分不破坏可读性 |
| 粒度评分 | 每个 claim 由 LLM/人工评为“太细 / 刚好 / 太粗”，统计太细率与太粗率 |
| 粒度稳定性 | 同一问题多次运行，claim 数量和边界是否稳定 |

**粒度校准机制**

- 建立 30–50 条人工标注的“黄金拆分样例”
- 每次调整 ClaimAnnotator 提示词后，用黄金集对比：
  - claim 数量是否接近
  - 边界是否一致
  - 是否出现重复 / 遗漏
- 统计“太细率”和“太粗率”，作为 ClaimAnnotator 的优化指标
- 如果某次 run 拆出 5 个、另一次拆出 20 个，说明规则不稳定，需要收紧

这些指标用来防止“拆得越碎越好”的偏移。

---

## 10. 实施阶段

| 阶段 | 内容 | 风险 |
|---|---|---|
| Phase A | 数据模型 + ClaimAnnotator + 写 claims.json | 低，不影响现有产物 |
| Phase B | 对未覆盖 claim 做原子验证 | 中，增加少量搜索成本 |
| Phase C | API + UI 双视图 | 中，前端工作量 |
| Phase D | `scripts/eval_claims.py` 指标 + 黄金拆分集 + 规则粒度审计 | 低，验证收益 |

每个阶段可独立上线，先做 Phase A 就能获得“可追溯的答案”。

---

## 11. 风险与对策

| 风险 | 对策 |
|---|---|
| 拆分导致答案支离破碎 | 非破坏式标注 + 原文子串约束 + 三条件规则 + 自动过细/过粗检测 + 父子层级兜底 + 粒度评分 |
| LLM 标注不稳定 | 规则兜底、复用已有 claim、失败静默跳过 |
| 原子验证增加成本 | 只验证新 claim，可配置开关和预算 |
| 事件链缺失 | 允许只有 URL 没有 event_id，UI 降级展示 |
| 答案被意外修改 | ClaimAnnotator 只读 report.md，验收时 diff 必须为空 |

---

## 12. 验收标准

1. 一个已完成 run 能生成 `claims.json`
2. 每个 claim 有状态、置信度，以及至少一条 evidence 或明确“无证据”
3. `report.md` 在加入 ClaimAnnotator 前后 diff 为空
4. UI 能点击 claim 查看证据链
5. 评测显示可追溯性提升，且连贯性不下降
