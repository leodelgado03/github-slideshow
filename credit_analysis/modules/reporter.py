"""
Módulo 6 — Reporter

Formata e exibe a análise completa no terminal usando a biblioteca Rich.
Oferece:
  - Resumo executivo (saída compacta)
  - Detalhamento completo (critérios, métricas, comparação)
  - Histórico tabular
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from credit_analysis.config import (
    CRITERIA_LABELS,
    GRADE_RISK_LABELS,
    GRADE_RECOMMENDATIONS,
    WEIGHTS,
)
from credit_analysis.database.models import Analysis
from credit_analysis.modules.identifier import IssuerInfo
from credit_analysis.modules.scorer import ScoringResult
from credit_analysis.utils.helpers import fmt_brl, fmt_multiple, fmt_pct

console = Console()


# ---------------------------------------------------------------------------
# Paletas
# ---------------------------------------------------------------------------

GRADE_COLORS = {5: "bold green", 4: "green", 3: "yellow", 2: "orange3", 1: "bold red"}
MOVEMENT_COLORS = {
    "upgrade":          "bold green",
    "downgrade":        "bold red",
    "manutenção":       "yellow",
    "primeira_análise": "bold cyan",
}
WATCHLIST_COLORS = {
    "positivo": "green",
    "negativo": "red",
    "nenhum":   "dim",
}
SCORE_COLORS = {5: "green", 4: "green", 3: "yellow", 2: "orange3", 1: "red"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade_panel(grade: int) -> Panel:
    color = GRADE_COLORS.get(grade, "white")
    stars = "★" * grade + "☆" * (5 - grade)
    risk  = GRADE_RISK_LABELS.get(grade, "N/D")
    text  = Text(justify="center")
    text.append(f"\n  {stars}  \n", style=color)
    text.append(f"  Nota  {grade} / 5  \n", style=f"bold {color}")
    text.append(f"  {risk}  \n", style=color)
    return Panel(text, title="[bold]Nota Final[/bold]", border_style=color, padding=(0, 2))


def _movement_badge(movement: str) -> Text:
    labels = {
        "upgrade":          "▲ UPGRADE",
        "downgrade":        "▼ DOWNGRADE",
        "manutenção":       "= MANUTENÇÃO",
        "primeira_análise": "● PRIMEIRA ANÁLISE",
    }
    color  = MOVEMENT_COLORS.get(movement, "white")
    label  = labels.get(movement, movement.upper())
    return Text(label, style=f"bold {color}")


def _watchlist_badge(watchlist: str) -> Text:
    labels = {
        "positivo": "▲ WATCH POSITIVO",
        "negativo": "▼ WATCH NEGATIVO",
        "nenhum":   "— SEM WATCH",
    }
    color = WATCHLIST_COLORS.get(watchlist, "dim")
    label = labels.get(watchlist, watchlist.upper())
    return Text(label, style=color)


def _score_bar(score: Optional[float]) -> str:
    """Barra visual de 1 a 5."""
    if score is None:
        return "[dim]N/D[/dim]"
    filled   = int(round(score))
    color    = SCORE_COLORS.get(filled, "white")
    bar      = "█" * filled + "░" * (5 - filled)
    return f"[{color}]{bar}[/{color}] [bold]{score:.1f}[/bold]"


# ---------------------------------------------------------------------------
# Saída resumida
# ---------------------------------------------------------------------------

def print_summary(
    issuer: IssuerInfo,
    scoring: ScoringResult,
    movement: str,
    watchlist: str,
    comparison: Optional[dict] = None,
):
    console.rule(
        f"[bold]Análise de Crédito — {issuer.name} ({issuer.ticker})[/bold]"
    )

    # Cabeçalho
    header = Table.grid(padding=(0, 2))
    header.add_column(justify="left")
    header.add_column(justify="left")
    header.add_row("[dim]Emissor[/dim]",  f"[bold]{issuer.name}[/bold]")
    header.add_row("[dim]Ticker[/dim]",   issuer.ticker)
    header.add_row("[dim]Setor[/dim]",    f"{issuer.sector} / {issuer.subsector}")
    header.add_row(
        "[dim]Data Análise[/dim]",
        datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
    )
    header.add_row("[dim]Período[/dim]",  scoring.balance_period)
    console.print(header)
    console.print()

    # Nota e movimento lado a lado
    grade_panel = _grade_panel(scoring.final_grade)
    move_text   = Text(justify="left")
    move_text.append("\n")
    move_text.append("  Movimento:  ", style="dim")
    move_text.append(_movement_badge(movement))
    move_text.append("\n")
    move_text.append("  Watchlist:  ", style="dim")
    move_text.append(_watchlist_badge(watchlist))
    move_text.append("\n\n")
    move_text.append(
        f"  {GRADE_RECOMMENDATIONS.get(scoring.final_grade, '')}",
        style="italic",
    )
    move_text.append("\n")

    if comparison and comparison.get("prev_grade") is not None:
        prev = comparison["prev_grade"]
        ws_delta = comparison.get("delta_ws", 0) or 0
        sign = "+" if ws_delta >= 0 else ""
        move_text.append(
            f"\n  Análise anterior: Nota {prev}  "
            f"(score {sign}{ws_delta:.3f})",
            style="dim",
        )
        if comparison.get("prev_date"):
            move_text.append(
                f"\n  Data anterior: {comparison['prev_date'].strftime('%d/%m/%Y')}",
                style="dim",
            )

    console.print(
        Columns([grade_panel, Panel(move_text, title="Resultado", padding=(0, 1))],
                equal=False)
    )


# ---------------------------------------------------------------------------
# Saída detalhada
# ---------------------------------------------------------------------------

def print_detailed(
    issuer: IssuerInfo,
    scoring: ScoringResult,
    comparison: Optional[dict] = None,
):
    console.print()
    console.rule("[bold]Detalhamento por Critério[/bold]")

    # Tabela de critérios
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE_HEAVY,
        padding=(0, 1),
    )
    table.add_column("Critério",         style="bold", width=38)
    table.add_column("Peso",             justify="right", width=6)
    table.add_column("Nota",             justify="center", width=20)
    table.add_column("Manual",           justify="center", width=7)
    table.add_column("Comentário",       width=50)
    if comparison and comparison.get("criteria_deltas"):
        table.add_column("Δ vs Anterior", justify="center", width=14)

    for key, cr in scoring.criteria.items():
        label    = CRITERIA_LABELS.get(key, key)
        peso     = f"{WEIGHTS.get(key, 0)*100:.0f}%"
        score_bar = _score_bar(cr.score if cr.score else None)
        manual   = "[yellow]Sim[/yellow]" if cr.is_manual else "[dim]Não[/dim]"
        comment  = cr.comment[:100] + "..." if len(cr.comment or "") > 100 else (cr.comment or "")

        row = [label, peso, score_bar, manual, comment]
        if comparison and comparison.get("criteria_deltas"):
            delta = comparison["criteria_deltas"].get(key)
            if delta is not None:
                sign  = "+" if delta >= 0 else ""
                color = "green" if delta > 0 else ("red" if delta < 0 else "dim")
                row.append(f"[{color}]{sign}{delta:.1f}[/{color}]")
            else:
                row.append("[dim]N/D[/dim]")

        table.add_row(*row)

    console.print(table)

    # Score ponderado
    ws_color = GRADE_COLORS.get(scoring.final_grade, "white")
    console.print(
        f"  [dim]Score ponderado contínuo:[/dim] "
        f"[{ws_color}][bold]{scoring.weighted_score:.3f}[/bold][/{ws_color}]  →  "
        f"Nota final [{ws_color}][bold]{scoring.final_grade}[/bold][/{ws_color}]"
    )

    # Indicadores financeiros chave
    _print_financial_indicators(scoring.financial_data)


def _print_financial_indicators(raw: dict):
    """Exibe tabela com indicadores financeiros coletados."""
    if not raw:
        return
    console.print()
    console.rule("[dim]Indicadores Financeiros Coletados[/dim]")

    indicators = [
        ("Receita Líquida",         "revenue_current",          fmt_brl),
        ("EBITDA",                  "ebitda_current",            fmt_brl),
        ("Margem EBITDA",           "ebitda_margin_current",     fmt_pct),
        ("Dívida Líquida",          "net_debt_current",          fmt_brl),
        ("Dívida Total Bruta",      "total_debt_current",        fmt_brl),
        ("Caixa",                   "cash_current",              fmt_brl),
        ("Dívida CP",               "short_term_debt_current",   fmt_brl),
        ("Alavancagem (Dív/EBITDA)","leverage_current",          fmt_multiple),
        ("Cobertura de Juros",      "coverage_current",          fmt_multiple),
        ("Liquidez (Cx/DívCP)",     "liquidity_ratio",           fmt_multiple),
        ("FCO",                     "operating_cashflow_current",fmt_brl),
    ]

    tbl = Table(show_header=True, header_style="dim", box=box.MINIMAL)
    tbl.add_column("Indicador", width=30)
    tbl.add_column("Valor",     justify="right", width=16)

    for label, key, fmt_fn in indicators:
        val = raw.get(key)
        if val is not None:
            tbl.add_row(label, fmt_fn(val))

    console.print(tbl)


# ---------------------------------------------------------------------------
# Notícias relevantes
# ---------------------------------------------------------------------------

def print_news(news: list[dict], limit: int = 6):
    if not news:
        return
    console.print()
    console.rule("[dim]Notícias Recentes[/dim]")
    for item in news[:limit]:
        title     = item.get("title", "")
        source    = item.get("source", "")
        published = item.get("published", "")
        console.print(f"  • [bold]{title}[/bold]")
        console.print(f"    [dim]{source}  —  {published}[/dim]")


# ---------------------------------------------------------------------------
# Histórico tabular
# ---------------------------------------------------------------------------

def print_history_table(issuer_name: str, rows: list[dict]):
    console.rule(f"[bold]Histórico de Análises — {issuer_name}[/bold]")

    if not rows:
        console.print("[dim]Nenhuma análise registrada para este emissor.[/dim]")
        return

    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE_HEAVY,
    )
    for col in rows[0].keys():
        table.add_column(col, justify="center")

    for row in rows:
        cells = []
        for k, v in row.items():
            if k == "Nota Final" and v not in (None, "N/D"):
                color = GRADE_COLORS.get(int(v), "white")
                cells.append(f"[{color}][bold]{v}[/bold][/{color}]")
            elif k == "Movimento":
                color = MOVEMENT_COLORS.get(str(v).lower(), "white")
                cells.append(f"[{color}]{v}[/{color}]")
            else:
                cells.append(str(v))
        table.add_row(*cells)

    console.print(table)
