"""
Gerenciador do banco de dados — operações CRUD e queries.
"""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from credit_analysis.config import DB_PATH
from credit_analysis.database.models import Base, Issuer, Analysis


def _get_engine(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(db_path: Path = DB_PATH):
    """Cria as tabelas se não existirem."""
    engine = _get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(db_path: Path = DB_PATH) -> Session:
    engine = _get_engine(db_path)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal()


# ---------------------------------------------------------------------------
# Operações de Issuer
# ---------------------------------------------------------------------------

def get_or_create_issuer(session: Session, name: str, ticker: str, **kwargs) -> Issuer:
    """Retorna o emissor existente ou cria um novo."""
    issuer = (
        session.query(Issuer)
        .filter(Issuer.ticker == ticker)
        .first()
    )
    if issuer is None:
        issuer = Issuer(name=name, ticker=ticker, **kwargs)
        session.add(issuer)
        session.commit()
        session.refresh(issuer)
    else:
        # Atualiza campos que podem ter mudado
        for k, v in kwargs.items():
            if v and getattr(issuer, k, None) != v:
                setattr(issuer, k, v)
        session.commit()
    return issuer


def list_issuers(session: Session) -> list[Issuer]:
    return session.query(Issuer).order_by(Issuer.name).all()


def find_issuer_by_ticker(session: Session, ticker: str) -> Issuer | None:
    return session.query(Issuer).filter(Issuer.ticker == ticker).first()


# ---------------------------------------------------------------------------
# Operações de Analysis
# ---------------------------------------------------------------------------

def save_analysis(session: Session, analysis: Analysis) -> Analysis:
    """Persiste uma nova análise."""
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


def get_last_analysis(session: Session, issuer_id: int) -> Analysis | None:
    """Retorna a análise mais recente do emissor."""
    return (
        session.query(Analysis)
        .filter(Analysis.issuer_id == issuer_id)
        .order_by(Analysis.analysis_date.desc())
        .first()
    )


def get_analysis_history(
    session: Session, issuer_id: int, limit: int = 20
) -> list[Analysis]:
    """Retorna as últimas `limit` análises do emissor em ordem cronológica."""
    return (
        session.query(Analysis)
        .filter(Analysis.issuer_id == issuer_id)
        .order_by(Analysis.analysis_date.desc())
        .limit(limit)
        .all()
    )


def update_analysis(
    session: Session,
    analysis_id: int,
    updates: dict,
) -> Analysis | None:
    """Atualiza campos de uma análise existente (override manual)."""
    analysis = session.query(Analysis).filter(Analysis.id == analysis_id).first()
    if analysis is None:
        return None
    for key, value in updates.items():
        setattr(analysis, key, value)
    analysis.manual_override = True
    session.commit()
    session.refresh(analysis)
    return analysis
