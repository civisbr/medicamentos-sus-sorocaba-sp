---
status: partial
phase: 06-validation-data-quality
source: [06-VERIFICATION.md]
started: 2026-05-06T00:00:00Z
updated: 2026-05-06T00:00:00Z
---

## Current Test

[aguardando teste humano]

## Tests

### 1. Linha BPS match no terminal
expected: Ao executar `python main.py --step analyze` (ou `--step all`) com dados reais, o bloco "Resumo:" no terminal deve exibir a linha `Items: N | BPS match: X.X% | No match: Y.Y%`

result: [pending]

### 2. [WARNING] condicional quando cobertura BPS < 50%
expected: Ao executar o pipeline com um dataset onde a cobertura BPS é inferior a 50%, o terminal deve exibir a mensagem em amarelo: `[WARNING] Cobertura BPS X.X% abaixo de 50% — análise de preços pouco representativa para este conjunto de dados.`

result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
