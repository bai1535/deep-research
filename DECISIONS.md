# 设计决策

## 2026-08-25: 测试体系改为 asyncpg/PostgreSQL 真实库测试
- 原因: 当前 `Repository` 已迁移到 asyncpg 连接池，旧 SQLite 测试已失效
- 否决方案: 继续使用 SQLite 测试替身（与生产 DB 行为不一致）
- 约束: 测试使用唯一 `test-<uuid>` run id，并在 `finally` 中清理数据，避免污染真实数据

## 2026-08-25: pytest-asyncio 使用 session 级 event loop
- 原因: asyncpg 全局连接池不能跨不同 event loop 复用
- 否决方案: 每个测试新建连接池（增加复杂度和连接开销）
- 约束: `make test` 必须传入 `asyncio_mode=auto` 与 session 级 loop scope

## 2026-08-25: 效果评估使用 evidence.json 来源作为弱标注
- 原因: 当前没有人工标注的检索相关性集合，先利用最终引用来源做弱相关
- 否决方案: 等待人工标注（成本高，阻碍快速迭代）
- 约束: Hit@k/nDCG@k 只作为趋势参考，不能替代人工评估

## 2026-08-25: search_calls 增加 result_urls 字段
- 原因: 没有返回 URL 就无法计算 Hit@k/nDCG@k
- 否决方案: 只统计可用率/延迟（信息量不足）
- 约束: 从工具返回文本中提取 `URL:` 行，缺失时脚本降级为延迟/可用率报告

## 2026-08-25: response_parser 归一化全角双引号
- 原因: LLM 输出全角引号 `“”` 导致 JSON 非法，所有解析策略失败
- 否决方案: 只改 prompt（仍可能偶发；解析器兜底更稳）
- 约束: 仅在解析前做安全字符替换，不改变字符串内容语义

## 2026-08-25: 接入 DeepResearch Bench 与 BrowseComp-Plus
- 原因: 需要公开基准来检验深度搜索和长报告能力，避免只靠自建集
- 否决方案: 只做自建集（缺少外部可比性）
- 约束: 默认 `--limit` 小规模运行，避免高成本；先保存报告，评分后续接入

## 2026-08-25: 搜索策略优化
- 原因: BrowseComp-Plus 样本显示 cn.bing 中文市场对英文冷门事实检索差，且 Agent 查询策略堆砌
- 否决方案: 只增加新搜索后端（依赖外部服务/成本）
- 约束: 先用英文市场参数 + 提示词约束，低成本可回退

## 2026-08-25: 日志过滤与 Scorer 容错
- 原因: 日志级别带 padding 导致 `[ERROR]` 过滤不到；Scorer 漏 `overall_score` 导致 Total failure
- 否决方案: 只改前端（后端过滤更通用）
- 约束: `overall_score` 默认 0，保证可观测性优先

## 2026-08-27: 增加 Wikipedia/Wikidata 知识工具与最终答案抽取器
- 原因: BrowseComp-Plus 冷门英文事实在通用搜索引擎上召回差，且评测需要短答案而非长报告
- 否决方案: 只继续调通用搜索参数（上一轮已做，提升有限）
- 约束: 知识库工具免费、无 key，失败按统一 error schema 降级；最终答案先做确定性抽取，避免额外 LLM 成本

## 2026-08-27: 借鉴 ModSearch 的 Firecrawl keyless 桥接
- 原因: wikipedia.org/wikidata.org 在 CN 服务器直连超时，但 Firecrawl keyless 实测可通
- 否决方案: 继续找不稳定维基镜像
- 约束: 优先使用 Firecrawl keyless 免费通道；有 FIRECRAWL_API_KEY 时仍走原 key 逻辑

## 2026-08-27: Firecrawl 省额度策略
- 原因: Firecrawl keyless 每月约 1000 credits，不应作为默认搜索
- 方案: 默认 `get_search_tools()` 只含 Baidu/Bing/Wikipedia/Wikidata；Reflector 质量门失败触发 augment 时使用 `get_quality_search_tools()` 追加 Firecrawl/Tavily
- 否决方案: 让 LLM 自行判断是否用 Firecrawl（不可控，容易浪费额度）

## 2026-08-27: 轻量每轮搜索质量门
- 原因: 只靠整轮 Reflector 太晚，Baidu/Bing 不足时会浪费多轮
- 方案: 用确定性启发式（全错/为空/少于 2 条 URL）在 Agent 轮内解锁 reserved quality tools
- 否决方案: 每轮 LLM 评分（成本高、收益不明显）

## 2026-08-27: 查询规划器
- 原因: 不同问题类型需要不同搜索源和验证方式，统一搜索策略太低效
- 方案: 研究前用 LLM 分类问题类型，生成结构化搜索方案并注入 Orchestrator/Researcher
- 否决方案: 所有问题都用同一套搜索流程（对 BrowseComp 多跳题效果差）

## 2026-08-27: 日志页面稳定性与对比度
- 原因: 轮询请求可能重叠/挂起，导致页面看起来卡住；暗色下文字对比不足
- 方案: 前端加请求超时、防重叠、防过期响应、回到前台刷新；提高文字亮度与背景反差
- 否决方案: 改后端 SSE（成本高，当前轮询够用）

## 2026-08-28: 候选答案验证循环
- 原因: 查询规划器拆题后仍缺“锁答案”的环节
- 方案: 仅对 entity_fact / multi_hop_clue / historical_archive 启用，使用质量搜索工具逐条验证候选
- 否决方案: 对所有题型都做候选验证（开放题没有唯一候选，成本高且无意义）

## 2026-08-28: Wayback Machine 历史档案接入
- 原因: 旧事件/旧官网在普通搜索中索引不到
- 方案: 用 Firecrawl keyless 桥接 archive.org availability API，新增 wayback_lookup
- 否决方案: 直连 web.archive.org（CN 超时）

## 2026-08-28: 自动评测 Judge
- 原因: 没有自动判分，无法快速衡量优化效果
- 方案: 用 DeepSeek 裁判 final_answer vs gold，输出 yes/partial/no + 分数
- 否决方案: 纯字符串匹配（对别名/翻译不鲁棒）

## 2026-08-28: Verifier 主动搜索 + 矛盾裁决器
- 原因: Verifier 只能抓已有 URL，无法主动找反证；跨视角矛盾缺少裁决
- 方案: VERIFIER_CONFIG 增加搜索工具；跨视角矛盾由专门 Agent 裁决
- 否决方案: 只靠 Scorer 打分处理矛盾（缺少可解释裁决）

## 2026-08-28: 候选验证结果归一化
- 原因: LLM 返回结构不稳定，导致 candidates=0
- 方案: 归一化兼容单对象/数组两种返回；weak_candidate 不强制作为最终答案

## 2026-09-01: F19 存储策略采用方案 E（分层存储）
- 热数据：最近 50 个 run 保存完整事件 + 输出缓存，支持确定性回滚
- 冷数据：只保留哈希和摘要，回滚旧 run 时重新抓取/生成，确定性降级为近似重放
- 原因：避免全量保存页面/LLM 输出撑爆磁盘，同时保证近期 run 可完整回放

## 2026-09-01: F19-2 因果回溯引擎
- 方案: 从最终声明文本匹配事件，沿 parent 链反向遍历，对外部来源事件给高污染分
- 范围: 仅引擎与测试，未接 UI/API

## 2026-09-01: F19-3 确定性缓存与重放
- 方案: OutputCache 按 action+input_hash 缓存输出；ReplayEngine 重放时优先复用缓存
- 存储: 热数据保存完整输出缓存，冷数据只留哈希（方案 E）

## 2026-09-01: F19-4 分支级回滚与 API
- 方案: descendants 计算受影响子树，rollback API 返回 trusted/affected/unaffected 计划
- 范围: 只返回计划，不实际执行重放（执行留给后续）

## 2026-09-01: F19-5 实际执行 rollback
- 方案: 清除受影响分支缓存 + 写 rollback_state.json，标记 pending_replay
- 范围: 暂不自动重放生成报告，先让回滚状态真实可查

## 2026-09-01: F19-6 重放受影响分支
- 方案: 回滚后重放受影响的外部工具事件，写 replay_output.jsonl，状态置 tools_replayed
- 范围: 暂不重放 LLM/报告生成

## 2026-09-01: F19-7 重放 LLM + 重新生成报告
- 方案: 回滚+重放工具后调用 SynthesisCrewRunner 重新生成报告/evidence
- 范围: 合成阶段 LLM 重放；研究阶段 LLM 分支重放仍为后续

## 2026-09-01: F19-8 日志/前端事件查看和回滚入口
- 方案: 在 logs.html 增加事件/回滚页签，调用现有 events/rollback/trace API

## 2026-09-02: Verifier 状态容错 + Researcher JSON 约束
- 原因: 日志中大量 VerificationEntry 构造失败和 Researcher JSON 解析失败
- 方案: 状态字段自动归一化；Researcher 提示和重试提示更严格

## 2026-09-02: Claim 级溯源 Phase A 采用非破坏式标注
- 原因: 最终答案与已有证据体系之间缺少可点击绑定
- 方案: 不改写 report.md，新增 ClaimAnnotator 抽取 claims 写入 claims.json，
  并映射到研究阶段 claim；粒度控制用“原文子串 + 三条件 + 自动校验 + 父子层级”
- 否决方案: 直接按 claims 重写答案（会破坏可读性）

## 2026-09-02: Claim 级溯源 Phase B 对未覆盖 claim 做原子验证
- 原因: Phase A 只继承已有验证，新 claim 或未验证 claim 仍缺少独立核查
- 方案: 新增 AtomicClaimVerifier，对 status=unverifiable 的 claim 逐条使用
  质量搜索工具验证，写回状态/置信度/证据/推理/事件 ID
- 否决方案: 对全部 claim 重新验证（浪费成本，已有 verified 无需重复）

## 2026-09-02: Claim 级溯源 Phase C 使用独立报告证据页
- 原因: 需要让用户能点击 claim 查看证据链，而不只停留在 JSON
- 方案: 新增 `/report/{run_id}` 独立页面，提供流畅版/证据版双视图；
  API 增加 claims 与 claim trace 接口
- 否决方案: 塞进 logs.html 事件页签（职责混杂，页面会更复杂）

## 2026-09-02: Claim 级溯源 Phase D 先做离线指标与规则审计
- 原因: 需要量化 Claim 溯源效果，但 LLM 粒度评分成本高、难稳定
- 方案: 新增 `scripts/eval_claims.py` 计算覆盖率/证据覆盖率/可追溯性/验证通过率，
  并用规则审计（子串包含、并列词、过短）作为粒度代理指标；
  同时提供黄金拆分样例 `data/claim_golden.json` 供后续人工/LLM 校准
- 否决方案: 立即接 LLM 粒度评分（成本高，先有离线基线再上）

## 2026-09-02: Verifier 增加独立二次核查，区分事实与表述
- 原因: 多个事实正确的 claim 因“口径提醒/表述风格”被降为 suspect/disputed
- 方案: 第一轮非全 verified 时运行独立二次核查员（不参考前序结论、用质量工具），
  输出 fact_status/status/confidence/presentation_issues；合并时允许
  “独立复核确认事实成立”将 claim 恢复为 verified
- 否决方案: 继续只靠同一模型自证（容易自我说服降级）

## 2026-09-02: Researcher 输出救捞
- 原因: Researcher 是日志中“ALL parse strategies failed”最多的模块，多次重试后仍输出 Markdown/散文
- 方案: 重试耗尽后调用无工具格式化 Agent，把最后一段非 JSON 原始输出转换为标准 ResearchCard
- 否决方案: 只增加重试次数（成本高，且模型可能继续输出同样格式）

## 2026-09-02: Agent 独立性治理 Phase 1
- 原因: Agent 目前只有“角色/工具列表”差异，缺少正式权限、数据域、验证标准边界
- 方案: 先新增 AgentPolicy 数据模型，create_agent 自动附加默认 Policy；默认全放行，不改变行为
- 后续: Phase 2 再做 ScopedBlackboard 和工具权限强制

## 2026-09-02: Agent 独立性治理 Phase 2
- 原因: Phase 1 只是元数据，还没有真正限制 Agent 行为
- 方案: 新增 ScopedBlackboard 按 ContextPolicy 限制读写；Agent 工具调用前按 ToolPolicy 检查
- 默认策略仍全放行，但机制已可被自定义 Policy 触发

## 2026-09-02: Agent 独立性治理 Phase 3
- 原因: 需要控制单个 Agent 的资源消耗并记录策略拒绝
- 方案: ResourceBudget 限制工具次数/LLM 次数/token/成本；拒绝行为写入 logs/policy_audit.jsonl
- 默认预算为 None，不改变现有流程

## 2026-09-02: Agent 独立性治理 Phase 4
- 原因: 验证标准仍散落在各 task Prompt 中，难以统一配置和回归
- 方案: VerificationStandard.render_prompt() 从 Policy 生成“验证标准块”，由 create_agent 注入 system prompt
- 不同 Agent（verifier/researcher/scorer/second-opinion）有独立 rubric

## 2026-09-02: Agent 独立性治理 Phase 5
- 原因: 仅提示词“不得查看第一轮”不够，需要运行时隔离
- 方案: second-opinion/contradiction-adjudicator 的 ContextPolicy 只允许读取 run_id/trace_id/event_bus/search_plan/usage:*，
  不允许读取 run:* 等第一轮数据；ScopedBlackboard 强制生效

## 2026-09-03: 自适应计算分配 F34
- 原因: 所有 Researcher 使用相同固定预算，质量门补强时无差别重跑全部卡片，
  强卡浪费预算、弱卡又可能不够深
- 方案: 新增纯确定性 `adaptive.py`；首轮按问题类型/角色/关键词宽度生成
  `ComputeAllocation`，并映射到 Researcher 的 ResourceBudget；补强轮用
  `card_weakness_score` 挑弱卡并给动态预算（弱卡深、强卡浅），后续轮次递增 15%
- 否决方案: 让 LLM 自己决定预算（不可审计、易波动）；首轮直接取消预算（失去 ResourceBudget 意义）
- 范围: 只做确定性规则版，先验证收益；后续可接 MCTS/信息增益决策器
