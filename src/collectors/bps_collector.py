"""
bps_collector.py
Coleta precos de referencia do BPS (Base de Precos em Saude) do Ministerio da Saude.
Fonte: https://dadosabertos.saude.gov.br/dataset/bps
"""

import re
import io
import logging
from pathlib import Path

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rich.console import Console

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None  # type: ignore[assignment]

ROOT = Path(__file__).parent.parent.parent
BPS_DATASET_PAGE = "https://dadosabertos.saude.gov.br/dataset/bps"
OUTPUT_DEFAULT = ROOT / "data" / "raw" / "bps_precos_referencia.csv"

logger = logging.getLogger(__name__)
console = Console()


def _criar_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "MedAuditSUS/1.0 (civic tech; contato@civisbr.org)",
        "Accept": "text/html,application/json,*/*",
    })
    return session


def _descobrir_url_csv(session: requests.Session, ano: int) -> str:
    """
    Parseia a pagina do dataset BPS e retorna a URL do CSV para o ano solicitado.
    Se nenhum link com o ano for encontrado via requests+regex, usa fallback Playwright.
    """
    resp = session.get(BPS_DATASET_PAGE, timeout=30)
    resp.raise_for_status()

    # Buscar todos os hrefs que terminam em .csv
    csv_links = re.findall(r'href=["\']([^"\']*\.csv[^"\']*)["\']', resp.text, re.IGNORECASE)

    # Filtrar por ano
    ano_links = [lnk for lnk in csv_links if str(ano) in lnk]
    if ano_links:
        url = ano_links[0]
    elif csv_links:
        url = csv_links[-1]
        logger.warning("CSV do ano %d nao encontrado; usando: %s", ano, url)
    else:
        # Fallback: portal pode usar JS para gerar links — tentar headless
        logger.warning(
            "Nenhum link CSV encontrado via requests em %s. "
            "Tentando fallback Playwright headless...",
            BPS_DATASET_PAGE
        )
        return _descobrir_url_csv_headless(ano)

    # Garantir URL absoluta
    if url.startswith("/"):
        url = "https://dadosabertos.saude.gov.br" + url
    return url


def _descobrir_url_csv_headless(ano: int) -> str:
    """
    Fallback: usa Playwright headless para obter URL do CSV BPS
    quando o portal renderiza links via JavaScript.

    Args:
        ano: Ano do dataset desejado

    Returns:
        URL absoluta do CSV BPS

    Raises:
        ValueError: quando nenhum link .csv é encontrado
        ImportError: quando playwright não está instalado
    """
    if not _PLAYWRIGHT_AVAILABLE:
        raise ImportError(
            "playwright não está instalado. Execute: pip install playwright && "
            "python -m playwright install chromium"
        )

    logger.info("Tentando descobrir URL BPS via Playwright headless (ano=%d)...", ano)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(BPS_DATASET_PAGE, timeout=60000)
            # Aguarda carregamento completo do DOM (mais confiável que networkidle em portais
            # com analytics/tracking que podem nunca atingir networkidle)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            # Tenta aguardar link CSV aparecer (timeout curto — se não aparecer, usa o que tem)
            try:
                page.wait_for_selector("a[href*='.csv']", timeout=15000)
            except Exception:
                pass  # Continua mesmo sem o seletor — eval_on_selector_all retornará []
            links = page.eval_on_selector_all(
                "a[href*='.csv']",
                "els => els.map(el => el.href)"
            )
        finally:
            browser.close()

    if not links:
        raise ValueError(
            f"Nenhum CSV encontrado via headless browser em {BPS_DATASET_PAGE}. "
            "Verifique se o portal está acessível e se o playwright chromium está instalado."
        )

    # Preferir link com o ano solicitado; fallback: último link disponível
    ano_links = [lnk for lnk in links if str(ano) in lnk]
    return ano_links[0] if ano_links else links[-1]


def _baixar_csv(url: str, session: requests.Session) -> pd.DataFrame:
    """Baixa e parseia o CSV BPS com fallback de encoding."""
    console.print(f"[cyan]Baixando BPS CSV:[/cyan] {url}")
    resp = session.get(url, timeout=120)
    resp.raise_for_status()

    for enc in ("utf-8", "latin-1"):
        try:
            content = resp.content.decode(enc)
            first_line = content.split("\n")[0]
            sep = ";" if first_line.count(";") > first_line.count(",") else ","
            df = pd.read_csv(io.StringIO(content), sep=sep, dtype=str, low_memory=False)
            console.print(f"[dim]BPS CSV lido com encoding={enc}, sep='{sep}', {len(df)} linhas totais[/dim]")
            return df
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue

    raise ValueError(f"Nao foi possivel parsear o CSV BPS de {url}")


def _filtrar_bps(df: pd.DataFrame, uf: str = "SP", min_registros: int = 5) -> pd.DataFrame:
    """Filtra por UF e numero minimo de registros."""
    df.columns = [c.strip().upper() for c in df.columns]

    uf_col = "SG_UF" if "SG_UF" in df.columns else None
    qt_col = "QT_REGISTROS" if "QT_REGISTROS" in df.columns else None

    if uf_col:
        df = df[df[uf_col].str.strip().str.upper() == uf.upper()].copy()

    if qt_col:
        df = df.copy()
        df[qt_col] = pd.to_numeric(df[qt_col], errors="coerce").fillna(0).astype(int)
        df = df[df[qt_col] >= min_registros]

    return df.reset_index(drop=True)


class BPSCollector:
    """
    Coleta precos de referencia do BPS para o ano e UF especificados.
    Fonte: dadosabertos.saude.gov.br (CSVs anuais, licenca CC-BY-ND 3.0)
    """

    def __init__(self):
        self._session = _criar_session()

    def coletar_precos_referencia(self, uf: str = "SP", ano: int = 2023) -> pd.DataFrame:
        """
        Baixa, filtra e salva o CSV de precos BPS.

        Args:
            uf: UF para filtrar (default "SP")
            ano: Ano de referencia do dataset (default 2023)

        Returns:
            DataFrame filtrado com precos de referencia
        """
        url = _descobrir_url_csv(self._session, ano)
        df_raw = _baixar_csv(url, self._session)
        df = _filtrar_bps(df_raw, uf=uf, min_registros=5)
        console.print(f"[green]BPS:[/green] {len(df)} registros apos filtro UF={uf}, QT_REGISTROS>=5")
        self.salvar_csv(df, str(OUTPUT_DEFAULT))
        return df

    def salvar_csv(self, df: pd.DataFrame, path: str = "data/raw/bps_precos_referencia.csv"):
        """Salva a tabela de precos em CSV."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False, encoding="utf-8")
        console.print(f"[green]BPS salvo:[/green] {path} ({len(df)} itens)")
