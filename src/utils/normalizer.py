"""
normalizer.py
Normalização de nomes de medicamentos para permitir comparação entre
as descrições usadas nos empenhos municipais e o catálogo BPS/CATMAT.
"""

import re
import os
import glob
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from tqdm import tqdm

try:
    from rapidfuzz import fuzz, process as fuzz_process
    HAS_FUZZY = True
except ImportError:
    HAS_FUZZY = False

try:
    from rich.console import Console
    console = Console()
    def _log(msg: str, style: str = "") -> None:
        console.print(f"[{style}]{msg}[/{style}]" if style else msg)
except ImportError:
    def _log(msg: str, style: str = "") -> None:
        print(msg)

logger = logging.getLogger(__name__)

# Abreviações comuns em empenhos municipais → forma expandida
ABREVIACOES = {
    "CPS": "CAPSULAS",
    "CPR": "COMPRIMIDOS",
    "CP": "COMPRIMIDO",
    "AMP": "AMPOLAS",
    "FR": "FRASCO",
    "SOL": "SOLUCAO",
    "INJ": "INJETAVEL",
    "MG": "MG",
    "ML": "ML",
    "UI": "UNIDADES INTERNACIONAIS",
    "C/": "COM ",
}

# Palavras que não ajudam na busca — remover antes do fuzzy match
STOPWORDS_FARMACEUTICAS = [
    "GENERICO", "SIMILAR", "REFERENCIA", "CAIXA", "UNIDADE",
    "EMBALAGEM", "PRODUTO", "FARMACEUTICO", "MANIPULADO",
    "COM", "C/", "PCT", "PACOTE"
]

# Prefixos de empenho a remover antes da normalização
_PREFIXOS_EMPENHO = re.compile(
    r"^(AQUISICAO\s+DE\s+MEDICAMENTOS?\s*[-–]\s*|"
    r"COMPRA\s+DE\s+MEDICAMENTOS?\s*[-–]\s*|"
    r"FORNECIMENTO\s+DE\s+MEDICAMENTOS?\s*[-–]\s*|"
    r"MATERIAL\s+FARMACOLOGICO\s*[-–]\s*|"
    r"AQUISICAO\s+DE\s+MEDICAMENTOS?\s+INJETAVEIS?\s*[-–]\s*)",
    re.IGNORECASE
)

# Sufixos de empenho a remover (pregão, processo, etc.)
_SUFIXOS_EMPENHO = re.compile(
    r"\s*[-–]\s*(PREGAO|PROCESSO|CONTRATO|EDITAL|DISPENSA|LICITACAO|PE\s+\d).*$",
    re.IGNORECASE
)

# Padrão de concentração sem espaço: "500MG" → "500 MG", "10ML" → "10 ML"
_CONCENTRACAO = re.compile(r"(\d+(?:[.,]\d+)?)\s*(MG|ML|MCG|G\b|UI|MEQ|%)")

# Padrão de princípio ativo: tudo antes da primeira concentração ou forma farmacêutica
_CONC_MARKER = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:MG|ML|MCG|G\b|UI|MEQ|%)|"
    r"\b(?:CAPSULAS?|COMPRIMIDOS?|AMPOLAS?|FRASCO|SOLUCAO|INJETAVEL|SUSPENSAO|XAROPE|POMADA|CREME|GEL|SUPOSITORIO)\b",
    re.IGNORECASE
)

# Score mínimo para incluir no resultado do fuzzy match
_SCORE_MINIMO = 70
# Score mínimo para considerar match "aceito" (sucesso de fase 2)
SCORE_ACEITO = 85

# Caminho padrão para o catálogo BPS — ancorado via Path(__file__) para funcionar em cron/CI
_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_CATMAT_PATH = str(_ROOT / "data" / "raw" / "bps_precos_referencia.csv")


class MedicamentoNormalizer:
    """
    Normaliza descrições de medicamentos e faz fuzzy match com catálogo CATMAT.

    Fluxo:
    1. Limpar: remover prefixos de empenho, caracteres especiais, padronizar maiúsculas
    2. Expandir abreviações
    3. Padronizar concentrações (500MG → 500 MG)
    4. Remover stopwords farmacêuticas
    5. Fuzzy match contra catálogo CATMAT do BPS via rapidfuzz
    """

    def __init__(self, catmat_catalog_path: str = _DEFAULT_CATMAT_PATH):
        self.catalog: Optional[pd.DataFrame] = None
        self._catalog_descriptions: Optional[list] = None
        catalog_file = Path(catmat_catalog_path)
        if catalog_file.exists():
            try:
                self.catalog = pd.read_csv(catmat_catalog_path)
                # Normalizar DS_ITEM do catálogo para comparação justa
                self._catalog_descriptions = (
                    self.catalog["DS_ITEM"]
                    .fillna("")
                    .str.upper()
                    .str.strip()
                    .tolist()
                )
            except Exception as e:
                logger.warning(f"Falha ao carregar catálogo CATMAT: {e}")
        else:
            logger.warning(
                f"Catálogo BPS não encontrado em {catmat_catalog_path}. "
                "Todos os items receberão catmat_codigo=null."
            )

    def limpar_descricao(self, texto: str) -> str:
        """
        Normaliza uma string de descrição de medicamento.

        Etapas:
        1. Converter para maiúsculas e strip
        2. Remover prefixos de empenho ("AQUISICAO DE MEDICAMENTOS -")
        3. Remover sufixos de processo ("- PREGAO ELETRONICO 012/2023")
        4. Remover caracteres especiais (manter letras, números, espaços, / .)
        5. Padronizar concentrações sem espaço: "500MG" → "500 MG"
        6. Expandir abreviações (CPS → CAPSULAS)
        7. Remover stopwords farmacêuticas
        8. Colapsar múltiplos espaços

        Exemplo:
            "AQUISICAO DE MEDICAMENTOS - AMOXICILINA 500MG CPS C/21 GENERICO - PREGAO 012"
            → "AMOXICILINA 500 MG CAPSULAS"
        """
        if not isinstance(texto, str) or not texto.strip():
            return ""

        texto = texto.upper().strip()

        # Remover prefixos de empenho
        texto = _PREFIXOS_EMPENHO.sub("", texto).strip()

        # Remover sufixos de processo
        texto = _SUFIXOS_EMPENHO.sub("", texto).strip()

        # Remover padrão de quantidade "C/21", "C/100", etc. antes de processar abreviações
        texto = re.sub(r"\bC/\d+\b", "", texto)

        # Remover caracteres especiais (manter letras, dígitos, espaço, /, .)
        texto = re.sub(r"[^A-Z0-9\s/.]", " ", texto)

        # Padronizar concentrações: "500MG" → "500 MG"
        texto = _CONCENTRACAO.sub(r"\1 \2", texto)

        # Expandir abreviações — substituição de palavra inteira
        palavras = texto.split()
        palavras_expandidas = [ABREVIACOES.get(p, p) for p in palavras]
        texto = " ".join(palavras_expandidas)

        # Remover stopwords farmacêuticas
        palavras = texto.split()
        palavras_filtradas = [p for p in palavras if p not in STOPWORDS_FARMACEUTICAS]
        texto = " ".join(palavras_filtradas)

        # Colapsar espaços múltiplos
        texto = re.sub(r"\s+", " ", texto).strip()

        return texto

    def extrair_principio_ativo(self, descricao: str) -> str:
        """
        Extrai o princípio ativo da descrição (já limpa).

        Estratégia: tudo que vem antes da primeira concentração numérica
        ou forma farmacêutica reconhecida.

        Exemplo: "AMOXICILINA TRIIDRATADA 500 MG CAPSULAS" → "AMOXICILINA TRIIDRATADA"
        """
        if not isinstance(descricao, str) or not descricao.strip():
            return ""

        desc_upper = descricao.upper().strip()
        match = _CONC_MARKER.search(desc_upper)
        if match:
            principio = desc_upper[: match.start()].strip()
            return principio if principio else desc_upper
        return desc_upper

    def fuzzy_match_catmat(self, descricao: str, top_n: int = 3) -> list:
        """
        Busca os itens mais similares no catálogo CATMAT usando token_set_ratio.

        Retorna lista de dicts com campos:
          {"catmat": str, "descricao": str, "score": float}

        Apenas matches com score >= _SCORE_MINIMO (70) são retornados.
        Lista vazia quando catálogo não disponível ou nenhum match.
        """
        if not HAS_FUZZY or self.catalog is None or self._catalog_descriptions is None:
            return []

        if not isinstance(descricao, str) or not descricao.strip():
            return []

        resultados = fuzz_process.extract(
            descricao,
            self._catalog_descriptions,
            scorer=fuzz.token_set_ratio,
            limit=top_n,
            score_cutoff=_SCORE_MINIMO,
        )

        matches = []
        for ds_item, score, idx in resultados:
            catmat_row = self.catalog.iloc[idx]
            matches.append({
                "catmat": str(catmat_row.get("CD_CATMAT", "")),
                "descricao": ds_item,
                "score": round(float(score), 2),
            })

        return matches

    def processar(self, input_glob: str, output_file: str) -> pd.DataFrame:
        """
        Carrega todos os arquivos de empenho matching input_glob,
        normaliza as descrições de medicamentos e salva JSON com colunas adicionais.

        Colunas adicionadas ao DataFrame original:
          - descricao_normalizada: str — descrição após limpeza e expansão
          - catmat_codigo: str | None — código CATMAT do melhor match (None se sem match)
          - catmat_descricao: str | None — descrição CATMAT do melhor match
          - match_score: float — score do melhor match (0.0 se sem match)
          - concentracao_extraida: str — concentração extraída da descrição normalizada
          - forma_farmaceutica: str — forma farmacêutica extraída da descrição normalizada

        Performance: usa rapidfuzz.process.cdist para matching em batch quando possível.

        Modo fixture: se MEDAUDIT_FIXTURE=1, usa data/fixtures/ em vez de input_glob.
        """
        fixture_mode = os.environ.get("MEDAUDIT_FIXTURE", "0") == "1"

        # Carregar dados de entrada
        frames: list = []

        if fixture_mode:
            # Localizar fixture relativa ao projeto (busca do arquivo normalizer.py para cima)
            base = Path(__file__).parent.parent.parent
            fixture_path = base / "data" / "fixtures" / "sorocaba_despesas_saude_2023_sample.json"
            if fixture_path.exists():
                frames.append(pd.read_json(str(fixture_path)))
                _log(f"Modo FIXTURE: carregando {fixture_path}")
            else:
                _log(f"FIXTURE não encontrada: {fixture_path}")
        else:
            arquivos = sorted(glob.glob(input_glob))
            if not arquivos:
                _log(f"Nenhum arquivo encontrado: {input_glob}")
            for arq in arquivos:
                try:
                    frames.append(pd.read_json(arq))
                except Exception as e:
                    logger.warning(f"Erro ao ler {arq}: {e}")

        if not frames:
            df_vazio = pd.DataFrame(columns=[
                "ds_historico", "descricao_normalizada",
                "catmat_codigo", "catmat_descricao", "match_score",
                "concentracao_extraida", "forma_farmaceutica"
            ])
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            df_vazio.to_json(output_file, orient="records", force_ascii=False, indent=2)
            return df_vazio

        df = pd.concat(frames, ignore_index=True)

        # Garantir que ds_historico existe
        if "ds_historico" not in df.columns:
            df["ds_historico"] = ""

        _log(f"Normalizando {len(df)} registros...")

        # Limpar descrições
        descricoes_limpas = [
            self.limpar_descricao(str(h)) for h in df["ds_historico"].fillna("")
        ]
        df["descricao_normalizada"] = descricoes_limpas

        # Extrair concentração e forma farmacêutica para validação pós-score (REQ-004)
        # Phase 3 usa estes campos para evitar falso CRÍTICO por mismatch de embalagem
        _FORMA_PAT = re.compile(
            r"\b(CAPSULAS?|COMPRIMIDOS?|AMPOLAS?|FRASCO|SOLUCAO|INJETAVEL|SUSPENSAO|XAROPE|POMADA|CREME|GEL)\b",
            re.IGNORECASE
        )

        def _extr_conc(s: str) -> str:
            m = _CONCENTRACAO.search(s)
            return m.group(0).strip() if m else ""

        def _extr_forma(s: str) -> str:
            m = _FORMA_PAT.search(s)
            return m.group(0).strip().upper() if m else ""

        df["concentracao_extraida"] = [_extr_conc(s) for s in descricoes_limpas]
        df["forma_farmaceutica"] = [_extr_forma(s) for s in descricoes_limpas]

        # Fuzzy match em batch
        catmat_codigos: list = []
        catmat_descricoes: list = []
        match_scores: list = []

        if HAS_FUZZY and self.catalog is not None and self._catalog_descriptions:
            # Batch via cdist para performance em grandes volumes
            # cdist retorna matriz (n_queries × n_choices) com scores
            from rapidfuzz.process import cdist as fuzz_cdist

            _log("Calculando fuzzy matches em batch (cdist)...")
            scores_matrix = fuzz_cdist(
                descricoes_limpas,
                self._catalog_descriptions,
                scorer=fuzz.token_set_ratio,
                workers=-1,  # usa todos os cores disponíveis
            )

            for i, scores_row in enumerate(tqdm(scores_matrix, desc="Matching CATMAT", leave=False)):
                best_idx = int(scores_row.argmax())
                best_score = float(scores_row[best_idx])

                if best_score >= _SCORE_MINIMO:
                    catmat_row = self.catalog.iloc[best_idx]
                    catmat_codigos.append(str(catmat_row.get("CD_CATMAT", "")))
                    catmat_descricoes.append(str(catmat_row.get("DS_ITEM", "")))
                    match_scores.append(round(best_score, 2))
                else:
                    catmat_codigos.append(None)
                    catmat_descricoes.append(None)
                    match_scores.append(0.0)
        else:
            # Sem catálogo: todos recebem null
            catmat_codigos = [None] * len(df)
            catmat_descricoes = [None] * len(df)
            match_scores = [0.0] * len(df)

        df["catmat_codigo"] = catmat_codigos
        df["catmat_descricao"] = catmat_descricoes
        df["match_score"] = match_scores

        # Salvar JSON
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        df.to_json(output_file, orient="records", force_ascii=False, indent=2)

        n_matched = sum(1 for s in match_scores if s >= SCORE_ACEITO)
        n_total = len(df)
        _log(
            f"Normalização concluída: {n_matched}/{n_total} "
            f"com score >= {SCORE_ACEITO} | Arquivo: {output_file}"
        )

        return df
