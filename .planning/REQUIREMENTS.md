# REQUIREMENTS — MedAudit SUS

> Pipeline ETL cívico que detecta sobrepreço em compras de medicamentos do SUS em Sorocaba/SP.

---

## v1 — Escopo Inicial (MVP funcional)

### REQ-001 — Coleta do Portal de Transparência
**Prioridade:** Crítica | **Fase:** 1
- Coletar licitações e empenhos de saúde do portal de Sorocaba para o ano especificado via `--ano`
- Salvar como JSON em `data/raw/sorocaba_despesas_saude_{ano}.json`
- Implementar retry com backoff exponencial (3 tentativas)
- Validar Content-Type da resposta antes de parsear
- **Nota:** Estrutura da API do portal é desconhecida — requer sessão DevTools/HAR antes de implementar

### REQ-002 — Coleta BPS (Base de Preços em Saúde)
**Prioridade:** Crítica | **Fase:** 1
- Consultar API `apibps.saude.gov.br` para preços de referência de medicamentos
- Salvar como JSON em `data/raw/bps_precos.json`
- Implementar rate limiting (máx 10 req/s)
- Só marcar CRÍTICO se houver ≥5 registros BPS para o item

### REQ-003 — Enriquecimento CNPJ
**Prioridade:** Alta | **Fase:** 1
- Consultar BrasilAPI para dados cadastrais de cada fornecedor
- Cache em disco em `data/raw/cnpj_cache.json` (TTL 30 dias)
- Validar dígito verificador do CNPJ antes de consultar
- Corrigir bug: ano hardcoded em `2023` (usar valor de `--ano`)

### REQ-004 — Normalização de Descrições
**Prioridade:** Crítica | **Fase:** 2
- Implementar `limpar_descricao()`: lowercase, remoção de abreviações, strip de unidades
- Fuzzy matching CATMAT com `rapidfuzz.fuzz.token_set_ratio` (score ≥ 85)
- Extrair concentração e via de administração para validação pós-score
- Evitar falso CRÍTICO por mismatch de embalagem (comprimido vs. caixa)
- Arquivo `data/processed/medicamentos_normalizados.json`

### REQ-005 — Análise de Preços
**Prioridade:** Crítica | **Fase:** 3
- Implementar `PriceAnalyzer` com margem SP +15% sobre preço BPS
- Sistema de 4 tiers de alerta:
  - ATENÇÃO: desvio 30–99%
  - ALERTA: desvio 100–199%
  - CRÍTICO: desvio ≥200%
  - SUSPEITO: concentração de empenhos para 1 fornecedor >60%
- Calcular `valor_excedente_total` (BRL) para ranking
- Arquivo `data/processed/analise_precos.json`

### REQ-006 — Criação do SupplierAnalyzer
**Prioridade:** Crítica | **Fase:** 3
- Criar `src/analyzers/supplier_analyzer.py` (arquivo não existe — causa crash imediato)
- Score de risco ponderado por tipo de alerta
- Flags: CNPJ com < 2 anos de existência, situação cadastral irregular
- Tier SUSPEITO para concentração anormal de contratos

### REQ-007 — Análise IA (Claude)
**Prioridade:** Média | **Fase:** 4
- Corrigir threshold hardcoded em `ai_analyzer.py:148` (usar parâmetro `--threshold`)
- Atualizar SDK anthropic para ≥0.40.0 e modelo para `claude-sonnet-4-5`
- Prompt não-acusatório com disclaimer legal
- Máximo 5 itens críticos por chamada (controle de custo)
- Tratar erro graciosamente se API key não configurada

### REQ-008 — Exportação CSV
**Prioridade:** Alta | **Fase:** 4
- Exportar alertas classificados como `data/output/alertas_{ano}.csv`
- Colunas: item, fornecedor, cnpj, preco_pago, preco_bps, desvio_pct, tier, valor_excedente, narrativa_ia
- Ordenar por `valor_excedente_total` DESC

### REQ-009 — Relatório HTML Self-Contained
**Prioridade:** Alta | **Fase:** 4
- Relatório Jinja2 com CSS/JS/dados todos inline (sem CDN)
- Tamanho máximo: 5MB
- Tabela interativa ordenável por qualquer coluna
- Narrativa IA no topo
- Ordenação padrão: `valor_excedente_total` DESC

### REQ-010 — Dashboard GitHub Pages
**Prioridade:** Média | **Fase:** 4
- Gerar arquivos estáticos em `docs/` para deploy no GitHub Pages
- Histórico comparativo entre anos
- Link direto para download do CSV

### REQ-011 — Documentação de Credibilidade
**Prioridade:** Alta | **Fase:** 4
- `METODOLOGIA.md`: fontes, fórmulas de cálculo, limitações
- `COMO_INTERPRETAR.md`: guia para jornalistas e promotores
- Disclaimer legal em todos os outputs

---

## v1.1 — Estabilização (milestone atual)

### STAB-01 — BUG-003: --threshold forwarded para AIAnalyzer
**Prioridade:** Alta | **Fase:** 5
- Usuário passa `--threshold 20` e a narrativa gerada pela IA reflete o limiar correto
- Corrigir `ai_analyzer.py:148` onde threshold está hardcoded como `30`
- Parâmetro deve ser propagado do CLI até `AIAnalyzer.analisar(threshold=...)`

### STAB-02 — BPS Headless: Coleta via portal JavaScript
**Prioridade:** Alta | **Fase:** 5
- Coleta BPS funciona mesmo quando o portal usa JS para gerar a URL de download
- Implementar fallback Selenium/headless browser quando a URL dinâmica falha
- Manter compatibilidade com o modo de fixture para testes offline

### STAB-03 — empresa_nova com BrasilAPI real
**Prioridade:** Média | **Fase:** 5
- Flag `empresa_nova` calculada com `data_abertura` real da BrasilAPI (não apenas mock)
- Cobrir edge case de CNPJ sem `data_abertura` na resposta (campo ausente ou nulo)
- Testes de integração que consomem fixture da resposta real da BrasilAPI

### STAB-04 — numpy explícito em requirements.txt
**Prioridade:** Baixa | **Fase:** 5
- `numpy` listado com versão mínima em `requirements.txt`
- Garantir instalação limpa sem dependência implícita de pandas

### STAB-05 — --ano all sem sobrescrever fornecedores
**Prioridade:** Média | **Fase:** 5
- `--ano all` agrega dados de múltiplos anos sem sobrescrever `fornecedores_enriquecidos.json`
- Usar estratégia de merge por CNPJ (atualizar apenas campos desatualizados, preservar cache)

### STAB-06 — VALIDATION.md retroativo para Phases 0, 1, 3
**Prioridade:** Alta | **Fase:** 6
- Criar `.planning/phases/phase-0/VALIDATION.md`, `phase-1/VALIDATION.md`, `phase-3/VALIDATION.md`
- Cada arquivo documenta critérios de sucesso observáveis e evidência de cobertura existente

### STAB-07 — Logging de qualidade de dados
**Prioridade:** Média | **Fase:** 6
- Pipeline imprime resumo ao final: total de itens, % com match BPS, % sem match BPS
- Emite aviso visível (rich `[WARNING]`) quando cobertura BPS < 50%
- Inclui total de alertas por tier (ATENÇÃO / ALERTA / CRÍTICO) no summary.json

---

## v2 — Melhorias Futuras

### REQ-101 — Mapeamento Marca → INN
- Lookup brand-to-INN para top 100 medicamentos
- Fonte: lista ANVISA (verificar disponibilidade)

### REQ-102 — Detecção de Fracionamento
- Identificar SUSPEITO quando mesmo medicamento aparece em múltiplos empenhos pequenos
- Padrão típico de "jogo do licitante"

### REQ-103 — Suporte Multi-Município
- Parametrizar coletor para outras cidades paulistas

### REQ-104 — Normalização de Unidade de Medida
- Converter preço por comprimido vs. por caixa consistentemente

---

## Fora do Escopo

- Interface administrativa web
- Banco de dados relacional (filesystem é suficiente)
- Integração TCE-SP automatizada
- API REST
- Cobertura de municípios fora de Sorocaba (v1)

---

## Bugs Bloqueantes (devem ser corrigidos na Fase 0)

| ID | Arquivo | Linha | Descrição |
|----|---------|-------|-----------|
| BUG-001 | main.py | 81 | Import `supplier_analyzer` — arquivo não existe → crash imediato |
| BUG-002 | main.py | 69 | Ano hardcoded `2023` no caminho do arquivo CNPJ |
| BUG-003 | ai_analyzer.py | 148 | Threshold hardcoded `30` em vez de usar parâmetro |
| BUG-004 | requirements.txt | — | `anthropic==0.25.0` incompatível com modelo 2025; `fuzzywuzzy` deprecated |
| BUG-005 | vários | — | Caminhos relativos quebram em cron/CI |

---

## Traceability

| Requisito | Fase | Status | Research | Codebase |
|-----------|------|--------|----------|----------|
| BUG-001 | Phase 0 | Complete | ARCHITECTURE.md §SupplierAnalyzer | src/analyzers/supplier_analyzer.py |
| BUG-002 | Phase 0 | Complete | — | main.py (--ano parametrizado) |
| BUG-003 | Phase 0 | Complete | STACK.md §Anthropic | src/analyzers/ai_analyzer.py |
| BUG-004 | Phase 0 | Complete | STACK.md §rapidfuzz, §Anthropic | requirements.txt |
| BUG-005 | Phase 0 | Complete | — | main.py ROOT = Path(__file__).parent |
| REQ-001 | Phase 1 | Complete | ARCHITECTURE.md §Collectors, PITFALLS.md §API | src/collectors/portal_sorocaba.py |
| REQ-002 | Phase 1 | Complete | STACK.md §BPS, ARCHITECTURE.md §BPS | src/collectors/bps_collector.py |
| REQ-003 | Phase 1 | Complete | FEATURES.md §CNPJ, PITFALLS.md §CNPJ | src/collectors/cnpj_collector.py |
| REQ-004 | Phase 2 | Complete | STACK.md §rapidfuzz, FEATURES.md §Normalization | src/utils/normalizer.py |
| REQ-005 | Phase 3 | Complete | FEATURES.md §Alert tiers | src/analyzers/price_analyzer.py |
| REQ-006 | Phase 3 | Complete | ARCHITECTURE.md §SupplierAnalyzer | src/analyzers/supplier_analyzer.py |
| REQ-007 | Phase 4 | Complete | STACK.md §Anthropic, PITFALLS.md §AI | src/analyzers/ai_analyzer.py |
| REQ-008 | Phase 4 | Complete | FEATURES.md §CSV export | src/utils/exporter.py |
| REQ-009 | Phase 4 | Complete | FEATURES.md §HTML, ARCHITECTURE.md §HTML | src/utils/exporter.py:gerar_html() |
| REQ-010 | Phase 4 | Complete | FEATURES.md §Dashboard | docs/ (GitHub Pages) |
| REQ-011 | Phase 4 | Complete | FEATURES.md §Credibility | docs/METODOLOGIA.md, docs/COMO_INTERPRETAR.md |
| STAB-01 | Phase 5 | Complete | — | src/analyzers/ai_analyzer.py |
| STAB-02 | Phase 5 | Complete | — | src/collectors/bps_collector.py (Playwright fallback) |
| STAB-03 | Phase 5 | Complete | — | src/collectors/cnpj_collector.py (empresa_nova) |
| STAB-04 | Phase 5 | Complete | — | requirements.txt (numpy explícito) |
| STAB-05 | Phase 5 | Complete | — | src/collectors/cnpj_collector.py (merge por CNPJ) |
| STAB-06 | Phase 6 | Complete | — | .planning/phases/00-stabilization/00-VALIDATION.md, .planning/phases/01-data-collection/01-VALIDATION.md, .planning/phases/03-analysis/03-VALIDATION.md |
| STAB-07 | Phase 6 | Complete | — | src/utils/exporter.py:gerar_summary(), main.py bloco resumo |
