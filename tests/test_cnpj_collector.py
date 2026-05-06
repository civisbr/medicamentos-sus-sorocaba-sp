"""
tests/test_cnpj_collector.py
Suite TDD para CNPJCollector — STAB-03 e STAB-05

STAB-03: empresa_nova=True/False como booleano explícito no resultado
STAB-05: enriquecer_fornecedores() preserva CNPJs existentes (merge por CNPJ)
"""
import json
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.cnpj_collector import CNPJCollector, avaliar_risco_cnpj_standalone


# ---------------------------------------------------------------------------
# Fixtures de dados BrasilAPI reais (conforme documentado em RESEARCH.md)
# ---------------------------------------------------------------------------

def _dados_cnpj_empresa_nova(data_abertura: str) -> dict:
    """Fixture: empresa com data de abertura recente."""
    return {
        "cnpj": "11222333000181",
        "razao_social": "FARMACIA NOVA LTDA",
        "situacao_cadastral": "ATIVA",
        "data_inicio_atividade": data_abertura,
        "data_abertura": None,
    }


def _dados_cnpj_empresa_antiga(data_abertura: str) -> dict:
    """Fixture: empresa com data de abertura antiga."""
    return {
        "cnpj": "11222333000181",
        "razao_social": "FARMACIA ANTIGA LTDA",
        "situacao_cadastral": "ATIVA",
        "data_inicio_atividade": data_abertura,
        "data_abertura": None,
    }


def _dados_cnpj_sem_data_abertura() -> dict:
    """Fixture: empresa sem campo data_abertura (edge case STAB-03)."""
    return {
        "cnpj": "11222333000181",
        "razao_social": "FARMACIA SEM DATA LTDA",
        "situacao_cadastral": "ATIVA",
        # data_inicio_atividade ausente, data_abertura ausente, abertura ausente
    }


def _empenho(cnpj_numerico: str, data: str = "2023-06-01") -> dict:
    """Fixture: empenho com CNPJ e data."""
    return {
        "cd_cnpj_cpf_fornecedor": f"CNPJ - PESSOA JURIDICA - {cnpj_numerico}",
        "dt_empenho": data,
        "ds_historico": "MEDICAMENTO TESTE",
        "vl_empenho": 1000.0,
    }


# ---------------------------------------------------------------------------
# TestEmpresaNovaBool — STAB-03
# ---------------------------------------------------------------------------

class TestEmpresaNovaBool:
    """Verifica que enriquecer_fornecedores() retorna empresa_nova: bool em todos os cenários."""

    def _executar_enriquecimento(self, tmp_path: Path, dados_cnpj: dict | None,
                                  data_empenho: str = "2023-06-01") -> dict:
        """Helper: executa enriquecer_fornecedores() e retorna o único entry do resultado."""
        # CNPJ válido (dígito verificador correto)
        cnpj_numerico = "46634044000174"
        empenhos = [_empenho(cnpj_numerico, data_empenho)]

        input_file = tmp_path / "despesas.json"
        input_file.write_text(json.dumps(empenhos), encoding="utf-8")
        output_file = tmp_path / "fornecedores.json"

        coletor = CNPJCollector()
        with patch.object(coletor, "consultar", return_value=dados_cnpj):
            resultado = coletor.enriquecer_fornecedores(
                input_file=str(input_file),
                output_file=str(output_file),
            )

        assert len(resultado) == 1, f"Esperado 1 entry, got {len(resultado)}"
        return resultado[0]

    def test_empresa_nova_true_quando_abertura_recente(self, tmp_path):
        """empresa_nova=True quando data_inicio_atividade < 6 meses antes do empenho."""
        # Empenho em 2023-06-01; abertura 3 meses antes = 2023-03-01 → < 6 meses → nova
        dados = _dados_cnpj_empresa_nova("2023-03-01")
        entry = self._executar_enriquecimento(tmp_path, dados, data_empenho="2023-06-01")

        assert "empresa_nova" in entry, "Campo 'empresa_nova' ausente no resultado"
        assert entry["empresa_nova"] is True, (
            f"Esperado empresa_nova=True, got: {entry['empresa_nova']}"
        )

    def test_empresa_nova_false_quando_abertura_antiga(self, tmp_path):
        """empresa_nova=False quando data_inicio_atividade >= 6 meses antes do empenho."""
        # Empenho em 2023-06-01; abertura 2 anos antes = 2021-06-01 → >= 6 meses → não nova
        dados = _dados_cnpj_empresa_antiga("2021-06-01")
        entry = self._executar_enriquecimento(tmp_path, dados, data_empenho="2023-06-01")

        assert "empresa_nova" in entry, "Campo 'empresa_nova' ausente no resultado"
        assert entry["empresa_nova"] is False, (
            f"Esperado empresa_nova=False, got: {entry['empresa_nova']}"
        )

    def test_empresa_nova_false_quando_campo_data_ausente(self, tmp_path):
        """empresa_nova=False quando dados_cnpj não tem campo data_abertura (edge case STAB-03)."""
        dados = _dados_cnpj_sem_data_abertura()
        entry = self._executar_enriquecimento(tmp_path, dados, data_empenho="2023-06-01")

        assert "empresa_nova" in entry, "Campo 'empresa_nova' ausente no resultado"
        assert entry["empresa_nova"] is False, (
            f"Esperado empresa_nova=False quando data_abertura ausente, got: {entry['empresa_nova']}"
        )

    def test_empresa_nova_false_quando_dados_api_none(self, tmp_path):
        """empresa_nova=False quando dados_api é None (CNPJ não encontrado na BrasilAPI)."""
        entry = self._executar_enriquecimento(tmp_path, dados_cnpj=None, data_empenho="2023-06-01")

        assert "empresa_nova" in entry, "Campo 'empresa_nova' ausente no resultado"
        assert entry["empresa_nova"] is False, (
            f"Esperado empresa_nova=False quando dados_api=None, got: {entry['empresa_nova']}"
        )

    def test_empresa_nova_false_quando_data_abertura_vazia(self, tmp_path):
        """empresa_nova=False quando data_abertura é string vazia."""
        dados = {
            "cnpj": "11222333000181",
            "situacao_cadastral": "ATIVA",
            "data_inicio_atividade": "",  # string vazia
            "data_abertura": "",
        }
        entry = self._executar_enriquecimento(tmp_path, dados, data_empenho="2023-06-01")

        assert "empresa_nova" in entry, "Campo 'empresa_nova' ausente no resultado"
        assert entry["empresa_nova"] is False, (
            f"Esperado empresa_nova=False quando data_abertura vazia, got: {entry['empresa_nova']}"
        )

    def test_empresa_nova_e_tipo_bool(self, tmp_path):
        """empresa_nova deve ser do tipo bool (não string, não int)."""
        dados = _dados_cnpj_empresa_nova("2023-03-01")
        entry = self._executar_enriquecimento(tmp_path, dados, data_empenho="2023-06-01")

        assert isinstance(entry["empresa_nova"], bool), (
            f"empresa_nova deve ser bool, got: {type(entry['empresa_nova'])}"
        )


# ---------------------------------------------------------------------------
# TestMergePorCNPJ — STAB-05
# ---------------------------------------------------------------------------

class TestMergePorCNPJ:
    """Verifica que enriquecer_fornecedores() preserva CNPJs existentes no output_file."""

    CNPJ_A = "46634044000174"  # CNPJ válido
    CNPJ_B = "11222333000181"  # CNPJ válido

    def _executar_enriquecimento(self, tmp_path: Path, cnpjs: list[str],
                                  output_file: Path) -> list[dict]:
        """Helper: executa enriquecer_fornecedores() com lista de CNPJs mockados."""
        empenhos = [_empenho(cnpj) for cnpj in cnpjs]
        input_file = tmp_path / "despesas.json"
        input_file.write_text(json.dumps(empenhos), encoding="utf-8")

        coletor = CNPJCollector()
        with patch.object(coletor, "consultar", return_value=None):
            return coletor.enriquecer_fornecedores(
                input_file=str(input_file),
                output_file=str(output_file),
            )

    def test_cnpj_existente_preservado_quando_novo_ano_processado(self, tmp_path):
        """CNPJs do primeiro run devem estar presentes após o segundo run com CNPJ diferente."""
        output_file = tmp_path / "fornecedores_enriquecidos.json"

        # Primeiro run: CNPJ_A
        self._executar_enriquecimento(tmp_path, [self.CNPJ_A], output_file)
        cnpjs_apos_run1 = {
            e["cnpj"] for e in json.loads(output_file.read_text())
        }
        assert self.CNPJ_A in cnpjs_apos_run1

        # Segundo run: CNPJ_B (diferente)
        self._executar_enriquecimento(tmp_path, [self.CNPJ_B], output_file)
        cnpjs_apos_run2 = {
            e["cnpj"] for e in json.loads(output_file.read_text())
        }

        # Ambos devem estar presentes (merge preservou CNPJ_A)
        assert self.CNPJ_A in cnpjs_apos_run2, (
            f"CNPJ_A ({self.CNPJ_A}) foi perdido após segundo run. CNPJs presentes: {cnpjs_apos_run2}"
        )
        assert self.CNPJ_B in cnpjs_apos_run2

    def test_cnpj_duplicado_sobrescrito_pelo_mais_recente(self, tmp_path):
        """Quando mesmo CNPJ aparece em dois runs, o segundo (mais recente) deve prevalecer."""
        output_file = tmp_path / "fornecedores_enriquecidos.json"

        # Primeiro run: CNPJ_A com dados_api=None
        self._executar_enriquecimento(tmp_path, [self.CNPJ_A], output_file)

        # Segundo run: CNPJ_A com dados_api simulado
        empenhos = [_empenho(self.CNPJ_A, "2024-01-01")]
        input_file = tmp_path / "despesas2.json"
        input_file.write_text(json.dumps(empenhos), encoding="utf-8")

        dados_novos = {"cnpj": self.CNPJ_A, "razao_social": "FARMACIA ATUALIZADA LTDA"}
        coletor = CNPJCollector()
        with patch.object(coletor, "consultar", return_value=dados_novos):
            coletor.enriquecer_fornecedores(
                input_file=str(input_file),
                output_file=str(output_file),
            )

        merged = json.loads(output_file.read_text())
        entry_a = next((e for e in merged if e["cnpj"] == self.CNPJ_A), None)
        assert entry_a is not None
        # Entry mais recente deve ter dados_api preenchido (não None)
        assert entry_a["dados_api"] is not None, (
            "Esperado que dados_api do segundo run sobrescrevesse None do primeiro"
        )

    def test_arquivo_inexistente_nao_causa_erro(self, tmp_path):
        """Quando output_file não existe ainda, enriquecer_fornecedores() deve funcionar normalmente."""
        output_file = tmp_path / "novo_arquivo.json"
        assert not output_file.exists()  # garantir que não existe

        resultado = self._executar_enriquecimento(tmp_path, [self.CNPJ_A], output_file)

        assert output_file.exists(), "output_file deve ser criado mesmo sem arquivo prévio"
        assert len(resultado) >= 0  # pode ser 0 se CNPJ inválido, mas não deve lançar exceção
