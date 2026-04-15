"""
Módulo 1 — Identificação do Emissor

Recebe nome ou ticker e encontra o emissor correto:
  1. Busca no catálogo local (issuers_catalog.json)
  2. Busca no banco de dados (emissores já analisados)
  3. Consulta yfinance como fallback
  4. Se houver ambiguidade, retorna lista de opções para o usuário escolher
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

import yfinance as yf

from credit_analysis.config import CATALOG_PATH
from credit_analysis.utils.helpers import normalize_text, clean_ticker, is_b3_ticker


@dataclass
class IssuerInfo:
    """Dados identificados de um emissor."""
    name: str
    ticker: str
    yfinance_ticker: str
    sector: str = "N/D"
    subsector: str = "N/D"
    cnpj: str = ""
    cvm_code: str = ""
    source: str = "catalog"          # catalog | database | yfinance | manual

    def to_db_kwargs(self) -> dict:
        return {
            "name":             self.name,
            "ticker":           self.ticker,
            "yfinance_ticker":  self.yfinance_ticker,
            "sector":           self.sector,
            "subsector":        self.subsector,
            "cnpj":             self.cnpj,
            "cvm_code":         self.cvm_code,
        }


def _load_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("issuers", [])


def _catalog_match(query: str, catalog: list[dict]) -> list[IssuerInfo]:
    """Busca fuzzy no catálogo por nome, alias ou ticker."""
    q = normalize_text(query)
    q_clean = clean_ticker(query)
    results: list[IssuerInfo] = []
    seen: set[str] = set()

    for entry in catalog:
        # Correspondência exata por ticker
        if entry.get("ticker", "").upper() == q_clean:
            info = _entry_to_info(entry)
            if info.ticker not in seen:
                results.append(info)
                seen.add(info.ticker)
            continue

        # Correspondência por nome normalizado
        if q in normalize_text(entry.get("name", "")):
            info = _entry_to_info(entry)
            if info.ticker not in seen:
                results.append(info)
                seen.add(info.ticker)
            continue

        # Correspondência por aliases
        for alias in entry.get("aliases", []):
            if q in normalize_text(alias) or normalize_text(alias) in q:
                info = _entry_to_info(entry)
                if info.ticker not in seen:
                    results.append(info)
                    seen.add(info.ticker)
                break

    return results


def _entry_to_info(entry: dict) -> IssuerInfo:
    return IssuerInfo(
        name=entry["name"],
        ticker=entry.get("ticker", ""),
        yfinance_ticker=entry.get("yfinance_ticker", entry.get("ticker", "") + ".SA"),
        sector=entry.get("sector", "N/D"),
        subsector=entry.get("subsector", "N/D"),
        cnpj=entry.get("cnpj", ""),
        cvm_code=entry.get("cvm_code", ""),
        source="catalog",
    )


def _yfinance_lookup(query: str) -> Optional[IssuerInfo]:
    """Tenta resolver o emissor via yfinance como último recurso."""
    candidates = [query]
    if is_b3_ticker(query.upper()):
        candidates = [query.upper() + ".SA", query.upper()]
    elif not query.endswith(".SA"):
        candidates.append(query.upper() + ".SA")

    for ticker_str in candidates:
        try:
            t = yf.Ticker(ticker_str)
            info = t.info or {}
            if info.get("shortName") or info.get("longName"):
                name = info.get("longName") or info.get("shortName", ticker_str)
                sector = info.get("sector", "N/D")
                return IssuerInfo(
                    name=name,
                    ticker=ticker_str.replace(".SA", ""),
                    yfinance_ticker=ticker_str if ".SA" in ticker_str else ticker_str + ".SA",
                    sector=sector,
                    source="yfinance",
                )
        except Exception:
            continue
    return None


def identify_issuer(
    query: str,
    db_session=None,
) -> tuple[Optional[IssuerInfo], list[IssuerInfo]]:
    """
    Identifica o emissor a partir de um nome ou ticker.

    Retorna:
        (issuer_info, candidates)
        - Se encontrou exatamente um resultado: (issuer_info, [issuer_info])
        - Se encontrou múltiplos: (None, [lista de opções])
        - Se não encontrou nada: (None, [])
    """
    catalog = _load_catalog()
    candidates = _catalog_match(query, catalog)

    # Se não encontrou no catálogo, tenta o banco de dados
    if not candidates and db_session is not None:
        from credit_analysis.database.manager import list_issuers
        q = normalize_text(query)
        for issuer in list_issuers(db_session):
            if (
                q in normalize_text(issuer.name)
                or clean_ticker(query) == (issuer.ticker or "").upper()
            ):
                candidates.append(
                    IssuerInfo(
                        name=issuer.name,
                        ticker=issuer.ticker or "",
                        yfinance_ticker=issuer.yfinance_ticker or "",
                        sector=issuer.sector or "N/D",
                        subsector=issuer.subsector or "N/D",
                        cnpj=issuer.cnpj or "",
                        source="database",
                    )
                )

    # Fallback yfinance
    if not candidates:
        yf_result = _yfinance_lookup(query)
        if yf_result:
            candidates.append(yf_result)

    if len(candidates) == 1:
        return candidates[0], candidates
    if len(candidates) > 1:
        return None, candidates
    return None, []


def resolve_ambiguity(candidates: list[IssuerInfo], choice: int) -> Optional[IssuerInfo]:
    """Retorna o emissor escolhido pelo índice (1-based)."""
    idx = choice - 1
    if 0 <= idx < len(candidates):
        return candidates[idx]
    return None
