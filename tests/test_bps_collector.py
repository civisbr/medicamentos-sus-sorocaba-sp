"""
tests/test_bps_collector.py
Suite TDD para BPSCollector — STAB-02
Testa fallback headless quando portal BPS usa JS para gerar links CSV.
"""
from unittest.mock import MagicMock, patch, call
import pytest

from src.collectors.bps_collector import (
    BPS_DATASET_PAGE,
    _descobrir_url_csv,
    _descobrir_url_csv_headless,
    _criar_session,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

HTML_SEM_CSV = "<html><body><p>Portal em manutenção</p></body></html>"
HTML_COM_CSV = (
    '<html><body>'
    '<a href="/dataset/bps/resource/bps_sp_2023.csv">BPS 2023</a>'
    '<a href="/dataset/bps/resource/bps_sp_2022.csv">BPS 2022</a>'
    '</body></html>'
)


def _mock_session_response(html: str) -> MagicMock:
    """Cria mock de requests.Session.get retornando HTML fornecido."""
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.get.return_value = resp
    return session


# ---------------------------------------------------------------------------
# TestDescobridorUrlCsvFallback — verifica ativação do fallback
# ---------------------------------------------------------------------------

class TestDescobridorUrlCsvFallback:
    def test_fallback_headless_chamado_quando_sem_csv_no_html(self):
        """Quando HTML não tem links .csv, _descobrir_url_csv_headless deve ser chamado."""
        session = _mock_session_response(HTML_SEM_CSV)

        with patch(
            "src.collectors.bps_collector._descobrir_url_csv_headless",
            return_value="https://example.com/bps_2023.csv"
        ) as mock_headless:
            resultado = _descobrir_url_csv(session, ano=2023)

        mock_headless.assert_called_once_with(2023)
        assert resultado == "https://example.com/bps_2023.csv"

    def test_headless_nao_chamado_quando_html_tem_csv(self):
        """Quando HTML tem links .csv, _descobrir_url_csv_headless NÃO deve ser chamado."""
        session = _mock_session_response(HTML_COM_CSV)

        with patch(
            "src.collectors.bps_collector._descobrir_url_csv_headless"
        ) as mock_headless:
            resultado = _descobrir_url_csv(session, ano=2023)

        mock_headless.assert_not_called()
        assert "2023" in resultado

    def test_url_relativa_convertida_para_absoluta(self):
        """URL relativa no href deve ser convertida para URL absoluta."""
        session = _mock_session_response(HTML_COM_CSV)

        with patch("src.collectors.bps_collector._descobrir_url_csv_headless"):
            resultado = _descobrir_url_csv(session, ano=2023)

        assert resultado.startswith("https://")


# ---------------------------------------------------------------------------
# TestDescobridorUrlCsvHeadless — verifica comportamento do fallback em si
# ---------------------------------------------------------------------------

class TestDescobridorUrlCsvHeadless:
    def _mock_playwright(self, links: list[str]) -> MagicMock:
        """Cria mock completo de sync_playwright para retornar links fornecidos."""
        page = MagicMock()
        page.eval_on_selector_all.return_value = links

        browser = MagicMock()
        browser.new_page.return_value = page

        chromium = MagicMock()
        chromium.launch.return_value = browser

        playwright_instance = MagicMock()
        playwright_instance.chromium = chromium

        sync_pw_ctx = MagicMock()
        sync_pw_ctx.__enter__ = MagicMock(return_value=playwright_instance)
        sync_pw_ctx.__exit__ = MagicMock(return_value=False)

        return sync_pw_ctx

    def test_retorna_url_quando_playwright_encontra_links(self):
        """_descobrir_url_csv_headless retorna URL quando playwright encontra links .csv."""
        links = [
            "https://example.com/bps_2022.csv",
            "https://example.com/bps_2023.csv",
        ]
        mock_pw = self._mock_playwright(links)

        with patch("src.collectors.bps_collector.sync_playwright", return_value=mock_pw):
            resultado = _descobrir_url_csv_headless(2023)

        # Deve preferir link com "2023" no href
        assert "2023" in resultado

    def test_retorna_ultimo_link_quando_ano_nao_encontrado(self):
        """_descobrir_url_csv_headless retorna último link quando ano não está em nenhum href."""
        links = [
            "https://example.com/bps_2021.csv",
            "https://example.com/bps_2022.csv",
        ]
        mock_pw = self._mock_playwright(links)

        with patch("src.collectors.bps_collector.sync_playwright", return_value=mock_pw):
            resultado = _descobrir_url_csv_headless(2023)

        # Fallback: retorna o último link disponível
        assert resultado == "https://example.com/bps_2022.csv"

    def test_lanca_valueerror_quando_sem_links(self):
        """_descobrir_url_csv_headless lança ValueError quando playwright não encontra links."""
        mock_pw = self._mock_playwright([])

        with patch("src.collectors.bps_collector.sync_playwright", return_value=mock_pw):
            with pytest.raises(ValueError, match="Nenhum CSV encontrado via headless"):
                _descobrir_url_csv_headless(2023)

    def test_browser_sempre_fechado_mesmo_com_excecao(self):
        """Browser deve ser fechado mesmo quando page.goto lança exceção."""
        page = MagicMock()
        page.goto.side_effect = Exception("Timeout ao carregar página")

        browser = MagicMock()
        browser.new_page.return_value = page

        chromium = MagicMock()
        chromium.launch.return_value = browser

        playwright_instance = MagicMock()
        playwright_instance.chromium = chromium

        sync_pw_ctx = MagicMock()
        sync_pw_ctx.__enter__ = MagicMock(return_value=playwright_instance)
        sync_pw_ctx.__exit__ = MagicMock(return_value=False)

        with patch("src.collectors.bps_collector.sync_playwright", return_value=sync_pw_ctx):
            with pytest.raises(Exception):
                _descobrir_url_csv_headless(2023)

        # browser.close() deve ter sido chamado (via finally)
        browser.close.assert_called_once()
