"""Smoke tests de existência e integridade dos arquivos de documentação — REQ-011."""
import re
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"


def test_metodologia_existe() -> None:
    """docs/METODOLOGIA.md deve existir."""
    assert (DOCS_DIR / "METODOLOGIA.md").exists(), "docs/METODOLOGIA.md não encontrado"


def test_como_interpretar_existe() -> None:
    """docs/COMO_INTERPRETAR.md deve existir."""
    assert (DOCS_DIR / "COMO_INTERPRETAR.md").exists(), (
        "docs/COMO_INTERPRETAR.md não encontrado"
    )


def test_index_html_existe() -> None:
    """docs/index.html deve existir."""
    assert (DOCS_DIR / "index.html").exists(), "docs/index.html não encontrado"


def test_index_html_sem_cdn() -> None:
    """docs/index.html não deve conter URLs externas (sem CDN, sem fontes externas)."""
    index_path = DOCS_DIR / "index.html"
    assert index_path.exists(), "docs/index.html não encontrado"

    content = index_path.read_text(encoding="utf-8")

    # Procura por URLs http:// ou https:// em atributos de tags HTML
    # (src=, href=, url(), @import, etc.)
    external_urls = re.findall(r'(?:src|href|url|@import)\s*[=:(]\s*["\']?\s*https?://', content)
    assert not external_urls, (
        f"URLs externas encontradas em docs/index.html: {external_urls}"
    )


def test_index_html_tem_fetch() -> None:
    """docs/index.html deve conter fetch('./summary.json') conforme UI-SPEC."""
    index_path = DOCS_DIR / "index.html"
    assert index_path.exists(), "docs/index.html não encontrado"

    content = index_path.read_text(encoding="utf-8")
    assert "fetch('./summary.json')" in content, (
        "docs/index.html não contém fetch('./summary.json')"
    )


def test_index_html_min_linhas() -> None:
    """docs/index.html deve ter pelo menos 100 linhas."""
    index_path = DOCS_DIR / "index.html"
    assert index_path.exists(), "docs/index.html não encontrado"

    lines = index_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 100, (
        f"docs/index.html tem apenas {len(lines)} linhas (mínimo 100)"
    )
