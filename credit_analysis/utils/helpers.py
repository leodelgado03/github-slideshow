"""
Funções utilitárias compartilhadas entre módulos.
"""

from __future__ import annotations

import re
from typing import Optional
from unicodedata import normalize


def normalize_text(text: str) -> str:
    """Remove acentos e converte para minúsculas para comparação."""
    return normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower().strip()


def clean_ticker(ticker: str) -> str:
    """Normaliza um ticker removendo espaços e colocando em maiúsculas."""
    return ticker.strip().upper()


def is_b3_ticker(ticker: str) -> bool:
    """Retorna True se o ticker parece ser um ticker de ação da B3."""
    return bool(re.match(r"^[A-Z]{4}[0-9]{1,2}$", ticker))


def score_from_thresholds(value: float, thresholds: list[tuple]) -> int:
    """
    Aplica thresholds do tipo (low, high, score) para determinar a nota.
    Os intervalos são [low, high).
    """
    for low, high, score in thresholds:
        if low <= value < high:
            return score
    return 1  # fallback para o pior caso


def weighted_average(scores: dict[str, float], weights: dict[str, float]) -> float:
    """Calcula a média ponderada dos critérios com nota."""
    total_weight = 0.0
    total_score = 0.0
    for key, score in scores.items():
        if score is not None:
            w = weights.get(key, 0.0)
            total_score += score * w
            total_weight += w
    if total_weight == 0:
        return 0.0
    return total_score / total_weight


def score_to_grade(weighted_score: float, thresholds: list[tuple]) -> int:
    """Converte a pontuação ponderada para a nota final 1-5."""
    for low, high, grade in thresholds:
        if low <= weighted_score < high:
            return grade
    return 1


def fmt_brl(value: Optional[float], decimals: int = 1) -> str:
    """Formata um número em bilhões ou milhões de reais."""
    if value is None:
        return "N/D"
    if abs(value) >= 1e9:
        return f"R$ {value/1e9:.{decimals}f}B"
    if abs(value) >= 1e6:
        return f"R$ {value/1e6:.{decimals}f}M"
    return f"R$ {value:,.0f}"


def fmt_pct(value: Optional[float], decimals: int = 1) -> str:
    """Formata um valor como porcentagem."""
    if value is None:
        return "N/D"
    return f"{value*100:.{decimals}f}%"


def fmt_multiple(value: Optional[float], decimals: int = 2) -> str:
    """Formata um valor como múltiplo (ex.: 2.34x)."""
    if value is None:
        return "N/D"
    return f"{value:.{decimals}f}x"


def yoy_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Calcula variação YoY. Retorna None se dados insuficientes."""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)
