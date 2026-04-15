"""
Modelos SQLAlchemy para o banco de dados do sistema de análise de crédito.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, Text, ForeignKey, JSON,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Issuer(Base):
    """Cadastro de emissores."""
    __tablename__ = "issuers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    ticker = Column(String(20))
    yfinance_ticker = Column(String(20))
    cnpj = Column(String(20))
    sector = Column(String(100))
    subsector = Column(String(100))
    cvm_code = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    analyses = relationship("Analysis", back_populates="issuer", order_by="Analysis.analysis_date")

    def __repr__(self):
        return f"<Issuer {self.ticker} — {self.name}>"


class Analysis(Base):
    """
    Uma análise completa de um emissor em uma data específica.
    Cada consulta gera uma nova linha de histórico.
    """
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issuer_id = Column(Integer, ForeignKey("issuers.id"), nullable=False)

    # Metadados
    analysis_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    balance_period = Column(String(30))   # ex.: "3T2024", "LTM set/24"
    analyst = Column(String(100), default="Sistema")

    # -----------------------------------------------------------------------
    # Notas por critério (1-5, aceita float para granularidade)
    # -----------------------------------------------------------------------
    score_leverage         = Column(Float)
    score_coverage         = Column(Float)
    score_liquidity        = Column(Float)
    score_debt_profile     = Column(Float)
    score_cash_generation  = Column(Float)
    score_revenue_trend    = Column(Float)
    score_margin_trend     = Column(Float)
    score_deleveraging     = Column(Float)
    score_governance       = Column(Float)
    score_sector_risk      = Column(Float)

    # -----------------------------------------------------------------------
    # Comentários por critério
    # -----------------------------------------------------------------------
    comment_leverage         = Column(Text)
    comment_coverage         = Column(Text)
    comment_liquidity        = Column(Text)
    comment_debt_profile     = Column(Text)
    comment_cash_generation  = Column(Text)
    comment_revenue_trend    = Column(Text)
    comment_margin_trend     = Column(Text)
    comment_deleveraging     = Column(Text)
    comment_governance       = Column(Text)
    comment_sector_risk      = Column(Text)

    # -----------------------------------------------------------------------
    # Resultado final
    # -----------------------------------------------------------------------
    weighted_score = Column(Float)   # média ponderada contínua (1.0 – 5.0)
    final_grade    = Column(Integer) # nota final 1-5

    # -----------------------------------------------------------------------
    # Comparação com análise anterior
    # -----------------------------------------------------------------------
    movement  = Column(String(20))  # upgrade | downgrade | manutenção | primeira_análise
    watchlist = Column(String(20))  # positivo | negativo | nenhum

    # -----------------------------------------------------------------------
    # Dados brutos e indicadores coletados
    # -----------------------------------------------------------------------
    raw_financial_data = Column(JSON)  # dict com indicadores numéricos usados

    # -----------------------------------------------------------------------
    # Narrativa
    # -----------------------------------------------------------------------
    executive_summary = Column(Text)
    key_positives     = Column(Text)
    key_risks         = Column(Text)
    relevant_news     = Column(Text)
    sources           = Column(Text)

    # -----------------------------------------------------------------------
    # Controle de override manual
    # -----------------------------------------------------------------------
    manual_override = Column(Boolean, default=False)
    manual_notes    = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    issuer = relationship("Issuer", back_populates="analyses")

    # ------------------------------------------------------------------
    # Helpers de leitura
    # ------------------------------------------------------------------
    def scores_dict(self) -> dict:
        return {
            "leverage":        self.score_leverage,
            "coverage":        self.score_coverage,
            "liquidity":       self.score_liquidity,
            "debt_profile":    self.score_debt_profile,
            "cash_generation": self.score_cash_generation,
            "revenue_trend":   self.score_revenue_trend,
            "margin_trend":    self.score_margin_trend,
            "deleveraging":    self.score_deleveraging,
            "governance":      self.score_governance,
            "sector_risk":     self.score_sector_risk,
        }

    def comments_dict(self) -> dict:
        return {
            "leverage":        self.comment_leverage,
            "coverage":        self.comment_coverage,
            "liquidity":       self.comment_liquidity,
            "debt_profile":    self.comment_debt_profile,
            "cash_generation": self.comment_cash_generation,
            "revenue_trend":   self.comment_revenue_trend,
            "margin_trend":    self.comment_margin_trend,
            "deleveraging":    self.comment_deleveraging,
            "governance":      self.comment_governance,
            "sector_risk":     self.comment_sector_risk,
        }

    def __repr__(self):
        return (
            f"<Analysis issuer_id={self.issuer_id} "
            f"date={self.analysis_date.date()} grade={self.final_grade}>"
        )
