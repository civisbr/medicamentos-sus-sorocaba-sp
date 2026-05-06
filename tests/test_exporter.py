"""
tests/test_exporter.py
Suite TDD para Exporter: TestGerarCSV, TestGerarHTML, TestGerarSummary
"""

import json
import pathlib
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from jinja2 import Environment


# ---------------------------------------------------------------------------
# Fixtures compartilhadas
# ---------------------------------------------------------------------------


@pytest.fixture
def alertas_df_fixture():
    """
    DataFrame com 10 linhas usando as 12 colunas originais de alertas_superfaturamento.csv.
    Valores variados para testar ordenação.
    Tiers: 2x CRÍTICO, 3x ALERTA, 5x ATENÇÃO
    """
    dados = [
        {
            "nr_empenho": f"EMP-{i:03d}",
            "data_empenho": f"2023-0{(i % 9) + 1}-01",
            "descricao_item": f"MEDICAMENTO {i} 500MG",
            "catmat_codigo": f"CAT{i:04d}",
            "cnpj_fornecedor": f"12.345.{i:03d}/0001-99",
            "nome_fornecedor": f"FARMACIA {chr(65 + i)} LTDA",
            "preco_unitario_pago": 2.50 + i * 0.5,
            "preco_bps_mediana": 0.80 + i * 0.1,
            "variacao_percentual": 200.0 + i * 10.0,
            "nivel_alerta": (
                "CRÍTICO" if i < 2 else ("ALERTA" if i < 5 else "ATENÇÃO")
            ),
            "valor_excedente_total": float(100000 - i * 8000),
            "qt_registros_bps": 10 + i,
        }
        for i in range(10)
    ]
    return pd.DataFrame(dados)


@pytest.fixture
def alertas_csv_fixture(tmp_path, alertas_df_fixture):
    """Arquivo CSV temporário com os alertas para usar em gerar_html e gerar_summary."""
    csv_path = tmp_path / "alertas_superfaturamento.csv"
    alertas_df_fixture.to_csv(str(csv_path), index=False)
    return str(csv_path)


@pytest.fixture
def fornecedores_df_fixture():
    """DataFrame com 6 linhas usando as 10 colunas de fornecedores_suspeitos.csv."""
    dados = [
        {
            "cnpj_fornecedor": f"12.345.{i:03d}/0001-99",
            "nome_fornecedor": f"FARMACIA {chr(65 + i)} LTDA",
            "total_alertas": 10 - i,
            "alertas_criticos": 3 - (i % 4),
            "score_risco": 0.9 - i * 0.1,
            "tier_suspeito": "ALTO" if i < 2 else "MÉDIO",
            "valor_excedente_total": float(500000 - i * 50000),
            "flag_empresa_nova": i % 2 == 0,
            "flag_situacao_irregular": i % 3 == 0,
            "data_abertura_cnpj": f"202{i}-01-01",
        }
        for i in range(6)
    ]
    return pd.DataFrame(dados)


@pytest.fixture
def fornecedores_csv_fixture(tmp_path, fornecedores_df_fixture):
    """Arquivo CSV temporário com os fornecedores."""
    csv_path = tmp_path / "fornecedores_suspeitos.csv"
    fornecedores_df_fixture.to_csv(str(csv_path), index=False)
    return str(csv_path)


# ---------------------------------------------------------------------------
# Helpers para template mínimo em testes
# ---------------------------------------------------------------------------

TEMPLATE_MINIMO = (
    "{% if narrativa_ia %}Análise Gerada por IA {{ narrativa_ia | e }}{% endif %}"
    "<script>"
    "const ALERTAS = {{ alertas | tojson }};"
    "const FORNECEDORES = {{ fornecedores | tojson }};"
    "</script>"
)


def _make_minimal_env() -> Environment:
    """Retorna um Environment Jinja2 com template mínimo inline via DictLoader."""
    from jinja2 import DictLoader
    env = Environment(
        loader=DictLoader({"relatorio.html.j2": TEMPLATE_MINIMO}),
        autoescape=False,
    )
    return env


# ---------------------------------------------------------------------------
# TestGerarCSV
# ---------------------------------------------------------------------------


class TestGerarCSV:

    COLUNAS_ESPERADAS = [
        "item", "fornecedor", "cnpj", "preco_pago",
        "preco_bps", "desvio_pct", "tier", "valor_excedente", "narrativa_ia",
    ]

    def test_nove_colunas(self, alertas_df_fixture, tmp_path):
        """gerar_csv() deve produzir arquivo com header de exatamente 9 colunas na ordem correta."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "alertas_2023.csv")
        e.gerar_csv(alertas_df_fixture, 2023, output)

        lines = pathlib.Path(output).read_text(encoding="utf-8").splitlines()
        # linha 0 = disclaimer, linha 1 = header
        header_line = lines[1]
        cols = header_line.split(",")
        assert len(cols) == 9, f"Esperado 9 colunas, encontrado {len(cols)}: {cols}"
        assert cols == self.COLUNAS_ESPERADAS, (
            f"Ordem de colunas incorreta.\n"
            f"Esperado: {self.COLUNAS_ESPERADAS}\n"
            f"Obtido:   {cols}"
        )

    def test_disclaimer_cabecalho(self, alertas_df_fixture, tmp_path):
        """Primeira linha do arquivo deve começar com '# Dados públicos'."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "alertas_2023.csv")
        e.gerar_csv(alertas_df_fixture, 2023, output)

        first_line = pathlib.Path(output).read_text(encoding="utf-8").splitlines()[0]
        assert first_line.startswith("# Dados públicos"), (
            f"Disclaimer ausente ou incorreto: {first_line!r}"
        )

    def test_ordenacao_desc(self, alertas_df_fixture, tmp_path):
        """Linhas devem estar ordenadas por valor_excedente DESC (maior primeiro)."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "alertas_2023.csv")
        e.gerar_csv(alertas_df_fixture, 2023, output)

        lines = pathlib.Path(output).read_text(encoding="utf-8").splitlines()
        # linha 0 = disclaimer, linha 1 = header, linhas 2+ = dados
        header = lines[1].split(",")
        idx_valor = header.index("valor_excedente")

        valores = []
        for line in lines[2:]:
            if line.strip():
                cols = line.split(",")
                try:
                    valores.append(float(cols[idx_valor]))
                except ValueError:
                    pass

        assert valores == sorted(valores, reverse=True), (
            f"Valores não estão em ordem decrescente: {valores}"
        )

    def test_narrativa_ia_vazia(self, alertas_df_fixture, tmp_path):
        """Coluna narrativa_ia deve existir e ter valor vazio quando não passada."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "alertas_2023.csv")
        e.gerar_csv(alertas_df_fixture, 2023, output)

        df = pd.read_csv(output, comment="#")
        assert "narrativa_ia" in df.columns, "Coluna 'narrativa_ia' não encontrada"
        assert df["narrativa_ia"].fillna("").eq("").all(), (
            "Coluna narrativa_ia deveria ser vazia para todas as linhas"
        )

    def test_cria_diretorio_output(self, alertas_df_fixture, tmp_path):
        """gerar_csv() deve criar data/output/ se não existir."""
        from src.utils.exporter import Exporter
        e = Exporter()
        nested = tmp_path / "novos" / "subdirs" / "alertas_2023.csv"
        # diretório pai não existe
        assert not nested.parent.exists()
        e.gerar_csv(alertas_df_fixture, 2023, str(nested))
        assert nested.exists(), "Arquivo não foi criado no diretório novo"


# ---------------------------------------------------------------------------
# TestGerarHTML
# ---------------------------------------------------------------------------


class TestGerarHTML:

    def _run_gerar_html(self, tmp_path, alertas_csv, fornecedores_csv=None,
                        ai_narrative_file=None, use_minimal_template=True):
        """Helper que executa gerar_html com template mínimo ou real."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "relatorio.html")
        ai_file = ai_narrative_file if ai_narrative_file else str(tmp_path / "nao_existe.md")

        if use_minimal_template:
            # Monkey-patch o Environment para usar template mínimo
            from jinja2 import DictLoader, Environment as JinjaEnv
            mock_env = JinjaEnv(
                loader=DictLoader({"relatorio.html.j2": TEMPLATE_MINIMO}),
                autoescape=False,
            )
            with patch("src.utils.exporter.Environment", return_value=mock_env):
                with patch("src.utils.exporter.FileSystemLoader"):
                    result = e.gerar_html(
                        alertas_file=alertas_csv,
                        ai_narrative_file=ai_file,
                        output_file=output,
                        fornecedores_file=fornecedores_csv,
                    )
        else:
            result = e.gerar_html(
                alertas_file=alertas_csv,
                ai_narrative_file=ai_file,
                output_file=output,
                fornecedores_file=fornecedores_csv,
            )
        return result, output

    def _make_large_alertas_csv(self, tmp_path, n=100):
        """Cria CSV com n alertas para teste de tamanho."""
        dados = [
            {
                "nr_empenho": f"EMP-{i:03d}",
                "data_empenho": "2023-01-01",
                "descricao_item": f"MEDICAMENTO {i} 500MG CAPSULAS TESTE TAMANHO FIXTURE",
                "catmat_codigo": f"CAT{i:04d}",
                "cnpj_fornecedor": f"12.345.{i:03d}/0001-99",
                "nome_fornecedor": f"FARMACIA NOME COMPLETO {i} LTDA ME",
                "preco_unitario_pago": 2.50 + i * 0.1,
                "preco_bps_mediana": 0.80,
                "variacao_percentual": 212.5 + i,
                "nivel_alerta": "CRÍTICO" if i % 3 == 0 else "ALERTA",
                "valor_excedente_total": float(10000 + i * 1000),
                "qt_registros_bps": 10,
            }
            for i in range(n)
        ]
        df = pd.DataFrame(dados)
        csv_path = tmp_path / "alertas_grande.csv"
        df.to_csv(str(csv_path), index=False)
        return str(csv_path)

    def test_tamanho_max_5mb(self, tmp_path):
        """HTML gerado com 100 alertas deve ter len(html.encode()) < 5_000_000."""
        from src.utils.exporter import Exporter
        e = Exporter()
        alertas_csv = self._make_large_alertas_csv(tmp_path, n=100)
        output = str(tmp_path / "relatorio_grande.html")
        ai_file = str(tmp_path / "nao_existe.md")

        from jinja2 import DictLoader, Environment as JinjaEnv
        mock_env = JinjaEnv(
            loader=DictLoader({"relatorio.html.j2": TEMPLATE_MINIMO}),
            autoescape=False,
        )
        with patch("src.utils.exporter.Environment", return_value=mock_env):
            with patch("src.utils.exporter.FileSystemLoader"):
                html = e.gerar_html(alertas_csv, ai_file, output)

        size = len(html.encode("utf-8"))
        assert size < 5_000_000, f"HTML muito grande: {size} bytes"

    def test_sem_cdn(self, tmp_path, alertas_csv_fixture):
        """HTML gerado não deve conter 'http://' ou 'https://' em nenhuma tag."""
        import re
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "relatorio.html")
        ai_file = str(tmp_path / "nao_existe.md")

        # Usar template REAL para testar ausência de CDN
        result = e.gerar_html(alertas_csv_fixture, ai_file, output)
        html_content = pathlib.Path(output).read_text(encoding="utf-8")

        external = re.findall(r'https?://[^\s"\']+', html_content)
        assert not external, f"CDN/URLs externas encontradas no HTML: {external}"

    def test_sem_narrativa_ia(self, tmp_path, alertas_csv_fixture, fornecedores_csv_fixture):
        """gerar_html() com ai_narrative_file inexistente não deve lançar exceção."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "relatorio.html")
        ai_file = str(tmp_path / "nao_existe.md")  # arquivo não existe

        from jinja2 import DictLoader, Environment as JinjaEnv
        mock_env = JinjaEnv(
            loader=DictLoader({"relatorio.html.j2": TEMPLATE_MINIMO}),
            autoescape=False,
        )
        with patch("src.utils.exporter.Environment", return_value=mock_env):
            with patch("src.utils.exporter.FileSystemLoader"):
                # Não deve lançar exceção
                html = e.gerar_html(
                    alertas_csv_fixture, ai_file, output,
                    fornecedores_file=fornecedores_csv_fixture,
                )

        assert "Análise Gerada por IA" not in html, (
            "Seção de narrativa IA não deveria aparecer quando arquivo não existe"
        )

    def test_com_narrativa_ia(self, tmp_path, alertas_csv_fixture, fornecedores_csv_fixture):
        """Quando ai_narrative_file existe, HTML deve conter 'Análise Gerada por IA'."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "relatorio.html")
        ai_file = tmp_path / "analise_ia.md"
        ai_file.write_text("Texto de análise", encoding="utf-8")

        from jinja2 import DictLoader, Environment as JinjaEnv
        mock_env = JinjaEnv(
            loader=DictLoader({"relatorio.html.j2": TEMPLATE_MINIMO}),
            autoescape=False,
        )
        with patch("src.utils.exporter.Environment", return_value=mock_env):
            with patch("src.utils.exporter.FileSystemLoader"):
                html = e.gerar_html(
                    alertas_csv_fixture, str(ai_file), output,
                    fornecedores_file=fornecedores_csv_fixture,
                )

        assert "Análise Gerada por IA" in html, (
            "Seção 'Análise Gerada por IA' não encontrada no HTML quando narrativa existe"
        )

    def test_dados_inline(self, tmp_path, alertas_csv_fixture, fornecedores_csv_fixture):
        """HTML deve conter 'const ALERTAS' e 'const FORNECEDORES' injetados via tojson."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "relatorio.html")
        ai_file = str(tmp_path / "nao_existe.md")

        from jinja2 import DictLoader, Environment as JinjaEnv
        mock_env = JinjaEnv(
            loader=DictLoader({"relatorio.html.j2": TEMPLATE_MINIMO}),
            autoescape=False,
        )
        with patch("src.utils.exporter.Environment", return_value=mock_env):
            with patch("src.utils.exporter.FileSystemLoader"):
                html = e.gerar_html(
                    alertas_csv_fixture, ai_file, output,
                    fornecedores_file=fornecedores_csv_fixture,
                )

        assert "const ALERTAS" in html, "const ALERTAS não encontrado no HTML"
        assert "const FORNECEDORES" in html, "const FORNECEDORES não encontrado no HTML"


# ---------------------------------------------------------------------------
# TestGerarSummary
# ---------------------------------------------------------------------------


class TestGerarSummary:

    def test_top5(self, alertas_csv_fixture, fornecedores_csv_fixture, tmp_path):
        """summary['top_itens'] e summary['top_fornecedores'] devem ter exatamente 5 entradas."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "summary.json")
        summary = e.gerar_summary(
            alertas_file=alertas_csv_fixture,
            output_file=output,
            ano=2023,
            fornecedores_file=fornecedores_csv_fixture,
        )

        assert len(summary["top_itens"]) == 5, (
            f"top_itens deveria ter 5 entradas, tem {len(summary['top_itens'])}"
        )
        assert len(summary["top_fornecedores"]) == 5, (
            f"top_fornecedores deveria ter 5 entradas, tem {len(summary['top_fornecedores'])}"
        )

    def test_top5_menos_que_5(self, tmp_path):
        """Quando alertas_df tem 3 linhas, top_itens deve ter 3 entradas (não crash)."""
        from src.utils.exporter import Exporter
        e = Exporter()

        # Criar CSV com apenas 3 alertas
        dados = [
            {
                "nr_empenho": f"EMP-{i}",
                "data_empenho": "2023-01-01",
                "descricao_item": f"MED {i}",
                "catmat_codigo": f"CAT{i}",
                "cnpj_fornecedor": f"12.345.00{i}/0001-99",
                "nome_fornecedor": f"FARM {i}",
                "preco_unitario_pago": 2.0 + i,
                "preco_bps_mediana": 1.0,
                "variacao_percentual": 100.0 + i * 10,
                "nivel_alerta": "ALERTA",
                "valor_excedente_total": float(10000 + i * 1000),
                "qt_registros_bps": 8,
            }
            for i in range(3)
        ]
        csv_path = tmp_path / "alertas_3.csv"
        pd.DataFrame(dados).to_csv(str(csv_path), index=False)
        output = str(tmp_path / "summary.json")

        summary = e.gerar_summary(
            alertas_file=str(csv_path),
            output_file=output,
            ano=2023,
        )

        assert len(summary["top_itens"]) == 3, (
            f"Com 3 alertas, top_itens deveria ter 3 entradas, tem {len(summary['top_itens'])}"
        )

    def test_schema_totais(self, alertas_csv_fixture, tmp_path):
        """summary['totais'] deve ter todas as chaves esperadas."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "summary.json")
        summary = e.gerar_summary(
            alertas_file=alertas_csv_fixture,
            output_file=output,
            ano=2023,
        )

        chaves_esperadas = {
            "empenhos_analisados",
            "alertas_atencao",
            "alertas_alerta",
            "alertas_criticos",
            "valor_total_excedente",
            "fornecedores_suspeitos",
        }
        chaves_presentes = set(summary["totais"].keys())
        ausentes = chaves_esperadas - chaves_presentes
        assert not ausentes, f"Chaves ausentes em totais: {ausentes}"

    def test_salva_arquivo(self, alertas_csv_fixture, tmp_path):
        """gerar_summary() deve salvar JSON no output_file e retornar dict."""
        from src.utils.exporter import Exporter
        e = Exporter()
        output = str(tmp_path / "summary.json")
        result = e.gerar_summary(
            alertas_file=alertas_csv_fixture,
            output_file=output,
            ano=2023,
        )

        assert isinstance(result, dict), "gerar_summary() deve retornar dict"
        assert pathlib.Path(output).exists(), "Arquivo summary.json não foi criado"

        saved = json.loads(pathlib.Path(output).read_text(encoding="utf-8"))
        assert saved == result or saved.keys() == result.keys(), (
            "Conteúdo do arquivo salvo difere do dict retornado"
        )

    def test_summary_json_sem_nan(self, tmp_path):
        """BLOCKER-1: summary.json não deve conter literais NaN (JSON inválido para browser)."""
        from src.utils.exporter import Exporter
        e = Exporter()

        # Dados com SEM_REFERÊNCIA → preco_bps_mediana e variacao_percentual ficam NaN
        dados = [
            {
                "nr_empenho": "EMP-001",
                "data_empenho": "2023-01-01",
                "descricao_item": "AMOXICILINA 500MG",
                "catmat_codigo": None,
                "cnpj_fornecedor": "12.345.678/0001-99",
                "nome_fornecedor": "FARMACIA A",
                "preco_unitario_pago": 5.0,
                "preco_bps_mediana": float("nan"),
                "variacao_percentual": float("nan"),
                "nivel_alerta": "SEM_REFERÊNCIA",
                "valor_excedente_total": 0.0,
                "qt_registros_bps": 0,
            }
        ]
        csv_path = tmp_path / "alertas_nan.csv"
        pd.DataFrame(dados).to_csv(str(csv_path), index=False)
        output = str(tmp_path / "summary_nan.json")

        e.gerar_summary(alertas_file=str(csv_path), output_file=output, ano=2023)

        raw = pathlib.Path(output).read_text(encoding="utf-8")
        assert "NaN" not in raw, f"Literal NaN encontrado no JSON: {raw}"
        # Deve ser JSON válido (não lança exceção)
        parsed = json.loads(raw)
        assert "top_itens" in parsed

    def test_nivel_risco_suspeito(self, tmp_path, alertas_csv_fixture):
        """BLOCKER-2: nivel_risco deve ser 'SUSPEITO' para tier_suspeito=True, não 'True'."""
        from src.utils.exporter import Exporter
        e = Exporter()

        forn_dados = [
            {
                "cnpj_fornecedor": "12.345.001/0001-99",
                "nome_fornecedor": "FARMACIA SUSPEITA",
                "total_alertas": 5,
                "alertas_criticos": 4,
                "score_risco": 0.9,
                "tier_suspeito": True,
                "valor_excedente_total": 900000.0,
                "flag_empresa_nova": False,
                "flag_situacao_irregular": False,
                "data_abertura_cnpj": "2023-01-01",
            },
            {
                "cnpj_fornecedor": "12.345.002/0001-99",
                "nome_fornecedor": "FARMACIA NORMAL",
                "total_alertas": 1,
                "alertas_criticos": 0,
                "score_risco": 0.1,
                "tier_suspeito": False,
                "valor_excedente_total": 100000.0,
                "flag_empresa_nova": False,
                "flag_situacao_irregular": False,
                "data_abertura_cnpj": "2020-01-01",
            },
        ]
        forn_csv = tmp_path / "forn.csv"
        pd.DataFrame(forn_dados).to_csv(str(forn_csv), index=False)
        output = str(tmp_path / "summary_risco.json")

        summary = e.gerar_summary(
            alertas_file=alertas_csv_fixture,
            output_file=output,
            ano=2023,
            fornecedores_file=str(forn_csv),
        )

        nivel_suspeito = summary["top_fornecedores"][0]["nivel_risco"]
        nivel_ok = summary["top_fornecedores"][1]["nivel_risco"]
        assert nivel_suspeito == "SUSPEITO", (
            f"Esperado 'SUSPEITO', obtido '{nivel_suspeito}'"
        )
        assert nivel_ok == "OK", f"Esperado 'OK', obtido '{nivel_ok}'"
