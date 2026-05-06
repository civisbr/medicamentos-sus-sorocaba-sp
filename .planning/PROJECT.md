# MedAudit SUS

## What This Is

Ferramenta de civic tech em Python que cruza dados do Portal da Transparência Municipal de Sorocaba
(via TCE-SP) com o Banco de Preços em Saúde (BPS/MS) para detectar possível superfaturamento em
compras públicas de medicamentos. Gera alertas classificados por nível de criticidade (ATENÇÃO /
ALERTA / CRÍTICO), relatório narrativo opcional via Claude API, CSV publicável, relatório HTML
self-contained e dashboard estático para GitHub Pages.

Destinado a jornalistas, vereadores, promotores e cidadãos sem formação técnica que precisam de
evidências concretas para investigação ou denúncia.

## Core Value

**Um pipeline executável de ponta a ponta que transforma dados públicos brutos em alertas de superfaturamento prontos para investigação** — o mínimo indispensável é: coletar → normalizar → analisar → exportar CSV com alertas classificados.

## Latest Milestone: v1.1 Estabilização — ARCHIVED

**Goal:** Fechar todos os gaps técnicos do v1.0 e elevar a qualidade observável dos dados gerados.

**Status:** ✅ Arquivado — shipped 2026-05-06 (Phases 5–6) | Próximo: `/gsd-new-milestone` para v2

## Current State

**Versão:** v1.1 Estabilização (shipped 2026-05-06)
**Código:** ~4.479 linhas Python (produção + testes) | **Testes:** 94/94 passando
**Stack:** Python 3.11+, pandas 2.2.x, rapidfuzz, anthropic≥0.40.0, click, jinja2, rich, playwright

Pipeline executável de ponta a ponta. Todos os módulos implementados. Coletores com fallback
headless (BPS) e modo fixture (TCE-SP). summary.json inclui métricas de cobertura BPS
(`total_itens`, `cobertura_bps_pct`, `alertas_por_tier`). VALIDATION.md retroativos criados para
fases 0, 1 e 3. Coleta de dados reais requer acesso à internet; testes passam com fixtures.

## Requirements

### Validated

- ✓ CLI click com flags `--municipio`, `--ano`, `--threshold`, `--step`, `--skip-ai`, `--output` — v1.0
- ✓ Estrutura de pipeline em 3 etapas selecionáveis: `collect → normalize → analyze → export` — v1.0
- ✓ `PortalSorocabaCollector.baixar_e_filtrar_tcesp()` com streaming ZIP, fixture mode, retry/backoff — v1.0
- ✓ `BPSCollector.coletar_precos_referencia()` com filtro SP, QT_REGISTROS≥5 — v1.0
- ✓ `CNPJCollector.enriquecer_fornecedores()` com cache TTL-30d, validação de dígito — v1.0
- ✓ `MedicamentoNormalizer` com rapidfuzz cdist (SCORE_ACEITO=85), CATMAT match, catmat_codigo=null retido — v1.0
- ✓ `PriceAnalyzer.analisar()` — SP +15%, 4 tiers, valor_excedente_total — v1.0
- ✓ `SupplierAnalyzer.analisar()` — score ponderado, tier SUSPEITO — v1.0
- ✓ `AIAnalyzer` — lazy init, degradação graciosa, claude-sonnet-4-5-20250929 — v1.0
- ✓ `Exporter.gerar_csv()` — 9 colunas REQ-008, disclaimer, ordenado DESC — v1.0
- ✓ `Exporter.gerar_html()` — Jinja2 self-contained, sem CDN, < 5MB — v1.0
- ✓ `Exporter.gerar_summary()` — JSON válido RFC 8259 (sem NaN), nivel_risco mapeado — v1.0
- ✓ Dashboard `docs/index.html` — fetch(summary.json), top-5, XSS via textContent — v1.0
- ✓ `docs/METODOLOGIA.md` + `docs/COMO_INTERPRETAR.md` — fórmulas + guia jornalistas — v1.0

### Validated (v1.1 — shipped 2026-05-06)

- ✓ `--threshold` CLI forwarded para `AIAnalyzer.analisar()` (STAB-01) — v1.1
- ✓ BPS URL dinâmica com fallback Playwright headless (STAB-02) — v1.1
- ✓ flag `empresa_nova` validada com dados BrasilAPI reais (STAB-03) — v1.1
- ✓ `numpy` adicionado explicitamente em `requirements.txt` (STAB-04) — v1.1
- ✓ `--ano all` sem sobrescrever `fornecedores_enriquecidos.json` (STAB-05) — v1.1
- ✓ VALIDATION.md retroativo para Phases 0, 1, 3 (STAB-06) — v1.1
- ✓ Logging de cobertura BPS: `total_itens`, `cobertura_bps_pct`, `alertas_por_tier` no summary.json (STAB-07) — v1.1

### Out of Scope

- Suporte a outros municípios além de Sorocaba — exigiria mapeamento de APIs distintas por portal
- Integração com TCE-SP automatizada — marcado como opcional no README
- Banco de dados (SQLite/PostgreSQL) — file-based é suficiente para o volume esperado
- Interface web de administração — dashboard é read-only, estático, sem backend
- Brand-to-INN mapping — v2 (REQ-101)
- Detecção de fracionamento — v2 (REQ-102)
- Multi-município — v2 (REQ-103)
- Normalização de UoM — v2 (REQ-104)

## Context

**Codebase atual (v1.0):** Pipeline completo. Todos os módulos implementados. 72 testes passando.
Relatório HTML de 14KB gerado em execução de teste com dados de fixture.

**Coleta de dados reais:** BPS via scraping de portal (pode exigir headless browser). TCE-SP
disponível via bulk ZIP público. CNPJ via BrasilAPI (~3 req/s).

**Público-alvo:** Jornalistas, vereadores, promotores, ativistas de transparência.
O relatório HTML foi projetado para ser compreensível sem formação técnica.

**Dados são 100% públicos**, coletados sob a Lei de Acesso à Informação. O projeto sinaliza
inconsistências para investigação, nunca acusa diretamente.

## Constraints

- **Tech stack:** Python ≥ 3.10, manter dependências do `requirements.txt` (rapidfuzz, anthropic≥0.40.0)
- **Acesso:** APIs públicas sem autenticação (exceto `ANTHROPIC_API_KEY` para análise IA, opcional com `--skip-ai`)
- **Performance:** ~1.000–5.000 empenhos/ano para Sorocaba — sem necessidade de otimização para escala
- **Portabilidade:** Pipeline roda do diretório raiz; todos os paths ancorados com `Path(__file__).parent`
- **HTML report:** Auto-contido (< 5MB), funciona offline, qualquer browser moderno

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Usar mediana BPS (não média) | Mais robusta a outliers nos dados de compras públicas | ✓ Validado — distribuição de preços BPS tem cauda longa |
| Margem regional SP de 15% | SP historicamente mais caro; evita falsos positivos | ✓ Mantido — sem evidência para alterar |
| File-based handoff entre etapas | Permite rodar etapas isoladamente (`--step`); debug mais fácil | ✓ Validado — permitiu desenvolvimento incremental por fase |
| `fuzzywuzzy` → `rapidfuzz` | Deprecated, API idêntica, sem breaking changes | ✓ Aplicado — 5.000 linhas em < 1s |
| Mínimo de 5 registros BPS para CRÍTICO | Itens com poucos registros são menos confiáveis como referência | ✓ Implementado como guarda em price_analyzer.py |
| `cdist` batch em vez de loop | O(n×m) vetorizado com `workers=-1` — orders of magnitude mais rápido | ✓ Validado — 0.09s para 5.000 linhas |
| Tier SUSPEITO via OR lógico | 3+ CRÍTICO OU concentração >60% — cobre dois cenários distintos | ✓ Implementado e testado |
| `autoescape=False` em Jinja2 | Dados JSON em `<script>` não devem ser double-escaped | ✓ Necessário — autoescape=True quebrava JSON |
| `_safe_float()` para NaN | `json.dumps()` serializa `nan` como literal `NaN` (JSON inválido RFC 8259) | ✓ Fix aplicado no audit — dashboard funcional |

## Evolution

Este documento evolui a cada transição de fase e milestone.

**Após cada milestone** (via `/gsd-complete-milestone`):
1. Revisão completa de todas as seções
2. Core Value check — ainda a prioridade certa?
3. Auditoria de Out of Scope — razões ainda válidas?
4. Requirements implementados → Mover para Validated

---
*Last updated: 2026-05-06 — Milestone v1.1 Estabilização archived*
