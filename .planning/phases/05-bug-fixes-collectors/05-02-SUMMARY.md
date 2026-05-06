---
phase: 05-bug-fixes-collectors
plan: 02
subsystem: collectors
tags: [bps, playwright, headless, fallback, tdd]
dependency_graph:
  requires: []
  provides: [BPS headless fallback, _descobrir_url_csv_headless]
  affects: [src/collectors/bps_collector.py]
tech_stack:
  added: [playwright (optional dependency, try/except guard)]
  patterns: [TDD RED/GREEN, playwright headless browser, module-level import guard]
key_files:
  created:
    - tests/test_bps_collector.py
  modified:
    - src/collectors/bps_collector.py
decisions:
  - Import playwright com try/except no nivel de modulo para permitir mock via patch() nos testes
  - browser.close() em bloco finally para garantir fechamento mesmo em excecoes
  - Fallback ativado apenas quando requests nao encontra nenhum link CSV (caminho rapido preservado)
  - domcontentloaded como estado de espera (mais confiavel que networkidle em portais com tracking)
metrics:
  duration: "~5 min"
  completed: "2026-05-06"
  tasks_completed: 2
  files_modified: 2
---

# Phase 05 Plan 02: BPS Headless Fallback (STAB-02) Summary

**One-liner:** Fallback Playwright headless em BPSCollector com try/except guard no import, browser.close() em finally e preferencia por link do ano solicitado.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Criar tests/test_bps_collector.py com testes do fallback headless | b15a5bb | tests/test_bps_collector.py |
| 2 (GREEN) | Implementar _descobrir_url_csv_headless() e fallback em bps_collector.py | da0f20a | src/collectors/bps_collector.py |

## What Was Built

- **`_descobrir_url_csv_headless(ano: int) -> str`**: nova funcao modulo-level que usa Playwright
  para navegar em `dadosabertos.saude.gov.br/dataset/bps`, aguarda carregamento do DOM e extrai
  todos os hrefs de links `.csv` via `eval_on_selector_all`. Prefere links com o ano solicitado;
  fallback para o ultimo link disponivel.

- **Fallback em `_descobrir_url_csv()`**: o bloco `else: raise ValueError(...)` foi substituido
  por uma chamada a `_descobrir_url_csv_headless(ano)`. O caminho rapido (requests + regex) e
  preservado e headless so e ativado quando `csv_links` esta vazio.

- **Import guard**: playwright importado com `try/except ImportError` no nivel de modulo,
  expondo `sync_playwright` como nome de modulo — necessario para que testes possam usar
  `patch("src.collectors.bps_collector.sync_playwright")`.

- **Seguranca (T-05-03)**: `browser.close()` garantido via `finally` block. Timeout de 60s
  em `page.goto()` e 30s em `wait_for_load_state`. Fallback so ativado apos falha do requests.

## TDD Gate Compliance

- RED gate: commit `b15a5bb` — `test(05-02): add failing tests for BPS headless fallback`
- GREEN gate: commit `da0f20a` — `feat(05-02): implement _descobrir_url_csv_headless() fallback`
- Sequencia RED → GREEN respeitada.

## Verification Evidence

```
$ grep "_descobrir_url_csv_headless" src/collectors/bps_collector.py
76:        return _descobrir_url_csv_headless(ano)
84:def _descobrir_url_csv_headless(ano: int) -> str:

$ grep "sync_playwright" src/collectors/bps_collector.py
19:    from playwright.sync_api import sync_playwright
23:    sync_playwright = None  # type: ignore[assignment]
107:    with sync_playwright() as p:

$ grep "finally:" src/collectors/bps_collector.py
124:        finally:

$ python -m pytest tests/test_bps_collector.py -v
7 passed in 0.45s

$ python -m pytest tests/ -x -q
79 passed in 2.16s
```

## Deviations from Plan

None - plano executado exatamente como escrito.

## Known Stubs

None.

## Threat Flags

None — superficie de rede apenas para portal publico do MS (dadosabertos.saude.gov.br),
sem autenticacao e sem dados sensiveis transmitidos. T-05-03 (DoS via playwright loop)
mitigado por: finally block, timeouts, e ativacao apenas como fallback de ultimo recurso.

## Self-Check: PASSED

- tests/test_bps_collector.py: FOUND
- src/collectors/bps_collector.py (modified): FOUND
- commit b15a5bb (RED): FOUND
- commit da0f20a (GREEN): FOUND
