"""
Módulo 5 — Comparação

Compara a nova análise com a análise anterior do mesmo emissor:
  - Determina movimento: upgrade | downgrade | manutenção | primeira_análise
  - Sugere status de watchlist: positivo | negativo | nenhum
"""

from __future__ import annotations

from typing import Optional

from credit_analysis.database.models import Analysis
from credit_analysis.modules.scorer import ScoringResult
from credit_analysis.config import WEIGHTS


def determine_movement(
    current_grade: int,
    previous_analysis: Optional[Analysis],
) -> str:
    """
    Determina o movimento em relação à análise anterior.

    Returns:
        'upgrade' | 'downgrade' | 'manutenção' | 'primeira_análise'
    """
    if previous_analysis is None or previous_analysis.final_grade is None:
        return "primeira_análise"
    prev_grade = previous_analysis.final_grade
    if current_grade > prev_grade:
        return "upgrade"
    if current_grade < prev_grade:
        return "downgrade"
    return "manutenção"


def determine_watchlist(
    scoring: ScoringResult,
    previous_analysis: Optional[Analysis],
) -> str:
    """
    Sugere status de watchlist mesmo quando a nota final não mudou.

    Lógica:
      - Compara o weighted_score atual com o anterior (não só o grade arredondado)
      - Analisa critérios-chave que mais pesam para detectar tendências

    Returns:
        'positivo' | 'negativo' | 'nenhum'
    """
    if previous_analysis is None:
        return "nenhum"

    current_ws  = scoring.weighted_score
    previous_ws = previous_analysis.weighted_score

    if previous_ws is None:
        return "nenhum"

    delta_ws = current_ws - previous_ws

    # Nota final igual mas score contínuo mudou significativamente
    if scoring.final_grade == previous_analysis.final_grade:
        if delta_ws >= 0.20:
            return "positivo"
        if delta_ws <= -0.20:
            return "negativo"

    # Análise de critérios-chave (leverage, coverage, liquidity)
    key_criteria = ["leverage", "coverage", "liquidity"]
    key_deltas = []
    prev_scores = previous_analysis.scores_dict() if previous_analysis else {}
    curr_scores = scoring.scores_dict()

    for k in key_criteria:
        prev_val = prev_scores.get(k)
        curr_val = curr_scores.get(k)
        if prev_val and curr_val:
            key_deltas.append(curr_val - prev_val)

    if key_deltas:
        avg_key_delta = sum(key_deltas) / len(key_deltas)
        if avg_key_delta >= 0.5 and delta_ws >= 0.10:
            return "positivo"
        if avg_key_delta <= -0.5 and delta_ws <= -0.10:
            return "negativo"

    return "nenhum"


def build_comparison_summary(
    scoring: ScoringResult,
    previous_analysis: Optional[Analysis],
    movement: str,
    watchlist: str,
) -> dict:
    """
    Constrói um dict de comparação detalhada para uso no reporter.
    """
    if previous_analysis is None:
        return {
            "movement":     movement,
            "watchlist":    watchlist,
            "prev_grade":   None,
            "prev_ws":      None,
            "delta_ws":     None,
            "criteria_deltas": {},
        }

    prev_scores = previous_analysis.scores_dict()
    curr_scores = scoring.scores_dict()

    criteria_deltas = {}
    for key in curr_scores:
        prev = prev_scores.get(key)
        curr = curr_scores.get(key)
        if prev is not None and curr is not None:
            criteria_deltas[key] = round(curr - prev, 2)

    return {
        "movement":        movement,
        "watchlist":       watchlist,
        "prev_grade":      previous_analysis.final_grade,
        "prev_ws":         previous_analysis.weighted_score,
        "delta_ws":        round(scoring.weighted_score - (previous_analysis.weighted_score or 0), 3),
        "prev_date":       previous_analysis.analysis_date,
        "prev_period":     previous_analysis.balance_period,
        "criteria_deltas": criteria_deltas,
    }
