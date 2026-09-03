# models/ — 数据契约

所有跨模块传递的结构化数据都用这里的 Pydantic 模型；DB JSONB 列存 `model_dump_json()`，读回用 `model_validate_json()`。

## 模型

| 模型 | 字段要点 | 校验 |
|---|---|---|
| `Claim` | text / confidence / sources / counterpoints | sources、counterpoints 默认空列表 |
| `ResearchCard` | perspective / role / research_question / key_findings / gaps / raw_transcript | role 默认空，gaps 默认空 |
| `ReflectionResult` | quality_score(0-100) / issues / feedback / acceptable / skipped | issues 是 `list[str]`；acceptable 由 pipeline 计算 |
| `VerificationEntry` | claim_index / claim_text / status / reasoning / checked_sources | — |
| `RefutationEntry` | claim_index / claim_text / challenge / severity / counter_evidence | claim_text 可缺省，由 crew 回填 |
| `VerifiedCard` | perspective / original_card_id / verification_round / entries / refutations / resolved / summary | verification_round 默认 1 |
| `ScoreResult` | overall_score(0-100) / claim_scores / summary | score 越界抛错；claim_scores 是 dict 列表 |
| `InsightResult` | consensus_signals / contradictions / blind_spots / time_sensitive_items | 默认空列表 |
| `ResearchRun` | id / question / status / created_at / completed_at / cards / verified / score / insights | id 自动生成时间戳式 |

## 枚举（`enums.py`）

- `Perspective`：technical / industry / critical / future（历史遗留四视角）。
- `Confidence`：high / medium / low。
- `VerificationStatus`：verified / suspect / false / disputed。
- `RunStatus`：pending / researching / verifying / synthesizing / completed / failed。

## 约束

1. 给 LLM 输出定义新字段时，先在模型加默认值，老 evidence.json 才能继续 `model_validate`。
2. DB 里 `claims` 表是扁平化视图，字段和 `Claim` 保持一一对应；改 `Claim` 必须同步 `db/repo.py` 和 SCHEMA。
3. 严格 JSON 解析后要用 `safe_construct_*` 构造模型，不要绕过 Pydantic 校验直接 dict 拼装。
4. `ReflectionResult.issues` 是字符串列表；如果 prompt 要求结构化对象，先改模型再改 parser，
   否则会出现 “str[0] is not a dict” 的静默丢弃。
