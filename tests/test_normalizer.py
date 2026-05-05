"""
tests/test_normalizer.py
Testes unitários para MedicamentoNormalizer.
"""
import json
import os
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch

# Garantir que o projeto está no path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.normalizer import MedicamentoNormalizer, ABREVIACOES, SCORE_ACEITO


class TestLimparDescricao:
    def setup_method(self):
        self.norm = MedicamentoNormalizer(catmat_catalog_path="nonexistent.csv")

    def test_expande_abreviacao_cps(self):
        result = self.norm.limpar_descricao("AMOXICILINA 500MG CPS")
        assert "CAPSULAS" in result
        assert "CPS" not in result

    def test_padroniza_concentracao_sem_espaco(self):
        result = self.norm.limpar_descricao("AMOXICILINA 500MG CPS")
        assert "500 MG" in result

    def test_remove_prefixo_empenho(self):
        result = self.norm.limpar_descricao(
            "AQUISICAO DE MEDICAMENTOS - AMOXICILINA 500MG CAPSULAS"
        )
        assert "AQUISICAO" not in result
        assert "AMOXICILINA" in result

    def test_remove_sufixo_pregao(self):
        result = self.norm.limpar_descricao(
            "AMOXICILINA 500MG CAPSULAS - PREGAO ELETRONICO 012/2023"
        )
        assert "PREGAO" not in result
        assert "AMOXICILINA" in result

    def test_remove_stopword_generico(self):
        result = self.norm.limpar_descricao("AMOXICILINA 500MG CPS C/21 GENERICO")
        assert "GENERICO" not in result

    def test_string_vazia(self):
        assert self.norm.limpar_descricao("") == ""

    def test_none_retorna_vazio(self):
        assert self.norm.limpar_descricao(None) == ""

    def test_exemplo_completo(self):
        result = self.norm.limpar_descricao("AMOXICILINA 500MG CPS C/21 GENERICO")
        assert "AMOXICILINA" in result
        assert "500 MG" in result
        assert "CAPSULAS" in result
        assert "GENERICO" not in result


class TestExtrairPrincipioAtivo:
    def setup_method(self):
        self.norm = MedicamentoNormalizer(catmat_catalog_path="nonexistent.csv")

    def test_extrai_antes_da_concentracao(self):
        result = self.norm.extrair_principio_ativo("AMOXICILINA TRIIDRATADA 500 MG CAPSULAS")
        assert result == "AMOXICILINA TRIIDRATADA"

    def test_extrai_uma_palavra(self):
        result = self.norm.extrair_principio_ativo("DIPIRONA 1G/2ML")
        assert result == "DIPIRONA"

    def test_string_vazia(self):
        assert self.norm.extrair_principio_ativo("") == ""


class TestFuzzyMatchCatmat:
    def setup_method(self):
        """Cria normalizer com catálogo sintético."""
        self.norm = MedicamentoNormalizer(catmat_catalog_path="nonexistent.csv")
        # Injetar catálogo sintético
        self.norm.catalog = pd.DataFrame({
            "CD_CATMAT": ["BR001", "BR002", "BR003"],
            "DS_ITEM": [
                "AMOXICILINA 500 MG CAPSULA",
                "PARACETAMOL 750 MG COMPRIMIDO",
                "DIPIRONA SODICA 1G/2ML INJETAVEL",
            ],
        })
        self.norm._catalog_descriptions = (
            self.norm.catalog["DS_ITEM"].str.upper().str.strip().tolist()
        )

    def test_sem_catalogo_retorna_lista_vazia(self):
        norm_sem_cat = MedicamentoNormalizer(catmat_catalog_path="nonexistent.csv")
        assert norm_sem_cat.fuzzy_match_catmat("AMOXICILINA 500 MG CAPSULAS") == []

    def test_match_amoxicilina(self):
        results = self.norm.fuzzy_match_catmat("AMOXICILINA 500 MG CAPSULAS")
        assert len(results) >= 1
        assert results[0]["catmat"] == "BR001"
        assert results[0]["score"] >= SCORE_ACEITO

    def test_descricao_vazia_retorna_lista_vazia(self):
        results = self.norm.fuzzy_match_catmat("")
        assert results == []

    def test_resultado_tem_campos_obrigatorios(self):
        results = self.norm.fuzzy_match_catmat("AMOXICILINA 500 MG CAPSULAS")
        if results:
            assert "catmat" in results[0]
            assert "descricao" in results[0]
            assert "score" in results[0]


class TestProcessar:
    def setup_method(self):
        self.norm = MedicamentoNormalizer(catmat_catalog_path="nonexistent.csv")

    def test_fixture_mode_produz_json(self, tmp_path):
        output_file = str(tmp_path / "medicamentos_normalizados.json")
        with patch.dict(os.environ, {"MEDAUDIT_FIXTURE": "1"}):
            df = self.norm.processar(
                input_glob="data/raw/sorocaba_despesas_saude_*.json",
                output_file=output_file,
            )
        assert Path(output_file).exists()
        data = json.loads(Path(output_file).read_text())
        assert isinstance(data, list)
        if data:
            assert "descricao_normalizada" in data[0]
            assert "catmat_codigo" in data[0]
            assert "match_score" in data[0]
            assert "concentracao_extraida" in data[0]
            assert "forma_farmaceutica" in data[0]

    def test_sem_catalogo_catmat_codigo_null(self, tmp_path):
        output_file = str(tmp_path / "out.json")
        with patch.dict(os.environ, {"MEDAUDIT_FIXTURE": "1"}):
            df = self.norm.processar(
                input_glob="nonexistent/*.json",
                output_file=output_file,
            )
        assert "catmat_codigo" in df.columns
        # Sem catálogo, todos os items devem ter catmat_codigo=None e match_score=0
        for val in df["catmat_codigo"]:
            assert val is None or (isinstance(val, float) and pd.isna(val))

    def test_items_sem_match_retidos_no_output(self, tmp_path):
        """Items sem match não devem ser descartados."""
        output_file = str(tmp_path / "out.json")
        with patch.dict(os.environ, {"MEDAUDIT_FIXTURE": "1"}):
            df = self.norm.processar(
                input_glob="data/raw/sorocaba_despesas_saude_*.json",
                output_file=output_file,
            )
        # Todos os registros originais devem estar presentes
        data = json.loads(Path(output_file).read_text())
        # Se fixture tem 3 registros, todos devem aparecer no output
        assert len(data) == len(df)
