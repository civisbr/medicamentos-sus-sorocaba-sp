"""
exporter.py
Exporta os resultados da análise em múltiplos formatos:
- alertas_{ano}.csv: CSV com 9 colunas + disclaimer legal (REQ-008)
- summary.json: dados estruturados para o dashboard HTML (REQ-010)
- relatorio_completo.html: relatório auto-contido sem dependências externas (REQ-009)
"""

import io
import json
import math
import urllib.parse
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader


# ---------------------------------------------------------------------------
# Constantes de módulo
# ---------------------------------------------------------------------------

MAPA_COLUNAS = {
    "descricao_item": "item",
    "nome_fornecedor": "fornecedor",
    "cnpj_fornecedor": "cnpj",
    "preco_unitario_pago": "preco_pago",
    "preco_bps_mediana": "preco_bps",
    "variacao_percentual": "desvio_pct",
    "nivel_alerta": "tier",
    "valor_excedente_total": "valor_excedente",
}

COLUNAS_REQ008 = [
    "item",
    "fornecedor",
    "cnpj",
    "preco_pago",
    "preco_bps",
    "desvio_pct",
    "tier",
    "valor_excedente",
    "narrativa_ia",
]

DISCLAIMER = (
    "# Dados públicos — Portal Transparência Sorocaba · BPS/MS · "
    "Gerado por MedAudit SUS. "
    "Este arquivo apresenta alertas para investigação, não conclusões de ilegalidade."
)


def _safe_float(v) -> Optional[float]:
    """Converte v para float, retornando None para NaN/None (serializa como JSON null)."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Classe Exporter
# ---------------------------------------------------------------------------


class Exporter:

    def gerar_csv(
        self,
        alertas_df: pd.DataFrame,
        ano: int,
        output_file: str,
    ) -> None:
        """
        Gera CSV de alertas com 9 colunas (REQ-008) + disclaimer como primeira linha.

        Args:
            alertas_df: DataFrame com as 12 colunas originais de alertas_superfaturamento.csv
            ano: Ano de referência (para metadados)
            output_file: Caminho de saída do arquivo CSV
        """
        df_out = alertas_df.rename(columns=MAPA_COLUNAS)
        if "narrativa_ia" not in df_out.columns:
            df_out = df_out.copy()
            df_out["narrativa_ia"] = ""

        # Selecionar e ordenar colunas conforme REQ-008
        df_out = df_out[COLUNAS_REQ008].copy()
        df_out = df_out.sort_values("valor_excedente", ascending=False)

        # Montar conteúdo com disclaimer na primeira linha
        buf = io.StringIO()
        buf.write(DISCLAIMER + "\n")
        df_out.to_csv(buf, index=False, encoding="utf-8")

        # Criar diretório pai e gravar arquivo
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(buf.getvalue(), encoding="utf-8")

    def gerar_summary(
        self,
        alertas_file: str,
        output_file: str,
        ano: int = 2023,
        fornecedores_file: Optional[str] = None,
    ) -> dict:
        """
        Gera o summary.json consumido pelo dashboard HTML (REQ-010).

        Args:
            alertas_file: Caminho para alertas_superfaturamento.csv
            output_file: Caminho de saída do summary.json
            ano: Ano de referência
            fornecedores_file: Caminho para fornecedores_suspeitos.csv (opcional)

        Returns:
            dict com a estrutura completa do summary
        """
        # Ler alertas (gracioso se arquivo ausente)
        alertas_path = Path(alertas_file)
        if alertas_path.exists():
            alertas_df = pd.read_csv(str(alertas_path))
        else:
            alertas_df = pd.DataFrame()

        # Calcular totais
        total_empenhos = len(alertas_df)

        if not alertas_df.empty and "nivel_alerta" in alertas_df.columns:
            contagem = alertas_df["nivel_alerta"].value_counts()
            alertas_atencao = int(contagem.get("ATENÇÃO", 0))
            alertas_alerta = int(contagem.get("ALERTA", 0))
            alertas_criticos = int(contagem.get("CRÍTICO", 0))
        else:
            alertas_atencao = alertas_alerta = alertas_criticos = 0

        if not alertas_df.empty and "valor_excedente_total" in alertas_df.columns:
            valor_total = float(alertas_df["valor_excedente_total"].sum())
        else:
            valor_total = 0.0

        # Ler fornecedores (gracioso se arquivo ausente)
        fornecedores_df = pd.DataFrame()
        if fornecedores_file:
            forn_path = Path(fornecedores_file)
            if forn_path.exists():
                fornecedores_df = pd.read_csv(str(forn_path))

        qtd_fornecedores_suspeitos = len(fornecedores_df) if not fornecedores_df.empty else 0

        # Período de análise
        if not alertas_df.empty and "data_empenho" in alertas_df.columns:
            datas = pd.to_datetime(alertas_df["data_empenho"], errors="coerce").dropna()
            inicio = datas.min().strftime("%Y-%m-%d") if not datas.empty else f"{ano}-01-01"
            fim = datas.max().strftime("%Y-%m-%d") if not datas.empty else f"{ano}-12-31"
        else:
            inicio = f"{ano}-01-01"
            fim = f"{ano}-12-31"

        # Top 5 itens por valor_excedente_total
        top_itens = []
        if not alertas_df.empty and "valor_excedente_total" in alertas_df.columns:
            top_df = alertas_df.nlargest(5, "valor_excedente_total")
            for _, row in top_df.iterrows():
                top_itens.append({
                    "descricao": str(row.get("descricao_item", "")),
                    "preco_pago": _safe_float(row.get("preco_unitario_pago")),
                    "preco_bps": _safe_float(row.get("preco_bps_mediana")),
                    "variacao": _safe_float(row.get("variacao_percentual")),
                    "valor_excedente_total": _safe_float(row.get("valor_excedente_total")),
                    "nivel": str(row.get("nivel_alerta", "")),
                })

        # Top 5 fornecedores
        top_fornecedores = []
        if not fornecedores_df.empty and "valor_excedente_total" in fornecedores_df.columns:
            top_forn_df = fornecedores_df.nlargest(5, "valor_excedente_total")
            for _, row in top_forn_df.iterrows():
                top_fornecedores.append({
                    "cnpj": str(row.get("cnpj_fornecedor", "")),
                    "razao_social": str(row.get("nome_fornecedor", "")),
                    "total_alertas": int(row.get("total_alertas", 0) or 0),
                    "valor_excedente_total": float(row.get("valor_excedente_total", 0) or 0),
                    "nivel_risco": "SUSPEITO" if row.get("tier_suspeito") else "OK",
                })
        elif not alertas_df.empty and "cnpj_fornecedor" in alertas_df.columns:
            # Fallback: calcular agrupando alertas por CNPJ
            grp = (
                alertas_df.groupby(["cnpj_fornecedor", "nome_fornecedor"])
                .agg(
                    total_alertas=("nr_empenho", "count"),
                    valor_excedente_total=("valor_excedente_total", "sum"),
                )
                .reset_index()
                .nlargest(5, "valor_excedente_total")
            )
            for _, row in grp.iterrows():
                top_fornecedores.append({
                    "cnpj": str(row.get("cnpj_fornecedor", "")),
                    "razao_social": str(row.get("nome_fornecedor", "")),
                    "total_alertas": int(row.get("total_alertas", 0) or 0),
                    "valor_excedente_total": float(row.get("valor_excedente_total", 0) or 0),
                    "nivel_risco": "DESCONHECIDO",
                })

        # Distribuição de alertas
        distribuicao = {
            "ATENÇÃO": alertas_atencao,
            "ALERTA": alertas_alerta,
            "CRÍTICO": alertas_criticos,
        }

        summary = {
            "gerado_em": datetime.now().isoformat(),
            "municipio": "Sorocaba",
            "ano": ano,
            "periodo_analise": {"inicio": inicio, "fim": fim},
            "totais": {
                "empenhos_analisados": total_empenhos,
                "alertas_atencao": alertas_atencao,
                "alertas_alerta": alertas_alerta,
                "alertas_criticos": alertas_criticos,
                "valor_total_excedente": valor_total,
                "fornecedores_suspeitos": qtd_fornecedores_suspeitos,
            },
            "top_itens": top_itens,
            "top_fornecedores": top_fornecedores,
            "distribuicao_alertas": distribuicao,
        }

        # Salvar JSON
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return summary

    def gerar_html(
        self,
        alertas_file: str,
        ai_narrative_file: str,
        output_file: str,
        ano: int = 2023,
        fornecedores_file: Optional[str] = None,
    ) -> str:
        """
        Gera relatório HTML auto-contido, sem dependências externas (REQ-009).

        Args:
            alertas_file: Caminho para alertas_superfaturamento.csv
            ai_narrative_file: Caminho para analise_ia.md (pode não existir — --skip-ai)
            output_file: Caminho de saída do relatório HTML
            ano: Ano de referência
            fornecedores_file: Caminho para fornecedores_suspeitos.csv (opcional)

        Returns:
            String com o conteúdo HTML gerado
        """
        template_dir = Path(__file__).parent.parent / "templates"
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=False,  # Dados JSON em <script> não devem ser escaped
        )
        template = env.get_template("relatorio.html.j2")

        # Ler alertas (gracioso se arquivo ausente)
        alertas_path = Path(alertas_file)
        if alertas_path.exists():
            alertas_df = pd.read_csv(str(alertas_path))
            alertas = alertas_df.to_dict("records")
        else:
            alertas_df = pd.DataFrame()
            alertas = []

        # Ler fornecedores (gracioso se arquivo ausente)
        fornecedores = []
        if fornecedores_file:
            forn_path = Path(fornecedores_file)
            if forn_path.exists():
                forn_df = pd.read_csv(str(forn_path))
                fornecedores = forn_df.to_dict("records")

        # Narrativa IA (None quando --skip-ai)
        narrativa_ia = None
        ai_path = Path(ai_narrative_file)
        if ai_path.exists():
            narrativa_ia = ai_path.read_text(encoding="utf-8")

        # Calcular totais para os cards de resumo
        if not alertas_df.empty and "nivel_alerta" in alertas_df.columns:
            contagem = alertas_df["nivel_alerta"].value_counts()
            alertas_criticos = int(contagem.get("CRÍTICO", 0))
        else:
            alertas_criticos = 0

        if not alertas_df.empty and "valor_excedente_total" in alertas_df.columns:
            valor_total = float(alertas_df["valor_excedente_total"].sum())
        else:
            valor_total = 0.0

        totais = {
            "empenhos_analisados": len(alertas),
            "alertas_criticos": alertas_criticos,
            "valor_total_excedente": valor_total,
            "fornecedores_suspeitos": len(fornecedores),
        }

        # CSV data URI para botão de download inline
        buf = io.StringIO()
        buf.write(DISCLAIMER + "\n")
        if not alertas_df.empty:
            alertas_df.to_csv(buf, index=False, encoding="utf-8")
        csv_content = buf.getvalue()
        csv_data_uri = "data:text/csv;charset=utf-8," + urllib.parse.quote(csv_content)
        csv_tamanho_kb = max(1, len(csv_content.encode("utf-8")) // 1024)

        # Renderizar template
        html = template.render(
            ano=ano,
            gerado_em=datetime.now().isoformat(),
            narrativa_ia=narrativa_ia,
            alertas=alertas,
            fornecedores=fornecedores,
            totais=totais,
            csv_data_uri=csv_data_uri,
            csv_tamanho_kb=csv_tamanho_kb,
        )

        # Criar diretório pai e gravar HTML
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")

        return html
