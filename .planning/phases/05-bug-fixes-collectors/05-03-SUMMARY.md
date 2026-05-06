---
phase: 05-bug-fixes-collectors
plan: 03
subsystem: testing
tags: [python, cnpj, pytest, tdd, merge, json]

# Dependency graph
requires:
  - phase: 05-bug-fixes-collectors
    provides: cnpj_collector.py com avaliar_risco_cnpj() e enriquecer_fornecedores()
provides:
  - empresa_nova: bool como campo explícito no schema de resultado de enriquecer_fornecedores()
  - merge por CNPJ em enriquecer_fornecedores() preservando CNPJs de runs anteriores
  - suite de testes TDD para CNPJCollector (9 testes cobrindo STAB-03 e STAB-05)
affects: [05-bug-fixes-collectors, cnpj_collector, supplier_analyzer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED/GREEN: testes escritos antes da implementação, com mocks de cache para isolamento"
    - "Merge por CNPJ: arquivo JSON de saída acumulativo — new sobrescreve existing por chave cnpj"
    - "Defensive JSON load: try/except em json.loads de arquivo existente (T-05-04)"

key-files:
  created:
    - tests/test_cnpj_collector.py
  modified:
    - src/collectors/cnpj_collector.py

key-decisions:
  - "empresa_nova: bool calculado como 'empresa_nova' in flags — mantém compatibilidade com supplier_analyzer.py que lê flags_risco diretamente"
  - "return resultado (não merged) preserva semântica de retorno da função — callers usam o retorno para contar itens do ano, não o acumulado total"
  - "Mocks de carregar_cache() e salvar_cache() nos testes para isolar do cache de disco real — evita flakiness por dados reais no cache"

patterns-established:
  - "Cache mock pattern: patch.object(cnpj_module, 'carregar_cache', return_value={}) isolates tests from disk cache"
  - "Merge pattern: carregar existentes → dict por chave → sobrescrever com novos → write merged list"

requirements-completed: [STAB-03, STAB-05]

# Metrics
duration: 8min
completed: 2026-05-06
---

# Phase 05 Plan 03: CNPJCollector empresa_nova + merge por CNPJ Summary

**Campo empresa_nova: bool adicionado ao schema de enriquecer_fornecedores() e merge por CNPJ implementado para preservar dados em processamentos multi-ano (--ano all)**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-06T13:43:25Z
- **Completed:** 2026-05-06T13:51:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- STAB-03: `empresa_nova: bool` adicionado como campo de primeiro nível no resultado de `enriquecer_fornecedores()` — booleano explícito calculado como `"empresa_nova" in flags`, compatível com `supplier_analyzer.py`
- STAB-05: lógica de merge por CNPJ implementada antes do write em `output_file` — carrega existentes como dict keyed by cnpj, sobrescreve com novos (dados mais recentes prevalecem), preserva todos os CNPJs anteriores
- Suite TDD com 9 testes verificando todos os edge cases de `empresa_nova` (campo ausente, dados_api None, string vazia, abertura recente, abertura antiga) e 3 testes de merge por CNPJ

## Task Commits

Cada task foi commitada atomicamente:

1. **Task 1: Criar tests/test_cnpj_collector.py com testes de empresa_nova e merge** - `b663b6f` (test)
2. **Task 2: Adicionar empresa_nova: bool no schema e merge por CNPJ em cnpj_collector.py** - `d9a3f7f` (feat)

_Nota: Task 1 usou TDD — testes escritos primeiro (RED), implementação na Task 2 (GREEN)_

## Files Created/Modified

- `tests/test_cnpj_collector.py` - Suite TDD com 9 testes para CNPJCollector (STAB-03 e STAB-05)
- `src/collectors/cnpj_collector.py` - Campo `empresa_nova: bool` no schema de resultado + lógica de merge por CNPJ + função `avaliar_risco_cnpj_standalone()`

## Decisions Made

- `empresa_nova: bool` calculado inline como `"empresa_nova" in flags` — mantém `flags_risco` intocado para compatibilidade com `supplier_analyzer.py` que lê via `"empresa_nova" in flags_risco`
- `return resultado` (não `return merged`) na função — preserva semântica de retorno: callers esperam apenas os CNPJs processados nesta chamada, não o acumulado total
- Cache mock nos testes: `patch.object(cnpj_module, "carregar_cache", return_value={})` e `patch.object(cnpj_module, "salvar_cache")` para isolar dos dados reais em disco

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrigir cache de disco interferindo nos testes**
- **Found during:** Task 2 (execução dos testes para verificar GREEN)
- **Issue:** Cache de disco `cnpj_cache.json` continha dados reais do CNPJ `46634044000174` (Prefeitura de Sorocaba, fundada 1974). O mock de `consultar()` era ignorado porque o cache hit tinha prioridade. Todos os 6 testes de `empresa_nova` falhavam com `empresa_nova=False` mesmo com dados mockados de empresa recente.
- **Fix:** Adicionado `patch.object(cnpj_module, "carregar_cache", return_value={})` e `patch.object(cnpj_module, "salvar_cache")` em todos os helpers de teste para garantir isolamento completo do cache de disco.
- **Files modified:** `tests/test_cnpj_collector.py`
- **Verification:** `python -m pytest tests/test_cnpj_collector.py -v` — 9/9 PASS
- **Committed in:** `d9a3f7f` (Task 2 commit)

**2. [Rule 3 - Blocking] Adicionar avaliar_risco_cnpj_standalone() antes dos testes**
- **Found during:** Task 1 (collection phase)
- **Issue:** `tests/test_cnpj_collector.py` importava `avaliar_risco_cnpj_standalone` que ainda não existia, causando `ImportError` durante a coleta do pytest.
- **Fix:** Adicionada função `avaliar_risco_cnpj_standalone()` ao `cnpj_collector.py` antecipando a Modificação 3 do plano (descrita como "opcional mas recomendada"). Incluída no commit da Task 1.
- **Files modified:** `src/collectors/cnpj_collector.py`
- **Verification:** `python -m pytest tests/test_cnpj_collector.py --co -q` coleta 9 testes sem erro
- **Committed in:** `b663b6f` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Ambas as correções necessárias para funcionamento correto dos testes. Nenhum scope creep.

## Issues Encountered

- Cache de disco com dados reais do CNPJ `46634044000174` causou falha silenciosa nos testes (mock ignorado por cache hit) — resolvido com mocks de `carregar_cache()` e `salvar_cache()` em todos os helpers de teste.

## User Setup Required

Nenhum — nenhuma configuração externa necessária.

## TDD Gate Compliance

- Gate RED: commit `b663b6f` com prefix `test(05-03)` — testes criados antes da implementação
- Gate GREEN: commit `d9a3f7f` com prefix `feat(05-03)` — implementação que fez os testes passar
- Resultado: 9/9 testes PASS, 79/79 suite completa PASS

## Self-Check: PASSED

- tests/test_cnpj_collector.py: FOUND
- src/collectors/cnpj_collector.py: FOUND
- 05-03-SUMMARY.md: FOUND
- Commits b663b6f e d9a3f7f: FOUND

## Next Phase Readiness

- `empresa_nova: bool` disponível para leitura direta no JSON de fornecedores enriquecidos
- `--ano all` agora preserva dados de todos os anos processados sem sobrescrever
- Suite completa em 79/79 — sem regressões

---
*Phase: 05-bug-fixes-collectors*
*Completed: 2026-05-06*
