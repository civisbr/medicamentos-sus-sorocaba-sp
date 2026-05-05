"""
MedAudit SUS — Pipeline principal
Orquestra coleta, análise e exportação de dados de superfaturamento
de medicamentos na Prefeitura de Sorocaba.

Uso:
    python main.py --ano 2023 --threshold 30
    python main.py --step collect
    python main.py --ano all --skip-ai
"""

import click
import json
import pandas as pd
from pathlib import Path
from rich.console import Console
from rich.progress import track
from dotenv import load_dotenv

load_dotenv()
console = Console()
ROOT = Path(__file__).parent


@click.command()
@click.option("--municipio", default="sorocaba", help="Município alvo")
@click.option("--ano", default="2023", help="Ano de referência (ou 'all' para 2020-2024)")
@click.option("--threshold", default=30, help="% acima do BPS para gerar alerta")
@click.option("--step", default="all", type=click.Choice(["all", "collect", "analyze", "export"]))
@click.option("--skip-ai", is_flag=True, help="Pular análise qualitativa com Claude API")
@click.option("--output", default="data/reports", help="Diretório de saída")
def main(municipio, ano, threshold, step, skip_ai, output):
    """MedAudit SUS — Detector de superfaturamento em medicamentos do SUS."""

    console.print("\n[bold cyan]💊 MedAudit SUS[/bold cyan] — Iniciando pipeline...\n")

    anos = list(range(2020, 2025)) if ano == "all" else [int(ano)]
    output_path = ROOT / output
    output_path.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────
    # ETAPA 1: COLETA DE DADOS
    # ─────────────────────────────────────────────
    if step in ("all", "collect"):
        console.print("[bold]Etapa 1:[/bold] Coletando dados do Portal da Transparência...")

        from src.collectors.portal_sorocaba import PortalSorocabaCollector
        from src.collectors.bps_collector import BPSCollector
        from src.collectors.cnpj_collector import CNPJCollector

        # 1a. Despesas de medicamentos em Sorocaba
        portal = PortalSorocabaCollector()
        for a in track(anos, description="Baixando despesas..."):
            despesas = portal.coletar_despesas_saude(ano=a)
            portal.salvar(despesas, path=str(ROOT / f"data/raw/sorocaba_despesas_saude_{a}.json"))
            # Enriquecimento CNPJ por ano
            try:
                cnpj = CNPJCollector()
                cnpj.enriquecer_fornecedores(
                    input_file=str(ROOT / f"data/raw/sorocaba_despesas_saude_{a}.json"),
                    output_file=str(ROOT / "data/processed/fornecedores_enriquecidos.json")
                )
            except NotImplementedError:
                console.print("[yellow]CNPJ collector ainda não implementado — pulando[/yellow]")

        # 1b. Preços de referência do BPS
        console.print("[bold]Etapa 1b:[/bold] Baixando tabela BPS...")
        bps = BPSCollector()
        try:
            df_bps = bps.coletar_precos_referencia(uf="SP", ano=int(anos[0]))
        except NotImplementedError:
            console.print("[yellow]BPS collector ainda não implementado — pulando[/yellow]")
        except Exception as e:
            console.print(f"[yellow]BPS indisponível ({type(e).__name__}) — pulando coleta de preços de referência[/yellow]")

    # ─────────────────────────────────────────────
    # ETAPA 2: ANÁLISE
    # ─────────────────────────────────────────────
    if step in ("all", "analyze"):
        console.print("\n[bold]Etapa 2:[/bold] Analisando preços...")

        from src.utils.normalizer import MedicamentoNormalizer
        from src.analyzers.price_analyzer import PriceAnalyzer
        from src.analyzers.supplier_analyzer import SupplierAnalyzer
        from src.analyzers.ai_analyzer import AIAnalyzer

        # 2a. Normalização de nomes de medicamentos
        normalizer = MedicamentoNormalizer(
            catmat_catalog_path=str(ROOT / "data/raw/bps_precos_referencia.csv")
        )
        despesas_norm = normalizer.processar(
            input_glob=str(ROOT / "data/raw/sorocaba_despesas_saude_*.json"),
            output_file=str(ROOT / "data/processed/medicamentos_normalizados.json")
        )

        # 2b. Comparação de preços com BPS
        analyzer = PriceAnalyzer(
            threshold_atencao=threshold,   # do CLI --threshold
            threshold_alerta=100,          # fixo por REQUIREMENTS.md REQ-005
            threshold_critico=200,         # fixo por REQUIREMENTS.md REQ-005
        )
        alertas = analyzer.analisar(
            despesas_file=str(ROOT / "data/processed/medicamentos_normalizados.json"),
            bps_file=str(ROOT / "data/raw/bps_precos_referencia.csv"),
            output_file=str(ROOT / "data/reports/alertas_superfaturamento.csv")
        )
        estatisticas = analyzer.gerar_estatisticas(alertas)
        import json as _json
        _stats_path = ROOT / "data" / "processed" / "analise_precos.json"
        _stats_path.parent.mkdir(parents=True, exist_ok=True)
        _stats_path.write_text(_json.dumps(estatisticas, ensure_ascii=False, indent=2), encoding="utf-8")

        # 2c. Análise por fornecedor
        supplier_analyzer = SupplierAnalyzer()
        # TODO (Claude Code): agrupar alertas por CNPJ, calcular score de risco,
        # identificar padrões de reincidência
        supplier_analyzer.analisar(
            alertas_file=str(ROOT / "data/reports/alertas_superfaturamento.csv"),
            cnpj_file=str(ROOT / "data/processed/fornecedores_enriquecidos.json"),
            output_file=str(ROOT / "data/reports/fornecedores_suspeitos.csv")
        )

        # 2d. Análise qualitativa com IA (opcional)
        if not skip_ai:
            console.print("[bold]Etapa 2d:[/bold] Análise qualitativa com Claude API...")
            ai = AIAnalyzer()
            try:
                narrativa = ai.analisar(
                    alertas_file=str(ROOT / "data/reports/alertas_superfaturamento.csv"),
                    output_file=str(ROOT / "data/reports/analise_ia.md")
                )
            except Exception as e:
                console.print(f"[yellow]Análise IA falhou ({e}) — continuando sem narrativa[/yellow]")
                narrativa = None

    # ─────────────────────────────────────────────
    # ETAPA 3: EXPORTAÇÃO
    # ─────────────────────────────────────────────
    if step in ("all", "export"):
        console.print("\n[bold]Etapa 3:[/bold] Exportando relatórios...")

        from src.utils.exporter import Exporter
        exporter = Exporter()

        # Garantir diretórios de saída
        (ROOT / "data/output").mkdir(parents=True, exist_ok=True)
        (ROOT / "docs").mkdir(parents=True, exist_ok=True)

        # Gera summary.json para o dashboard GitHub Pages (em docs/)
        exporter.gerar_summary(
            alertas_file=str(ROOT / "data/reports/alertas_superfaturamento.csv"),
            fornecedores_file=str(ROOT / "data/reports/fornecedores_suspeitos.csv"),
            output_file=str(ROOT / "docs/summary.json"),
            ano=int(anos[0])
        )

        # Gera CSV publicável com 9 colunas + disclaimer (REQ-008)
        alertas_csv_path = ROOT / "data/reports/alertas_superfaturamento.csv"
        if alertas_csv_path.exists():
            alertas_df = pd.read_csv(str(alertas_csv_path))
        else:
            alertas_df = pd.DataFrame()
        exporter.gerar_csv(
            alertas_df=alertas_df,
            ano=int(anos[0]),
            output_file=str(ROOT / f"data/output/alertas_{anos[0]}.csv")
        )

        # Gera relatório HTML auto-contido (REQ-009)
        exporter.gerar_html(
            alertas_file=str(ROOT / "data/reports/alertas_superfaturamento.csv"),
            ai_narrative_file=str(ROOT / "data/reports/analise_ia.md"),
            output_file=str(ROOT / "data/reports/relatorio_completo.html"),
            ano=int(anos[0]),
            fornecedores_file=str(ROOT / "data/reports/fornecedores_suspeitos.csv")
        )

        console.print(f"\n[bold green]✅ Pipeline concluído![/bold green]")
        console.print(f"   Relatórios em: [cyan]{output_path.absolute()}[/cyan]")

    # Mostrar resumo no terminal (lê de docs/summary.json se disponível)
    summary_file = ROOT / "docs" / "summary.json"
    if not summary_file.exists():
        summary_file = output_path / "summary.json"
    if summary_file.exists():
        with open(summary_file) as f:
            s = json.load(f)
        totais = s.get("totais", {})
        console.print(f"\n[bold]Resumo:[/bold]")
        console.print(f"   Empenhos analisados: {totais.get('empenhos_analisados', '?')}")
        console.print(f"   Alertas CRÍTICOS: {totais.get('alertas_criticos', '?')}")
        console.print(f"   Valor total excedente: R$ {totais.get('valor_total_excedente', '?')}")


if __name__ == "__main__":
    main()
