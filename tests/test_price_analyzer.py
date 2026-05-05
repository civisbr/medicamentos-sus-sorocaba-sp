"""
tests/test_price_analyzer.py
Testes unitários e de integração para PriceAnalyzer.

Suite TDD cobrindo critérios de sucesso da Phase 3:
- Classificação correta de alertas (ATENÇÃO/ALERTA/CRÍTICO/SEM_REFERÊNCIA)
- Guarda mínima de 5 registros BPS (nunca CRÍTICO com < 5)
- Output com exatamente 12 colunas
- Ordenação por valor_excedente_total DESC
- Comportamento defensivo quando BPS ausente
"""
import json
import os
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzers.price_analyzer import PriceAnalyzer

COLUNAS_ESPERADAS = [
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


class TestClassificarAlerta:
    """Testes unitários para os métodos já implementados (passam no RED)."""

    def setup_method(self):
        self.analyzer = PriceAnalyzer(
            threshold_atencao=30,
            threshold_alerta=100,
            threshold_critico=200,
        )

    def test_250_pct_acima_bps_e_critico(self):
        """Critério de sucesso Phase 3 item 2: 250% acima do BPS mediano → CRÍTICO."""
        # BPS mediano = R$1.00, SP ajustado = R$1.15
        # Preço pago = R$4.04 → variação = (4.04 - 1.15) / 1.15 * 100 = 251.3%
        variacao = self.analyzer.calcular_variacao(preco_pago=4.04, preco_referencia=1.15)
        assert variacao > 250, f"Esperado > 250%, obtido {variacao:.2f}%"
        nivel = self.analyzer.classificar_alerta(variacao)
        assert nivel == "CRÍTICO", f"Esperado CRÍTICO, obtido {nivel}"

    def test_150_pct_e_alerta_nao_critico(self):
        """130% acima do BPS → ALERTA (não CRÍTICO)."""
        # preco_pago=2.645, preco_ref=1.15 → variação ≈ 130%
        variacao = self.analyzer.calcular_variacao(preco_pago=2.645, preco_referencia=1.15)
        assert 100 <= variacao < 200, f"Esperado entre 100% e 200%, obtido {variacao:.2f}%"
        nivel = self.analyzer.classificar_alerta(variacao)
        assert nivel == "ALERTA", f"Esperado ALERTA, obtido {nivel}"

    def test_40_pct_e_atencao(self):
        """40% acima do BPS → ATENÇÃO."""
        # preco_pago=1.61, preco_ref=1.15 → variação ≈ 40%
        variacao = self.analyzer.calcular_variacao(preco_pago=1.61, preco_referencia=1.15)
        assert 30 <= variacao < 100, f"Esperado entre 30% e 100%, obtido {variacao:.2f}%"
        nivel = self.analyzer.classificar_alerta(variacao)
        assert nivel == "ATENÇÃO", f"Esperado ATENÇÃO, obtido {nivel}"

    def test_ok_abaixo_limiar(self):
        """4.3% acima do BPS → OK."""
        # preco_pago=1.20, preco_ref=1.15 → variação ≈ 4.3%
        variacao = self.analyzer.calcular_variacao(preco_pago=1.20, preco_referencia=1.15)
        assert variacao < 30, f"Esperado < 30%, obtido {variacao:.2f}%"
        nivel = self.analyzer.classificar_alerta(variacao)
        assert nivel == "OK", f"Esperado OK, obtido {nivel}"

    def test_sem_referencia_quando_nan(self):
        """classificar_alerta(float('nan')) → SEM_REFERÊNCIA."""
        nivel = self.analyzer.classificar_alerta(float("nan"))
        assert nivel == "SEM_REFERÊNCIA", f"Esperado SEM_REFERÊNCIA, obtido {nivel}"


class TestAnalisar:
    """Testes de integração para PriceAnalyzer.analisar() — RED no commit 1, GREEN no commit 2."""

    def setup_method(self):
        self.analyzer = PriceAnalyzer(
            threshold_atencao=30,
            threshold_alerta=100,
            threshold_critico=200,
        )
        self._bps_fixture = str(
            Path(__file__).parent.parent / "data" / "fixtures" / "bps_precos_referencia_sample.csv"
        )
        self._med_fixture = str(
            Path(__file__).parent.parent / "data" / "processed" / "medicamentos_normalizados.json"
        )

    def test_output_tem_12_colunas(self, tmp_path):
        """analisar() retorna DataFrame com exatamente as 12 colunas esperadas."""
        output_file = str(tmp_path / "alertas_superfaturamento.csv")
        df = self.analyzer.analisar(
            despesas_file=self._med_fixture,
            bps_file=self._bps_fixture,
            output_file=output_file,
        )
        assert isinstance(df, pd.DataFrame), "analisar() deve retornar um DataFrame"
        for col in COLUNAS_ESPERADAS:
            assert col in df.columns, f"Coluna ausente no output: {col}"
        assert set(df.columns) == set(COLUNAS_ESPERADAS), (
            f"Colunas extras ou ausentes. Esperado: {sorted(COLUNAS_ESPERADAS)}, "
            f"Obtido: {sorted(df.columns.tolist())}"
        )

    def test_sem_bps_retorna_sem_referencia(self, tmp_path):
        """analisar() com bps_file inexistente → nivel_alerta == SEM_REFERÊNCIA para todos."""
        output_file = str(tmp_path / "alertas_sem_bps.csv")
        df = self.analyzer.analisar(
            despesas_file=self._med_fixture,
            bps_file="/nao/existe/bps.csv",
            output_file=output_file,
        )
        assert isinstance(df, pd.DataFrame), "analisar() deve retornar DataFrame mesmo sem BPS"
        assert Path(output_file).exists(), "CSV deve ser salvo mesmo sem BPS"
        assert len(df) > 0, "DataFrame não deve ser vazio quando despesas existem"
        assert all(df["nivel_alerta"] == "SEM_REFERÊNCIA"), (
            "Todos os itens devem ser SEM_REFERÊNCIA quando BPS ausente"
        )

    def test_sem_critico_com_menos_5_registros_bps(self, tmp_path):
        """CLAUDE.md: item com QT_REGISTROS=3 e preço 300% acima → ALERTA, nunca CRÍTICO."""
        # Criar despesas fictícias com catmat_codigo apontando para DIPIRONA (QT_REGISTROS=3)
        despesas = [
            {
                "nr_empenho": "2023NE099999",
                "dt_empenho": "2023-01-01",
                "vl_empenho": 50000,
                "cd_cnpj_cpf_fornecedor": "CNPJ - PESSOA JURIDICA - 46634044000174",
                "nm_fornecedor": "TESTE LTDA",
                "ds_historico": "DIPIRONA 2ML INJETAVEL",
                "descricao_normalizada": "DIPIRONA SODICA 500 MG/ML SOLUCAO INJETAVEL 2 ML",
                "catmat_codigo": "BR0301455",  # DIPIRONA — QT_REGISTROS=3
                "catmat_descricao": "DIPIRONA SODICA 500MG ML SOLUCAO INJETAVEL 2ML",
                "match_score": 95.0,
                "concentracao_extraida": "500 MG",
                "forma_farmaceutica": "SOLUCAO",
                "cd_municipio": 6667,
                "nm_municipio": "SOROCABA",
                "cd_orgao": 2,
                "nm_orgao": "SECRETARIA MUNICIPAL DA SAUDE",
                "cd_funcao": 10,
                "nm_funcao": "Saude",
                "cd_elemento": "33.90.30",
                "nm_elemento": "Material de Consumo",
                "nm_programa": "Urgencia",
                "nm_acao": "Atendimento",
            }
        ]
        despesas_file = str(tmp_path / "despesas_dipirona.json")
        Path(despesas_file).write_text(
            json.dumps(despesas, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        output_file = str(tmp_path / "alertas_dipirona.csv")
        df = self.analyzer.analisar(
            despesas_file=despesas_file,
            bps_file=self._bps_fixture,
            output_file=output_file,
        )
        assert len(df) == 1, "Deve ter exatamente 1 linha"
        # Preço BPS mediana DIPIRONA = 1.60; SP ajustado = 1.60 * 1.15 = 1.84
        # vl_empenho = 50000 como proxy → variação enorme → seria CRÍTICO sem guarda
        nivel = df.iloc[0]["nivel_alerta"]
        assert nivel != "CRÍTICO", (
            f"Item com QT_REGISTROS=3 nunca pode ser CRÍTICO. Obtido: {nivel}"
        )

    def test_valor_excedente_total_ordenado_desc(self, tmp_path):
        """DataFrame retornado por analisar() deve estar ordenado por valor_excedente_total DESC."""
        output_file = str(tmp_path / "alertas_ordenados.csv")
        df = self.analyzer.analisar(
            despesas_file=self._med_fixture,
            bps_file=self._bps_fixture,
            output_file=output_file,
        )
        if len(df) > 1:
            valores = df["valor_excedente_total"].tolist()
            assert valores == sorted(valores, reverse=True), (
                f"DataFrame não está ordenado por valor_excedente_total DESC: {valores}"
            )

    def test_csv_e_salvo_em_output_file(self, tmp_path):
        """analisar() deve salvar o CSV em output_file."""
        output_file = str(tmp_path / "subdir" / "alertas.csv")
        self.analyzer.analisar(
            despesas_file=self._med_fixture,
            bps_file=self._bps_fixture,
            output_file=output_file,
        )
        assert Path(output_file).exists(), f"CSV não foi salvo em {output_file}"

    def test_cnpj_extraido_corretamente(self, tmp_path):
        """cnpj_fornecedor deve conter apenas dígitos, não o formato TCE-SP completo."""
        output_file = str(tmp_path / "alertas.csv")
        df = self.analyzer.analisar(
            despesas_file=self._med_fixture,
            bps_file=self._bps_fixture,
            output_file=output_file,
        )
        for cnpj in df["cnpj_fornecedor"].dropna():
            assert "CNPJ" not in str(cnpj), (
                f"CNPJ deve ser numérico, não o formato TCE-SP: {cnpj}"
            )
            assert "PESSOA JURIDICA" not in str(cnpj), (
                f"CNPJ deve ser numérico: {cnpj}"
            )


class TestGerarEstatisticas:
    """Testes para PriceAnalyzer.gerar_estatisticas()."""

    def setup_method(self):
        self.analyzer = PriceAnalyzer(
            threshold_atencao=30,
            threshold_alerta=100,
            threshold_critico=200,
        )

    def test_gerar_estatisticas_retorna_dict_com_chaves_obrigatorias(self):
        """gerar_estatisticas() deve retornar dict com as 5 chaves obrigatórias."""
        alertas_df = pd.DataFrame([
            {
                "nr_empenho": "2023NE001234",
                "descricao_item": "AMOXICILINA 500 MG",
                "cnpj_fornecedor": "46634044000174",
                "nome_fornecedor": "FARMA LTDA",
                "nivel_alerta": "CRÍTICO",
                "valor_excedente_total": 10000.0,
            },
            {
                "nr_empenho": "2023NE002345",
                "descricao_item": "ATORVASTATINA 20 MG",
                "cnpj_fornecedor": "11222333000181",
                "nome_fornecedor": "MEDPHARMA LTDA",
                "nivel_alerta": "ALERTA",
                "valor_excedente_total": 5000.0,
            },
        ])
        resultado = self.analyzer.gerar_estatisticas(alertas_df)
        assert isinstance(resultado, dict), "gerar_estatisticas() deve retornar dict"
        chaves_obrigatorias = [
            "total_empenhos_analisados",
            "total_alertas",
            "valor_total_excedente",
            "top_10_itens_por_excedente",
            "top_10_fornecedores_por_excedente",
        ]
        for chave in chaves_obrigatorias:
            assert chave in resultado, f"Chave ausente em gerar_estatisticas(): {chave}"
        assert resultado["total_empenhos_analisados"] == 2
        assert resultado["valor_total_excedente"] == 15000.0
        assert isinstance(resultado["total_alertas"], dict)
        assert "CRÍTICO" in resultado["total_alertas"]
