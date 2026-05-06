---
phase: 06-validation-data-quality
plan: "02"
subsystem: exporter
tags: [data-quality, observability, bps-coverage, summary-json, tdd]
dependency_graph:
  requires: []
  provides: [summary.json/total_itens, summary.json/cobertura_bps_pct, summary.json/alertas_por_tier]
  affects: [docs/summary.json, terminal-output]
tech_stack:
  added: []
  patterns: [TDD RED/GREEN, pandas value_counts, pandas vectorized sum]
key_files:
  created: []
  modified:
    - src/utils/exporter.py
    - main.py
    - tests/test_exporter.py
decisions:
  - "total_itens reutiliza total_empenhos (alias) para evitar duplicação de len(alertas_df)"
  - "Campos novos ficam na raiz do summary dict, não dentro de totais, para separação de concerns"
  - "alertas_por_tier usa value_counts() que inclui todos os tiers automaticamente (SEM_REFERÊNCIA inclusive)"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-05-06"
  tasks_completed: 3
  files_changed: 3
---

# Phase 6 Plan 02: Data Quality Metrics in Summary JSON Summary

**One-liner:** Campos de qualidade BPS (total_itens, cobertura_bps_pct, alertas_por_tier) adicionados ao summary.json com linha observável "Items: N | BPS match: X% | No match: Y%" no terminal e WARNING condicional abaixo de 50%.

## Objective

Estendeu `gerar_summary()` em `src/utils/exporter.py` com 3 novos campos de qualidade de dados na raiz do summary.json, e expandiu o bloco de resumo final em `main.py` com linha de cobertura BPS e aviso condicional. Implementação seguiu ciclo TDD RED/GREEN.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Testes para 3 novos campos (RED) | 9edbcae | tests/test_exporter.py |
| 2 | Implementar 3 novos campos (GREEN) | 07cafb1 | src/utils/exporter.py |
| 3 | Expandir bloco de resumo em main.py | b027a61 | main.py |

## What Was Built

### Campos adicionados ao summary.json (raiz do dict)

```json
{
  "total_itens": 42,
  "cobertura_bps_pct": 73.8,
  "alertas_por_tier": {
    "OK": 15,
    "ATENÇÃO": 12,
    "ALERTA": 8,
    "CRÍTICO": 5,
    "SEM_REFERÊNCIA": 2
  }
}
```

- `total_itens` (int): número total de linhas no CSV de alertas (alias de `total_empenhos`)
- `cobertura_bps_pct` (float, 1 casa decimal): percentual de itens com preço BPS disponível — `round((com_bps / total_itens) * 100, 1)` onde `com_bps = total_itens - sem_ref`
- `alertas_por_tier` (dict str→int): contagem por valor de `nivel_alerta` via `value_counts()`
- Fallback para DataFrame vazio: `total_itens=0, cobertura_bps_pct=0.0, alertas_por_tier={}`

### Linha de resumo adicionada ao main.py

```
Items: 42 | BPS match: 73.8% | No match: 26.2%
[WARNING] Cobertura BPS 32.1% abaixo de 50% — análise de preços pouco representativa para este conjunto de dados.
```

- Linha sempre impressa quando summary.json existe
- WARNING em `[bold yellow]` emitido condicionalmente quando `cobertura_bps_pct < 50`
- `no_match = round(100.0 - cobertura, 1)` calculado no bloco de resumo

## Success Criteria Results

| # | Critério | Resultado |
|---|----------|-----------|
| 1 | `pytest tests/test_exporter.py::TestGerarSummary -v` → 10 passed | PASS (10 passed, 0 failed) |
| 2 | `grep -c "total_itens" src/utils/exporter.py` >= 2 | PASS (4 ocorrências) |
| 3 | `grep -c "cobertura_bps_pct" src/utils/exporter.py` >= 2 | PASS (3 ocorrências) |
| 4 | `grep -c "alertas_por_tier" src/utils/exporter.py` >= 2 | PASS (3 ocorrências) |
| 5 | `grep "BPS match" main.py` → 1 linha com formato correto | PASS |
| 6 | `grep "bold yellow.*WARNING" main.py` → 1 linha | PASS |
| 7 | `ast.parse(main.py)` → "OK" | PASS (syntax OK) |
| 8 | `pytest tests/ -q` → zero regressões | PASS (94 passed, 0 failed) |

## TDD Gate Compliance

- RED gate: commit `9edbcae` — `test(06-02): add failing tests for total_itens, cobertura_bps_pct, alertas_por_tier` (4 falhas confirmadas, 6 existentes passando)
- GREEN gate: commit `07cafb1` — `feat(06-02): add total_itens, cobertura_bps_pct, alertas_por_tier to gerar_summary()` (10 passed)
- REFACTOR: nenhuma refatoração necessária

## Deviations from Plan

None — plano executado exatamente como escrito.

## Known Stubs

None — todos os campos são computados a partir de dados reais do DataFrame de alertas.

## Threat Flags

Nenhuma nova superfície de segurança introduzida. Todos os threats do plano (T-06-02-01 a T-06-02-03) disposição `accept` — campos calculados de dados públicos, operações pandas vetorizadas sem risco de OOM.

## Self-Check: PASSED

- `src/utils/exporter.py` existe e contém `total_itens`, `cobertura_bps_pct`, `alertas_por_tier`
- `main.py` existe e contém `BPS match` e `[WARNING]`
- `tests/test_exporter.py` contém os 4 novos métodos
- Commits `9edbcae`, `07cafb1`, `b027a61` presentes no log
