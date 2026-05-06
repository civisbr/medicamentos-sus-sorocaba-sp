"""
tests/test_ai_analyzer.py
Suite TDD para AIAnalyzer — REQ-007

Testa que AIAnalyzer():
  - Instancia sem crash mesmo sem ANTHROPIC_API_KEY
  - analisar() retorna None graciosamente em todos os cenários de erro
  - Usa modelo datado claude-sonnet-4-5-20250929
  - Limita prompt a máximo top_n=5 itens
"""
import json
import os
import re
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.analyzers.ai_analyzer import AIAnalyzer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = [
    "data_empenho",
    "descricao_item",
    "cnpj_fornecedor",
    "nome_fornecedor",
    "preco_unitario_pago",
    "preco_bps_mediana",
    "variacao_percentual",
    "valor_excedente_total",
    "nivel_alerta",
]


def _make_alertas_csv(tmp_path: Path, n: int = 3, nivel: str = "CRÍTICO") -> Path:
    """Cria CSV de alertas temporário com n linhas."""
    rows = []
    for i in range(n):
        rows.append({
            "data_empenho": "2023-06-01",
            "descricao_item": f"MEDICAMENTO {i + 1}",
            "cnpj_fornecedor": f"00.000.00{i:04d}/0001-00",
            "nome_fornecedor": f"FARMACIA {i + 1} LTDA",
            "preco_unitario_pago": 100.0 + i * 10,
            "preco_bps_mediana": 50.0,
            "variacao_percentual": 100.0 + i * 5,
            "valor_excedente_total": 500.0 + i * 50,
            "nivel_alerta": nivel,
        })
    df = pd.DataFrame(rows)
    path = tmp_path / "alertas_superfaturamento.csv"
    df.to_csv(path, index=False)
    return path


def _make_mock_message(text: str = "Relatório de análise mock.") -> MagicMock:
    """Cria mock de resposta da API Anthropic."""
    content_block = MagicMock()
    content_block.text = text
    message = MagicMock()
    message.content = [content_block]
    return message


# ---------------------------------------------------------------------------
# TestAIAnalyzerInit
# ---------------------------------------------------------------------------

class TestAIAnalyzerInit:
    def test_instancia_sem_api_key(self, monkeypatch):
        """AIAnalyzer() NÃO deve lançar ValueError quando ANTHROPIC_API_KEY ausente."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # Deve instanciar sem erro
        ai = AIAnalyzer()
        assert ai is not None

    def test_instancia_com_api_key(self, monkeypatch):
        """AIAnalyzer() instancia normalmente quando ANTHROPIC_API_KEY definida."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        ai = AIAnalyzer()
        assert ai is not None
        assert ai.api_key == "sk-test-key"


# ---------------------------------------------------------------------------
# TestAIAnalyzerAnalisar
# ---------------------------------------------------------------------------

class TestAIAnalyzerAnalisar:
    def test_sem_api_key_retorna_none(self, monkeypatch, tmp_path):
        """analisar() com key ausente deve retornar None sem chamar a API."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        alertas_file = str(_make_alertas_csv(tmp_path))
        output_file = str(tmp_path / "analise_ia.md")

        with patch("anthropic.Anthropic") as mock_anthropic_cls:
            ai = AIAnalyzer()
            result = ai.analisar(alertas_file, output_file)

        assert result is None
        # anthropic.Anthropic não deve ter sido instanciado
        mock_anthropic_cls.assert_not_called()

    def test_authentication_error_retorna_none(self, monkeypatch, tmp_path):
        """analisar() deve retornar None quando AuthenticationError é lançada."""
        from anthropic import AuthenticationError

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-invalid-key")
        alertas_file = str(_make_alertas_csv(tmp_path))
        output_file = str(tmp_path / "analise_ia.md")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.headers = {}

        with patch("anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.side_effect = AuthenticationError(
                message="Invalid API key",
                response=mock_response,
                body={"error": {"type": "authentication_error", "message": "Invalid API key"}},
            )

            ai = AIAnalyzer()
            result = ai.analisar(alertas_file, output_file)

        assert result is None

    def test_rate_limit_retorna_none(self, monkeypatch, tmp_path):
        """analisar() deve retornar None quando RateLimitError é lançada."""
        from anthropic import RateLimitError

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid-key")
        alertas_file = str(_make_alertas_csv(tmp_path))
        output_file = str(tmp_path / "analise_ia.md")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        with patch("anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.side_effect = RateLimitError(
                message="Rate limit exceeded",
                response=mock_response,
                body={"error": {"type": "rate_limit_error", "message": "Rate limit exceeded"}},
            )

            ai = AIAnalyzer()
            result = ai.analisar(alertas_file, output_file)

        assert result is None

    def test_api_error_retorna_none(self, monkeypatch, tmp_path):
        """analisar() deve retornar None quando APIError genérico (status 500) é lançado."""
        from anthropic import APIStatusError

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid-key")
        alertas_file = str(_make_alertas_csv(tmp_path))
        output_file = str(tmp_path / "analise_ia.md")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}

        with patch("anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.side_effect = APIStatusError(
                message="Internal server error",
                response=mock_response,
                body={"error": {"type": "api_error", "message": "Internal server error"}},
            )

            ai = AIAnalyzer()
            result = ai.analisar(alertas_file, output_file)

        assert result is None

    def test_exception_generica_retorna_none(self, monkeypatch, tmp_path):
        """analisar() deve retornar None quando Exception genérica é lançada."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid-key")
        alertas_file = str(_make_alertas_csv(tmp_path))
        output_file = str(tmp_path / "analise_ia.md")

        with patch("anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("Unexpected error")

            ai = AIAnalyzer()
            result = ai.analisar(alertas_file, output_file)

        assert result is None

    def test_usa_modelo_datado(self, monkeypatch, tmp_path):
        """analisar() deve passar model='claude-sonnet-4-5-20250929' para messages.create."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid-key")
        alertas_file = str(_make_alertas_csv(tmp_path))
        output_file = str(tmp_path / "analise_ia.md")

        with patch("anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_mock_message()

            ai = AIAnalyzer()
            ai.analisar(alertas_file, output_file)

        # Verificar que messages.create foi chamado com model correto
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs is not None
        model_used = call_kwargs.kwargs.get("model") or call_kwargs.args[0] if call_kwargs.args else None
        if model_used is None:
            # Tentar via kwargs
            model_used = call_kwargs[1].get("model") if len(call_kwargs) > 1 else None
        # Buscar model em qualquer forma da chamada
        all_kwargs = dict(call_kwargs.kwargs) if call_kwargs.kwargs else {}
        if call_kwargs.args:
            # positional args não esperados para messages.create — ok verificar só kwargs
            pass
        assert all_kwargs.get("model") == "claude-sonnet-4-5-20250929", (
            f"Esperado 'claude-sonnet-4-5-20250929', recebido: {all_kwargs.get('model')}"
        )

    def test_top_n_maximo_5(self, monkeypatch, tmp_path):
        """analisar() com DataFrame de 20 linhas deve enviar no máximo 5 casos ao prompt."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid-key")
        alertas_file = str(_make_alertas_csv(tmp_path, n=20))
        output_file = str(tmp_path / "analise_ia.md")

        captured_prompt = {}

        def capture_create(**kwargs):
            msgs = kwargs.get("messages", [])
            if msgs:
                captured_prompt["content"] = msgs[0].get("content", "")
            return _make_mock_message()

        with patch("anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.side_effect = capture_create

            ai = AIAnalyzer()
            ai.analisar(alertas_file, output_file, top_n=5)

        assert "content" in captured_prompt, "Prompt não foi capturado"
        content = captured_prompt["content"]

        # Extrair o bloco JSON de casos do prompt
        json_blocks = re.findall(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        assert len(json_blocks) >= 1, "Nenhum bloco JSON encontrado no prompt"

        # O primeiro bloco JSON deve ter os casos (top_n)
        casos = json.loads(json_blocks[0])
        assert len(casos) <= 5, (
            f"Prompt contém {len(casos)} casos, esperado máximo 5"
        )

    def test_salva_output_file(self, monkeypatch, tmp_path):
        """analisar() deve criar o arquivo output_file quando API retorna sucesso."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid-key")
        alertas_file = str(_make_alertas_csv(tmp_path))
        output_file = str(tmp_path / "analise_ia.md")

        with patch("anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_mock_message(
                "Relatório gerado com sucesso."
            )

            ai = AIAnalyzer()
            ai.analisar(alertas_file, output_file)

        assert Path(output_file).exists(), f"Arquivo {output_file} não foi criado"

    def test_retorna_texto(self, monkeypatch, tmp_path):
        """analisar() deve retornar a string de texto quando API retorna sucesso."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid-key")
        alertas_file = str(_make_alertas_csv(tmp_path))
        output_file = str(tmp_path / "analise_ia.md")
        expected_text = "Este é o relatório de análise qualitativa."

        with patch("anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_mock_message(expected_text)

            ai = AIAnalyzer()
            result = ai.analisar(alertas_file, output_file)

        assert result is not None
        assert expected_text in result


# ---------------------------------------------------------------------------
# TestThresholdPropagado
# ---------------------------------------------------------------------------

class TestThresholdPropagado:
    """Verifica que o parâmetro threshold chega ao prompt enviado para Claude."""

    def _capturar_prompt(self, monkeypatch, tmp_path, threshold_value: int) -> str:
        """Helper: executa analisar() e retorna o conteúdo do prompt capturado."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid-key")
        alertas_file = str(_make_alertas_csv(tmp_path))
        output_file = str(tmp_path / "analise_ia.md")
        captured = {}

        def capture_create(**kwargs):
            msgs = kwargs.get("messages", [])
            if msgs:
                captured["content"] = msgs[0].get("content", "")
            return _make_mock_message()

        with patch("anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.side_effect = capture_create
            ai = AIAnalyzer()
            ai.analisar(alertas_file, output_file, threshold=threshold_value)

        return captured.get("content", "")

    def test_threshold_20_aparece_no_prompt(self, monkeypatch, tmp_path):
        """Quando threshold=20, o prompt deve conter '20%'."""
        content = self._capturar_prompt(monkeypatch, tmp_path, threshold_value=20)
        assert "20%" in content, (
            f"Esperado '20%' no prompt mas não encontrado. Prompt (100 chars): {content[:100]}"
        )

    def test_threshold_50_aparece_no_prompt(self, monkeypatch, tmp_path):
        """Quando threshold=50, o prompt deve conter '50%'."""
        content = self._capturar_prompt(monkeypatch, tmp_path, threshold_value=50)
        assert "50%" in content, (
            f"Esperado '50%' no prompt mas não encontrado. Prompt (100 chars): {content[:100]}"
        )
