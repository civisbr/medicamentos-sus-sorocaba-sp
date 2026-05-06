---
phase: 01-data-collection
created: 2026-05-06
source: 01-01/02/03-SUMMARY.md + 01-01/02/03-PLAN.md §success_criteria (retroativo — fase executada em 2026-05-03)
status: retroativo
---

# Phase 1: Data Collection — Validation Plan

**Phase:** 1 — Data Collection
**Date:** 2026-05-03 (retroativo — documento criado em 2026-05-06)
**Source:** SUMMARYs de 01-01, 01-02, 01-03 — evidências reais de execução

---

## Framework

| Propriedade | Valor |
|-------------|-------|
| Framework | pytest 8.3.4 |
| Config | nenhuma (descoberta automática de `tests/`) |
| Comando rápido | `python -m pytest tests/test_bps_collector.py tests/test_cnpj_collector.py -x -q` |
| Suite completa | `python -m pytest tests/ -q` |

---

## Matriz de Testes por Requisito

| Req ID | Comportamento | Tipo | Arquivo | Status |
|--------|--------------|------|---------|--------|
| REQ-001 | `PortalSorocabaCollector(fixture=True).coletar_despesas_saude(2023)` retorna 3 registros | integration (fixture) | Smoke via python -c | PASS [VERIFIED: 01-01-SUMMARY.md] |
| REQ-001 | Modo fixture ativado via env var `MEDAUDIT_FIXTURE=1` | integration (env) | Smoke via python -c | PASS [VERIFIED: 01-01-SUMMARY.md] |
| REQ-002 | `BPSCollector._filtrar_bps()` retorna apenas registros com `SG_UF==SP` e `QT_REGISTROS>=5` | unit | `tests/test_bps_collector.py` | PASS [VERIFIED: 7 testes] |
| REQ-002 | BPS collector lida com encoding utf-8 e latin-1 | unit | `tests/test_bps_collector.py` | PASS [VERIFIED: 7 testes] |
| REQ-003 | `CNPJCollector.validar_cnpj()` valida dígito verificador | unit | `tests/test_cnpj_collector.py` | PASS [VERIFIED: 9 testes] |
| REQ-003 | Cache CNPJ TTL 30 dias: `cache_valido()` retorna False após expirar | unit | `tests/test_cnpj_collector.py` | PASS [VERIFIED: 9 testes] |
| REQ-003 | `enriquecer_fornecedores()` grava `fornecedores_enriquecidos.json` com 2 CNPJs | integration (fixture) | Smoke via MEDAUDIT_FIXTURE=1 | PASS [VERIFIED: 01-03-SUMMARY.md] |

---

## Validators

| Name | Type | Check | Command |
|------|------|-------|---------|
| `portal_fixture_3_registros` | integration | Fixture retorna 3 registros com modo `MEDAUDIT_FIXTURE=1` | `MEDAUDIT_FIXTURE=1 python -c "from src.collectors.portal_sorocaba import PortalSorocabaCollector; c = PortalSorocabaCollector(fixture=True); d = c.coletar_despesas_saude(2023); assert len(d) == 3; print('OK')"` |
| `bps_collector_suite` | unit | 7 testes passando em test_bps_collector.py | `python -m pytest tests/test_bps_collector.py -v -q` |
| `cnpj_collector_suite` | unit | 9 testes passando em test_cnpj_collector.py | `python -m pytest tests/test_cnpj_collector.py -v -q` |
| `cnpj_validacao_digito` | unit | `validar_cnpj()` rejeita CNPJ inválido | `python -m pytest tests/test_cnpj_collector.py -k "validar" -v` |
| `cache_ttl_30_dias` | unit | `cache_valido()` funciona com TTL de 30 dias | `python -m pytest tests/test_cnpj_collector.py -k "cache" -v` |
| `bps_filtro_uf_qt` | unit | `_filtrar_bps()` filtra por SG_UF==SP e QT_REGISTROS>=5 | `python -m pytest tests/test_bps_collector.py -k "filtrar" -v` |

---

## Full Validation Commands

```bash
cd /path/to/medicamentos-sus-sorocaba-sp

# 1. BPS Collector — suite completa
python -m pytest tests/test_bps_collector.py -v
# Esperado: 7 passed

# 2. CNPJ Collector — suite completa
python -m pytest tests/test_cnpj_collector.py -v
# Esperado: 9 passed

# 3. Portal Sorocaba — smoke com fixture
MEDAUDIT_FIXTURE=1 python -c "
from src.collectors.portal_sorocaba import PortalSorocabaCollector
c = PortalSorocabaCollector(fixture=True)
d = c.coletar_despesas_saude(2023)
assert len(d) == 3, f'Esperado 3, obtido {len(d)}'
print(f'Portal fixture OK: {len(d)} registros')
"

# 4. CNPJ enriquecimento com fixture
MEDAUDIT_FIXTURE=1 python main.py --step collect --ano 2023
# Verificar: data/processed/fornecedores_enriquecidos.json existe com 2 CNPJs
```

---

## Evidências de Execução

| Plano | Artefato | Evidência |
|-------|----------|-----------|
| 01-01 | `src/collectors/portal_sorocaba.py` | "3 registros — OK" [VERIFIED: 01-01-SUMMARY.md] |
| 01-02 | `src/collectors/bps_collector.py` | BPS com `_descobrir_url_csv()` e `_baixar_csv()` implementados [VERIFIED: 01-02-SUMMARY.md] |
| 01-03 | `src/collectors/cnpj_collector.py` | `validar_cnpj()`, `enriquecer_fornecedores()`, cache JSON — "2 CNPJs únicos → 2 fornecedores enriquecidos" [VERIFIED: 01-03-SUMMARY.md] |

**Nota sobre BPS real:** O portal `dadosabertos.saude.gov.br` usa JavaScript para gerar links de
download CSV — a coleta automática pode falhar em ambiente sem internet ou JS headless. Fallback
Playwright implementado na Phase 5 (STAB-02). O modo fixture funciona sem dependência de rede.
