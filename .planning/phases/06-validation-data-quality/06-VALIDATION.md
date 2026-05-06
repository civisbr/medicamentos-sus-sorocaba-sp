---
phase: 6
slug: validation-data-quality
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` / nenhum (pytest detecta automaticamente) |
| **Quick run command** | `python -m pytest tests/ -x -q --tb=short` |
| **Full suite command** | `python -m pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `python -m pytest tests/ -q --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | STAB-06 | — | N/A | file-exists | `ls .planning/phases/00-stabilization/00-VALIDATION.md` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | STAB-06 | — | N/A | file-exists | `ls .planning/phases/01-data-collection/01-VALIDATION.md` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | STAB-06 | — | N/A | file-exists | `ls .planning/phases/03-analysis/03-VALIDATION.md` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | STAB-07 | — | N/A | unit | `python -m pytest tests/test_exporter.py -k summary -x -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Testes de summary.json novos campos em `tests/test_exporter.py`

*Infraestrutura existente (pytest, rich, pandas) cobre todos os requisitos da fase. O comportamento de print/WARNING em main.py usa `rich.Console` que não é capturado pelo capsys do pytest (Pitfall 5 do RESEARCH.md) — verificado manualmente.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Print `Items: N \| BPS match: X% \| No match: Y%` no terminal | STAB-07 | `rich.Console` não capturado pelo capsys do pytest (Pitfall 5 RESEARCH.md) | Executar `python main.py --step analyze` com dados coletados e observar output no terminal |
| `[WARNING]` emitido quando cobertura BPS < 50% | STAB-07 | Mesmo motivo — rich.Console não testável via capsys | Criar dataset com maioria de itens sem match BPS e executar o pipeline completo |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
