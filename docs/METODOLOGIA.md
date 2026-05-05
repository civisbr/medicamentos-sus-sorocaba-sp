# Metodologia de Detecção de Superfaturamento

## Definição

Superfaturamento ocorre quando o preço pago por um item é significativamente superior ao preço de mercado para o mesmo item. Este projeto usa o **Banco de Preços em Saúde (BPS)** do Ministério da Saúde como referência de mercado.

## Por que a Mediana BPS?

O BPS agrega todas as compras federais e estaduais de medicamentos registradas no SCTIE e sistemas similares. Usamos a **mediana** (e não a média) porque:

1. A mediana é menos sensível a outliers (uma compra muito cara não distorce o valor)
2. Representa o valor central praticado pelo mercado
3. É mais difícil de manipular do que a média

## Ajuste Regional

Preços em São Paulo tendem a ser ~15% mais altos do que a mediana nacional, por fatores logísticos e trabalhistas. Por isso, antes de comparar:

```
preco_referencia_ajustado = preco_bps_mediana * (1 + 0.15)
variacao = ((preco_pago - preco_referencia_ajustado) / preco_referencia_ajustado) * 100
```

Isso torna o sistema mais conservador e reduz falsos positivos.

## Critérios de Exclusão (não geram alerta)

- Itens com menos de 5 registros no BPS (amostra insuficiente para referência confiável)
- Medicamentos órfãos ou de uso controlado especial (preços intrinsecamente variáveis)
- Compras de emergência declarada (podem ter preços mais altos por urgência legítima)

## Fórmula do Valor Excedente

```
valor_excedente = (preco_pago - preco_referencia_ajustado) * quantidade
```

Representa o quanto de dinheiro público foi pago a mais em relação ao preço justo de mercado, **naquela compra específica**. É o número mais importante para comunicação pública.

## Limitações

1. **Qualidade dos dados:** Empenhos municipais frequentemente têm descrições inconsistentes, dificultando o match com o catálogo CATMAT.
2. **Contexto de compra:** Uma compra cara pode ser legítima (emergência, item específico, logística).
3. **BPS desatualizado:** O BPS pode não refletir variações recentes de preço.
4. **Dados incompletos:** Nem todas as compras são registradas no portal de transparência.

**Por isso, este sistema gera alertas para investigação — não conclusões.**

## Tiers de Alerta

Os tiers categorizam o grau de desvio do preço pago em relação ao preço de referência ajustado.
O threshold inferior (ATENÇÃO) é configurável via parâmetro `--threshold` (padrão: 30%).
Os demais são fixos conforme REQ-005.

| Tier | Condição de Ativação | Threshold |
|------|---------------------|-----------|
| SEM_REFERÊNCIA | Menos de 5 registros BPS para o item | — (critério de exclusão) |
| ATENÇÃO | variação >= 30% e < 100% | Configurável via `--threshold` (padrão 30%) |
| ALERTA | variação >= 100% e < 200% | Fixo — REQ-005 |
| CRÍTICO | variação >= 200% | Fixo — REQ-005 |

**Regra de exclusão CRÍTICO:** Um item só pode ser classificado como CRÍTICO se tiver pelo
menos 5 registros no BPS nacional. Com menos de 5 registros, o preço de referência não é
considerado confiável e o item recebe SEM_REFERÊNCIA independentemente do desvio calculado.

---

## Fórmulas Completas

As três fórmulas principais do sistema, em ordem de aplicação:

```
preco_referencia_ajustado = preco_bps_mediana * 1.15
variacao_percentual = ((preco_pago - preco_referencia_ajustado) / preco_referencia_ajustado) * 100
valor_excedente_total = (preco_pago - preco_referencia_ajustado) * quantidade_comprada
```

**Fórmula 1 — Ajuste regional SP (+15%):**
A mediana do BPS representa preços nacionais. O coeficiente 1.15 aplica o ajuste para o
estado de São Paulo, onde custos logísticos e trabalhistas são estruturalmente mais altos.
Esse ajuste torna o sistema mais conservador, reduzindo falsos positivos.

**Fórmula 2 — Variação percentual:**
Mede quanto o preço pago desvia do preço de referência ajustado, em percentual.
Valores negativos indicam que a prefeitura pagou menos que a referência (sem alerta).
Valores positivos indicam sobrepreço potencial.

**Fórmula 3 — Valor excedente total:**
Quantifica o impacto fiscal em reais. É o indicador mais relevante para comunicação pública
porque expressa o quanto poderia ter sido economizado naquela compra específica.

---

## Algoritmo de Risco de Fornecedor

O sistema analisa o histórico de cada fornecedor na análise para detectar concentração
anormal de alertas que pode indicar prática sistemática de sobrepreço.

**Score de risco:**
- Calculado por quantidade ponderada de alertas CRÍTICO e ALERTA do mesmo fornecedor
- Alertas CRÍTICO têm peso maior na composição do score

**Critério de classificação SUSPEITO:**
- Fornecedor é marcado como SUSPEITO se acumula 3 ou mais alertas CRÍTICO na mesma análise

**Flags adicionais de risco (verificados via BrasilAPI CNPJ):**

| Flag | Definição |
|------|-----------|
| `empresa_nova` | CNPJ com data de abertura menos de 6 meses antes da data do contrato |
| `situacao_irregular` | Status do CNPJ diferente de "ATIVA" na BrasilAPI no momento da consulta |

Essas flags aumentam o score de risco do fornecedor e são exibidas no relatório como
indicadores adicionais para investigação, não como prova de irregularidade.

---

## Referências

- [BPS - Banco de Preços em Saúde](https://bps.saude.gov.br/)
- [CATMAT - Catálogo de Materiais](https://www.comprasnet.gov.br/seguro/loginPortalAnexos.asp)
- [TCU - Referencial de Combate à Fraude e Corrupção](https://portal.tcu.gov.br/)
- [CGU - Manual de Auditoria em Compras](https://www.gov.br/cgu/)
