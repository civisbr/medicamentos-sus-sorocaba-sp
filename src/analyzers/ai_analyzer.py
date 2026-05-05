"""
ai_analyzer.py
Integração com a Claude API para análise qualitativa dos alertas.

Envia os casos mais críticos para o Claude e recebe um relatório
narrativo que contextualiza os números, prioriza investigações
e sugere perguntas para os responsáveis.

Isso é o que transforma dados brutos em algo que um vereador,
jornalista ou promotor pode usar sem precisar de formação técnica.
"""

import os
import json
import logging
import anthropic
from anthropic import APIError, RateLimitError, AuthenticationError
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Você é um analista especializado em controle de gastos públicos e combate à corrupção no Brasil, com foco em compras de saúde pública.

Você recebe dados de análise de possível superfaturamento em compras de medicamentos de um município brasileiro e deve produzir um relatório objetivo, claro e útil para investigação.

Diretrizes:
- Seja direto e objetivo, sem sensacionalismo
- Sempre considere possíveis explicações legítimas (urgência, especificidade do item, logística)
- Priorize casos por impacto financeiro E consistência (padrão repetido = mais grave)
- Use linguagem acessível — o relatório será lido por pessoas sem formação técnica
- Não acuse diretamente nenhuma pessoa ou empresa — indique para investigação
- Sugira perguntas concretas que devem ser feitas aos responsáveis
- Formate em Markdown para facilitar a leitura"""

USER_PROMPT_TEMPLATE = """Analise os seguintes casos de possível superfaturamento em compras de medicamentos pela Prefeitura de {municipio} ({periodo}).

## Contexto da Análise
- Total de empenhos analisados: {total_empenhos}
- Preço de referência usado: mediana do Banco de Preços em Saúde (BPS/MS) para SP
- Threshold de alerta: {threshold}% acima da mediana BPS

## Top Casos por Valor Excedente

```json
{casos_json}
```

## Top Fornecedores com Mais Alertas

```json
{fornecedores_json}
```

Produza um relatório com as seguintes seções:
1. **Resumo Executivo** (3-5 linhas)
2. **Casos Prioritários para Investigação** (top 5, com justificativa)
3. **Padrões Identificados** (o que os casos têm em comum?)
4. **Possíveis Explicações Legítimas** (o que poderia justificar os preços?)
5. **Perguntas para os Responsáveis** (o que a Câmara Municipal deve perguntar?)
6. **Próximos Passos Recomendados**"""


class AIAnalyzer:
    """
    Usa Claude para gerar análise qualitativa dos alertas de superfaturamento.

    A IA não substitui a análise humana — ela organiza e contextualiza
    os dados para facilitar o trabalho de investigação.
    """

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        # Sem ValueError aqui — validação lazy em analisar()

    def analisar(
        self,
        alertas_file: str,
        output_file: str,
        municipio: str = "Sorocaba",
        periodo: str = "2023",
        top_n: int = 5,
        threshold: int = 30,
    ) -> str | None:
        """
        Envia os top N casos para Claude e salva o relatório narrativo.

        TODO (Claude Code):
        1. Carregar alertas_file (CSV) e filtrar nível CRÍTICO/ALERTA
        2. Ordenar por valor_excedente_total (maior primeiro)
        3. Pegar top_n casos
        4. Agregar fornecedores: GROUP BY cnpj, contar alertas, somar excedente
        5. Montar o prompt usando USER_PROMPT_TEMPLATE
        6. Chamar Claude API (claude-sonnet-4-20250514, max_tokens=4000)
        7. Salvar resposta em output_file (Markdown)
        8. Retornar o texto da análise

        Args:
            alertas_file: CSV com alertas classificados
            output_file: Caminho para salvar o relatório .md
            municipio: Nome do município
            periodo: Período de análise
            top_n: Quantos casos enviar para análise

        Returns:
            Texto do relatório em Markdown
        """

        # Validação lazy da API key
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY não definida — pulando análise IA")
            return None

        # Carregar alertas
        df = pd.read_csv(alertas_file) if Path(alertas_file).exists() else pd.DataFrame()

        if df.empty:
            raise FileNotFoundError(f"Arquivo de alertas não encontrado: {alertas_file}")

        # Preparar dados para o prompt
        top_casos = (
            df.sort_values("valor_excedente_total", ascending=False)
            .head(top_n)
            [[
                "data_empenho", "descricao_item", "cnpj_fornecedor",
                "nome_fornecedor", "preco_unitario_pago", "preco_bps_mediana",
                "variacao_percentual", "valor_excedente_total", "nivel_alerta"
            ]]
            .to_dict("records")
        )

        top_fornecedores = (
            df.groupby(["cnpj_fornecedor", "nome_fornecedor"])
            .agg(
                total_alertas=("nivel_alerta", "count"),
                valor_excedente_total=("valor_excedente_total", "sum"),
                alertas_criticos=("nivel_alerta", lambda x: (x == "CRÍTICO").sum())
            )
            .sort_values("valor_excedente_total", ascending=False)
            .head(10)
            .reset_index()
            .to_dict("records")
        )

        # Montar prompt
        prompt = USER_PROMPT_TEMPLATE.format(
            municipio=municipio,
            periodo=periodo,
            total_empenhos=len(df),
            threshold=threshold,
            casos_json=json.dumps(top_casos, ensure_ascii=False, indent=2),
            fornecedores_json=json.dumps(top_fornecedores, ensure_ascii=False, indent=2)
        )

        # Chamar Claude API com tratamento gracioso de todos os erros
        logger.info("Enviando para análise com Claude API...")
        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
        except AuthenticationError as e:
            logger.warning(f"Autenticação Anthropic falhou: {e} — pulando análise IA")
            return None
        except RateLimitError as e:
            logger.warning(f"Rate limit Anthropic: {e} — pulando análise IA")
            return None
        except APIError as e:
            logger.warning(f"Erro na API Anthropic: {e} — pulando análise IA")
            return None
        except Exception as e:
            logger.warning(f"Erro inesperado Anthropic: {e} — pulando análise IA")
            return None

        relatorio = message.content[0].text

        # Salvar relatório
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Análise de Superfaturamento — {municipio} ({periodo})\n\n")
            f.write("*Gerado automaticamente por MedAudit SUS com Claude API*\n\n")
            f.write("---\n\n")
            f.write(relatorio)

        logger.info(f"Relatório IA salvo: {output_file}")
        return relatorio
