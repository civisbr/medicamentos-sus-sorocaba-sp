# MILESTONES — MedAudit SUS

## v1.0 MVP — 2026-05-06

**Status:** ✅ SHIPPED
**Fases:** 0–4 | **Planos:** 12 | **Testes:** 72
**Período:** 2026-05-03 → 2026-05-06 (4 dias)
**Código:** ~5.100 linhas Python/HTML/J2

### Entregou

Pipeline ETL cívico de ponta a ponta que transforma dados públicos brutos em alertas de
superfaturamento prontos para investigação: coletar → normalizar → analisar → exportar CSV
classificado, relatório HTML self-contained, dashboard GitHub Pages e documentação para jornalistas.

### Realizações Principais

1. 5 bugs bloqueantes corrigidos (Phase 0) — pipeline deixou de crashar no import
2. Três coletores de dados públicos implementados — TCE-SP, BPS/MS, BrasilAPI CNPJ
3. `MedicamentoNormalizer` com rapidfuzz cdist — match CATMAT em < 1s para 5.000 linhas
4. `PriceAnalyzer` + `SupplierAnalyzer` — 4 tiers de alerta, score de risco ponderado, TDD RED→GREEN
5. Exportação completa — CSV 9 colunas, HTML Jinja2 sem CDN, dashboard `fetch(summary.json)`, docs para jornalistas

### Gaps Conhecidos no Fechamento

- BUG-003 / REQ-007: `--threshold` CLI não forwarded para AIAnalyzer (tech debt v1.1)
- REQ-002: BPS URL dinâmica pode falhar em produção (portal usa JS)
- REQ-006: flag `empresa_nova` não testada com dados BrasilAPI reais
- Phase 0, 1, 3: sem VALIDATION.md formal (Nyquist coverage parcial)
- `numpy` não listado em `requirements.txt` (transitivo de pandas)

### Deferred Items

| Item | Status |
|------|--------|
| REQ-101: Brand→INN mapping | v2 |
| REQ-102: Fracionamento detection | v2 |
| REQ-103: Multi-município | v2 |
| REQ-104: Normalização UoM | v2 |

**Arquivos:**
- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`
- `.planning/milestones/v1.0-MILESTONE-AUDIT.md`

---

## v1.1 Estabilização — 2026-05-06

**Status:** ✅ SHIPPED
**Fases:** 5–6 | **Planos:** 5 | **Testes:** 94
**Período:** 2026-05-06 (1 dia)
**Código:** ~4.479 linhas Python (produção + testes)

### Entregou

Ciclo de estabilização que fechou todos os 5 gaps técnicos do v1.0: threshold CLI propagado para
AIAnalyzer, fallback Playwright headless para BPS, empresa_nova validada com dados reais,
numpy explícito em requirements.txt, --ano all preserva cache via merge por CNPJ. Adicionou
observabilidade de qualidade de dados (cobertura BPS no terminal e summary.json) e VALIDATION.md
retroativos para as fases 0, 1 e 3.

### Realizações Principais

1. `--threshold` CLI propagado até `AIAnalyzer.analisar()` — narrativa IA reflete limiar correto (STAB-01)
2. Fallback Playwright headless em `BPSCollector` para portais que geram URL via JavaScript (STAB-02)
3. `empresa_nova: bool` calculado com `data_abertura` real da BrasilAPI — 9 edge cases cobertos (STAB-03)
4. `numpy>=1.26.0` e `playwright>=1.50.0` explícitos em `requirements.txt` (STAB-04)
5. `--ano all` preserva fornecedores via merge por CNPJ sem sobrescrever cache (STAB-05)
6. VALIDATION.md retroativos para Phases 0, 1, 3 com validators executáveis e TDD Gate Evidence (STAB-06)
7. `summary.json` estendido com `total_itens`, `cobertura_bps_pct`, `alertas_por_tier` + WARNING no terminal (STAB-07)

### Gaps Conhecidos no Fechamento

Nenhum — todos os 7 requisitos STAB entregues e verificados.

### Deferred Items

| Item | Status |
|------|--------|
| REQ-101: Brand→INN mapping | v2 |
| REQ-102: Fracionamento detection | v2 |
| REQ-103: Multi-município | v2 |
| REQ-104: Normalização UoM | v2 |

**Arquivos:**
- `.planning/milestones/v1.1-ROADMAP.md`
- `.planning/milestones/v1.1-REQUIREMENTS.md`
