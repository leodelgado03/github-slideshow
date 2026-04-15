"""
Módulo 4 — Histórico

Salva e recupera análises por emissor.
Toda consulta bem-sucedida vira uma nova revisão no histórico.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from credit_analysis.database.manager import (
    get_or_create_issuer,
    save_analysis,
    get_last_analysis,
    get_analysis_history,
)
from credit_analysis.database.models import Analysis, Issuer
from credit_analysis.modules.identifier import IssuerInfo
from credit_analysis.modules.scorer import ScoringResult


def persist_analysis(
    session: Session,
    issuer_info: IssuerInfo,
    scoring: ScoringResult,
    movement: str,
    watchlist: str,
    executive_summary: str = "",
    key_positives: str = "",
    key_risks: str = "",
    relevant_news: str = "",
    sources: str = "",
) -> tuple[Issuer, Analysis]:
    """
    Salva uma nova análise no banco de dados.

    Retorna o objeto Issuer e o objeto Analysis criados/atualizados.
    """
    # Garante que o emissor existe no banco
    issuer = get_or_create_issuer(
        session,
        name=issuer_info.name,
        ticker=issuer_info.ticker,
        yfinance_ticker=issuer_info.yfinance_ticker,
        sector=issuer_info.sector,
        subsector=issuer_info.subsector,
        cnpj=issuer_info.cnpj,
        cvm_code=issuer_info.cvm_code,
    )

    scores = scoring.scores_dict()
    comments = scoring.comments_dict()

    analysis = Analysis(
        issuer_id=issuer.id,
        analysis_date=datetime.utcnow(),
        balance_period=scoring.balance_period,

        # Scores
        score_leverage=scores.get("leverage"),
        score_coverage=scores.get("coverage"),
        score_liquidity=scores.get("liquidity"),
        score_debt_profile=scores.get("debt_profile"),
        score_cash_generation=scores.get("cash_generation"),
        score_revenue_trend=scores.get("revenue_trend"),
        score_margin_trend=scores.get("margin_trend"),
        score_deleveraging=scores.get("deleveraging"),
        score_governance=scores.get("governance"),
        score_sector_risk=scores.get("sector_risk"),

        # Comentários
        comment_leverage=comments.get("leverage"),
        comment_coverage=comments.get("coverage"),
        comment_liquidity=comments.get("liquidity"),
        comment_debt_profile=comments.get("debt_profile"),
        comment_cash_generation=comments.get("cash_generation"),
        comment_revenue_trend=comments.get("revenue_trend"),
        comment_margin_trend=comments.get("margin_trend"),
        comment_deleveraging=comments.get("deleveraging"),
        comment_governance=comments.get("governance"),
        comment_sector_risk=comments.get("sector_risk"),

        # Resultado
        weighted_score=scoring.weighted_score,
        final_grade=scoring.final_grade,

        # Comparação
        movement=movement,
        watchlist=watchlist,

        # Narrativa
        executive_summary=executive_summary,
        key_positives=key_positives,
        key_risks=key_risks,
        relevant_news=relevant_news,
        sources=sources,

        # Dados brutos (serialização segura)
        raw_financial_data=_safe_financial_dict(scoring.financial_data),
    )

    saved = save_analysis(session, analysis)
    return issuer, saved


def _safe_financial_dict(data: dict) -> dict:
    """Remove valores não serializáveis (como DataFrames) do dict de dados financeiros."""
    safe = {}
    for k, v in data.items():
        if isinstance(v, (int, float, str, bool, list, dict)) or v is None:
            safe[k] = v
        elif hasattr(v, "isoformat"):
            safe[k] = v.isoformat()
    return safe


def get_previous_analysis(session: Session, issuer_id: int) -> Optional[Analysis]:
    """Retorna a análise anterior (penúltima), excluindo a mais recente."""
    history = get_analysis_history(session, issuer_id, limit=2)
    if len(history) >= 2:
        return history[1]  # A mais recente é history[0]
    return None


def get_full_history(session: Session, issuer_id: int, limit: int = 20) -> list[Analysis]:
    return get_analysis_history(session, issuer_id, limit=limit)


def format_history_table(analyses: list[Analysis]) -> list[dict]:
    """Converte lista de Analysis em lista de dicts para exibição tabular."""
    rows = []
    for a in analyses:
        rows.append({
            "Data":          a.analysis_date.strftime("%d/%m/%Y"),
            "Período":       a.balance_period or "N/D",
            "Nota Final":    a.final_grade or "N/D",
            "Score":         f"{a.weighted_score:.2f}" if a.weighted_score else "N/D",
            "Movimento":     a.movement or "N/D",
            "Watchlist":     a.watchlist or "nenhum",
            "Manual":        "Sim" if a.manual_override else "Não",
        })
    return rows
