"""
cnpj_collector.py
Enriquece dados de fornecedores consultando a API da Receita Federal
via BrasilAPI (gratuita, sem necessidade de cadastro).

API: https://brasilapi.com.br/api/cnpj/v1/{cnpj}
"""

import re
import time
import datetime
import logging
import requests
import json
from pathlib import Path
from rich.console import Console

BRASIL_API_URL = "https://brasilapi.com.br/api/cnpj/v1"

ROOT = Path(__file__).parent.parent.parent
CACHE_PATH = ROOT / "data" / "raw" / "cnpj_cache.json"
CACHE_TTL_DAYS = 30

logger = logging.getLogger(__name__)
console = Console()


def validar_cnpj(cnpj: str) -> bool:
    """Valida CNPJ pelo algoritmo de digito verificador."""
    c = "".join(filter(str.isdigit, cnpj))
    if len(c) != 14 or len(set(c)) == 1:
        return False

    def calcular_digito(c: str, pesos: list) -> int:
        s = sum(int(c[i]) * pesos[i] for i in range(len(pesos)))
        r = s % 11
        return 0 if r < 2 else 11 - r

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return int(c[12]) == calcular_digito(c, p1) and int(c[13]) == calcular_digito(c, p2)


def extrair_cnpj(id_fornecedor: str) -> str | None:
    """
    Extrai CNPJ numerico de strings no formato TCE-SP.
    Exemplos: "CNPJ - PESSOA JURIDICA - 46634044000174" -> "46634044000174"
    """
    if not id_fornecedor:
        return None
    m = re.search(r'\b(\d{14})\b', id_fornecedor)
    return m.group(1) if m else None


def carregar_cache() -> dict:
    """Carrega cache CNPJ do disco. Retorna {} se arquivo nao existe."""
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cache CNPJ corrompido, iniciando novo: %s", e)
    return {}


def salvar_cache(cache: dict) -> None:
    """Salva cache CNPJ em disco (cria diretorios se necessario)."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def cache_valido(entry: dict) -> bool:
    """Verifica se entrada do cache nao expirou (TTL 30 dias)."""
    try:
        consultado = datetime.datetime.fromisoformat(entry["_consultado_em"])
        return (datetime.datetime.now() - consultado).days < CACHE_TTL_DAYS
    except (KeyError, ValueError):
        return False


class CNPJCollector:
    """
    Consulta dados de CNPJ para detectar fornecedores suspeitos:
    - Empresa recém-aberta quando ganhou o contrato
    - Empresa com situação cadastral irregular
    - Capital social muito baixo para o valor do contrato
    - Sócios com outros CNPJs com irregularidades
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MedAuditSUS/1.0"})
        self._cache = {}

    def consultar(self, cnpj: str) -> dict | None:
        """Consulta dados de um CNPJ na BrasilAPI."""
        cnpj_limpo = "".join(filter(str.isdigit, cnpj))
        if cnpj_limpo in self._cache:
            return self._cache[cnpj_limpo]

        try:
            resp = self.session.get(f"{BRASIL_API_URL}/{cnpj_limpo}", timeout=10)
            if resp.status_code == 200:
                dados = resp.json()
                self._cache[cnpj_limpo] = dados
                time.sleep(0.4)  # Respeitar rate limit
                return dados
            elif resp.status_code == 404:
                return None
            else:
                resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.warning("Erro ao consultar CNPJ %s: %s", cnpj, e)
            return None

    def enriquecer_fornecedores(self, input_file: str, output_file: str) -> list[dict]:
        """
        Le empenhos TCE-SP, extrai CNPJs unicos, consulta BrasilAPI com cache em disco,
        calcula flags de risco e salva resultado.

        Args:
            input_file: Caminho para JSON de empenhos
            output_file: Caminho de saida para fornecedores enriquecidos
        """
        empenhos = json.loads(Path(input_file).read_text(encoding="utf-8"))
        console.print(f"[cyan]CNPJ:[/cyan] processando {len(empenhos)} empenhos de {input_file}")

        # Mapear CNPJ -> data_empenho mais antiga
        cnpj_datas: dict[str, str] = {}
        for emp in empenhos:
            raw = emp.get("cd_cnpj_cpf_fornecedor", "") or ""
            cnpj = extrair_cnpj(raw)
            if cnpj:
                dt = emp.get("dt_empenho", "")
                if cnpj not in cnpj_datas or (dt and dt < cnpj_datas[cnpj]):
                    cnpj_datas[cnpj] = dt

        console.print(f"[cyan]CNPJ:[/cyan] {len(cnpj_datas)} CNPJs unicos extraidos")

        cache = carregar_cache()
        resultado: list[dict] = []

        total = len(cnpj_datas)
        for i, (cnpj, data_empenho) in enumerate(cnpj_datas.items(), 1):
            console.print(f"[dim]Consultando CNPJ {i}/{total}: {cnpj}[/dim]")
            if not validar_cnpj(cnpj):
                logger.warning("CNPJ invalido ignorado: %s", cnpj)
                continue

            # Cache hit
            if cnpj in cache and cache_valido(cache[cnpj]):
                dados_api = cache[cnpj]
            else:
                dados_api = self.consultar(cnpj)
                time.sleep(0.35)  # rate limit BrasilAPI (~3 req/s)
                if dados_api is not None:
                    dados_api["_consultado_em"] = datetime.datetime.now().isoformat()
                    cache[cnpj] = dados_api
                    salvar_cache(cache)

            flags = self.avaliar_risco_cnpj(
                dados_cnpj=dados_api or {},
                data_contrato=data_empenho,
            )

            resultado.append({
                "cnpj": cnpj,
                "dados_api": dados_api,
                "flags_risco": flags,                       # mantido para compatibilidade com supplier_analyzer.py
                "empresa_nova": "empresa_nova" in flags,    # STAB-03: booleano explícito
                "data_empenho_referencia": data_empenho,
            })

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Carregar existentes para merge (preserva CNPJs de iterações anteriores — STAB-05)
        existentes_por_cnpj: dict[str, dict] = {}
        if output_path.exists():
            try:
                existentes = json.loads(output_path.read_text(encoding="utf-8"))
                existentes_por_cnpj = {e["cnpj"]: e for e in existentes if "cnpj" in e}
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning("Arquivo de fornecedores existente inválido, iniciando do zero: %s", e)

        # Merge: novo sobrescreve existente (dados mais recentes prevalecem)
        for entry in resultado:
            existentes_por_cnpj[entry["cnpj"]] = entry

        merged = list(existentes_por_cnpj.values())

        output_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        console.print(
            f"[green]Fornecedores enriquecidos:[/green] {output_file} "
            f"({len(merged)} CNPJs total, {len(resultado)} novos/atualizados)"
        )
        return resultado  # retorna apenas os processados nesta chamada (não o merged completo)

    def avaliar_risco_cnpj(self, dados_cnpj: dict, data_contrato: str) -> list[str]:
        """
        Calcula flags de risco para um fornecedor.

        Returns:
            Lista de strings com flags ativas, ex: ["empresa_nova", "situacao_irregular"]
        """
        flags: list[str] = []
        if not dados_cnpj:
            return flags

        # Flag: situacao irregular
        # BrasilAPI pode retornar string ("ATIVA") ou codigo inteiro (2 = ativa)
        situacao = dados_cnpj.get("situacao_cadastral", "")
        if isinstance(situacao, str) and situacao and situacao.upper() != "ATIVA":
            flags.append("situacao_irregular")
        elif isinstance(situacao, int) and situacao != 2:
            flags.append("situacao_irregular")

        # Flag: empresa nova (abertura < 6 meses antes do contrato)
        data_abertura_str = (dados_cnpj.get("data_inicio_atividade", "")
                              or dados_cnpj.get("data_abertura", "")
                              or dados_cnpj.get("abertura", ""))
        if data_abertura_str and data_contrato:
            try:
                dt_abertura = None
                for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        dt_abertura = datetime.datetime.strptime(data_abertura_str[:10], fmt)
                        break
                    except ValueError:
                        continue

                dt_contrato = None
                for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        dt_contrato = datetime.datetime.strptime(data_contrato[:10], fmt)
                        break
                    except ValueError:
                        continue

                if dt_abertura and dt_contrato:
                    if (dt_contrato - dt_abertura).days < 180:  # < 6 meses
                        flags.append("empresa_nova")
            except Exception as e:
                logger.debug("Erro ao calcular empresa_nova para %s: %s", data_abertura_str, e)

        return flags


def avaliar_risco_cnpj_standalone(dados_cnpj: dict, data_contrato: str) -> list[str]:
    """Wrapper standalone de CNPJCollector.avaliar_risco_cnpj() para uso em testes."""
    return CNPJCollector().avaliar_risco_cnpj(dados_cnpj, data_contrato)
