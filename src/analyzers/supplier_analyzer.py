"""
supplier_analyzer.py
Análise de risco por fornecedor para o pipeline MedAudit SUS.

Agrupa alertas por CNPJ, calcula score de risco ponderado e identifica
padrões de concentração anormal de contratos ou irregularidades cadastrais.
"""

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

_ROOT = Path(__file__).parent.parent.parent

PESOS_ALERTA = {
    "CRÍTICO": 3,
    "ALERTA": 2,
    "ATENÇÃO": 1,
    "OK": 0,
    "SEM_REFERÊNCIA": 0,
}
PESO_EMPRESA_NOVA = 2
PESO_SITUACAO_IRREGULAR = 3
THRESHOLD_CONCENTRACAO = 0.60   # 60% do volume total → SUSPEITO
MIN_CRITICOS_SUSPEITO = 3       # 3+ alertas CRÍTICO → SUSPEITO


class SupplierAnalyzer:
    """
    Classifica fornecedores por risco de superfaturamento.

    Flags de risco:
    - CNPJ com < 2 anos de existência na data do contrato (reusada do cnpj_collector)
    - Situação cadastral irregular (reusada do cnpj_collector)
    - Concentração anormal de contratos (>60% do volume para 1 CNPJ)
    - 3+ alertas CRÍTICO no mesmo período de análise → tier SUSPEITO
    """

    def _calcular_score_fornecedor(
        self,
        alertas_df: pd.DataFrame,
        cnpj_data: dict,
        valor_total_todos: float = 0.0,
    ) -> dict:
        """
        Calcula score de risco para um único fornecedor.

        Args:
            alertas_df: DataFrame com alertas do fornecedor (nivel_alerta, valor_excedente_total)
            cnpj_data: Entrada do fornecedores_enriquecidos.json para este CNPJ (ou {})
            valor_total_todos: Soma de valor_excedente_total de TODOS os alertas (para concentração)

        Returns:
            dict com: tier_suspeito, alertas_criticos, score_risco, flag_empresa_nova,
                      flag_situacao_irregular, data_abertura_cnpj
        """
        alertas_criticos = int((alertas_df["nivel_alerta"] == "CRÍTICO").sum())

        # Score ponderado por tier de alerta
        score_risco = sum(
            PESOS_ALERTA.get(nivel, 0)
            for nivel in alertas_df["nivel_alerta"]
        )

        # Flags CNPJ — reusar flags_risco já calculadas pelo cnpj_collector
        flags_risco = cnpj_data.get("flags_risco", [])
        flag_empresa_nova = "empresa_nova" in flags_risco
        flag_situacao_irregular = "situacao_irregular" in flags_risco

        # Adicionar peso das flags ao score
        score_risco += PESO_EMPRESA_NOVA * int(flag_empresa_nova)
        score_risco += PESO_SITUACAO_IRREGULAR * int(flag_situacao_irregular)

        # Concentração de valor excedente deste fornecedor sobre total
        valor_fornecedor = float(alertas_df["valor_excedente_total"].sum())
        concentracao = (valor_fornecedor / valor_total_todos) if valor_total_todos > 0 else 0.0

        # Tier SUSPEITO: 3+ CRÍTICO OU concentração > 60%
        tier_suspeito = bool(
            alertas_criticos >= MIN_CRITICOS_SUSPEITO
            or concentracao > THRESHOLD_CONCENTRACAO
        )

        # Data de abertura do CNPJ
        dados_api = cnpj_data.get("dados_api", {})
        data_abertura = (
            dados_api.get("data_inicio_atividade")
            or dados_api.get("data_abertura")
            or ""
        )

        return {
            "tier_suspeito": tier_suspeito,
            "alertas_criticos": alertas_criticos,
            "score_risco": float(score_risco),
            "flag_empresa_nova": flag_empresa_nova,
            "flag_situacao_irregular": flag_situacao_irregular,
            "data_abertura_cnpj": str(data_abertura),
        }

    def analisar(
        self,
        alertas_file: str,
        cnpj_file: str,
        output_file: str,
    ) -> None:
        """
        Agrupa alertas por fornecedor, calcula score de risco e salva relatório.

        Args:
            alertas_file: Caminho para CSV de alertas classificados (alertas_superfaturamento.csv).
            cnpj_file: Caminho para JSON de fornecedores enriquecidos (fornecedores_enriquecidos.json).
            output_file: Caminho para CSV de saída com fornecedores suspeitos (fornecedores_suspeitos.csv).
        """
        # 1. Carregar alertas CSV
        alertas_path = Path(alertas_file)
        if not alertas_path.exists():
            logger.warning(f"Arquivo de alertas não encontrado: {alertas_file}")
            return
        try:
            df_alertas = pd.read_csv(alertas_file, dtype=str)
        except Exception as e:
            logger.warning(f"Falha ao ler alertas CSV {alertas_file}: {e}")
            return

        # Validar colunas obrigatórias
        required_cols = {"cnpj_fornecedor", "nivel_alerta", "valor_excedente_total"}
        missing = required_cols - set(df_alertas.columns)
        if missing:
            logger.warning(f"Colunas obrigatórias ausentes em {alertas_file}: {missing}")
            return

        # Converter valor_excedente_total para float
        df_alertas["valor_excedente_total"] = pd.to_numeric(
            df_alertas["valor_excedente_total"], errors="coerce"
        ).fillna(0.0)

        # 2. Carregar fornecedores enriquecidos (defensivo — arquivo pode não existir)
        cnpj_map: dict = {}
        cnpj_path = Path(cnpj_file)
        if cnpj_path.exists():
            try:
                with open(cnpj_path, encoding="utf-8") as f:
                    fornecedores_data = json.load(f)
                cnpj_map = {entry["cnpj"]: entry for entry in fornecedores_data}
            except Exception as e:
                logger.warning(
                    f"Falha ao carregar {cnpj_file}: {e} — flags CNPJ serão False"
                )
        else:
            logger.warning(
                f"Arquivo de fornecedores não encontrado: {cnpj_file} — flags CNPJ serão False"
            )

        # 3. Valor total de todos os alertas para cálculo de concentração
        valor_total_todos = float(df_alertas["valor_excedente_total"].sum())

        # 4. Agrupar por cnpj_fornecedor (LEFT — todos os CNPJs dos alertas presentes)
        resultados = []
        for cnpj, grupo in df_alertas.groupby("cnpj_fornecedor", dropna=False):
            cnpj_str = str(cnpj) if pd.notna(cnpj) else ""
            cnpj_data = cnpj_map.get(cnpj_str, {})
            nome = (
                grupo["nome_fornecedor"].iloc[0]
                if "nome_fornecedor" in grupo.columns
                else ""
            )

            score_info = self._calcular_score_fornecedor(grupo, cnpj_data, valor_total_todos)

            resultados.append({
                "cnpj_fornecedor": cnpj_str,
                "nome_fornecedor": nome,
                "total_alertas": len(grupo),
                "alertas_criticos": score_info["alertas_criticos"],
                "score_risco": score_info["score_risco"],
                "tier_suspeito": score_info["tier_suspeito"],
                "valor_excedente_total": float(grupo["valor_excedente_total"].sum()),
                "flag_empresa_nova": score_info["flag_empresa_nova"],
                "flag_situacao_irregular": score_info["flag_situacao_irregular"],
                "data_abertura_cnpj": score_info["data_abertura_cnpj"],
            })

        df_suspeitos = pd.DataFrame(resultados)

        if not df_suspeitos.empty:
            df_suspeitos = df_suspeitos.sort_values("valor_excedente_total", ascending=False)
            # Garantir ordem das colunas
            colunas_ordenadas = [
                "cnpj_fornecedor", "nome_fornecedor", "total_alertas", "alertas_criticos",
                "score_risco", "tier_suspeito", "valor_excedente_total",
                "flag_empresa_nova", "flag_situacao_irregular", "data_abertura_cnpj",
            ]
            df_suspeitos = df_suspeitos[colunas_ordenadas]

        # 5. Salvar CSV
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        df_suspeitos.to_csv(output_file, index=False, encoding="utf-8")

        n_suspeitos = int(df_suspeitos["tier_suspeito"].sum()) if not df_suspeitos.empty else 0
        console.print(
            f"[green]Fornecedores suspeitos:[/green] {output_file} "
            f"({n_suspeitos} SUSPEITO / {len(df_suspeitos)} total)"
        )
