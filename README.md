# 💊 MedAudit SUS — Análise de Superfaturamento de Medicamentos em Sorocaba

> Projeto de civic tech que cruza dados do Portal da Transparência Municipal de Sorocaba com o Banco de Preços em Saúde (BPS) do Ministério da Saúde para identificar possíveis superfaturamentos em compras públicas de medicamentos.

---

## 🎯 Objetivo

Detectar compras de medicamentos realizadas pela Prefeitura de Sorocaba com preços significativamente acima do preço de referência federal (BPS), sinalizando fornecedores, contratos e períodos que merecem investigação.

---

## 🏗️ Estrutura do Projeto

```
medicamentos-sus/
│
├── README.md                    ← Este arquivo
├── requirements.txt             ← Dependências Python
├── .env.example                 ← Variáveis de ambiente necessárias
├── main.py                      ← Ponto de entrada — orquestra todo o pipeline
│
├── data/
│   ├── raw/                     ← Dados brutos baixados das APIs
│   │   ├── sorocaba_despesas_saude_YYYY.json
│   │   └── bps_precos_referencia.csv
│   ├── processed/               ← Dados limpos e normalizados
│   │   ├── despesas_medicamentos_YYYY.csv
│   │   └── bps_normalizado.csv
│   └── reports/                 ← Relatórios finais gerados
│       ├── alertas_superfaturamento.csv
│       ├── relatorio_completo.html
│       └── summary.json
│
├── src/
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── portal_sorocaba.py   ← Coleta despesas do portal municipal
│   │   ├── bps_collector.py     ← Coleta preços de referência do BPS/MS
│   │   └── cnpj_collector.py    ← Enriquece fornecedores via API Receita
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── price_analyzer.py    ← Lógica principal de comparação de preços
│   │   ├── supplier_analyzer.py ← Análise de padrões por fornecedor
│   │   └── ai_analyzer.py       ← Integração com Claude API para análise qualitativa
│   └── utils/
│       ├── __init__.py
│       ├── normalizer.py        ← Normalização de nomes de medicamentos (fuzzy match)
│       ├── logger.py            ← Logging estruturado
│       └── exporter.py          ← Exportação em CSV, JSON e HTML
│
├── dashboard/
│   ├── index.html               ← Dashboard visual dos resultados (GitHub Pages ready)
│   ├── style.css
│   └── app.js                   ← Carrega summary.json e renderiza os alertas
│
└── docs/
    ├── FONTES_DE_DADOS.md       ← Documentação das APIs utilizadas
    ├── METODOLOGIA.md           ← Como o cálculo de superfaturamento é feito
    └── COMO_INTERPRETAR.md      ← Guia para jornalistas e cidadãos
```

---

## 🔄 Pipeline de Dados (Fluxo Completo)

```
[Portal Transparência Sorocaba]          [BPS - Ministério da Saúde]
         │                                         │
         ▼                                         ▼
  portal_sorocaba.py                    bps_collector.py
  (filtra função=SAÚDE,                 (baixa tabela de preços
   natureza=material/serviço,            de referência por
   busca por descrição de med.)          CATMAT/CATSER)
         │                                         │
         └──────────────┬───────────────────────────┘
                        ▼
               normalizer.py
               (limpa nomes, padroniza
                unidades, faz fuzzy match
                entre descrições diferentes
                do mesmo medicamento)
                        │
                        ▼
             price_analyzer.py
             (calcula: preço_pago / preço_bps
              flags acima de 30% = ALERTA
              flags acima de 100% = CRÍTICO)
                        │
                        ▼
            supplier_analyzer.py
            (agrupa por CNPJ fornecedor,
             analisa frequência, valor total,
             verifica se CNPJ é suspeito)
                        │
                        ▼
               ai_analyzer.py
               (envia os top 20 casos para
                Claude API com contexto e
                pede análise qualitativa)
                        │
                        ▼
               exporter.py
               (gera alertas.csv,
                relatorio.html,
                summary.json p/ dashboard)
```

---

## 📡 Fontes de Dados

### 1. Portal da Transparência de Sorocaba
- **URL base:** `https://transparencia.sorocaba.sp.gov.br/`
- **O que coletar:** Despesas empenhadas/pagas na função **SAÚDE (10)**, natureza de despesa **339030** (material de consumo) e **339039** (outros serviços), filtrando por descrição de medicamento
- **Formato:** JSON (via API) ou CSV (download manual)
- **Período sugerido:** 2020–2024 (5 anos para análise de tendências)

### 2. Banco de Preços em Saúde (BPS)
- **URL:** `https://bps.saude.gov.br/`
- **API pública:** `https://apibps.saude.gov.br/api/`
- **O que coletar:** Preços de referência por item CATMAT, média nacional, mediana, menor e maior preço registrado
- **Endpoint principal:** `GET /precos?codigoMaterial={catmat}&uf=SP`

### 3. API CNPJ (Receita Federal)
- **URL:** `https://brasilapi.com.br/api/cnpj/v1/{cnpj}`
- **O que coletar:** Razão social, data de abertura, situação cadastral, sócios, capital social
- **Uso:** Detectar empresas com menos de 6 meses quando ganharam contratos grandes

### 4. TCE-SP (opcional, enriquecimento)
- **URL:** `https://transparencia.tce.sp.gov.br/`
- **API:** `https://api.tce.sp.gov.br/`
- **O que coletar:** Contratos vigentes, licitações dispensadas

---

## 🚀 Como Executar

### Pré-requisitos
```bash
python >= 3.10
pip install -r requirements.txt
```

### Configuração
```bash
cp .env.example .env
# Editar .env com sua chave da API Anthropic (para análise qualitativa com IA)
```

### Execução completa do pipeline
```bash
python main.py --municipio sorocaba --ano 2023 --threshold 30
```

### Parâmetros disponíveis
| Parâmetro | Descrição | Padrão |
|---|---|---|
| `--municipio` | Município alvo | `sorocaba` |
| `--ano` | Ano de referência (ou `all` para 2020-2024) | `2023` |
| `--threshold` | % acima do BPS para gerar alerta | `30` |
| `--skip-ai` | Pular análise qualitativa com Claude API | `False` |
| `--output` | Diretório de saída | `data/reports/` |

### Execução por etapas
```bash
# Só coleta
python main.py --step collect

# Só análise (dados já coletados)
python main.py --step analyze

# Só exporta relatório
python main.py --step export
```

---

## 📊 O que o Sistema Detecta

### Critérios de Alerta

| Nível | Critério | Cor |
|---|---|---|
| 🟡 **ATENÇÃO** | Preço pago 30–60% acima do BPS | Amarelo |
| 🟠 **ALERTA** | Preço pago 60–100% acima do BPS | Laranja |
| 🔴 **CRÍTICO** | Preço pago >100% acima do BPS | Vermelho |
| 🚨 **SUSPEITO** | Fornecedor com >3 alertas críticos no mesmo período | Vermelho escuro |

### Padrões adicionais investigados
- Fornecedor com CNPJ aberto há menos de 6 meses no momento do contrato
- Mesmo fornecedor vencendo múltiplas licitações sem concorrência
- Preços que sobem abruptamente em determinado período (possível combinação)
- Itens comprados em quantidades muito acima da média histórica

---

## 🤖 Uso da IA (Claude API)

O módulo `ai_analyzer.py` envia os casos mais críticos para o Claude com o seguinte contexto:

```
Sistema: Você é um analista de controle de gastos públicos no Brasil.
Analise os seguintes casos de possível superfaturamento em compras de
medicamentos pela Prefeitura de Sorocaba e produza um relatório objetivo,
indicando: (1) quais casos merecem investigação prioritária, (2) possíveis
explicações legítimas, (3) padrões que conectam múltiplos casos.

[DADOS: lista dos top 20 alertas em JSON]
```

**Resultado:** Um relatório textual que contextualiza os números e prioriza a investigação — útil para jornalistas e vereadores sem formação técnica.

---

## 📤 Outputs Gerados

### `alertas_superfaturamento.csv`
| Coluna | Descrição |
|---|---|
| data_empenho | Data da compra |
| descricao_item | Nome do medicamento (como aparece no empenho) |
| catmat | Código CATMAT normalizado |
| cnpj_fornecedor | CNPJ da empresa |
| razao_social | Nome da empresa |
| quantidade | Quantidade comprada |
| preco_unitario_pago | Preço pago por unidade (R$) |
| preco_bps_mediana | Mediana BPS para o mesmo item (R$) |
| variacao_percentual | Quanto acima do BPS (%) |
| valor_excedente_total | Quanto a mais foi pago no total (R$) |
| nivel_alerta | ATENÇÃO / ALERTA / CRÍTICO / SUSPEITO |
| numero_empenho | Referência do documento |

### `summary.json`
Usado pelo dashboard HTML. Contém totais, top fornecedores, série temporal e top itens alertados.

### `relatorio_completo.html`
Relatório auto-contido, sem dependências externas, pronto para envio por e-mail ou publicação.

---

## ⚖️ Aviso Legal

Os dados utilizados são 100% públicos, coletados de fontes governamentais oficiais conforme a Lei de Acesso à Informação (Lei 12.527/2011). Este projeto não acusa ninguém — sinaliza inconsistências para investigação. Toda conclusão deve ser verificada com os documentos originais.

---

## 🤝 Contribuição

Projeto open source. PRs bem-vindos. Se encontrar um alerta real, reporte ao:
- **TCE-SP:** [tce.sp.gov.br/ouvidoria](https://www.tce.sp.gov.br)
- **CGU:** [falabr.cgu.gov.br](https://falabr.cgu.gov.br)
- **MP-SP:** [mp.sp.gov.br](https://www.mp.sp.gov.br)
