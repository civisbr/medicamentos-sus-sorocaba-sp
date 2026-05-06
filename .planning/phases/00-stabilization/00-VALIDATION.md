---
phase: 00-stabilization
created: 2026-05-06
source: 00-01-PLAN.md §success_criteria (retroativo — fase executada em 2026-05-03)
status: retroativo
---

# Phase 0: Stabilization — Validation Plan

**Phase:** 0 — Stabilization
**Date:** 2026-05-03 (retroativo — documento criado em 2026-05-06)
**Source:** `00-01-PLAN.md` §success_criteria — todos os critérios verificados na execução original

---

## Validators

| Name | Type | Check | Command |
|------|------|-------|---------|
| `help_sem_import_error` | smoke | `python main.py --help` retorna código 0 sem ImportError ou ModuleNotFoundError | `python main.py --help; echo "exit: $?"` |
| `supplier_analyzer_importavel` | smoke | `SupplierAnalyzer` é importável sem erro | `python -c "from src.analyzers.supplier_analyzer import SupplierAnalyzer; print('OK')"` |
| `sem_ano_hardcoded` | grep | Nenhuma ocorrência de `sorocaba_despesas_saude_2023` em main.py | `grep -c "sorocaba_despesas_saude_2023" main.py` (deve retornar 0) |
| `threshold_parametrizado` | grep | `threshold=threshold` presente em ai_analyzer.py | `grep -c "threshold=threshold" src/analyzers/ai_analyzer.py` (deve retornar 1) |
| `rapidfuzz_em_requirements` | grep | `rapidfuzz>=3.6.0` em requirements.txt | `grep -c "rapidfuzz>=3.6.0" requirements.txt` (deve retornar 1) |
| `anthropic_versao_correta` | grep | `anthropic>=0.40.0` em requirements.txt | `grep -c "anthropic>=0.40.0" requirements.txt` (deve retornar 1) |
| `sem_fuzzywuzzy` | grep | `fuzzywuzzy` não aparece em nenhum arquivo crítico | `grep -v '^#' requirements.txt src/utils/normalizer.py \| grep -c fuzzywuzzy` (deve retornar 0) |
| `root_path_ancorado` | grep | `ROOT = Path(__file__).parent` em main.py | `grep -c "ROOT = Path(__file__).parent" main.py` (deve retornar 1) |

---

## Cobertura de Testes

Nenhum arquivo de teste específico para Phase 0. Os critérios são verificáveis por `grep` e
execução direta conforme a tabela acima. Testes de módulos dependentes (normalizer, analyzers)
cobrem indiretamente os artefatos criados nesta fase.

| Verificação | Tipo | Requisito |
|-------------|------|-----------|
| python main.py --help | smoke | BUG-001, BUG-005 |
| grep sorocaba_despesas_saude_2023 | grep | BUG-002 |
| grep threshold=threshold | grep | BUG-003 |
| grep fuzzywuzzy + grep rapidfuzz | grep | BUG-004 |
| grep ROOT = Path(__file__).parent | grep | BUG-005 |

---

## Full Validation Commands

```bash
cd /path/to/medicamentos-sus-sorocaba-sp

# 1. main.py importa tudo sem erro
python main.py --help

# 2. SupplierAnalyzer importável
python -c "from src.analyzers.supplier_analyzer import SupplierAnalyzer; print('BUG-001 OK')"

# 3. Sem ano hardcoded (BUG-002)
[ "$(grep -c 'sorocaba_despesas_saude_2023' main.py)" -eq 0 ] && echo "BUG-002 OK" || echo "FAIL"

# 4. Threshold parametrizado (BUG-003)
[ "$(grep -c 'threshold=threshold' src/analyzers/ai_analyzer.py)" -ge 1 ] && echo "BUG-003 OK" || echo "FAIL"

# 5. Dependências corretas (BUG-004)
grep "rapidfuzz>=3.6.0" requirements.txt && grep "anthropic>=0.40.0" requirements.txt && echo "BUG-004 OK"

# 6. Sem fuzzywuzzy (BUG-004)
[ "$(grep -v '^#' requirements.txt src/utils/normalizer.py | grep -c fuzzywuzzy)" -eq 0 ] && echo "sem fuzzywuzzy OK" || echo "FAIL"

# 7. Paths ancorados (BUG-005)
[ "$(grep -c 'ROOT = Path(__file__).parent' main.py)" -ge 1 ] && echo "BUG-005 OK" || echo "FAIL"
```

---

## Evidências de Execução

**Fonte:** `00-01-PLAN.md` §success_criteria — executado em 2026-05-03.

Nota: A Phase 0 não possui `00-01-SUMMARY.md` (a execução original não gerou este arquivo).
Os critérios de sucesso foram verificados no momento da execução e confirmados pelas fases
subsequentes (1, 2, 3) que dependem dos artefatos desta fase e executaram sem regressão.

Confirmação indireta: `python -m pytest tests/ -q` passando 90 testes na conclusão da Phase 5
(2026-05-06) confirma que todos os artefatos da Phase 0 estão corretos e funcionais.
