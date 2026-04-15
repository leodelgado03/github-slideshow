"""
Módulo 3 — Motor de Scoring

Transforma dados financeiros coletados em notas individuais (1-5)
e calcula a nota final ponderada.

Para critérios que não podem ser calculados automaticamente
(governança, risco setorial, perfil da dívida quando dados parciais),
o sistema pede input manual interativo ou aceita valor pré-definido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from credit_analysis.config import (
    WEIGHTS,
    CRITERIA_LABELS,
    GRADE_THRESHOLDS,
    LEVERAGE_THRESHOLDS,
    COVERAGE_THRESHOLDS,
    LIQUIDITY_THRESHOLDS,
    DEBT_PROFILE_THRESHOLDS,
    CASH_GEN_THRESHOLDS,
    REVENUE_TREND_THRESHOLDS,
    MARGIN_TREND_THRESHOLDS,
    DELEVERAGING_THRESHOLDS,
)
from credit_analysis.modules.collector import FinancialData
from credit_analysis.utils.helpers import (
    score_from_thresholds,
    weighted_average,
    score_to_grade,
    fmt_multiple,
    fmt_pct,
    yoy_change,
)


# ---------------------------------------------------------------------------
# Resultado do scoring de um critério individual
# ---------------------------------------------------------------------------

@dataclass
class CriterionResult:
    key: str
    label: str
    score: float
    weight: float
    comment: str
    is_manual: bool = False
    metric_value: Optional[float] = None
    metric_label: str = ""


# ---------------------------------------------------------------------------
# Resultado completo do scoring
# ---------------------------------------------------------------------------

@dataclass
class ScoringResult:
    criteria: dict[str, CriterionResult] = field(default_factory=dict)
    weighted_score: float = 0.0
    final_grade: int = 0
    balance_period: str = "N/D"
    financial_data: dict = field(default_factory=dict)

    def scores_dict(self) -> dict[str, float]:
        return {k: v.score for k, v in self.criteria.items()}

    def comments_dict(self) -> dict[str, str]:
        return {k: v.comment for k, v in self.criteria.items()}


# ---------------------------------------------------------------------------
# Helpers de scoring automático
# ---------------------------------------------------------------------------

def _score_leverage(data: FinancialData) -> CriterionResult:
    key = "leverage"
    lev = data.leverage_current
    if lev is None:
        return CriterionResult(
            key=key, label=CRITERIA_LABELS[key],
            score=0, weight=WEIGHTS[key],
            comment="Dado insuficiente para cálculo automático. Informe manualmente.",
            is_manual=True,
        )
    score = score_from_thresholds(lev, LEVERAGE_THRESHOLDS)
    comment = (
        f"Dívida Líquida / EBITDA = {fmt_multiple(lev)}. "
        + _leverage_comment(lev)
    )
    return CriterionResult(
        key=key, label=CRITERIA_LABELS[key],
        score=score, weight=WEIGHTS[key], comment=comment,
        metric_value=lev, metric_label="Dív. Líq. / EBITDA",
    )


def _leverage_comment(lev: float) -> str:
    if lev < 1.0:
        return "Alavancagem muito baixa — perfil conservador."
    if lev < 2.0:
        return "Alavancagem baixa — confortável."
    if lev < 3.5:
        return "Alavancagem moderada — aceitável para o setor."
    if lev < 5.0:
        return "Alavancagem elevada — requer monitoramento."
    return "Alavancagem muito elevada ou EBITDA negativo — risco significativo."


def _score_coverage(data: FinancialData) -> CriterionResult:
    key = "coverage"
    cov = data.coverage_current
    if cov is None:
        return CriterionResult(
            key=key, label=CRITERIA_LABELS[key],
            score=0, weight=WEIGHTS[key],
            comment="Dado insuficiente para cálculo automático. Informe manualmente.",
            is_manual=True,
        )
    score = score_from_thresholds(cov, COVERAGE_THRESHOLDS)
    comment = (
        f"EBITDA / Despesa Financeira = {fmt_multiple(cov)}. "
        + _coverage_comment(cov)
    )
    return CriterionResult(
        key=key, label=CRITERIA_LABELS[key],
        score=score, weight=WEIGHTS[key], comment=comment,
        metric_value=cov, metric_label="EBITDA / Desp. Financeira",
    )


def _coverage_comment(cov: float) -> str:
    if cov >= 5.0:
        return "Cobertura de juros excelente — ampla folga financeira."
    if cov >= 3.0:
        return "Cobertura de juros boa — confortável."
    if cov >= 2.0:
        return "Cobertura de juros adequada — monitorar."
    if cov >= 1.0:
        return "Cobertura de juros baixa — risco de pressão financeira."
    return "Cobertura de juros insuficiente — alerta de liquidez."


def _score_liquidity(data: FinancialData) -> CriterionResult:
    key = "liquidity"
    liq = data.liquidity_ratio
    if liq is None:
        return CriterionResult(
            key=key, label=CRITERIA_LABELS[key],
            score=0, weight=WEIGHTS[key],
            comment="Dado insuficiente para cálculo automático. Informe manualmente.",
            is_manual=True,
        )
    score = score_from_thresholds(liq, LIQUIDITY_THRESHOLDS)
    comment = (
        f"Caixa / Dívida CP = {fmt_multiple(liq)}. "
        + _liquidity_comment(liq)
    )
    return CriterionResult(
        key=key, label=CRITERIA_LABELS[key],
        score=score, weight=WEIGHTS[key], comment=comment,
        metric_value=liq, metric_label="Caixa / Dívida CP",
    )


def _liquidity_comment(liq: float) -> str:
    if liq >= 1.5:
        return "Caixa cobre com folga as obrigações de curto prazo."
    if liq >= 1.0:
        return "Caixa suficiente para cobrir dívida de curto prazo."
    if liq >= 0.7:
        return "Cobertura parcial — empresa pode precisar refinanciar."
    if liq >= 0.4:
        return "Liquidez de curto prazo pressionada."
    return "Liquidez de curto prazo crítica."


def _score_debt_profile(data: FinancialData) -> CriterionResult:
    key = "debt_profile"
    pct = data.short_term_debt_pct
    if pct is None:
        return CriterionResult(
            key=key, label=CRITERIA_LABELS[key],
            score=0, weight=WEIGHTS[key],
            comment="Concentração CP não calculável automaticamente. Informe manualmente.",
            is_manual=True,
        )
    score = score_from_thresholds(pct, DEBT_PROFILE_THRESHOLDS)
    comment = (
        f"Dívida CP / Dívida Total = {fmt_pct(pct)}. "
        + _debt_profile_comment(pct)
    )
    return CriterionResult(
        key=key, label=CRITERIA_LABELS[key],
        score=score, weight=WEIGHTS[key], comment=comment,
        metric_value=pct, metric_label="% Dívida CP / Total",
    )


def _debt_profile_comment(pct: float) -> str:
    if pct <= 0.15:
        return "Vencimentos bem distribuídos, baixa concentração no curto prazo."
    if pct <= 0.25:
        return "Concentração CP controlada — gestão de passivos adequada."
    if pct <= 0.40:
        return "Concentração CP moderada — monitorar renovação."
    if pct <= 0.60:
        return "Concentração significativa no curto prazo — risco de refinanciamento."
    return "Alta concentração de vencimentos no curto prazo — risco crítico."


def _score_cash_generation(data: FinancialData) -> CriterionResult:
    key = "cash_generation"
    margin = data.ebitda_margin_current
    if margin is None:
        return CriterionResult(
            key=key, label=CRITERIA_LABELS[key],
            score=0, weight=WEIGHTS[key],
            comment="Margem EBITDA não calculável. Informe manualmente.",
            is_manual=True,
        )
    score = score_from_thresholds(margin, CASH_GEN_THRESHOLDS)
    comment = (
        f"Margem EBITDA = {fmt_pct(margin)}. "
        + _cash_gen_comment(margin)
    )
    return CriterionResult(
        key=key, label=CRITERIA_LABELS[key],
        score=score, weight=WEIGHTS[key], comment=comment,
        metric_value=margin, metric_label="Margem EBITDA",
    )


def _cash_gen_comment(m: float) -> str:
    if m >= 0.25:
        return "Geração operacional de caixa excelente."
    if m >= 0.15:
        return "Boa geração de caixa operacional."
    if m >= 0.08:
        return "Geração de caixa satisfatória — monitorar."
    if m >= 0.00:
        return "Geração de caixa fraca — risco de pressão operacional."
    return "Empresa operando com EBITDA negativo — risco muito elevado."


def _score_revenue_trend(data: FinancialData) -> CriterionResult:
    key = "revenue_trend"
    change = yoy_change(data.revenue_current, data.revenue_prev_year)
    if change is None:
        return CriterionResult(
            key=key, label=CRITERIA_LABELS[key],
            score=0, weight=WEIGHTS[key],
            comment="Variação de receita YoY não disponível. Informe manualmente.",
            is_manual=True,
        )
    score = score_from_thresholds(change, REVENUE_TREND_THRESHOLDS)
    comment = (
        f"Crescimento receita YoY = {fmt_pct(change)}. "
        + _trend_comment(change, "receita")
    )
    return CriterionResult(
        key=key, label=CRITERIA_LABELS[key],
        score=score, weight=WEIGHTS[key], comment=comment,
        metric_value=change, metric_label="Crescimento Receita YoY",
    )


def _score_margin_trend(data: FinancialData) -> CriterionResult:
    key = "margin_trend"
    delta = None
    if data.ebitda_margin_current is not None and data.ebitda_margin_prev_year is not None:
        delta = data.ebitda_margin_current - data.ebitda_margin_prev_year
    if delta is None:
        return CriterionResult(
            key=key, label=CRITERIA_LABELS[key],
            score=0, weight=WEIGHTS[key],
            comment="Variação de margem YoY não disponível. Informe manualmente.",
            is_manual=True,
        )
    score = score_from_thresholds(delta, MARGIN_TREND_THRESHOLDS)
    sign = "+" if delta >= 0 else ""
    comment = (
        f"Variação margem EBITDA YoY = {sign}{fmt_pct(delta, 1)}pp. "
        + _margin_trend_comment(delta)
    )
    return CriterionResult(
        key=key, label=CRITERIA_LABELS[key],
        score=score, weight=WEIGHTS[key], comment=comment,
        metric_value=delta, metric_label="Δ Margem EBITDA YoY (pp)",
    )


def _margin_trend_comment(delta: float) -> str:
    if delta > 0.03:
        return "Forte expansão de margem — melhoria operacional relevante."
    if delta > 0.01:
        return "Margem em expansão — tendência positiva."
    if delta >= -0.01:
        return "Margem estável — sem deterioração significativa."
    if delta >= -0.03:
        return "Margem em contração leve — monitorar."
    return "Contração relevante de margem — pressão operacional."


def _score_deleveraging(data: FinancialData) -> CriterionResult:
    key = "deleveraging"
    delta = None
    if data.leverage_current is not None and data.leverage_prev_year is not None:
        delta = data.leverage_current - data.leverage_prev_year
    if delta is None:
        return CriterionResult(
            key=key, label=CRITERIA_LABELS[key],
            score=0, weight=WEIGHTS[key],
            comment="Tendência de alavancagem YoY não disponível. Informe manualmente.",
            is_manual=True,
        )
    score = score_from_thresholds(delta, DELEVERAGING_THRESHOLDS)
    sign = "+" if delta >= 0 else ""
    comment = (
        f"Variação alavancagem YoY = {sign}{fmt_multiple(delta, 2)}. "
        + _deleveraging_comment(delta)
    )
    return CriterionResult(
        key=key, label=CRITERIA_LABELS[key],
        score=score, weight=WEIGHTS[key], comment=comment,
        metric_value=delta, metric_label="Δ Alavancagem YoY (x)",
    )


def _trend_comment(change: float, metric: str) -> str:
    if change > 0.15:
        return f"Forte crescimento de {metric} — momentum positivo."
    if change > 0.05:
        return f"Crescimento moderado de {metric}."
    if change >= -0.05:
        return f"{metric.capitalize()} estável."
    if change >= -0.15:
        return f"Queda moderada de {metric} — atenção."
    return f"Queda relevante de {metric} — sinal de deterioração."


def _deleveraging_comment(delta: float) -> str:
    if delta < -1.0:
        return "Desalavancagem relevante — melhoria clara do perfil de crédito."
    if delta < -0.3:
        return "Tendência de desalavancagem — trajetória positiva."
    if delta <= 0.3:
        return "Alavancagem estável no período."
    if delta <= 1.0:
        return "Alavancagem crescente — monitorar deterioração."
    return "Alavancagem crescendo de forma acelerada — risco elevado."


# ---------------------------------------------------------------------------
# Critérios qualitativos (governance e sector_risk são manuais por padrão)
# ---------------------------------------------------------------------------

def _make_qualitative_criterion(key: str, score: float, comment: str) -> CriterionResult:
    return CriterionResult(
        key=key,
        label=CRITERIA_LABELS[key],
        score=score,
        weight=WEIGHTS[key],
        comment=comment,
        is_manual=True,
    )


# ---------------------------------------------------------------------------
# Função principal: executar scoring completo
# ---------------------------------------------------------------------------

def run_scoring(
    data: FinancialData,
    manual_scores: Optional[dict[str, float]] = None,
    manual_comments: Optional[dict[str, str]] = None,
    interactive: bool = True,
) -> ScoringResult:
    """
    Executa o scoring completo.

    Args:
        data:             dados financeiros coletados
        manual_scores:    scores já preenchidos manualmente (key → 1-5)
        manual_comments:  comentários manuais (key → texto)
        interactive:      se True, solicita input no terminal para critérios faltantes

    Returns:
        ScoringResult com todos os critérios preenchidos
    """
    manual_scores   = manual_scores or {}
    manual_comments = manual_comments or {}

    # Cálculo automático dos 8 critérios quantitativos
    auto_results: dict[str, CriterionResult] = {
        "leverage":        _score_leverage(data),
        "coverage":        _score_coverage(data),
        "liquidity":       _score_liquidity(data),
        "debt_profile":    _score_debt_profile(data),
        "cash_generation": _score_cash_generation(data),
        "revenue_trend":   _score_revenue_trend(data),
        "margin_trend":    _score_margin_trend(data),
        "deleveraging":    _score_deleveraging(data),
    }

    # Critérios qualitativos — sempre manuais
    auto_results["governance"] = _make_qualitative_criterion(
        "governance", score=0,
        comment="Avaliar qualidade de disclosure, governança corporativa, histórico e controlador.",
    )
    auto_results["sector_risk"] = _make_qualitative_criterion(
        "sector_risk", score=0,
        comment="Avaliar sensibilidade do setor a ciclos, juros, commodity, regulação e concentração.",
    )

    # Aplicar overrides manuais fornecidos programaticamente
    for key, score in manual_scores.items():
        if key in auto_results:
            auto_results[key].score = float(score)
            auto_results[key].is_manual = True
            if key in manual_comments:
                auto_results[key].comment = manual_comments[key]

    # Coleta interativa de critérios faltantes
    missing = [k for k, r in auto_results.items() if r.score == 0]
    if missing and interactive:
        _prompt_manual_scores(auto_results, missing)

    # Calcula nota final
    scores = {k: r.score for k, r in auto_results.items() if r.score > 0}
    w_score = weighted_average(scores, WEIGHTS)
    grade = score_to_grade(w_score, GRADE_THRESHOLDS)

    result = ScoringResult(
        criteria=auto_results,
        weighted_score=round(w_score, 3),
        final_grade=grade,
        balance_period=data.balance_period,
        financial_data=data.to_dict(),
    )
    return result


# ---------------------------------------------------------------------------
# Input interativo para critérios manuais
# ---------------------------------------------------------------------------

def _prompt_manual_scores(
    results: dict[str, CriterionResult],
    keys_to_fill: list[str],
):
    """Solicita input do usuário para critérios sem nota automática."""
    from rich.console import Console
    from rich.prompt import IntPrompt, Prompt

    console = Console()
    console.print(
        "\n[bold yellow]Critérios que precisam de avaliação manual:[/bold yellow]"
    )
    for key in keys_to_fill:
        r = results[key]
        console.print(f"\n  [cyan]{r.label}[/cyan]")
        console.print(f"  [dim]{r.comment}[/dim]")
        score = _get_int_prompt(f"  Nota (1-5)", min_val=1, max_val=5)
        comment = _get_str_prompt(f"  Comentário curto")
        r.score = float(score)
        r.comment = comment
        r.is_manual = True


def _get_int_prompt(label: str, min_val: int = 1, max_val: int = 5) -> int:
    """Captura input inteiro com validação."""
    while True:
        try:
            val = int(input(f"{label} [{min_val}-{max_val}]: ").strip())
            if min_val <= val <= max_val:
                return val
        except (ValueError, EOFError):
            pass
        print(f"  Por favor, informe um número entre {min_val} e {max_val}.")


def _get_str_prompt(label: str) -> str:
    """Captura input de texto."""
    try:
        return input(f"{label}: ").strip()
    except EOFError:
        return ""
