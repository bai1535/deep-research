# Sprint Contract

## Sprint / Feature
- Feature ID: F20
- Goal: Verifier 状态容错 + Researcher JSON 约束强化

## 范围（In Scope）
- `verification_crew.py`：状态归一化
- `research_crew.py`：JSON 输出约束与重试提示
- 新增 `tests/test_verification_status.py`

## 验收标准（Definition of Done）
- [ ] `node scripts/harness.mjs verify F20` 通过
- [ ] 远程 `make test` 全绿
- [ ] `make check` 通过

## 验证命令
- 本地镜像：`node scripts/verify-local-f20.mjs`
- 远程：`make test` + `make check`
