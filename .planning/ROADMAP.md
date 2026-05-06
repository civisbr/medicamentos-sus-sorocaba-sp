# Roadmap: MedAudit SUS

## Milestones

- ✅ **v1.0 MVP** — Phases 0–4 (shipped 2026-05-06) — [archive](.planning/milestones/v1.0-ROADMAP.md)
- 🚧 **v1.1 Estabilização** — Phases 5–6 (em progresso)

## Phases

---

## v1.1 Estabilização — Phase Details

### Phase 5: Bug Fixes & Collectors

**Goal:** Corrigir todos os bugs e gaps de coleta de dados identificados no audit do v1.0.

**Requirements:** STAB-01, STAB-02, STAB-03, STAB-04, STAB-05

**Plans:** 3 plans

Plans:
- [x] 05-01-PLAN.md — Propagar --threshold para AIAnalyzer + adicionar numpy/playwright a requirements.txt (STAB-01, STAB-04)
- [x] 05-02-PLAN.md — Implementar fallback Playwright headless em BPSCollector (STAB-02)
- [x] 05-03-PLAN.md — Campo empresa_nova: bool em CNPJCollector + merge por CNPJ em --ano all (STAB-03, STAB-05)

**Success criteria:**
1. `python main.py --threshold 20 ...` gera narrativa IA mencionando o limiar de 20% (STAB-01)
2. `BPSCollector.coletar_precos_referencia()` retorna dados mesmo quando portal redireciona via JS — testável com mock headless (STAB-02)
3. `CNPJCollector` popula `empresa_nova=True/False` usando `data_abertura` real da BrasilAPI em todos os cenários incluindo campo ausente (STAB-03)
4. `pip install -r requirements.txt` em ambiente limpo instala numpy sem erro de dependência ausente (STAB-04)
5. `python main.py --ano all` completa sem sobrescrever CNPJs já em cache — merge por CNPJ verificável via diff do arquivo (STAB-05)

---

### Phase 6: Validation & Data Quality

**Goal:** Fechar lacunas de documentação de validação e adicionar observabilidade de qualidade de dados no pipeline.

**Requirements:** STAB-06, STAB-07

**Success criteria:**
1. Arquivos `.planning/phases/phase-0/VALIDATION.md`, `phase-1/VALIDATION.md` e `phase-3/VALIDATION.md` existem com critérios de sucesso e evidência de cobertura (STAB-06)
2. Execução do pipeline imprime ao final: `Items: N | BPS match: X% | No match: Y%` e emite `[WARNING]` quando cobertura < 50% (STAB-07)
3. `summary.json` inclui campos `total_itens`, `cobertura_bps_pct` e `alertas_por_tier` verificáveis no dashboard (STAB-07)

---

<details>
<summary>✅ v1.0 MVP (Phases 0–4) — SHIPPED 2026-05-06</summary>

- [x] Phase 0: Stabilization (1/1 plan) — completed 2026-05-03
- [x] Phase 1: Data Collection (3/3 plans) — completed 2026-05-03
- [x] Phase 2: Normalization (1/1 plan) — completed 2026-05-04
- [x] Phase 3: Analysis (3/3 plans) — completed 2026-05-05
- [x] Phase 4: Export & Docs (4/4 plans) — completed 2026-05-05

Full details: [.planning/milestones/v1.0-ROADMAP.md](.planning/milestones/v1.0-ROADMAP.md)

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 0. Stabilization | v1.0 | 1/1 | Complete | 2026-05-03 |
| 1. Data Collection | v1.0 | 3/3 | Complete | 2026-05-03 |
| 2. Normalization | v1.0 | 1/1 | Complete | 2026-05-04 |
| 3. Analysis | v1.0 | 3/3 | Complete | 2026-05-05 |
| 4. Export & Docs | v1.0 | 4/4 | Complete | 2026-05-05 |
| 5. Bug Fixes & Collectors | v1.1 | 3/3 | Complete | 2026-05-06 |
| 6. Validation & Data Quality | v1.1 | 0/1 | Pending | — |
