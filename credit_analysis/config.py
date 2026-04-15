"""
Configurações centrais do sistema de análise de crédito.
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "analyses.db"
CATALOG_PATH = DATA_DIR / "issuers_catalog.json"

# ---------------------------------------------------------------------------
# Pesos dos critérios (soma = 1.0)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "leverage":         0.15,
    "coverage":         0.15,
    "liquidity":        0.10,
    "debt_profile":     0.10,
    "cash_generation":  0.10,
    "revenue_trend":    0.08,
    "margin_trend":     0.08,
    "deleveraging":     0.09,
    "governance":       0.08,
    "sector_risk":      0.07,
}

CRITERIA_LABELS = {
    "leverage":         "Alavancagem (Dív. Líq. / EBITDA)",
    "coverage":         "Cobertura de Juros (EBITDA / Desp. Fin.)",
    "liquidity":        "Liquidez de Curto Prazo",
    "debt_profile":     "Perfil de Vencimento da Dívida",
    "cash_generation":  "Geração de Caixa (Margem EBITDA)",
    "revenue_trend":    "Tendência de Receita (YoY)",
    "margin_trend":     "Tendência de Margem EBITDA (YoY)",
    "deleveraging":     "Tendência de Desalavancagem (YoY)",
    "governance":       "Governança e Transparência",
    "sector_risk":      "Risco Setorial / Regulatório",
}

# ---------------------------------------------------------------------------
# Thresholds para nota final ponderada → grade 1-5
# ---------------------------------------------------------------------------
GRADE_THRESHOLDS = [
    (4.50, 5.01, 5),
    (3.70, 4.50, 4),
    (2.90, 3.70, 3),
    (2.00, 2.90, 2),
    (1.00, 2.00, 1),
]

# ---------------------------------------------------------------------------
# Rótulos e recomendações por nota final
# ---------------------------------------------------------------------------
GRADE_RISK_LABELS = {
    5: "Risco Muito Baixo",
    4: "Risco Baixo / Controlado",
    3: "Risco Moderado",
    2: "Risco Elevado",
    1: "Risco Muito Elevado",
}

GRADE_RECOMMENDATIONS = {
    5: "Apto para recomendação com alta convicção",
    4: "Apto para recomendação",
    3: "Recomendação seletiva — monitorar com atenção",
    2: "Evitar novas alocações",
    1: "Não recomendar",
}

# ---------------------------------------------------------------------------
# Thresholds individuais para scoring automático
# ---------------------------------------------------------------------------

# Leverage: Dívida Líquida / EBITDA (menor = melhor)
LEVERAGE_THRESHOLDS = [
    (float("-inf"), 1.0,  5),
    (1.0,           2.0,  4),
    (2.0,           3.5,  3),
    (3.5,           5.0,  2),
    (5.0,           float("inf"), 1),
]

# Coverage: EBITDA / Despesa Financeira (maior = melhor)
COVERAGE_THRESHOLDS = [
    (5.0,           float("inf"), 5),
    (3.0,           5.0,  4),
    (2.0,           3.0,  3),
    (1.0,           2.0,  2),
    (float("-inf"), 1.0,  1),
]

# Liquidity: Caixa / Dívida CP (maior = melhor)
LIQUIDITY_THRESHOLDS = [
    (1.5,           float("inf"), 5),
    (1.0,           1.5,  4),
    (0.7,           1.0,  3),
    (0.4,           0.7,  2),
    (float("-inf"), 0.4,  1),
]

# Debt Profile: % da dívida vencendo em 12m (menor = melhor)
DEBT_PROFILE_THRESHOLDS = [
    (float("-inf"), 0.15, 5),
    (0.15,          0.25, 4),
    (0.25,          0.40, 3),
    (0.40,          0.60, 2),
    (0.60,          float("inf"), 1),
]

# Cash Generation: Margem EBITDA (maior = melhor)
CASH_GEN_THRESHOLDS = [
    (0.25,          float("inf"), 5),
    (0.15,          0.25, 4),
    (0.08,          0.15, 3),
    (0.00,          0.08, 2),
    (float("-inf"), 0.00, 1),
]

# Revenue Trend: crescimento YoY de receita (maior = melhor)
REVENUE_TREND_THRESHOLDS = [
    (0.15,          float("inf"), 5),
    (0.05,          0.15, 4),
    (-0.05,         0.05, 3),
    (-0.15,         -0.05, 2),
    (float("-inf"), -0.15, 1),
]

# Margin Trend: variação em pp da margem EBITDA YoY (maior = melhor)
MARGIN_TREND_THRESHOLDS = [
    (0.03,          float("inf"), 5),
    (0.01,          0.03, 4),
    (-0.01,         0.01, 3),
    (-0.03,         -0.01, 2),
    (float("-inf"), -0.03, 1),
]

# Deleveraging Trend: variação YoY da alavancagem (negativo = desalavancagem = melhor)
DELEVERAGING_THRESHOLDS = [
    (float("-inf"), -1.0,  5),
    (-1.0,          -0.3,  4),
    (-0.3,           0.3,  3),
    (0.3,            1.0,  2),
    (1.0,            float("inf"), 1),
]
