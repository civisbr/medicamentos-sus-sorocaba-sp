# Como Interpretar os Alertas — Guia para Jornalistas

## O que é este relatório?

O MedAudit SUS é um sistema automatizado de detecção de possível sobrepreço em compras de
medicamentos realizadas pela Prefeitura de Sorocaba/SP com recursos do SUS. Os dados de compras
provêm do **Portal de Transparência de Sorocaba** (empenhos da Secretaria de Saúde) e são
comparados com os preços de referência do **Banco de Preços em Saúde (BPS)** do Ministério
da Saúde, que registra todas as compras federais e estaduais de medicamentos do país.

O sistema aplica um ajuste regional de 15% sobre a mediana nacional do BPS — reconhecendo que
preços em São Paulo são estruturalmente mais altos — e então calcula o desvio percentual de
cada compra em relação a esse valor ajustado. Compras com desvio acima de um threshold
(padrão: 30%) recebem um nível de alerta.

**O que este sistema NÃO é:** não é uma auditoria oficial, não é prova de irregularidade e
não substitui investigação jornalística ou apuração do Ministério Público. Os alertas são
pontos de partida para investigação, não conclusões. Uma compra cara pode ter explicações
legítimas (emergência, item com especificação diferente, logística, monopólio de fornecedor).

---

## O que significa cada Nível de Alerta?

| Nível | Desvio em relação ao preço BPS ajustado | O que fazer |
|-------|----------------------------------------|-------------|
| ATENÇÃO | 30% a 99% acima | Verificar contexto — pode ser legítimo (emergência, urgência, item específico) |
| ALERTA | 100% a 199% acima | Investigar — padrão preocupante, solicitar justificativa à prefeitura |
| CRÍTICO | 200% ou mais acima | Prioridade de investigação — desvio muito alto, difícil justificativa ordinária |
| SEM_REFERÊNCIA | — | Dados insuficientes no BPS para comparação confiável (menos de 5 registros nacionais) |

O sistema só classifica como **CRÍTICO** medicamentos com pelo menos 5 registros no BPS
nacional — para evitar que itens raros com poucos registros sejam indevidamente classificados
como prioridade.

---

## Como ler o CSV de alertas

O arquivo CSV de alertas (`alertas_{ano}.csv`) contém uma linha por empenho flagrado.
As 9 colunas são:

| Coluna | O que significa |
|--------|----------------|
| `item` | Descrição do medicamento conforme consta no empenho da prefeitura |
| `fornecedor` | Nome da empresa que forneceu o medicamento |
| `cnpj` | CNPJ da empresa fornecedora |
| `preco_pago` | Preço unitário pago pela prefeitura (R$/unidade) |
| `preco_bps` | Mediana nacional do BPS para aquele medicamento, ajustada em +15% para SP |
| `desvio_pct` | Diferença percentual entre o preço pago e o preço de referência BPS ajustado |
| `tier` | Nível de alerta: ATENÇÃO, ALERTA, CRÍTICO ou SEM_REFERÊNCIA |
| `valor_excedente` | Quanto dinheiro público foi pago a mais naquela compra (R$) |
| `narrativa_ia` | Comentário gerado por inteligência artificial resumindo o alerta (quando disponível) |

---

## O que é "Valor Excedente"?

O valor excedente representa **quanto de dinheiro público foi pago a mais** em relação ao
preço justo de mercado naquela compra específica.

**Exemplo simples:** Se o preço de referência BPS (ajustado para SP) é R$ 1,15 por comprimido,
e a prefeitura comprou 10.000 comprimidos a R$ 3,50 cada:

- Desvio: ((3,50 - 1,15) / 1,15) × 100 = **+204%** → nível CRÍTICO
- Valor excedente: (3,50 - 1,15) × 10.000 = **R$ 23.500,00**

Esse R$ 23.500,00 é o valor que poderia ter sido economizado se a compra tivesse ocorrido
pelo preço de referência nacional. É o número mais relevante para comunicação pública, porque
expressa o impacto fiscal em reais, não só em percentual.

---

## Perguntas a fazer antes de publicar

Antes de publicar uma reportagem baseada nos alertas, verifique:

1. **A prefeitura explica o preço alto?** Solicite nota oficial. Pode haver justificativa
   formal no processo licitatório (dispensa de licitação, emergência declarada, item especial).

2. **Houve declaração de emergência?** Compras emergenciais frequentemente têm preços mais
   altos por urgência logística. Verifique o tipo de licitação no empenho original.

3. **O item tem especificação diferente?** "Dipirona 500mg" pode se referir a formulações
   distintas (gotas, comprimidos, ampola EV). Preços de apresentações diferentes são
   incomparáveis diretamente.

4. **Outros municípios pagaram quanto?** Compare com municípios de porte similar usando o
   Portal da Transparência Federal ou outros dados do BPS.

5. **O fornecedor tem histórico?** Pesquise o CNPJ no Portal da Transparência Federal
   para ver se a empresa fornece para outros entes públicos e a que preços.

6. **Quantos registros BPS sustentam a referência?** Veja o campo implícito nos dados —
   referências baseadas em poucos registros nacionais são menos confiáveis.

7. **Qual é a data do empenho?** Preços de medicamentos variam com o tempo. Compare o
   preço BPS da época, não o atual.

---

## O que NÃO fazer com estes dados

- **Não publicar como "prova de corrupção"** — os alertas são indícios para investigação,
  não evidência de crime. A corrupção requer prova de dolo, prejuízo e enriquecimento ilícito.

- **Não nomear pessoas** — o sistema identifica empresas (CNPJs) e empenhos, não indivíduos.
  Identificar responsáveis pessoais requer apuração adicional.

- **Não usar apenas o desvio percentual sem o valor absoluto** — um desvio de 500% numa
  compra de R$ 50 é menos relevante para o interesse público do que um desvio de 50% numa
  compra de R$ 500.000.

- **Não comparar medicamentos com nomes similares mas apresentações diferentes** — verifique
  se a unidade de medida (comprimido, ampola, frasco) é a mesma antes de comparar preços.

- **Confirmar com a Prefeitura antes de publicar** — o contraditório é essencial e pode
  revelar informações que mudam completamente o contexto.

---

## Onde obter os dados originais

- **Portal de Transparência de Sorocaba:** [transparencia.sorocaba.sp.gov.br](https://transparencia.sorocaba.sp.gov.br/)
  — Empenhos, contratos e notas de empenho da Secretaria de Saúde

- **BPS — Banco de Preços em Saúde:** [bps.saude.gov.br](https://bps.saude.gov.br/)
  — Referência nacional de preços de medicamentos do SUS

- **Portal da Transparência Federal:** [portaltransparencia.gov.br](https://portaltransparencia.gov.br/)
  — Fornecedores, contratos e transferências federais por CNPJ

- **Consulta CNPJ BrasilAPI:** [brasilapi.com.br/api/cnpj/v1/{cnpj}](https://brasilapi.com.br/api/cnpj/v1/)
  — Situação cadastral, data de abertura e atividade da empresa

- **CATMAT — Catálogo de Materiais:** [comprasnet.gov.br](https://www.comprasnet.gov.br/)
  — Códigos e especificações técnicas dos medicamentos

---

## Disclaimer Legal

Os dados apresentados neste projeto são integralmente públicos, obtidos de fontes oficiais do
governo federal e municipal. O sistema MedAudit SUS é uma ferramenta de inteligência cívica
para apoio à investigação jornalística e ao controle social.

**Este relatório apresenta alertas para investigação, não conclusões de ilegalidade.**
Qualquer uso das informações aqui contidas para fins de acusação pública deve ser precedido
de verificação independente, contraditório com os envolvidos e assessoria jurídica.

Os autores não se responsabilizam pelo uso indevido dos dados ou conclusões extraídas
sem o rigor metodológico necessário.
