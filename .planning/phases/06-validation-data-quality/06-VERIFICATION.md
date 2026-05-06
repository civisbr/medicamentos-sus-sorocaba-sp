---
phase: 06-validation-data-quality
verified: 2026-05-06T00:00:00Z
status: human_needed
score: 3/3 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Executar o pipeline completo com dados coletados e observar linha de resumo no terminal"
    expected: "Linha 'Items: N | BPS match: X% | No match: Y%' impressa no terminal ao final do passo --step analyze"
    why_human: "rich.Console não é capturado pelo capsys do pytest — comportamento de print só verificável com execução real do pipeline"
  - test: "Executar o pipeline com dataset em que maioria dos itens não tem match BPS (cobertura < 50%)"
    expected: "Terminal exibe '[WARNING] Cobertura BPS X.X% abaixo de 50% — análise de preços pouco representativa para este conjunto de dados.'"
    why_human: "Mesmo motivo — rich.Console. O condicional `cobertura < 50` está no código mas o efeito visual só é observável em execução real"
---

# Phase 6: Validation & Data Quality — Verification Report

**Phase Goal:** Fechar lacunas de documentação de validação e adicionar observabilidade de qualidade de dados no pipeline.
**Verified:** 2026-05-06
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                    | Status     | Evidence                                                                                                                                       |
|----|----------------------------------------------------------------------------------------------------------|------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | VALIDATION.md de Phase 0 existe com critérios verificáveis por grep (STAB-06)                          | VERIFIED   | `.planning/phases/00-stabilization/00-VALIDATION.md` existe; contém `phase: 00-stabilization`, 8 validators com BUG-001..BUG-005, evidência indireta via 90 testes Phase 5 |
| 2  | VALIDATION.md de Phase 1 existe com referência a test_bps_collector.py e test_cnpj_collector.py (STAB-06) | VERIFIED | `.planning/phases/01-data-collection/01-VALIDATION.md` existe; `grep -c test_bps_collector` = 6, `grep -c test_cnpj_collector` = 7, REQ-001/002/003 todos referenciados |
| 3  | VALIDATION.md de Phase 3 existe com referência a test_price_analyzer.py e test_supplier_analyzer.py (STAB-06) | VERIFIED | `.planning/phases/03-analysis/03-VALIDATION.md` existe; `grep -c test_price_analyzer` = 9, `grep -c test_supplier_analyzer` = 8, TDD Gate Evidence presente com commits RED/GREEN |
| 4  | Cada VALIDATION.md cita evidência real dos SUMMARYs correspondentes (STAB-06)                          | VERIFIED   | 00-VALIDATION: confirmação indireta via 90 testes Phase 5; 01-VALIDATION: 7 ocorrências de "VERIFIED: 01-0X-SUMMARY.md"; 03-VALIDATION: 9 ocorrências de "VERIFIED: 03-0X-SUMMARY.md" |
| 5  | summary.json contém `total_itens` na raiz do JSON com valor inteiro (STAB-07)                          | VERIFIED   | `src/utils/exporter.py` linha 248: `"total_itens": total_itens` na raiz do dict; 4 ocorrências grep; teste `test_total_itens` PASS                 |
| 6  | summary.json contém `cobertura_bps_pct` na raiz do JSON com valor float arredondado a 1 casa (STAB-07) | VERIFIED   | `src/utils/exporter.py` linha 249; cálculo `round((com_bps / total_itens) * 100, 1)`; teste `test_cobertura_bps_pct` PASS (50.0 confirmado)       |
| 7  | summary.json contém `alertas_por_tier` como dict com contagens por valor de nivel_alerta (STAB-07)    | VERIFIED   | `src/utils/exporter.py` linha 250; usa `value_counts().items()`; teste `test_alertas_por_tier` PASS                                               |
| 8  | Pipeline imprime linha `Items: N \| BPS match: X% \| No match: Y%` ao final do resumo (STAB-07)       | VERIFIED (código) / HUMAN NEEDED (comportamento terminal) | `main.py` linha 199: `console.print(f"   Items: {n} \| BPS match: {cobertura:.1f}% \| No match: {no_match:.1f}%")`; rich.Console não testável via pytest |
| 9  | Pipeline emite [WARNING] quando cobertura_bps_pct < 50 (STAB-07)                                      | VERIFIED (código) / HUMAN NEEDED (comportamento terminal) | `main.py` linhas 200-205: condicional `if isinstance(cobertura, (int, float)) and cobertura < 50`; [bold yellow][WARNING][/bold yellow] presente; rich.Console não testável via pytest |
| 10 | Todos os testes existentes de TestGerarSummary continuam passando — zero regressões (STAB-07)          | VERIFIED   | `python -m pytest tests/test_exporter.py::TestGerarSummary -v` → 10 passed, 0 failed; `python -m pytest tests/ -q` → 94 passed, 0 failed          |

**Score:** 3/3 must-haves (ROADMAP success criteria) verified — código para SC-2 (terminal output) verificado estruturalmente; comportamento visual requer execução humana.

---

### Required Artifacts

| Artifact                                                      | Expected                                                         | Status     | Details                                                                          |
|---------------------------------------------------------------|------------------------------------------------------------------|------------|----------------------------------------------------------------------------------|
| `.planning/phases/00-stabilization/00-VALIDATION.md`         | Critérios Phase 0 com comandos verificáveis (python main.py --help) | VERIFIED | Existe; 3 ocorrências de "python main.py --help"; frontmatter correto              |
| `.planning/phases/01-data-collection/01-VALIDATION.md`       | Validators referenciando test_bps_collector.py e test_cnpj_collector.py | VERIFIED | Existe; 6 + 7 ocorrências respectivas; REQ-001/002/003 referenciados            |
| `.planning/phases/03-analysis/03-VALIDATION.md`              | Validators TDD com test_price_analyzer.py e test_supplier_analyzer.py | VERIFIED | Existe; TDD Gate Evidence com commits `888f41d`, `f3094de`, `80052ae`, `c66ec4d`, `e22c8c6` |
| `src/utils/exporter.py`                                       | gerar_summary() com 3 novos campos na raiz do dict               | VERIFIED   | Linhas 219-250; cálculo real com pandas value_counts e aritmética vetorizada     |
| `main.py`                                                     | Bloco de resumo expandido com linha BPS match e WARNING condicional | VERIFIED | Linhas 192-205; lê `cobertura_bps_pct` do summary.json, calcula `no_match`, imprime e condiciona WARNING |
| `tests/test_exporter.py`                                      | 4 novos testes em TestGerarSummary                               | VERIFIED   | `test_total_itens`, `test_cobertura_bps_pct`, `test_alertas_por_tier`, `test_cobertura_bps_df_vazio` presentes e passando |

---

### Key Link Verification

| From                                       | To                                    | Via                                                    | Status   | Details                                                                           |
|--------------------------------------------|---------------------------------------|--------------------------------------------------------|----------|-----------------------------------------------------------------------------------|
| `src/utils/exporter.py:gerar_summary()`    | `docs/summary.json`                   | `json.dumps()` linha 257                               | WIRED    | Campos `total_itens`, `cobertura_bps_pct`, `alertas_por_tier` na raiz do dict antes do dump |
| `main.py` bloco de resumo                  | `docs/summary.json`                   | `json.load()` lendo `summary_file` linha 190           | WIRED    | `s.get("cobertura_bps_pct", 0.0)` e `s.get("total_itens", ...)` lidos do JSON    |
| `tests/test_exporter.py:TestGerarSummary`  | `src/utils/exporter.py:gerar_summary()` | Instância de `Exporter` com fixture CSV de alertas   | WIRED    | 10 testes passando (6 existentes + 4 novos), inclusive fixture com nivel_alerta  |

---

### Data-Flow Trace (Level 4)

| Artifact             | Data Variable       | Source                                          | Produces Real Data                                      | Status   |
|----------------------|---------------------|-------------------------------------------------|---------------------------------------------------------|----------|
| `exporter.py`        | `alertas_por_tier`  | `alertas_df["nivel_alerta"].value_counts()`     | Sim — pandas value_counts sobre coluna do CSV de alertas | FLOWING  |
| `exporter.py`        | `cobertura_bps_pct` | `(alertas_df["nivel_alerta"] == "SEM_REFERÊNCIA").sum()` | Sim — soma vetorizada sobre DataFrame real  | FLOWING  |
| `exporter.py`        | `total_itens`       | `total_empenhos` = `len(alertas_df)`            | Sim — contagem de linhas do DataFrame                    | FLOWING  |
| `main.py` bloco BPS  | `cobertura`         | `s.get("cobertura_bps_pct", 0.0)` do JSON lido | Sim — depende de `gerar_summary()` ter sido executado   | FLOWING (condicional: só exibido quando `summary_file.exists()`) |

---

### Behavioral Spot-Checks

| Behavior                                            | Command                                                                                       | Result             | Status  |
|-----------------------------------------------------|-----------------------------------------------------------------------------------------------|---------------------|---------|
| TestGerarSummary 10 testes passando                 | `python -m pytest tests/test_exporter.py::TestGerarSummary -v -q`                           | 10 passed, 0 failed | PASS    |
| Suite completa sem regressão                        | `python -m pytest tests/ -q`                                                                 | 94 passed, 0 failed | PASS    |
| Sintaxe de main.py válida                           | `python -c "import ast; ast.parse(open('main.py').read()); print('syntax OK')"`             | syntax OK           | PASS    |
| BPS match linha presente em main.py                 | `grep -c "BPS match" main.py`                                                                | 1                   | PASS    |
| WARNING condicional presente em main.py              | `grep -c "bold yellow.*WARNING" main.py`                                                     | 1                   | PASS    |
| total_itens em raiz do summary dict                 | `grep -c "total_itens" src/utils/exporter.py`                                                | 4 (>= 2)            | PASS    |
| Terminal output real com rich.Console               | Requer execução do pipeline com dados reais                                                  | N/A                 | SKIP (human) |

---

### Requirements Coverage

| Requirement | Source Plan  | Description                                                                        | Status    | Evidence                                                                          |
|-------------|--------------|------------------------------------------------------------------------------------|-----------|-----------------------------------------------------------------------------------|
| STAB-06     | 06-01-PLAN.md | Criar VALIDATION.md retroativo para Phases 0, 1 e 3 com critérios e evidências   | SATISFIED | 3 arquivos criados e verificados: `00-VALIDATION.md`, `01-VALIDATION.md`, `03-VALIDATION.md`; commits `25e35ab`, `3debdc6`, `5d92fc3` |
| STAB-07     | 06-02-PLAN.md | Pipeline imprime resumo de cobertura BPS; emite WARNING; campos no summary.json   | SATISFIED (código) | `exporter.py` e `main.py` modificados; 4 novos testes passando; 94/94 testes sem regressão; terminal output requer verificação humana |

---

### Anti-Patterns Found

| File      | Line | Pattern                                                          | Severity | Impact                                                                                       |
|-----------|------|------------------------------------------------------------------|----------|----------------------------------------------------------------------------------------------|
| `main.py` | 115  | `TODO (Claude Code): agrupar alertas por CNPJ, calcular score` | Info     | Pré-existente, não relacionado à Phase 6; `supplier_analyzer.analisar()` já está chamado na linha 117 |

Nenhum anti-pattern bloqueante detectado nos arquivos modificados nesta fase.

---

### Nota sobre ROADMAP Success Criterion #1 (Paths)

O ROADMAP SC-1 refere "`.planning/phases/phase-0/VALIDATION.md`" como caminho esperado. Os arquivos foram criados em `.planning/phases/00-stabilization/00-VALIDATION.md`, `.planning/phases/01-data-collection/01-VALIDATION.md` e `.planning/phases/03-analysis/03-VALIDATION.md` — nomes que correspondem exatamente aos diretórios das fases já existentes no projeto. O ROADMAP usa uma notação abreviada (`phase-0`) que difere do nome real do diretório. O 06-01-PLAN.md especifica os caminhos corretos e estes foram respeitados. Classificado como inconsistência de nomenclatura na documentação do ROADMAP, não como falha de implementação.

---

### Human Verification Required

#### 1. Linha "Items: N | BPS match: X% | No match: Y%" no terminal

**Test:** Executar `python main.py --step analyze --ano 2023` com dados coletados no diretório `data/reports/alertas_superfaturamento.csv` presente.

**Expected:** O bloco "Resumo:" no terminal deve incluir a linha:
```
Items: N | BPS match: X.X% | No match: Y.Y%
```
onde N, X e Y são valores numéricos reais derivados do CSV de alertas.

**Why human:** `rich.Console` não é capturado pelo `capsys` do pytest. Identificado no 06-VALIDATION.md (Manual-Only Verifications) e confirmado pelo PLAN (Pitfall crítico documentado).

---

#### 2. [WARNING] condicional quando cobertura BPS < 50%

**Test:** Criar ou usar um dataset onde a maioria dos itens em `alertas_superfaturamento.csv` tem `nivel_alerta == "SEM_REFERÊNCIA"` (cobertura < 50%). Executar `python main.py --step analyze`.

**Expected:** Após a linha de resumo BPS, deve aparecer:
```
[WARNING] Cobertura BPS X.X% abaixo de 50% — análise de preços pouco representativa para este conjunto de dados.
```
Em `[bold yellow]` no terminal.

**Why human:** Mesmo motivo — `rich.Console` não testável via pytest/capsys. O condicional `cobertura < 50` está implementado e verificado na leitura do código (linha 200 de `main.py`), mas o efeito visual no terminal só pode ser confirmado por execução direta.

---

### Gaps Summary

Nenhum gap bloqueante identificado. Todos os artefatos existem, são substantivos e estão conectados. Os campos `total_itens`, `cobertura_bps_pct` e `alertas_por_tier` são calculados com dados reais e persistidos no `summary.json`. A linha de resumo BPS e o WARNING estão presentes no código com lógica correta — apenas o comportamento visual no terminal requer confirmação humana.

---

_Verified: 2026-05-06_
_Verifier: Claude (gsd-verifier)_
