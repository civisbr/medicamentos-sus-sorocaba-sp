---
phase: 05-bug-fixes-collectors
plan: "01"
subsystem: ai-analyzer
tags: [bug-fix, threshold, requirements, tdd]
dependency_graph:
  requires: []
  provides: [threshold-propagation-to-ai, numpy-pinned, playwright-pinned]
  affects: [main.py, requirements.txt, tests/test_ai_analyzer.py]
tech_stack:
  added: []
  patterns: [threshold-parameter-propagation, tdd-green]
key_files:
  created: []
  modified:
    - tests/test_ai_analyzer.py
    - main.py
    - requirements.txt
decisions:
  - "Adicionado numpy>=1.26.0 e playwright>=1.50.0 explicitamente ao requirements.txt para evitar falha em ambiente limpo"
  - "TestThresholdPropagado implementado diretamente em GREEN (ai_analyzer.py ja tinha threshold no template do prompt)"
metrics:
  duration: "~5 minutos"
  completed_date: "2026-05-06T13:44:40Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 05 Plan 01: Bug Fixes — Threshold Propagation e Dependencias Summary

**Uma linha:** Propagacao do parametro --threshold do CLI ate AIAnalyzer.analisar() corrigida (STAB-01), e numpy/playwright adicionados explicitamente ao requirements.txt (STAB-04).

## O que foi feito

### Task 1 — Teste TestThresholdPropagado (TDD)

Adicionada a classe `TestThresholdPropagado` ao final de `tests/test_ai_analyzer.py` com dois metodos:
- `test_threshold_20_aparece_no_prompt`: verifica que o valor 20 chega ao prompt como "20%"
- `test_threshold_50_aparece_no_prompt`: verifica que o valor 50 chega ao prompt como "50%"

Os testes passaram diretamente no GREEN porque `ai_analyzer.py` ja tinha o parametro `threshold` na assinatura de `analisar()` e `USER_PROMPT_TEMPLATE` ja usava `{threshold}%` na linha 43. O bug estava na chamada em `main.py`, nao na implementacao interna.

### Task 2 — Correcoes em main.py e requirements.txt

**STAB-01 (main.py):** A chamada `ai.analisar()` nas linhas 128-133 foi corrigida para incluir:
```python
threshold=threshold,
periodo=str(anos[0]),
municipio=municipio,
```

**STAB-04 (requirements.txt):** Adicionadas ao final do arquivo:
```
numpy>=1.26.0
playwright>=1.50.0
```

## Verificacao final

```
grep "threshold=threshold" main.py      → linha 131
grep "periodo=str(anos[0])" main.py     → linha 132
grep "numpy>=1.26.0" requirements.txt   → presente
grep "playwright>=1.50.0" requirements.txt → presente
python -m pytest tests/test_ai_analyzer.py -x -v → 13 passed
```

## Commits

| Hash    | Tipo | Descricao |
|---------|------|-----------|
| 1d0a5e1 | test | Adicionar TestThresholdPropagado em test_ai_analyzer.py |
| 4444dd1 | fix  | Propagar threshold/periodo/municipio em main.py + numpy e playwright em requirements.txt |

## Deviations from Plan

None - plano executado exatamente como escrito.

Nota: A Task 1 e TDD mas os testes passaram diretamente no GREEN (sem passar por RED) porque a implementacao em `ai_analyzer.py` ja estava correta — o bug era somente na chamada de `main.py` que nao passava o parametro. Conforme instrucoes do plano, isto e esperado: o plano descreve adicionar o teste (GREEN) e depois corrigir o bug na chamada (Task 2).

## Stubs

Nenhum stub encontrado nos arquivos modificados.

## Threat Flags

Nenhuma nova superficie de seguranca introduzida. O parametro `threshold` e validado como inteiro pelo click com default=30, sem exposicao de rede.

## Self-Check: PASSED

- [x] tests/test_ai_analyzer.py modificado e commitado (1d0a5e1)
- [x] main.py modificado e commitado (4444dd1)
- [x] requirements.txt modificado e commitado (4444dd1)
- [x] `grep "threshold=threshold" main.py` retorna linha 131
- [x] `grep "numpy>=1.26.0" requirements.txt` retorna 1 linha
- [x] `grep "playwright>=1.50.0" requirements.txt` retorna 1 linha
- [x] `grep -c "class TestThresholdPropagado" tests/test_ai_analyzer.py` retorna 1
- [x] 13 testes passando, sem regressoes
