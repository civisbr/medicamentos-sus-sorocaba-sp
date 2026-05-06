---
status: partial
phase: 05-bug-fixes-collectors
source: [05-VERIFICATION.md]
started: 2026-05-06T14:30:00Z
updated: 2026-05-06T14:30:00Z
---

## Current Test

[aguardando testes humanos]

## Tests

### 1. Narrativa IA menciona threshold em produção
expected: Executar `python main.py --threshold 20 --step analyze` com ANTHROPIC_API_KEY válida e dados coletados; confirmar que `data/reports/analise_ia.md` contém "20%" no contexto de alerta.
result: [pending]

### 2. Instalação limpa sem erro de numpy
expected: Executar `pip install -r requirements.txt` em virtualenv limpa e confirmar que numpy instala sem erro de dependência ausente.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
