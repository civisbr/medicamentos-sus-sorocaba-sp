"""
portal_sorocaba.py
Coleta despesas de saude do TCE-SP bulk CSV, filtrando registros de Sorocaba.
Fonte: https://www.tce.sp.gov.br/sites/default/files/conjunto-dados/despesas-{ano}.zip
"""

import json
import csv
import io
import os
import zipfile
import logging
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rich.progress import Progress, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from rich.console import Console

ROOT = Path(__file__).parent.parent.parent
FIXTURES_DIR = ROOT / "data" / "fixtures"
TCE_SP_URL = "https://www.tce.sp.gov.br/sites/default/files/conjunto-dados/despesas-{ano}.zip"
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB

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
    })
    return session


def _ler_fixture(ano: int) -> list[dict]:
    path = FIXTURES_DIR / f"sorocaba_despesas_saude_{ano}_sample.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Fixture nao encontrada: {path}. "
            f"Crie data/fixtures/sorocaba_despesas_saude_{ano}_sample.json "
            f"ou remova MEDAUDIT_FIXTURE para baixar o CSV real."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _detectar_delimitador(header_line: str) -> str:
    return ";" if header_line.count(";") > header_line.count(",") else ","


def _filtrar_registros(reader: csv.DictReader, municipio: str = "SOROCABA", funcao: str = "10") -> list[dict]:
    result = []
    for row in reader:
        nm = row.get("nm_municipio", "") or row.get("NM_MUNICIPIO", "")
        cd = row.get("cd_funcao", "") or row.get("CD_FUNCAO", "")
        if nm.strip().upper() == municipio.upper() and str(cd).strip() == funcao:
            result.append(dict(row))
    return result


def baixar_e_filtrar_tcesp(ano: int, session: Optional[requests.Session] = None) -> list[dict]:
    """Baixa o ZIP do TCE-SP e retorna apenas os registros de Sorocaba/Saude."""
    if session is None:
        session = _criar_session()

    url = TCE_SP_URL.format(ano=ano)
    console.print(f"[cyan]Baixando TCE-SP {ano}:[/cyan] {url}")

    resp = session.get(url, stream=True, timeout=300)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if "zip" not in content_type and "octet-stream" not in content_type:
        logger.warning("Content-Type inesperado: %s — continuando mesmo assim", content_type)

    # Streaming para evitar carregar 2GB na memoria
    buffer = io.BytesIO()
    total = int(resp.headers.get("Content-Length", 0)) or None

    with Progress(
        "[progress.description]{task.description}",
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"despesas-{ano}.zip", total=total)
        for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
            buffer.write(chunk)
            progress.advance(task, len(chunk))

    buffer.seek(0)
    with zipfile.ZipFile(buffer) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError(f"Nenhum CSV encontrado dentro do ZIP despesas-{ano}.zip")
        csv_name = csv_names[0]
        console.print(f"[dim]Lendo {csv_name} e filtrando Sorocaba/Saude...[/dim]")
        with zf.open(csv_name) as raw:
            first_line = raw.readline().decode("latin-1")
            raw.seek(0)
            delim = _detectar_delimitador(first_line)
            text_wrapper = io.TextIOWrapper(raw, encoding="latin-1")
            reader = csv.DictReader(text_wrapper, delimiter=delim)
            registros = _filtrar_registros(reader)

    console.print(f"[green]TCE-SP {ano}:[/green] {len(registros)} registros Sorocaba/Saude encontrados")
    return registros


class PortalSorocabaCollector:
    """
    Coleta despesas empenhadas na funcao SAUDE (cd_funcao=10) de Sorocaba
    a partir do bulk CSV anual publicado pelo TCE-SP (AUDESP).
    """

    def __init__(self, fixture: bool = False):
        self.fixture = fixture or os.getenv("MEDAUDIT_FIXTURE", "0") == "1"
        self._session = _criar_session()

    def coletar_despesas_saude(self, ano: int) -> list[dict]:
        """
        Retorna lista de empenhos de saude de Sorocaba para o ano indicado.

        Args:
            ano: Ano de referencia (2020-2024)

        Returns:
            Lista de dicts com todos os campos originais do CSV TCE-SP,
            filtrados por nm_municipio=SOROCABA e cd_funcao=10.
        """
        if self.fixture:
            console.print(f"[yellow]Modo fixture:[/yellow] usando amostra local para {ano}")
            return _ler_fixture(ano)
        return baixar_e_filtrar_tcesp(ano, session=self._session)

    def salvar(self, dados: list[dict], path: str) -> None:
        """Salva os dados brutos em JSON."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        console.print(f"[green]Salvo:[/green] {path} ({len(dados)} registros)")
