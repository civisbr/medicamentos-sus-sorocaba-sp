"""
tests/test_supplier_analyzer.py
Testes unitários e de integração para SupplierAnalyzer.
"""
import json
import os
import pytest
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzers.supplier_analyzer import SupplierAnalyzer

COLUNAS_ESPERADAS = [
    "cnpj_fornecedor", "nome_fornecedor", "total_alertas", "alertas_criticos",
    "score_risco", "tier_suspeito", "valor_excedente_total",
    "flag_empresa_nova", "flag_situacao_irregular", "data_abertura_cnpj"
]

# Fixtures sintéticas compartilhadas
ALERTAS_SINTETICOS = [
    {
        "cnpj_fornecedor": "12345678000195",
        "nome_fornecedor": "FARMA A LTDA",
        "nivel_alerta": "CRÍTICO",
        "valor_excedente_total": 10000.0,
        "nr_empenho": "E001",
        "descricao_item": "AMOXICILINA 500MG",
        "variacao_percentual": 250.0,
    },
    {
        "cnpj_fornecedor": "12345678000195",
        "nome_fornecedor": "FARMA A LTDA",
        "nivel_alerta": "CRÍTICO",
        "valor_excedente_total": 8000.0,
        "nr_empenho": "E002",
        "descricao_item": "ATORVASTATINA 20MG",
        "variacao_percentual": 220.0,
    },
    {
        "cnpj_fornecedor": "12345678000195",
        "nome_fornecedor": "FARMA A LTDA",
        "nivel_alerta": "CRÍTICO",
        "valor_excedente_total": 5000.0,
        "nr_empenho": "E003",
        "descricao_item": "LOSARTANA 50MG",
        "variacao_percentual": 210.0,
    },
    {
        "cnpj_fornecedor": "98765432000110",
        "nome_fornecedor": "MEDPHARMA LTDA",
        "nivel_alerta": "ATENÇÃO",
        "valor_excedente_total": 500.0,
        "nr_empenho": "E004",
        "descricao_item": "DIPIRONA 500MG",
        "variacao_percentual": 40.0,
    },
]

FORNECEDORES_SINTETICOS = [
    {
        "cnpj": "12345678000195",
        "dados_api": {
            "situacao_cadastral": 2,
            "data_inicio_atividade": "2022-12-01",
            "razao_social": "FARMA A LTDA",
        },
        "flags_risco": ["empresa_nova"],
        "data_empenho_referencia": "2023-03-15",
    },
    {
        "cnpj": "98765432000110",
        "dados_api": {
            "situacao_cadastral": 2,
            "data_inicio_atividade": "2010-05-10",
            "razao_social": "MEDPHARMA LTDA",
        },
        "flags_risco": [],
        "data_empenho_referencia": "2023-06-20",
    },
]


class TestCalcularScoreFornecedor:
    """Testa _calcular_score_fornecedor() diretamente com DataFrames sintéticos em memória."""

    def setup_method(self):
        self.analyzer = SupplierAnalyzer()

    def test_fornecedor_com_3_criticos_e_suspeito(self):
        """Critério de sucesso Phase 3 item 3: 3+ alertas CRÍTICO → tier_suspeito=True."""
        alertas_df = pd.DataFrame([
            {"cnpj_fornecedor": "12345678000195", "nome_fornecedor": "FARMA TESTE LTDA",
             "nivel_alerta": "CRÍTICO", "valor_excedente_total": 10000.0},
            {"cnpj_fornecedor": "12345678000195", "nome_fornecedor": "FARMA TESTE LTDA",
             "nivel_alerta": "CRÍTICO", "valor_excedente_total": 8000.0},
            {"cnpj_fornecedor": "12345678000195", "nome_fornecedor": "FARMA TESTE LTDA",
             "nivel_alerta": "CRÍTICO", "valor_excedente_total": 5000.0},
        ])
        resultado = self.analyzer._calcular_score_fornecedor(alertas_df, cnpj_data={})
        assert resultado["tier_suspeito"] is True
        assert resultado["alertas_criticos"] == 3

    def test_fornecedor_com_2_criticos_nao_suspeito(self):
        """2 alertas CRÍTICO e sem outras flags → tier_suspeito=False."""
        alertas_df = pd.DataFrame([
            {"cnpj_fornecedor": "12345678000195", "nome_fornecedor": "FARMA TESTE LTDA",
             "nivel_alerta": "CRÍTICO", "valor_excedente_total": 5000.0},
            {"cnpj_fornecedor": "12345678000195", "nome_fornecedor": "FARMA TESTE LTDA",
             "nivel_alerta": "CRÍTICO", "valor_excedente_total": 3000.0},
        ])
        resultado = self.analyzer._calcular_score_fornecedor(
            alertas_df, cnpj_data={}, valor_total_todos=100000.0
        )
        assert resultado["tier_suspeito"] is False

    def test_flag_empresa_nova_lida_do_json(self):
        """Fornecedor com flags_risco=['empresa_nova'] → flag_empresa_nova=True."""
        alertas_df = pd.DataFrame([
            {"cnpj_fornecedor": "12345678000195", "nome_fornecedor": "FARMA A LTDA",
             "nivel_alerta": "ALERTA", "valor_excedente_total": 2000.0},
        ])
        cnpj_data = {
            "cnpj": "12345678000195",
            "dados_api": {"situacao_cadastral": 2, "data_inicio_atividade": "2022-12-01"},
            "flags_risco": ["empresa_nova"],
        }
        resultado = self.analyzer._calcular_score_fornecedor(alertas_df, cnpj_data=cnpj_data)
        assert resultado["flag_empresa_nova"] is True

    def test_flag_situacao_irregular(self):
        """Fornecedor com situacao_cadastral != 2 e flags_risco com 'situacao_irregular' → flag=True."""
        alertas_df = pd.DataFrame([
            {"cnpj_fornecedor": "12345678000195", "nome_fornecedor": "FARMA A LTDA",
             "nivel_alerta": "ALERTA", "valor_excedente_total": 2000.0},
        ])
        cnpj_data = {
            "cnpj": "12345678000195",
            "dados_api": {"situacao_cadastral": 4, "data_inicio_atividade": "2010-05-10"},
            "flags_risco": ["situacao_irregular"],
        }
        resultado = self.analyzer._calcular_score_fornecedor(alertas_df, cnpj_data=cnpj_data)
        assert resultado["flag_situacao_irregular"] is True

    def test_score_risco_calculado_corretamente(self):
        """Score ponderado: 3 alertas CRÍTICO (3*3=9) + empresa_nova (2) = 11."""
        alertas_df = pd.DataFrame([
            {"cnpj_fornecedor": "12345678000195", "nivel_alerta": "CRÍTICO",
             "valor_excedente_total": 5000.0},
            {"cnpj_fornecedor": "12345678000195", "nivel_alerta": "CRÍTICO",
             "valor_excedente_total": 3000.0},
            {"cnpj_fornecedor": "12345678000195", "nivel_alerta": "CRÍTICO",
             "valor_excedente_total": 2000.0},
        ])
        cnpj_data = {"flags_risco": ["empresa_nova"]}
        resultado = self.analyzer._calcular_score_fornecedor(
            alertas_df, cnpj_data=cnpj_data, valor_total_todos=10000.0
        )
        # 3x CRÍTICO = 9, empresa_nova = 2 → total = 11
        assert resultado["score_risco"] == 11.0


class TestAnalisar:
    """Testa analisar() com tmp_path do pytest — independente de arquivos reais."""

    def setup_method(self):
        self.analyzer = SupplierAnalyzer()

    def _criar_arquivos_sinteticos(self, tmp_path):
        """Cria arquivos de alertas CSV e fornecedores JSON sintéticos em tmp_path."""
        alertas_file = str(tmp_path / "alertas_superfaturamento.csv")
        cnpj_file = str(tmp_path / "fornecedores_enriquecidos.json")
        output_file = str(tmp_path / "fornecedores_suspeitos.csv")

        pd.DataFrame(ALERTAS_SINTETICOS).to_csv(alertas_file, index=False)
        with open(cnpj_file, "w", encoding="utf-8") as f:
            json.dump(FORNECEDORES_SINTETICOS, f, ensure_ascii=False)

        return alertas_file, cnpj_file, output_file

    def test_concentracao_acima_60_pct_e_suspeito(self, tmp_path):
        """Fornecedor com 70% do valor_excedente_total total → tier_suspeito=True."""
        # FARMA A LTDA tem 10000+8000+5000=23000 de 23500 total = 97.9% → SUSPEITO
        alertas_file, cnpj_file, output_file = self._criar_arquivos_sinteticos(tmp_path)
        self.analyzer.analisar(alertas_file, cnpj_file, output_file)

        # CNPJ deve ser lido como string (CNPJs podem ter zeros à esquerda)
        df = pd.read_csv(output_file, dtype={"cnpj_fornecedor": str})
        farma_a = df[df["cnpj_fornecedor"] == "12345678000195"]
        assert len(farma_a) == 1
        assert farma_a.iloc[0]["tier_suspeito"] is True or farma_a.iloc[0]["tier_suspeito"] == True

    def test_cnpj_sem_dados_enriquecimento_aparece_no_csv(self, tmp_path):
        """CNPJ não presente no cnpj_file aparece no CSV com flags False (left join defensivo)."""
        # Criar alertas com um CNPJ não presente no fornecedores JSON
        alertas_extras = ALERTAS_SINTETICOS + [{
            "cnpj_fornecedor": "11111111000111",
            "nome_fornecedor": "DESCONHECIDO LTDA",
            "nivel_alerta": "ALERTA",
            "valor_excedente_total": 1000.0,
            "nr_empenho": "E999",
            "descricao_item": "MEDICAMENTO X",
            "variacao_percentual": 120.0,
        }]
        alertas_file = str(tmp_path / "alertas.csv")
        cnpj_file = str(tmp_path / "fornecedores.json")
        output_file = str(tmp_path / "suspeitos.csv")

        pd.DataFrame(alertas_extras).to_csv(alertas_file, index=False)
        with open(cnpj_file, "w", encoding="utf-8") as f:
            json.dump(FORNECEDORES_SINTETICOS, f, ensure_ascii=False)

        self.analyzer.analisar(alertas_file, cnpj_file, output_file)

        # CNPJ deve ser lido como string (CNPJs podem ter zeros à esquerda)
        df = pd.read_csv(output_file, dtype={"cnpj_fornecedor": str})
        desconhecido = df[df["cnpj_fornecedor"] == "11111111000111"]
        assert len(desconhecido) == 1
        assert desconhecido.iloc[0]["flag_empresa_nova"] == False
        assert desconhecido.iloc[0]["flag_situacao_irregular"] == False

    def test_output_tem_10_colunas(self, tmp_path):
        """CSV gerado por analisar() tem exatamente as 10 colunas definidas."""
        alertas_file, cnpj_file, output_file = self._criar_arquivos_sinteticos(tmp_path)
        self.analyzer.analisar(alertas_file, cnpj_file, output_file)

        df = pd.read_csv(output_file, dtype={"cnpj_fornecedor": str})
        assert list(df.columns) == COLUNAS_ESPERADAS

    def test_output_ordenado_por_valor_excedente_desc(self, tmp_path):
        """CSV é ordenado por valor_excedente_total decrescente."""
        alertas_file, cnpj_file, output_file = self._criar_arquivos_sinteticos(tmp_path)
        self.analyzer.analisar(alertas_file, cnpj_file, output_file)

        df = pd.read_csv(output_file, dtype={"cnpj_fornecedor": str})
        assert df["valor_excedente_total"].iloc[0] >= df["valor_excedente_total"].iloc[-1]
