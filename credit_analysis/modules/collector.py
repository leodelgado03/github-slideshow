"""
Módulo 2 — Coleta de Dados

Busca automática de:
  - Demonstrações financeiras via yfinance (trimestral e anual)
  - Notícias recentes via Google News RSS
  - Dados qualitativos básicos via yfinance.info

Estrutura do dicionário retornado (FinancialData):
  - revenue_current / revenue_prev_year  : receita líquida
  - ebitda_current / ebitda_prev_year    : EBITDA (calculado ou direto)
  - ebit_current                         : EBIT / resultado operacional
  - net_income_current                   : lucro líquido
  - total_debt_current                   : dívida total bruta
  - short_term_debt_current              : dívida de curto prazo
  - cash_current                         : caixa e equivalentes
  - net_debt_current                     : dívida líquida (= total_debt - cash)
  - interest_expense_current             : despesa financeira líquida
  - operating_cashflow_current           : FCO
  - ebitda_margin_current/prev_year      : margem EBITDA
  - leverage_current / prev_year         : Dív. Líq. / EBITDA
  - balance_period                       : período do balanço
  - news                                 : lista de notícias recentes
  - sources                              : fontes utilizadas
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

import feedparser
import pandas as pd
import yfinance as yf

from credit_analysis.modules.identifier import IssuerInfo


# ---------------------------------------------------------------------------
# Estrutura de dados coletados
# ---------------------------------------------------------------------------

class FinancialData:
    """Contêiner com os dados financeiros coletados para um emissor."""

    def __init__(self):
        # Receita
        self.revenue_current: Optional[float] = None
        self.revenue_prev_year: Optional[float] = None
        self.revenue_prev_quarter: Optional[float] = None

        # EBITDA
        self.ebitda_current: Optional[float] = None
        self.ebitda_prev_year: Optional[float] = None

        # EBIT / Resultado Operacional
        self.ebit_current: Optional[float] = None

        # Lucro Líquido
        self.net_income_current: Optional[float] = None

        # Dívida e Caixa
        self.total_debt_current: Optional[float] = None
        self.short_term_debt_current: Optional[float] = None
        self.long_term_debt_current: Optional[float] = None
        self.cash_current: Optional[float] = None
        self.net_debt_current: Optional[float] = None
        self.net_debt_prev_year: Optional[float] = None

        # Despesa financeira
        self.interest_expense_current: Optional[float] = None

        # Fluxo de caixa operacional
        self.operating_cashflow_current: Optional[float] = None

        # Indicadores derivados
        self.ebitda_margin_current: Optional[float] = None
        self.ebitda_margin_prev_year: Optional[float] = None
        self.leverage_current: Optional[float] = None
        self.leverage_prev_year: Optional[float] = None
        self.coverage_current: Optional[float] = None
        self.liquidity_ratio: Optional[float] = None
        self.short_term_debt_pct: Optional[float] = None   # CP / Total Debt

        # Metadados
        self.balance_period: str = "N/D"
        self.balance_date: Optional[datetime] = None
        self.news: list[dict] = []
        self.sources: list[str] = []
        self.company_info: dict = {}

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _safe_get(df: Optional[pd.DataFrame], row_keys: list[str], col_idx: int = 0) -> Optional[float]:
    """Tenta extrair um valor de um DataFrame usando múltiplos nomes de linha."""
    if df is None or df.empty:
        return None
    for key in row_keys:
        if key in df.index:
            try:
                val = df.loc[key].iloc[col_idx]
                if pd.notna(val):
                    return float(val)
            except Exception:
                continue
    return None


def _period_label(dt: datetime) -> str:
    """Converte datetime em label de período (ex.: '3T2024')."""
    quarter = (dt.month - 1) // 3 + 1
    return f"{quarter}T{dt.year}"


def _fetch_news(company_name: str, ticker: str, max_items: int = 8) -> list[dict]:
    """Busca notícias via Google News RSS."""
    query = f"{company_name} resultados crédito dívida"
    url = (
        "https://news.google.com/rss/search"
        f"?q={query.replace(' ', '+')}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )
    news_items: list[dict] = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_items]:
            news_items.append({
                "title":     entry.get("title", ""),
                "published": entry.get("published", ""),
                "link":      entry.get("link", ""),
                "source":    entry.get("source", {}).get("title", "Google News"),
            })
    except Exception:
        pass

    # Complementa com ticker-specific search
    if ticker:
        url2 = (
            "https://news.google.com/rss/search"
            f"?q={ticker}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        )
        try:
            feed2 = feedparser.parse(url2)
            existing_titles = {n["title"] for n in news_items}
            for entry in feed2.entries[:4]:
                title = entry.get("title", "")
                if title not in existing_titles:
                    news_items.append({
                        "title":     title,
                        "published": entry.get("published", ""),
                        "link":      entry.get("link", ""),
                        "source":    entry.get("source", {}).get("title", "Google News"),
                    })
                    existing_titles.add(title)
        except Exception:
            pass

    return news_items[:max_items]


# ---------------------------------------------------------------------------
# Coleta principal
# ---------------------------------------------------------------------------

def collect_financial_data(issuer: IssuerInfo) -> FinancialData:
    """
    Coleta todos os dados financeiros disponíveis para o emissor.
    Usa yfinance como fonte primária.
    """
    data = FinancialData()
    yf_ticker = issuer.yfinance_ticker or (issuer.ticker + ".SA")

    # ------------------------------------------------------------------
    # yfinance
    # ------------------------------------------------------------------
    try:
        t = yf.Ticker(yf_ticker)
        info = t.info or {}
        data.company_info = info
        data.sources.append(f"yfinance — {yf_ticker}")

        # ---- Demonstrações trimestrais --------------------------------
        q_income  = t.quarterly_income_stmt
        q_balance = t.quarterly_balance_sheet
        q_cf      = t.quarterly_cashflow

        # ---- Income Statement -----------------------------------------
        # Receita
        data.revenue_current = _safe_get(
            q_income,
            ["Total Revenue", "Revenue", "Net Revenue", "TotalRevenue"],
            col_idx=0,
        )
        data.revenue_prev_year = _safe_get(
            q_income,
            ["Total Revenue", "Revenue", "Net Revenue", "TotalRevenue"],
            col_idx=4,   # mesmo trimestre ~1 ano atrás
        )

        # EBIT
        data.ebit_current = _safe_get(
            q_income,
            ["EBIT", "Operating Income", "OperatingIncome"],
            col_idx=0,
        )

        # EBITDA — tenta direto, depois calcula
        data.ebitda_current = _safe_get(
            q_income,
            ["EBITDA", "Normalized EBITDA", "NormalizedEBITDA"],
            col_idx=0,
        )
        if data.ebitda_current is None and data.ebit_current is not None:
            da = _safe_get(
                q_cf,
                ["Depreciation And Amortization", "Depreciation", "DepreciationAndAmortization"],
                col_idx=0,
            ) or 0.0
            data.ebitda_current = data.ebit_current + da

        # EBITDA ano anterior (para tendência)
        ebit_prev = _safe_get(
            q_income,
            ["EBIT", "Operating Income", "OperatingIncome"],
            col_idx=4,
        )
        data.ebitda_prev_year = _safe_get(
            q_income,
            ["EBITDA", "Normalized EBITDA", "NormalizedEBITDA"],
            col_idx=4,
        )
        if data.ebitda_prev_year is None and ebit_prev is not None:
            da_prev = _safe_get(
                q_cf,
                ["Depreciation And Amortization", "Depreciation"],
                col_idx=4,
            ) or 0.0
            data.ebitda_prev_year = ebit_prev + da_prev

        # Despesa financeira
        data.interest_expense_current = _safe_get(
            q_income,
            ["Interest Expense", "InterestExpense", "Net Interest Income"],
            col_idx=0,
        )
        if data.interest_expense_current is not None:
            # yfinance retorna negativo para despesa — normalizamos para positivo
            data.interest_expense_current = abs(data.interest_expense_current)

        # Lucro Líquido
        data.net_income_current = _safe_get(
            q_income,
            ["Net Income", "NetIncome", "Net Income Common Stockholders"],
            col_idx=0,
        )

        # ---- Balance Sheet ---------------------------------------------
        data.cash_current = _safe_get(
            q_balance,
            ["Cash And Cash Equivalents", "Cash", "CashAndCashEquivalents",
             "Cash Cash Equivalents And Short Term Investments"],
            col_idx=0,
        )
        data.total_debt_current = _safe_get(
            q_balance,
            ["Total Debt", "TotalDebt"],
            col_idx=0,
        )
        if data.total_debt_current is None:
            long_debt = _safe_get(
                q_balance,
                ["Long Term Debt", "LongTermDebt"],
                col_idx=0,
            ) or 0.0
            short_debt = _safe_get(
                q_balance,
                ["Short Long Term Debt", "Current Debt", "ShortLongTermDebt",
                 "Current Portion Of Long Term Debt"],
                col_idx=0,
            ) or 0.0
            total = long_debt + short_debt
            if total > 0:
                data.total_debt_current = total

        data.short_term_debt_current = _safe_get(
            q_balance,
            ["Short Long Term Debt", "Current Debt", "CurrentDebt",
             "Short Term Debt", "Current Portion Of Long Term Debt"],
            col_idx=0,
        )
        data.long_term_debt_current = _safe_get(
            q_balance,
            ["Long Term Debt", "LongTermDebt"],
            col_idx=0,
        )

        # Dívida líquida
        if data.total_debt_current is not None and data.cash_current is not None:
            data.net_debt_current = data.total_debt_current - data.cash_current

        # Dívida líquida no período anterior (para tendência de alavancagem)
        cash_prev = _safe_get(
            q_balance,
            ["Cash And Cash Equivalents", "Cash", "CashAndCashEquivalents",
             "Cash Cash Equivalents And Short Term Investments"],
            col_idx=4,
        )
        debt_prev = _safe_get(
            q_balance,
            ["Total Debt", "TotalDebt"],
            col_idx=4,
        )
        if debt_prev is not None and cash_prev is not None:
            data.net_debt_prev_year = debt_prev - cash_prev

        # ---- Cash Flow -------------------------------------------------
        data.operating_cashflow_current = _safe_get(
            q_cf,
            ["Operating Cash Flow", "Cash From Operations",
             "Net Cash Provided By Operating Activities"],
            col_idx=0,
        )

        # ---- Período do Balanço ----------------------------------------
        if q_balance is not None and not q_balance.empty:
            col = q_balance.columns[0]
            if hasattr(col, "to_pydatetime"):
                data.balance_date = col.to_pydatetime()
                data.balance_period = _period_label(data.balance_date)

        # ---- Indicadores Derivados ------------------------------------
        # Margem EBITDA
        if data.ebitda_current and data.revenue_current:
            data.ebitda_margin_current = data.ebitda_current / data.revenue_current
        if data.ebitda_prev_year and data.revenue_prev_year:
            data.ebitda_margin_prev_year = data.ebitda_prev_year / data.revenue_prev_year

        # Alavancagem (Dív. Líq. / EBITDA) — usamos LTM quando possível
        if data.net_debt_current is not None and data.ebitda_current is not None:
            if data.ebitda_current > 0:
                data.leverage_current = data.net_debt_current / data.ebitda_current
            elif data.ebitda_current < 0:
                data.leverage_current = 99.0  # EBITDA negativo = alavancagem extrema

        if data.net_debt_prev_year is not None and data.ebitda_prev_year is not None:
            if data.ebitda_prev_year > 0:
                data.leverage_prev_year = data.net_debt_prev_year / data.ebitda_prev_year

        # Cobertura de juros (EBITDA / Despesa Financeira)
        if data.ebitda_current and data.interest_expense_current:
            if data.interest_expense_current > 0:
                data.coverage_current = data.ebitda_current / data.interest_expense_current

        # Liquidez (Caixa / Dívida CP)
        if data.cash_current and data.short_term_debt_current:
            if data.short_term_debt_current > 0:
                data.liquidity_ratio = data.cash_current / data.short_term_debt_current

        # Concentração CP (Short-term / Total)
        if data.short_term_debt_current and data.total_debt_current:
            if data.total_debt_current > 0:
                data.short_term_debt_pct = data.short_term_debt_current / data.total_debt_current

    except Exception as exc:
        data.sources.append(f"yfinance — erro: {exc}")

    # ------------------------------------------------------------------
    # Notícias (Google News RSS)
    # ------------------------------------------------------------------
    try:
        data.news = _fetch_news(issuer.name, issuer.ticker)
        if data.news:
            data.sources.append("Google News RSS")
    except Exception:
        pass

    return data
