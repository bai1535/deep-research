# Agent 独立性治理方案（AgentPolicy）

> 目标：把当前“角色扮演式的多 Agent”升级为“有明确边界、权限、验证标准的协作系统”。
> 原则：先做声明式策略 + 运行时强制，不做 OS 级沙箱。

---

## 1. 现状与差距

| 独立性维度 | 当前状态 | 差距 |
|---|---|---|
| 独立上下文 | 每个 Agent 有独立 messages | 仍会通过 Blackboard 注入共享上下文，缺少“谁可见谁不可见”的控制 |
| 独立工具 | 工具实例 deep-copy | 没有 per-agent 的可用/禁用、配额、速率限制 |
| 独立目标 | role/goal 不同 | 没有正式化，无法审计 |
| 独立权限 | 只有工具列表差异 | 没有数据域权限、写权限、事件权限 |
| 独立验证标准 | Prompt 内不同 | 没有统一可配置的评分标准对象 |

---

## 2. 设计目标

1. 每个 Agent 有**显式 Policy**，描述它能做什么、不能做什么、按什么标准验证。
2. 运行时在关键边界强制 Policy：
   - 工具调用前
   - Blackboard 读写前
   - 文件/DB 访问前
   - LLM 上下文注入前
3. 所有 Policy 决策可审计、可日志化。
4. 默认策略保持当前行为，避免一上来就破坏现有流程。
5. 支持“独立验证标准”：不同 Agent 可以有不同的阈值、评分规则、是否允许看其他 Agent 中间结论。

---

## 3. AgentPolicy 数据模型

```python
class AgentPolicy(BaseModel):
    agent_name: str

    # ── 上下文隔离 ─────────────────────────────
    context: ContextPolicy
    # 例如：允许读取哪些 blackboard 域、是否注入其他视角的结论

    # ── 工具权限 ─────────────────────────────
    tools: ToolPolicy
    # allowed_tools / denied_tools / per-tool max_calls / cooldown

    # ── 数据权限 ─────────────────────────────
    data: DataPolicy
    # blackboard_read_keys / blackboard_write_keys
    # allowed_db_tables / allowed_file_prefixes

    # ── 资源预算 ─────────────────────────────
    budget: ResourceBudget
    # max_tool_calls / max_llm_calls / max_tokens / max_cost

    # ── 验证标准 ─────────────────────────────
    verification: VerificationStandard
    # status_allowed / confidence_rubric / min_confidence
    # independent_review_required / can_see_first_pass
```

### 3.1 示例：Researcher Policy

```python
AgentPolicy(
    agent_name="researcher-*",
    context=ContextPolicy(
        read_blackboard_keys=["search_plan", "run_id", "trace_id"],
        write_blackboard_keys=[f"run:{run_id}:cards"],
        can_read_other_agents=False,
    ),
    tools=ToolPolicy(
        allowed_tools=["bing_search", "baidu_search", "web_fetch",
                       "wikipedia_search", "wikidata_lookup", "firecrawl_search"],
        denied_tools=["sqlite_read"],
        per_tool_max_calls={"firecrawl_search": 10},
    ),
    data=DataPolicy(
        allowed_db_tables=["research_cards"],
        allowed_file_prefixes=["runs/<run_id>/"],
    ),
    budget=ResourceBudget(max_tool_calls=40, max_cost_usd=0.1),
    verification=VerificationStandard(
        status_allowed=["high", "medium", "low"],
        confidence_rubric="researcher_rubric_v1",
    ),
)
```

### 3.2 示例：Verifier Policy

```python
AgentPolicy(
    agent_name="verifier-*",
    context=ContextPolicy(
        read_blackboard_keys=["run_id", "trace_id", f"run:{run_id}:cards"],
        write_blackboard_keys=[f"run:{run_id}:verified"],
        can_read_other_agents=False,
    ),
    tools=ToolPolicy(
        allowed_tools=["bing_search", "baidu_search", "web_fetch", "sqlite_read"],
        denied_tools=["firecrawl_search"],  # 默认不消耗 Firecrawl
    ),
    verification=VerificationStandard(
        status_allowed=["verified", "suspect", "false", "disputed"],
        confidence_rubric="verifier_rubric_v1",
        independent_review_required=True,
    ),
)
```

---

## 4. 运行时强制点

### 4.1 Agent 构造时
- `create_agent()` 接收 Policy
- 根据 Policy 过滤 tools
- 根据 Policy 构造 `ScopedBlackboard`
- 根据 Policy 注入 ContextPolicy 允许的共享上下文

### 4.2 Agent 运行时
| 边界 | 强制方式 |
|---|---|
| 工具调用 | `PolicyToolProxy`：执行前检查 allowed/denied、per-tool 次数、成本预算 |
| Blackboard 读 | `ScopedBlackboard.read()` 只允许 `read_blackboard_keys` |
| Blackboard 写 | `ScopedBlackboard.write()` 只允许 `write_blackboard_keys` |
| 文件/DB | Repository/FileCache 传入 Policy，按 allowed 表/路径前缀校验 |
| LLM 上下文 | `_blackboard_context()` 只注入 Policy 允许的 key |
| 验证标准 | Agent 的 task prompt 从 `VerificationStandard` 生成，而不是写死在代码里 |

### 4.3 进程级共享仍保留
- Firecrawl/Tavily 的不可恢复禁用和 429 cooldown 仍是进程级
- AgentPolicy 只做 per-agent 权限/配额，不替代全局熔断

---

## 5. 独立验证标准设计

这是“独立性”里最有技术含量的一部分。

### 5.1 每个 Agent 一套标准
```python
class VerificationStandard(BaseModel):
    name: str
    status_allowed: list[str]
    confidence_rubric: dict[str, int]
    min_confidence: int
    independent_review_required: bool
    can_see_first_pass: bool
```

### 5.2 标准注入方式
- 不再把评分规则散落在 Prompt 里
- 由 Policy 生成该 Agent 的“验证标准块”附加到 Prompt
- 例如 Verifier 的 Prompt 自动包含：
  ```
  【验证标准 verifier_rubric_v1】
  - 多源官方 = 90
  - 单源权威 = 75
  - 单源弱 = 50
  - 只有反证 = 20
  ```
- 不同 Agent 可用不同 rubric，便于 A/B 测试和回归

### 5.3 信息隔离
- 默认 Researcher 不能看其他 Researcher 的 raw_transcript
- Verifier 只能看被分配视角的卡片，不能看全部视角
- 独立二次核查员默认**不能看到第一轮结论**
- 这些都由 `ContextPolicy` 控制

---

## 6. 实施阶段

| 阶段 | 内容 | 影响 |
|---|---|---|
| Phase 1 | AgentPolicy 数据模型 + 注册表接入 | 无行为变化，先显式化 |
| Phase 2 | ScopedBlackboard + 工具权限强制 | 开始真正限制读写/工具 |
| Phase 3 | 资源预算 + 审计日志 | 可观测、可控制成本 |
| Phase 4 | VerificationStandard 独立化 | 评分标准可配置、可回归 |
| Phase 5 | 信息隔离完整化 | Researcher/Verifier 互不可见中间结论 |

每个阶段可独立上线，默认 Policy 保持当前能力，不会突然“锁死”现有流程。

---

## 7. 审计与可观测性

- 每次 Policy 拒绝都记录：
  - agent
  - action
  - 被拒绝原因
  - 时间
- 写入 `logs/policy_audit.jsonl`
- 日志页新增“策略审计”页签（可选）
- 指标：
  - 每个 Agent 工具调用次数
  - 被拒绝次数
  - 成本消耗
  - 是否触发独立复核

---

## 8. 风险与对策

| 风险 | 对策 |
|---|---|
| 默认 Policy 太严导致流程中断 | 默认 Policy = 当前全部权限，逐步收紧 |
| 配置爆炸 | Policy 支持通配符和继承（如 `researcher-*`） |
| 审计日志过大 | 只记录拒绝和高风险操作 |
| 黑名单遗漏 | 用 deny-by-default + allowlist 方式 |
| 过度设计 | 先不做 OS 沙箱，只做应用层边界 |

---

## 9. 验收标准

1. 每个 Agent 能从注册表查到自己的 Policy。
2. 未授权的工具调用会被拒绝并记录。
3. 未授权的 Blackboard key 读写会被拒绝并记录。
4. Researcher 默认看不到其他 Researcher 的原始结论。
5. 独立二次核查员默认看不到第一轮结论。
6. 不同 Agent 的验证标准可以从配置切换，并影响 Prompt。
7. 日志页能查看策略审计。
