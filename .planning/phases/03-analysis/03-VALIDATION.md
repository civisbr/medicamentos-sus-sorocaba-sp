---
phase: 03-analysis
created: 2026-05-06
source: 03-01/02/03-SUMMARY.md + 03-01/02/03-PLAN.md §success_criteria (retroativo — fase executada em 2026-05-05)
status: retroativo
---

# Phase 3: Analysis — Validation Plan

**Phase:** 3 — Analysis
**Date:** 2026-05-05 (retroativo — documento criado em 2026-05-06)
**Source:** SUMMARYs de 03-01, 03-02, 03-03 — evidências TDD com commits RED/GREEN documentados

---

## Framework

| Propriedade | Valor |
|-------------|-------|
| Framework | pytest 8.3.4 |
| Config | nenhuma (descoberta automática de `tests/`) |
| Comando rápido | `python -m pytest tests/test_price_analyzer.py tests/test_supplier_analyzer.py -x -q` |
| Suite completa | `python -m pytest tests/ -q` |
| Baseline ao final da fase | 39 testes passando |

---

## Matriz de Testes por Requisito

| Req ID | Comportamento | Tipo | Arquivo | Classe | Status |
|--------|--------------|------|---------|--------|--------|
| REQ-005 | `PriceAnalyzer(30,100,200).classificar_alerta(251.3)` retorna `"CRÍTICO"` | unit | `tests/test_price_analyzer.py` | `TestClassificarAlerta` | PASS [VERIFIED: 03-01-SUMMARY.md — 12 testes] |
| REQ-005 | `PriceAnalyzer.analisar()` produz CSV com 12 colunas | integration | `tests/test_price_analyzer.py` | `TestAnalisar` | PASS [VERIFIED: 03-01-SUMMARY.md] |
| REQ-005 | Itens com `QT_REGISTROS < 5` no BPS NÃO recebem tier CRÍTICO | unit | `tests/test_price_analyzer.py` | `TestClassificarAlerta` | PASS [VERIFIED: 03-01-SUMMARY.md] |
| REQ-005 | Itens sem match BPS recebem `nivel_alerta = "SEM_REFERÊNCIA"` | unit | `tests/test_price_analyzer.py` | `TestAnalisar` | PASS [VERIFIED: 03-01-SUMMARY.md] |
| REQ-005 | `THRESHOLD_ALERTA=100` e `THRESHOLD_CRITICO=200` definidos como constantes | grep | `src/analyzers/price_analyzer.py` | — | PASS [VERIFIED: 03-03-SUMMARY.md] |
| REQ-006 | `SupplierAnalyzer._calcular_score_fornecedor()` com 3+ CRÍTICO retorna tier SUSPEITO | unit | `tests/test_supplier_analyzer.py` | `TestCalcularScoreFornecedor` | PASS [VERIFIED: 03-02-SUMMARY.md — 9 testes] |
| REQ-006 | `SupplierAnalyzer.analisar()` produz CSV com 10 colunas | integration | `tests/test_supplier_analyzer.py` | `TestAnalisar` | PASS [VERIFIED: 03-02-SUMMARY.md] |
| REQ-006 | Concentração > 60% do valor_excedente_total → tier SUSPEITO | unit | `tests/test_supplier_analyzer.py` | `TestCalcularScoreFornecedor` | PASS [VERIFIED: 03-02-SUMMARY.md] |
| REQ-006 | Degradação graciosa quando `fornecedores_enriquecidos.json` ausente | unit | `tests/test_supplier_analyzer.py` | `TestAnalisar` | PASS [VERIFIED: 03-02-SUMMARY.md] |

---

## Validators

| Name | Type | Check | Command |
|------|------|-------|---------|
| `price_analyzer_suite` | unit | 12 testes passando em test_price_analyzer.py | `python -m pytest tests/test_price_analyzer.py -v -q` |
| `supplier_analyzer_suite` | unit | 9 testes passando em test_supplier_analyzer.py | `python -m pytest tests/test_supplier_analyzer.py -v -q` |
| `critico_limiar_200` | unit | Desvio >=200% → CRÍTICO | `python -m pytest tests/test_price_analyzer.py -k "critico" -v` |
| `sem_referencia_bps` | unit | Sem match BPS → SEM_REFERÊNCIA (não CRÍTICO) | `python -m pytest tests/test_price_analyzer.py -k "sem_referencia or SEM_REFERENCIA" -v` |
| `suspeito_concentracao` | unit | Concentração >60% → SUSPEITO | `python -m pytest tests/test_supplier_analyzer.py -k "concentracao or suspeito" -v` |
| `thresholds_main_py` | grep | `threshold_alerta=100` e `threshold_critico=200` em main.py | `grep -c "threshold_alerta=100" main.py` (deve retornar 1) e `grep -c "threshold_critico=200" main.py` (deve retornar 1) |
| `alertas_csv_12_colunas` | file | `data/reports/alertas_superfaturamento.csv` existe com 12 colunas | `python -c "import pandas as pd; df = pd.read_csv('data/reports/alertas_superfaturamento.csv'); assert len(df.columns) == 12, f'Colunas: {list(df.columns)}'; print('12 colunas OK')"` |
| `fornecedores_csv_10_colunas` | file | `data/reports/fornecedores_suspeitos.csv` existe com 10 colunas | `python -c "import pandas as pd; df = pd.read_csv('data/reports/fornecedores_suspeitos.csv'); assert len(df.columns) == 10, f'Colunas: {list(df.columns)}'; print('10 colunas OK')"` |

---

## Full Validation Commands

```bash
cd /path/to/medicamentos-sus-sorocaba-sp

# 1. PriceAnalyzer — suite completa
python -m pytest tests/test_price_analyzer.py -v
# Esperado: 12 passed (TestClassificarAlerta: 5, TestAnalisar: 6, TestGerarEstatisticas: 1)

# 2. SupplierAnalyzer — suite completa
python -m pytest tests/test_supplier_analyzer.py -v
# Esperado: 9 passed

# 3. Thresholds corretos em main.py
grep "threshold_alerta=100" main.py && grep "threshold_critico=200" main.py && echo "Thresholds OK"

# 4. Schema de alertas_superfaturamento.csv
python -c "
import pandas as pd
df = pd.read_csv('data/reports/alertas_superfaturamento.csv')
assert len(df.columns) == 12, f'Esperado 12 colunas, obtido {len(df.columns)}: {list(df.columns)}'
print(f'alertas_superfaturamento.csv OK: {len(df.columns)} colunas, {len(df)} linhas')
"

# 5. Schema de fornecedores_suspeitos.csv
python -c "
import pandas as pd
df = pd.read_csv('data/reports/fornecedores_suspeitos.csv')
assert len(df.columns) == 10, f'Esperado 10 colunas, obtido {len(df.columns)}: {list(df.columns)}'
print(f'fornecedores_suspeitos.csv OK: {len(df.columns)} colunas, {len(df)} linhas')
"

# 6. Suite completa (baseline 39 testes ao final da fase)
python -m pytest tests/ -q
```

---

## TDD Gate Evidence

A Phase 3 foi implementada com metodologia TDD rigorosa:

| Plano | RED commit | GREEN commit | Testes |
|-------|-----------|--------------|--------|
| 03-01 (PriceAnalyzer) | `888f41d` — test: add failing tests for PriceAnalyzer | `f3094de` — feat: implement PriceAnalyzer.analisar() | 12 testes |
| 03-02 (SupplierAnalyzer) | `80052ae` — test: add failing tests for SupplierAnalyzer | `c66ec4d` — feat: implement SupplierAnalyzer.analisar() | 9 testes |
| 03-03 (Pipeline E2E) | — (sem TDD, checkpoint humano) | `e22c8c6` — feat: wire PriceAnalyzer with correct thresholds | Checkpoint aprovado |

---

## Evidências de Execução

| Plano | Artefato | Evidência |
|-------|----------|-----------|
| 03-01 | `src/analyzers/price_analyzer.py` | "12 passed, 0 failed" — TestClassificarAlerta (5), TestAnalisar (6), TestGerarEstatisticas (1) [VERIFIED: 03-01-SUMMARY.md] |
| 03-02 | `src/analyzers/supplier_analyzer.py` | "9 passed" — score ponderado, tier SUSPEITO via OR, 10 colunas [VERIFIED: 03-02-SUMMARY.md] |
| 03-03 | `main.py`, `alertas_superfaturamento.csv`, `fornecedores_suspeitos.csv` | "Aprovado — CSVs gerados com as colunas corretas", 39/39 testes [VERIFIED: 03-03-SUMMARY.md] |
| 03-03 | `data/processed/analise_precos.json` | Existe com chave `total_empenhos_analisados` [VERIFIED: 03-03-SUMMARY.md] |

---

## Decisões de Implementação Documentadas

- **dtype=str para CNPJ em pd.read_csv():** pandas infere int64 e perde zeros à esquerda — padrão obrigatório em todos os testes e código de produção [VERIFIED: 03-02-SUMMARY.md]
- **Tier SUSPEITO via OR:** `alertas_criticos >= 3 OR concentracao > 0.60` — cobre dois cenários distintos de risco
- **Constantes exportadas:** `PESOS_ALERTA`, `MIN_CRITICOS_SUSPEITO`, `THRESHOLD_CONCENTRACAO` — importáveis em testes
- **Guarda mínima BPS:** `QT_REGISTROS < 5` → impossibilitado de receber CRÍTICO (REQ-002)
