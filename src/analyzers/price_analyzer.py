"""
price_analyzer.py
Núcleo da análise de superfaturamento.

Compara preços pagos pela Prefeitura de Sorocaba com os preços
de referência do BPS e classifica o nível de alerta.

Metodologia completa em: docs/METODOLOGIA.md
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process as fuzz_process
from rich.console import Console

from src.collectors.cnpj_collector import extrair_cnpj
from src.utils.normalizer import SCORE_ACEITO

logger = logging.getLogger(__name__)
console = Console()
_ROOT = Path(__file__).parent.parent.parent


# Thresholds de alerta (podem ser sobrescritos via env/CLI)
THRESHOLD_ATENCAO = 30   # 30-99% acima do BPS → ATENÇÃO
THRESHOLD_ALERTA = 100   # 100-199% acima do BPS → ALERTA
THRESHOLD_CRITICO = 200  # >=200% acima do BPS → CRÍTICO

# Score mínimo para fallback fuzzy no join BPS
_SCORE_FUZZY_MIN = 70

# Colunas do output de alertas
COLUNAS_ALERTAS = [
    "nr_empenho",
    "data_empenho",
    "descricao_item",
    "catmat_codigo",
    "cnpj_fornecedor",
    "nome_fornecedor",
    "preco_unitario_pago",
    "preco_bps_mediana",
    "variacao_percentual",
    "nivel_alerta",
    "valor_excedente_total",
    "qt_registros_bps",
]


class PriceAnalyzer:
    """
    Detecta superfaturamento comparando preço pago com BPS.

    Fórmula principal:
        variacao = ((preco_pago - preco_bps_mediana) / preco_bps_mediana) * 100

    Se variacao > threshold → alerta gerado.

    Importante:
    - Usar mediana BPS (não média) para ser menos sensível a outliers
    - Considerar variação regional (SP costuma ter preços até 15% maiores)
    - Descontar itens com poucos registros no BPS (<5 compras) — menos confiáveis
    - Normalizar unidades antes de comparar (ex: caixa com 30cp vs unidade)
    """

    def __init__(
        self,
        threshold_atencao: int = THRESHOLD_ATENCAO,
        threshold_alerta: int = THRESHOLD_ALERTA,
        threshold_critico: int = THRESHOLD_CRITICO,
        margem_regional_sp: float = 0.15  # SP pode ser 15% mais caro — descontar
    ):
        self.threshold_atencao = threshold_atencao
        self.threshold_alerta = threshold_alerta
        self.threshold_critico = threshold_critico
        self.margem_regional_sp = margem_regional_sp

    def _carregar_bps(self, bps_file: str) -> Optional[pd.DataFrame]:
        """Carrega e valida o CSV de preços de referência BPS."""
        p = Path(bps_file)
        if not p.exists():
            logger.warning(
                f"BPS não encontrado: {bps_file} — classificando tudo como SEM_REFERÊNCIA"
            )
            return None
        try:
            df = pd.read_csv(bps_file, dtype=str)
            df.columns = [c.strip().upper() for c in df.columns]
            # Validar colunas obrigatórias (T-03-01-01)
            required_cols = {"CD_CATMAT", "VL_PRECO_MEDIANO", "QT_REGISTROS"}
            if not required_cols.issubset(df.columns):
                missing = required_cols - set(df.columns)
                logger.warning(
                    f"BPS CSV incompleto — colunas ausentes: {missing}. "
                    "Classificando tudo como SEM_REFERÊNCIA."
                )
                return None
            # Converter preços para float
            for col in ["VL_PRECO_MEDIANO", "VL_PRECO_MINIMO", "VL_PRECO_MAXIMO", "VL_PRECO_MEDIO"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(
                        df[col].str.replace(",", "."), errors="coerce"
                    )
            if "QT_REGISTROS" in df.columns:
                df["QT_REGISTROS"] = (
                    pd.to_numeric(df["QT_REGISTROS"], errors="coerce")
                    .fillna(0)
                    .astype(int)
                )
            return df
        except Exception as e:
            logger.warning(f"Erro ao carregar BPS: {e} — classificando tudo como SEM_REFERÊNCIA")
            return None

    def _criar_df_sem_referencia(self, df_med: pd.DataFrame) -> pd.DataFrame:
        """Cria DataFrame de alertas com SEM_REFERÊNCIA para todos os itens."""
        registros = []
        for _, row in df_med.iterrows():
            cnpj = extrair_cnpj(str(row.get("cd_cnpj_cpf_fornecedor", "")))
            registros.append({
                "nr_empenho": row.get("nr_empenho"),
                "data_empenho": row.get("dt_empenho"),
                "descricao_item": row.get("descricao_normalizada"),
                "catmat_codigo": row.get("catmat_codigo"),
                "cnpj_fornecedor": cnpj,
                "nome_fornecedor": row.get("nm_fornecedor"),
                "preco_unitario_pago": float(row.get("vl_empenho", 0) or 0),
                "preco_bps_mediana": None,
                "variacao_percentual": None,
                "nivel_alerta": "SEM_REFERÊNCIA",
                "valor_excedente_total": 0.0,
                "qt_registros_bps": 0,
            })
        return pd.DataFrame(registros, columns=COLUNAS_ALERTAS)

    def analisar(
        self,
        despesas_file: str,
        bps_file: str,
        output_file: str
    ) -> pd.DataFrame:
        """
        Análise principal: cruza despesas com BPS e gera alertas de superfaturamento.

        Args:
            despesas_file: JSON com despesas normalizadas (medicamentos_normalizados.json)
            bps_file: CSV com preços de referência BPS
            output_file: Caminho para salvar os alertas CSV

        Returns:
            DataFrame com alertas classificados, ordenado por valor_excedente_total DESC
        """
        # PASSO 1: Carregar despesas (T-03-01-02)
        try:
            df_med = pd.read_json(despesas_file)
            # Validar campos obrigatórios
            required = {"nr_empenho", "vl_empenho", "cd_cnpj_cpf_fornecedor"}
            if not required.issubset(df_med.columns):
                missing = required - set(df_med.columns)
                logger.warning(
                    f"medicamentos_normalizados.json sem campos obrigatórios: {missing}"
                )
                df_empty = pd.DataFrame(columns=COLUNAS_ALERTAS)
                Path(output_file).parent.mkdir(parents=True, exist_ok=True)
                df_empty.to_csv(output_file, index=False, encoding="utf-8")
                return df_empty
        except Exception as e:
            logger.warning(f"Erro ao carregar despesas: {e}")
            df_empty = pd.DataFrame(columns=COLUNAS_ALERTAS)
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            df_empty.to_csv(output_file, index=False, encoding="utf-8")
            return df_empty

        if df_med.empty:
            df_empty = pd.DataFrame(columns=COLUNAS_ALERTAS)
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            df_empty.to_csv(output_file, index=False, encoding="utf-8")
            return df_empty

        # PASSO 2: Extrair CNPJ (T-03-01-03)
        df_med = df_med.copy()
        df_med["cnpj_fornecedor"] = df_med["cd_cnpj_cpf_fornecedor"].apply(
            lambda x: extrair_cnpj(str(x)) if pd.notna(x) else None
        )

        # PASSO 3: Carregar BPS
        df_bps = self._carregar_bps(bps_file)

        if df_bps is None:
            # BPS ausente — retornar SEM_REFERÊNCIA para todos
            df_alertas = self._criar_df_sem_referencia(df_med)
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            df_alertas.to_csv(output_file, index=False, encoding="utf-8")
            console.print(
                f"[yellow]BPS ausente:[/yellow] todos os {len(df_alertas)} itens "
                f"classificados como SEM_REFERÊNCIA → {output_file}"
            )
            return df_alertas

        # PASSO 4: JOIN principal por catmat_codigo (left join)
        # Converter catmat_codigo para string (pode ser NaN/float quando null no JSON)
        df_med["catmat_codigo"] = df_med["catmat_codigo"].apply(
            lambda x: str(x) if pd.notna(x) and x is not None else None
        )
        df_bps["CD_CATMAT"] = df_bps["CD_CATMAT"].astype(str).str.strip()

        df_merged = df_med.merge(
            df_bps[["CD_CATMAT", "VL_PRECO_MEDIANO", "QT_REGISTROS", "SG_UNIDADE_MEDIDA"]],
            left_on="catmat_codigo",
            right_on="CD_CATMAT",
            how="left",
        )

        # PASSO 5: FALLBACK fuzzy para linhas sem join BPS
        sem_bps_mask = df_merged["VL_PRECO_MEDIANO"].isna()
        if sem_bps_mask.any() and "DS_ITEM" in df_bps.columns:
            bps_descriptions = df_bps["DS_ITEM"].str.upper().str.strip().tolist()
            for idx in df_merged[sem_bps_mask].index:
                desc = str(df_merged.at[idx, "descricao_normalizada"] or "")
                if not desc:
                    continue
                match = fuzz_process.extractOne(
                    desc.upper(),
                    bps_descriptions,
                    scorer=fuzz.token_set_ratio,
                    score_cutoff=_SCORE_FUZZY_MIN,
                )
                if match is not None:
                    matched_desc, score, match_idx = match
                    bps_row = df_bps.iloc[match_idx]
                    df_merged.at[idx, "VL_PRECO_MEDIANO"] = bps_row["VL_PRECO_MEDIANO"]
                    df_merged.at[idx, "QT_REGISTROS"] = bps_row["QT_REGISTROS"]
                    df_merged.at[idx, "SG_UNIDADE_MEDIDA"] = bps_row.get("SG_UNIDADE_MEDIDA", "")

        # PASSO 6: Calcular variação, classificar alertas e valor excedente
        registros = []
        for _, row in df_merged.iterrows():
            preco_mediano = row.get("VL_PRECO_MEDIANO")
            qt_registros = int(row.get("QT_REGISTROS", 0) or 0)
            vl_empenho = float(row.get("vl_empenho", 0) or 0)

            if pd.isna(preco_mediano) or preco_mediano is None or float(preco_mediano) <= 0:
                # Sem referência BPS
                registros.append({
                    "nr_empenho": row.get("nr_empenho"),
                    "data_empenho": row.get("dt_empenho"),
                    "descricao_item": row.get("descricao_normalizada"),
                    "catmat_codigo": row.get("catmat_codigo"),
                    "cnpj_fornecedor": row.get("cnpj_fornecedor"),
                    "nome_fornecedor": row.get("nm_fornecedor"),
                    "preco_unitario_pago": vl_empenho,
                    "preco_bps_mediana": None,
                    "variacao_percentual": None,
                    "nivel_alerta": "SEM_REFERÊNCIA",
                    "valor_excedente_total": 0.0,
                    "qt_registros_bps": qt_registros,
                })
                continue

            preco_mediano = float(preco_mediano)
            preco_ref_ajustado = preco_mediano * (1 + self.margem_regional_sp)
            variacao = self.calcular_variacao(vl_empenho, preco_ref_ajustado)

            # Classificar nível de alerta (baseado em variação)
            nivel_alerta = self.classificar_alerta(variacao)

            # Calcular valor excedente (proxy proporcional quando quantidade indisponível)
            if not pd.isna(variacao) and variacao > 0:
                fator = (variacao / 100) / (1 + variacao / 100)
                valor_excedente_total = vl_empenho * fator
            else:
                valor_excedente_total = 0.0

            registros.append({
                "nr_empenho": row.get("nr_empenho"),
                "data_empenho": row.get("dt_empenho"),
                "descricao_item": row.get("descricao_normalizada"),
                "catmat_codigo": row.get("catmat_codigo"),
                "cnpj_fornecedor": row.get("cnpj_fornecedor"),
                "nome_fornecedor": row.get("nm_fornecedor"),
                "preco_unitario_pago": vl_empenho,
                "preco_bps_mediana": preco_mediano,
                "variacao_percentual": round(variacao, 2) if not pd.isna(variacao) else None,
                "nivel_alerta": nivel_alerta,
                "valor_excedente_total": round(valor_excedente_total, 2),
                "qt_registros_bps": qt_registros,
            })

        df_alertas = pd.DataFrame(registros, columns=COLUNAS_ALERTAS)

        # PASSO 7: Guarda mínima — nunca CRÍTICO com qt_registros_bps < 5
        mask_critico_sem_base = (
            (df_alertas["nivel_alerta"] == "CRÍTICO")
            & (df_alertas["qt_registros_bps"] < 5)
        )
        df_alertas.loc[mask_critico_sem_base, "nivel_alerta"] = "ALERTA"

        # PASSO 8: Ordenar por valor_excedente_total DESC
        df_alertas = df_alertas.sort_values(
            "valor_excedente_total", ascending=False
        ).reset_index(drop=True)

        # PASSO 9: Salvar CSV
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        df_alertas.to_csv(output_file, index=False, encoding="utf-8")

        n_criticos = (df_alertas["nivel_alerta"] == "CRÍTICO").sum()
        n_alertas = (df_alertas["nivel_alerta"] == "ALERTA").sum()
        console.print(
            f"[green]Alertas gerados:[/green] {output_file} "
            f"({len(df_alertas)} itens | {n_criticos} CRÍTICO | {n_alertas} ALERTA)"
        )

        return df_alertas

    def calcular_variacao(self, preco_pago: float, preco_referencia: float) -> float:
        """
        Calcula a variação percentual entre preço pago e referência.

        variacao = ((preco_pago - preco_ref) / preco_ref) * 100

        Positivo = superfaturamento, negativo = preço abaixo do mercado.
        """
        if preco_referencia <= 0:
            return np.nan
        return ((preco_pago - preco_referencia) / preco_referencia) * 100

    def classificar_alerta(self, variacao: float) -> str:
        """
        Classifica o nível de alerta com base na variação percentual.

        Returns: "OK" | "ATENÇÃO" | "ALERTA" | "CRÍTICO" | "SEM_REFERÊNCIA"
        """
        if pd.isna(variacao):
            return "SEM_REFERÊNCIA"
        if variacao >= self.threshold_critico:
            return "CRÍTICO"
        if variacao >= self.threshold_alerta:
            return "ALERTA"
        if variacao >= self.threshold_atencao:
            return "ATENÇÃO"
        return "OK"

    def calcular_valor_excedente(
        self,
        preco_pago: float,
        preco_referencia: float,
        quantidade: float
    ) -> float:
        """
        Calcula o valor total pago a mais em relação ao preço de referência.

        excedente = (preco_pago - preco_ref) * quantidade

        Esse é o número que representa "quanto dinheiro público foi desperdiçado
        nessa compra específica" — o mais impactante para comunicação pública.
        """
        excedente_unitario = preco_pago - preco_referencia
        if excedente_unitario <= 0:
            return 0.0
        return excedente_unitario * quantidade

    def gerar_estatisticas(self, alertas_df: pd.DataFrame) -> dict:
        """
        Gera estatísticas agregadas para o relatório.

        Returns:
            dict com:
            - total_empenhos_analisados
            - total_alertas (dict por nível)
            - valor_total_excedente
            - top_10_itens_por_excedente (lista de dicts)
            - top_10_fornecedores_por_excedente (lista de dicts)
        """
        contagem_niveis = alertas_df["nivel_alerta"].value_counts().to_dict()

        top_itens = (
            alertas_df.nlargest(10, "valor_excedente_total")[
                ["descricao_item", "valor_excedente_total", "nivel_alerta"]
            ].to_dict("records")
        )

        top_fornecedores = (
            alertas_df.groupby(["cnpj_fornecedor", "nome_fornecedor"])[
                "valor_excedente_total"
            ]
            .sum()
            .nlargest(10)
            .reset_index()
            .to_dict("records")
        )

        return {
            "total_empenhos_analisados": len(alertas_df),
            "total_alertas": contagem_niveis,
            "valor_total_excedente": float(alertas_df["valor_excedente_total"].sum()),
            "top_10_itens_por_excedente": top_itens,
            "top_10_fornecedores_por_excedente": top_fornecedores,
        }
