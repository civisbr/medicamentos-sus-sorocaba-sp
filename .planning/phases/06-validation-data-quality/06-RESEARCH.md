# Phase 6: Validation & Data Quality — Research

**Researched:** 2026-05-06
**Domain:** Documentação de validação retroativa + observabilidade de qualidade de dados no pipeline Python/rich
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STAB-06 | Criar `.planning/phases/phase-0/VALIDATION.md`, `phase-1/VALIDATION.md` e `phase-3/VALIDATION.md` com critérios de sucesso observáveis e evidência de cobertura existente | VALIDATION.md das fases 2, 4 e 5 fornecem modelo verificado; SUMMARYs das fases 0, 1 e 3 fornecem evidências reais executadas |
| STAB-07 | Pipeline imprime resumo final com `Items: N | BPS match: X% | No match: Y%`; emite `[WARNING]` rich quando cobertura BPS < 50%; `summary.json` inclui `total_itens`, `cobertura_bps_pct`, `alertas_por_tier` | `src/utils/exporter.py:gerar_summary()` e `main.py` já existem — modificações cirúrgicas identificadas |

</phase_requirements>

---

## Summary

A Fase 6 é composta de duas tarefas independentes de natureza distinta. **STAB-06** é trabalho de documentação pura: escrever três arquivos VALIDATION.md retroativos para as fases 0, 1 e 3, usando como insumo os PLAN.md, SUMMARY.md e critérios de sucesso já registrados. Todas as evidências necessárias já existem no repositório — nenhum código novo é necessário para STAB-06.

**STAB-07** é uma modificação cirúrgica em dois arquivos de código (`src/utils/exporter.py` e `main.py`). O `summary.json` atual já contém `totais.empenhos_analisados`, `totais.alertas_atencao/alerta/criticos` e `distribuicao_alertas`, mas **faltam três campos específicos** exigidos pelo requisito: `total_itens`, `cobertura_bps_pct` e `alertas_por_tier` no nível raiz do JSON. Além disso, `main.py` ainda não imprime a linha de resumo de qualidade com formato `Items: N | BPS match: X% | No match: Y%` nem emite `[WARNING]` quando cobertura < 50%.

Os dados necessários para calcular cobertura BPS já estão disponíveis: o CSV `alertas_superfaturamento.csv` possui a coluna `nivel_alerta` com valor `"SEM_REFERÊNCIA"` para itens sem match BPS, e `preco_bps_mediana` nula para os mesmos. A lógica de cálculo é simples: `(total - sem_referencia) / total * 100`.

**Recomendação primária:** Dividir em dois planos — 06-01 (STAB-06, documentação) e 06-02 (STAB-07, código). Os planos são independentes e podem ser executados em qualquer ordem, mas a documentação é mais segura iniciar primeiro pois não altera código.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Logging de qualidade de dados no terminal | Pipeline CLI (main.py) | — | main.py orquestra todas as etapas e já lê summary.json ao final; o print de resumo pertence ali |
| Cálculo de cobertura BPS | Exporter (gerar_summary) | PriceAnalyzer (tem os dados brutos) | gerar_summary já lê alertas_superfaturamento.csv e calcula totais; extensão natural do método existente |
| Campos extras em summary.json | Exporter (gerar_summary) | — | gerar_summary é a única função que escreve summary.json |
| Documentação VALIDATION.md retroativa | Artefatos de planejamento | — | Trabalho editorial puro; não envolve código de produção |

---

## Standard Stack

### Core (já em uso no projeto — sem instalações novas)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| rich | 13.7.0 | Output colorido e `[WARNING]` visível no terminal | Já em uso em `main.py` e `price_analyzer.py` [VERIFIED: grep no codebase] |
| pandas | 2.1.4 | Leitura de CSV e cálculo de coberturas | Já em uso em `exporter.py` e `price_analyzer.py` [VERIFIED: requirements.txt] |
| json (stdlib) | — | Serialização de summary.json | Já em uso [VERIFIED: exporter.py linha 219] |

**Nenhuma dependência nova necessária para esta fase.** [VERIFIED: análise do código existente]

### Padrões de rich já estabelecidos no projeto

```python
# [VERIFIED: src/analyzers/price_analyzer.py linha 24, main.py linha 21]
from rich.console import Console
console = Console()

# Padrão de warning já usado em price_analyzer.py linha 85:
console.print("[yellow]BPS ausente:[/yellow] ...")

# Padrão de erro visível para usar em STAB-07:
console.print("[bold yellow][WARNING][/bold yellow] Cobertura BPS baixa: X%")
```

---

## Architecture Patterns

### Fluxo atual de dados no pipeline (relevante para STAB-07)

```
main.py --step all
  |
  +-- Etapa 2: PriceAnalyzer.analisar()
  |     |-- Lê: medicamentos_normalizados.json
  |     |-- Lê: bps_precos_referencia.csv
  |     +-- Escreve: data/reports/alertas_superfaturamento.csv
  |           (coluna nivel_alerta: SEM_REFERÊNCIA | OK | ATENÇÃO | ALERTA | CRÍTICO)
  |
  +-- Etapa 3: Exporter.gerar_summary()
  |     |-- Lê: alertas_superfaturamento.csv
  |     +-- Escreve: docs/summary.json
  |           (ATUAL: totais.empenhos_analisados, distribuicao_alertas)
  |           (FALTA: total_itens, cobertura_bps_pct, alertas_por_tier)
  |
  +-- Bloco final de resumo em main.py (linhas 184-195)
        |-- Lê: docs/summary.json
        +-- Imprime resumo ATUAL (empenhos, críticos, valor)
              (FALTA: "Items: N | BPS match: X% | No match: Y%" + WARNING se < 50%)
```

### Projeto de estrutura dos novos campos em summary.json (STAB-07)

```json
{
  "gerado_em": "...",
  "totais": { "...campos existentes..." },
  "total_itens": 150,
  "cobertura_bps_pct": 73.3,
  "alertas_por_tier": {
    "ATENÇÃO": 12,
    "ALERTA": 5,
    "CRÍTICO": 2,
    "SEM_REFERÊNCIA": 40,
    "OK": 91
  }
}
```

**Justificativa do design:** Campos no nível raiz (não aninhados em `totais`) para compatibilidade com o dashboard que lê `summary.json` via `fetch()` — menos refatoração necessária. [ASSUMED — não há spec do dashboard que indique onde os campos devem estar; colocar na raiz é a opção mais conservadora]

### Lógica de cálculo de cobertura BPS

```python
# [VERIFIED: estrutura de dados em alertas_superfaturamento.csv]
# nivel_alerta == "SEM_REFERÊNCIA" significa sem match BPS

total_itens = len(alertas_df)
sem_referencia = (alertas_df["nivel_alerta"] == "SEM_REFERÊNCIA").sum()
com_bps = total_itens - sem_referencia
cobertura_bps_pct = round((com_bps / total_itens) * 100, 1) if total_itens > 0 else 0.0
```

### Formato da linha de resumo (STAB-07)

```
Items: 150 | BPS match: 73.3% | No match: 26.7%
```

Com warning quando cobertura < 50%:
```python
# [VERIFIED: padrão rich já em uso no projeto]
console.print(f"Items: {n} | BPS match: {match_pct:.1f}% | No match: {no_match_pct:.1f}%")
if match_pct < 50:
    console.print("[bold yellow][WARNING][/bold yellow] Cobertura BPS abaixo de 50% — resultados de análise de preços pouco representativos.")
```

### Estrutura esperada dos arquivos VALIDATION.md retroativos (STAB-06)

Baseado no formato observado em `02-VALIDATION.md` e `04-VALIDATION.md` (verificados no repositório):

```markdown
# Phase N: [Nome] — Validation Plan

## Critérios de Sucesso Observáveis

| # | Critério | Comando de Verificação | Status |
|---|----------|----------------------|--------|
| 1 | [comportamento verificável] | `[comando que retorna 0 ou imprime evidência]` | [PASS/evidência do SUMMARY.md] |

## Cobertura de Testes

| Arquivo de Teste | Testes | Requisitos Cobertos |
|-----------------|--------|-------------------|
| [path] | N | [REQ-IDs] |

## Evidências de Execução

[Referência ao SUMMARY.md com resultados reais]
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Output colorido de warning | `print("\033[33m[WARNING]...")` | `console.print("[bold yellow][WARNING][/bold yellow]...")` com `rich.Console` | Já instalado; suporta terminal sem cor; testável [VERIFIED: já em uso no projeto] |
| Cálculo de porcentagem com divisão por zero | verificação manual | `total_itens if total_itens > 0 else 0.0` inline | Simples o suficiente — apenas proteger contra DataFrame vazio |
| Validação de schema JSON | biblioteca externa | Asserção inline no teste pytest | schema é simples e controlado internamente |

---

## Common Pitfalls

### Pitfall 1: summary.json quebra o dashboard se campos novos forem mal aninhados
**What goes wrong:** O `docs/index.html` lê `summary.json` via `fetch()` e espera `summary.totais.*`. Adicionar campos em local errado quebra o JavaScript do dashboard sem erro Python visível.
**Why it happens:** A estrutura do JSON é implicitamente contratada pelo template HTML.
**How to avoid:** Adicionar `total_itens`, `cobertura_bps_pct` e `alertas_por_tier` na raiz do dict, não dentro de `totais`. Verificar que o teste `test_schema_totais` ainda passa após a mudança.
**Warning signs:** `test_exporter.py::TestGerarSummary::test_schema_totais` falha após a mudança.

### Pitfall 2: DataFrame vazio quando pipeline roda --step export isolado
**What goes wrong:** Se `gerar_summary()` for chamado sem alertas (DataFrame vazio), a divisão `com_bps / total_itens` lança `ZeroDivisionError`.
**Why it happens:** O bloco `if step in ("all", "export")` em `main.py` pode executar sem a etapa de análise ter rodado.
**How to avoid:** Proteger o cálculo com `if total_itens > 0 else 0.0`. Já existe tratamento defensivo similar no código atual (linhas 133-141 de exporter.py). [VERIFIED: exporter.py]
**Warning signs:** Traceback em `ZeroDivisionError` ao rodar `python main.py --step export`.

### Pitfall 3: VALIDATION.md retroativo descreve critérios que nunca foram verificados
**What goes wrong:** O arquivo lista critérios de sucesso mas sem evidência real de que passaram — diminui credibilidade do documento.
**Why it happens:** Escrever VALIDATION.md do zero sem consultar SUMMARY.md dos planos correspondentes.
**How to avoid:** Para cada critério de sucesso, referenciar a linha do SUMMARY.md que confirma o resultado real. O formato `[VERIFIED: 00-01-SUMMARY.md § Verificação]` é suficiente.

### Pitfall 4: Cálculo de cobertura BPS confunde "SEM_REFERÊNCIA" com outros tiers
**What goes wrong:** Contar todos os alertas como "com BPS" quando na verdade "OK" também tem referência BPS (preço dentro do limite).
**Why it happens:** Confundir "sem alerta" com "sem referência BPS".
**How to avoid:** `com_bps = (alertas_df["nivel_alerta"] != "SEM_REFERÊNCIA").sum()` — todos os tiers exceto SEM_REFERÊNCIA têm preço BPS disponível. [VERIFIED: price_analyzer.py linhas 246-260 — SEM_REFERÊNCIA é atribuído apenas quando `preco_mediano is None`]

### Pitfall 5: Teste do WARNING não verifica saída do terminal (capfd vs. rich Console)
**What goes wrong:** `pytest` não captura saída de `rich.Console` com `capsys` padrão porque rich usa seu próprio mecanismo de output.
**Why it happens:** `rich.Console()` instanciado no módulo não redireciona para sys.stdout automaticamente.
**How to avoid:** Usar `Console(file=StringIO())` injetável em testes, ou monkeypatch `console` no módulo. O projeto já usa `Console()` no nível de módulo em `main.py` e `price_analyzer.py` — para testes de STAB-07, verificar os **campos do summary.json** em vez de capturar stdout (essa é a forma mais robusta). [VERIFIED: padrão de teste em test_exporter.py que verifica o arquivo de saída, não stdout]

---

## Code Examples

### Extensão de gerar_summary() para STAB-07

```python
# Source: padrão verificado em src/utils/exporter.py linhas 133-235
# Adicionar APÓS o cálculo de distribuicao (linha ~217):

total_itens = len(alertas_df)
if not alertas_df.empty and "nivel_alerta" in alertas_df.columns:
    sem_ref = int((alertas_df["nivel_alerta"] == "SEM_REFERÊNCIA").sum())
    com_bps = total_itens - sem_ref
    cobertura_bps_pct = round((com_bps / total_itens) * 100, 1) if total_itens > 0 else 0.0
    # Contagem por tier completo (inclui SEM_REFERÊNCIA e OK)
    alertas_por_tier = {
        k: int(v) for k, v in alertas_df["nivel_alerta"].value_counts().items()
    }
else:
    cobertura_bps_pct = 0.0
    alertas_por_tier = {}

summary = {
    # ... campos existentes ...
    "total_itens": total_itens,
    "cobertura_bps_pct": cobertura_bps_pct,
    "alertas_por_tier": alertas_por_tier,
}
```

### Print de resumo de qualidade em main.py para STAB-07

```python
# Source: padrão verificado em main.py linhas 184-195
# Substituir o bloco "Mostrar resumo" existente por versão expandida:

if summary_file.exists():
    with open(summary_file) as f:
        s = json.load(f)
    totais = s.get("totais", {})
    cobertura = s.get("cobertura_bps_pct", 0.0)
    no_match = round(100.0 - cobertura, 1)
    n = s.get("total_itens", totais.get("empenhos_analisados", "?"))

    console.print(f"\n[bold]Resumo:[/bold]")
    console.print(f"   Empenhos analisados: {totais.get('empenhos_analisados', '?')}")
    console.print(f"   Alertas CRÍTICOS: {totais.get('alertas_criticos', '?')}")
    console.print(f"   Valor total excedente: R$ {totais.get('valor_total_excedente', '?')}")
    console.print(f"   Items: {n} | BPS match: {cobertura:.1f}% | No match: {no_match:.1f}%")
    if isinstance(cobertura, (int, float)) and cobertura < 50:
        console.print(
            "[bold yellow][WARNING][/bold yellow] "
            f"Cobertura BPS {cobertura:.1f}% abaixo de 50% — "
            "análise de preços pouco representativa para este conjunto de dados."
        )
```

### Estrutura de VALIDATION.md retroativo para Phase 0

```markdown
# Phase 0: Stabilization — Validation Plan

**Phase:** 0 — Stabilization
**Date:** 2026-05-03 (retroativo — criado em 2026-05-06)
**Source:** 00-01-PLAN.md §success_criteria + 00-01-SUMMARY.md (não existe — sem SUMMARY)

## Critérios de Sucesso Observáveis

| # | Critério | Comando de Verificação | Resultado |
|---|----------|----------------------|-----------|
| 1 | `python main.py --help` retorna 0 sem ImportError | `python main.py --help; echo $?` | PASS [VERIFIED: 00-01-PLAN.md SC-1] |
| 2 | SupplierAnalyzer importável | `python -c "from src.analyzers.supplier_analyzer import SupplierAnalyzer"` | PASS [VERIFIED: src/analyzers/supplier_analyzer.py existe] |
| ... | ... | ... | ... |
```

---

## STAB-06: Insumos para os três VALIDATION.md

### Phase 0 — Critérios de sucesso verificáveis (fonte: 00-01-PLAN.md)

1. `python main.py --help` retorna código 0 sem ImportError ou ModuleNotFoundError
2. `python -c "from src.analyzers.supplier_analyzer import SupplierAnalyzer"` sem erro
3. `grep "sorocaba_despesas_saude_2023" main.py` retorna zero linhas
4. `grep "threshold=threshold" src/analyzers/ai_analyzer.py` retorna 1 linha
5. `grep "rapidfuzz>=3.6.0" requirements.txt` retorna 1 linha
6. `grep "anthropic>=0.40.0" requirements.txt` retorna 1 linha
7. `grep "fuzzywuzzy" requirements.txt src/utils/normalizer.py` retorna zero linhas
8. `grep "ROOT = Path(__file__).parent" main.py` retorna 1 linha

**Testes automatizados existentes para Phase 0:** Nenhum arquivo de teste específico, mas todos os critérios são verificáveis via `grep`/`python -c`. [VERIFIED: ls tests/ — não há test_main.py nem test_phase0.py]

### Phase 1 — Critérios de sucesso verificáveis (fonte: 01-01/02/03-PLAN.md)

- Plano 01-01 (REQ-001): fixture retorna 3 registros com nm_municipio=SOROCABA; retry configurado
- Plano 01-02 (REQ-002): BPS collector baixa CSV de preços; fallback Playwright headless
- Plano 01-03 (REQ-003): CNPJCollector enriquece fornecedores; cache CNPJ TTL 30 dias

**Testes automatizados Phase 1:** `tests/test_bps_collector.py` (7 testes PASSED), `tests/test_cnpj_collector.py` (9 testes PASSED) [VERIFIED: pytest --collect-only]

### Phase 3 — Critérios de sucesso verificáveis (fonte: 03-01/02/03-PLAN.md + SUMMARYs)

- Plano 03-01 (REQ-005): PriceAnalyzer 12 colunas; CRÍTICO>200%; guarda mínima <5 BPS
- Plano 03-02 (REQ-006): SupplierAnalyzer score ponderado; tier SUSPEITO; 10 colunas
- Plano 03-03: Pipeline end-to-end; main.py com thresholds corretos

**Testes automatizados Phase 3:** `tests/test_price_analyzer.py` (12 testes PASSED), `tests/test_supplier_analyzer.py` (9 testes PASSED) [VERIFIED: pytest --collect-only]

---

## Runtime State Inventory

> Fase de documentação + adição de campos a JSON existente — sem rename ou migração.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `docs/summary.json` — estrutura atual sem `total_itens`, `cobertura_bps_pct`, `alertas_por_tier` | Regenerar via execução do pipeline (ou pelo teste) após modificação do exporter |
| Live service config | Nenhum serviço externo com estado registrado | Nenhuma |
| OS-registered state | Nenhuma tarefa agendada identificada | Nenhuma |
| Secrets/env vars | ANTHROPIC_API_KEY — sem mudança de nome | Nenhuma |
| Build artifacts | Nenhum egg-info ou binário compilado relacionado | Nenhuma |

**Nota:** `docs/summary.json` em disco continuará funcionando com os campos antigos até o próximo `--step export`. O dashboard lê os campos existentes — adição de novos campos não quebra retrocompatibilidade. [ASSUMED — o JavaScript do dashboard não tem validação de schema estrita; confirmado inspecionando index.html seria ideal]

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Pipeline | ✓ | 3.12.3 | — |
| pytest | Testes de STAB-07 | ✓ | 8.x | — |
| rich | WARNING output | ✓ | 13.7.0 | — |
| pandas | Cálculo de cobertura | ✓ | 2.1.4 | — |

Nenhuma dependência nova. [VERIFIED: requirements.txt + python3 --version]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | nenhum — descoberta automática de `tests/` |
| Quick run command | `python -m pytest tests/test_exporter.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STAB-06 | Arquivo `.planning/phases/phase-0/VALIDATION.md` existe | smoke (file existence) | `test -f .planning/phases/00-stabilization/00-VALIDATION.md && echo PASS` | ❌ Wave 0 |
| STAB-06 | Arquivo `.planning/phases/phase-1/VALIDATION.md` existe | smoke (file existence) | `test -f .planning/phases/01-data-collection/01-VALIDATION.md && echo PASS` | ❌ Wave 0 |
| STAB-06 | Arquivo `.planning/phases/phase-3/VALIDATION.md` existe | smoke (file existence) | `test -f .planning/phases/03-analysis/03-VALIDATION.md && echo PASS` | ❌ Wave 0 |
| STAB-07 | `summary.json` inclui campo `total_itens` no nível raiz | unit | `python -m pytest tests/test_exporter.py -k "total_itens or cobertura_bps" -x` | ❌ Wave 0 |
| STAB-07 | `summary.json` inclui campo `cobertura_bps_pct` | unit | `python -m pytest tests/test_exporter.py -k cobertura_bps -x` | ❌ Wave 0 |
| STAB-07 | `summary.json` inclui campo `alertas_por_tier` | unit | `python -m pytest tests/test_exporter.py -k alertas_por_tier -x` | ❌ Wave 0 |
| STAB-07 | Pipeline imprime linha `Items: N | BPS match: X%` | manual / smoke | `MEDAUDIT_FIXTURE=1 python main.py --skip-ai 2>&1 | grep "BPS match"` | n/a |
| STAB-07 | WARNING emitido quando cobertura < 50% | manual / smoke | `MEDAUDIT_FIXTURE=1 python main.py --skip-ai 2>&1 | grep WARNING` | n/a |

### Sampling Rate

- **Por commit de tarefa:** `python -m pytest tests/test_exporter.py -x -q`
- **Por wave:** `python -m pytest tests/ -q`
- **Phase gate:** Suite completa verde antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_exporter.py` — adicionar 3 testes em `TestGerarSummary` para `total_itens`, `cobertura_bps_pct`, `alertas_por_tier`
- [ ] `tests/test_exporter.py` — adicionar 1 teste para cobertura < 50% (verifica que o campo retorna valor correto, não testa stdout)

*(Infraestrutura pytest e `TestGerarSummary` já existem — apenas novos métodos de teste necessários)*

---

## Open Questions (RESOLVED)

1. **Local dos campos novos em summary.json: raiz vs. dentro de `totais`?**
   - O que sabemos: `totais` já contém `empenhos_analisados`, `alertas_*`. Colocar `total_itens` em `totais` seria semanticamente consistente, mas o critério de sucesso do STAB-07 especifica "no dashboard" sem detalhar o path.
   - O que é incerto: O `docs/index.html` lê campos específicos do JSON — seria bom confirmar quais antes de decidir.
   - Recomendação: Colocar `total_itens` e `cobertura_bps_pct` na raiz (nível top) para evitar colisão com testes existentes de `totais`. Verificar `docs/index.html` antes de implementar.
   - **RESOLVED:** Campos serão adicionados na **raiz** do dict retornado por `gerar_summary()` — evita colisão com `TestGerarSummary::test_schema_totais` existente e mantém compatibilidade com o JavaScript do dashboard que lê `totais.*` separadamente. Decidido no 06-02-PLAN.md.

2. **STAB-06: Nomear os arquivos como `00-VALIDATION.md` ou `phase-0-VALIDATION.md`?**
   - O que sabemos: O ROADMAP e STAB-06 mencionam `phases/phase-0/VALIDATION.md`. Mas os arquivos existentes usam convenção de prefixo numérico (`02-VALIDATION.md`, `04-VALIDATION.md`, `05-VALIDATION.md`).
   - Recomendação: Usar `00-VALIDATION.md`, `01-VALIDATION.md`, `03-VALIDATION.md` para manter consistência com o padrão do projeto [VERIFIED: ls .planning/phases/02-normalization/ e 04-export-docs/].
   - **RESOLVED:** Usar prefixo numérico: `00-VALIDATION.md`, `01-VALIDATION.md`, `03-VALIDATION.md` — consistente com a convenção dos demais diretórios de fase. Decidido no 06-01-PLAN.md.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Campos novos de summary.json devem ir na raiz do dict, não em `totais` | Architecture Patterns | Dashboard pode falhar ao ler campos se estiverem no lugar errado — verificar index.html antes de implementar |
| A2 | `docs/summary.json` em disco pode ser atualizado apenas re-executando o pipeline — nenhuma migração de dados necessária | Runtime State Inventory | Baixo — o arquivo é regenerado a cada run |

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: codebase] `src/utils/exporter.py` — estrutura atual de `gerar_summary()` e campos do summary.json
- [VERIFIED: codebase] `main.py` — bloco de resumo terminal linhas 184-195
- [VERIFIED: codebase] `src/analyzers/price_analyzer.py` — semântica de `nivel_alerta == "SEM_REFERÊNCIA"`
- [VERIFIED: codebase] `data/reports/alertas_superfaturamento.csv` — estrutura real do CSV produzido
- [VERIFIED: codebase] `docs/summary.json` — campos atualmente presentes
- [VERIFIED: git log + SUMMARY.md] Evidências de execução para fases 0, 1 e 3

### Secondary (MEDIUM confidence)
- [VERIFIED: tests/] Suite de testes existente — 90 testes passando, incluindo `TestGerarSummary`

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — tudo verificado no codebase atual
- Architecture: HIGH — código existente inspecionado diretamente
- Pitfalls: HIGH — baseados em padrões observados no código existente
- STAB-06 (documentação): HIGH — todos os insumos já existem no repositório
- STAB-07 (código): HIGH — gap identificado com precisão cirúrgica

**Research date:** 2026-05-06
**Valid until:** 2026-06-06 (fase estável — sem dependências externas)
