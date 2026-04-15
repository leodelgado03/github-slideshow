"""
Sistema de Análise de Emissores de Crédito Privado
===================================================

CLI principal. Comandos disponíveis:

  analyze   — Analisa um emissor sob demanda
  history   — Exibe o histórico de análises de um emissor
  list      — Lista todos os emissores já analisados
  edit      — Ajuste manual de uma análise existente
"""

from __future__ import annotations

import sys
from typing import Optional

import click
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

from credit_analysis.database.manager import (
    get_session,
    get_last_analysis,
    list_issuers,
    update_analysis,
    get_analysis_history,
)
from credit_analysis.modules.collector import collect_financial_data
from credit_analysis.modules.comparator import (
    build_comparison_summary,
    determine_movement,
    determine_watchlist,
)
from credit_analysis.modules.history import (
    format_history_table,
    get_full_history,
    get_previous_analysis,
    persist_analysis,
)
from credit_analysis.modules.identifier import identify_issuer, resolve_ambiguity
from credit_analysis.modules.reporter import (
    console,
    print_detailed,
    print_history_table,
    print_news,
    print_summary,
)
from credit_analysis.modules.scorer import run_scoring
from credit_analysis.config import CRITERIA_LABELS

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """Sistema de Análise de Emissores de Crédito Privado."""
    pass


# ---------------------------------------------------------------------------
# Comando: analyze
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query", metavar="EMISSOR_OU_TICKER")
@click.option("--no-news",     is_flag=True, default=False, help="Não exibe notícias.")
@click.option("--auto",        is_flag=True, default=False,
              help="Não solicita inputs manuais (usa 3 para critérios qualitativos).")
@click.option("--save/--no-save", default=True, help="Salva a análise no histórico.")
def analyze(query: str, no_news: bool, auto: bool, save: bool):
    """Analisa um emissor sob demanda.

    EMISSOR_OU_TICKER pode ser o ticker (SIMH3), o nome (Simpar) ou parte do nome.
    """
    session = get_session()
    try:
        _run_analysis(query, session, show_news=not no_news, auto=auto, do_save=save)
    finally:
        session.close()


def _run_analysis(
    query: str,
    session,
    show_news: bool = True,
    auto: bool = False,
    do_save: bool = True,
):
    # ------------------------------------------------------------------
    # 1. Identificação do emissor
    # ------------------------------------------------------------------
    console.print(f"\n[bold cyan]Identificando emissor:[/bold cyan] {query}")
    issuer_info, candidates = identify_issuer(query, db_session=session)

    if not candidates:
        console.print(
            f"[bold red]Emissor não encontrado:[/bold red] '{query}'\n"
            "Verifique o nome, ticker ou adicione o emissor ao catálogo."
        )
        return

    if issuer_info is None:
        # Ambiguidade — pede confirmação ao usuário
        console.print(
            f"\n[yellow]Múltiplos emissores encontrados para '[bold]{query}[/bold]':[/yellow]"
        )
        for i, c in enumerate(candidates, 1):
            console.print(f"  {i}. {c.name} ({c.ticker}) — {c.sector}")
        choice = IntPrompt.ask("Escolha o número do emissor", default=1)
        issuer_info = resolve_ambiguity(candidates, choice)
        if issuer_info is None:
            console.print("[red]Escolha inválida.[/red]")
            return

    console.print(
        f"[green]✓ Emissor identificado:[/green] {issuer_info.name} "
        f"([bold]{issuer_info.ticker}[/bold]) — {issuer_info.sector}"
    )

    # ------------------------------------------------------------------
    # 2. Coleta de dados
    # ------------------------------------------------------------------
    console.print("\n[bold cyan]Coletando dados financeiros...[/bold cyan]")
    data = collect_financial_data(issuer_info)

    collected = []
    if data.revenue_current:
        collected.append("receita")
    if data.ebitda_current:
        collected.append("EBITDA")
    if data.net_debt_current is not None:
        collected.append("dívida líquida")
    if data.leverage_current is not None:
        collected.append("alavancagem")

    if collected:
        console.print(f"[green]✓ Dados coletados:[/green] {', '.join(collected)}")
        if data.balance_period != "N/D":
            console.print(f"  [dim]Período de referência: {data.balance_period}[/dim]")
    else:
        console.print(
            "[yellow]⚠ Não foi possível coletar dados financeiros automáticos.[/yellow]\n"
            "  Os critérios quantitativos precisarão ser informados manualmente."
        )

    # ------------------------------------------------------------------
    # 3. Scoring
    # ------------------------------------------------------------------
    console.print("\n[bold cyan]Calculando scores...[/bold cyan]")

    # Se --auto: preenche critérios manuais com nota 3 (neutro)
    manual_scores: dict[str, float] = {}
    manual_comments: dict[str, str] = {}
    if auto:
        manual_scores   = {"governance": 3.0, "sector_risk": 3.0}
        manual_comments = {
            "governance":   "Avaliação automática padrão (3/5). Revisar manualmente.",
            "sector_risk":  "Avaliação automática padrão (3/5). Revisar manualmente.",
        }

    scoring = run_scoring(
        data,
        manual_scores=manual_scores,
        manual_comments=manual_comments,
        interactive=not auto,
    )

    # ------------------------------------------------------------------
    # 4. Comparação com análise anterior
    # ------------------------------------------------------------------
    # Busca o emissor no banco para obter análise anterior
    from credit_analysis.database.manager import find_issuer_by_ticker
    existing_issuer = find_issuer_by_ticker(session, issuer_info.ticker)
    previous = None
    if existing_issuer:
        previous = get_last_analysis(session, existing_issuer.id)

    movement  = determine_movement(scoring.final_grade, previous)
    watchlist = determine_watchlist(scoring, previous)
    comparison = build_comparison_summary(scoring, previous, movement, watchlist)

    # ------------------------------------------------------------------
    # 5. Narrativa (resumo automático)
    # ------------------------------------------------------------------
    executive_summary = _build_executive_summary(issuer_info, scoring, movement, watchlist)
    key_positives     = _build_positives(scoring)
    key_risks         = _build_risks(scoring)
    relevant_news     = _format_news_text(data.news)
    sources           = "; ".join(data.sources)

    # ------------------------------------------------------------------
    # 6. Exibição
    # ------------------------------------------------------------------
    print_summary(issuer_info, scoring, movement, watchlist, comparison)
    print_detailed(issuer_info, scoring, comparison)

    if show_news and data.news:
        print_news(data.news)

    # ------------------------------------------------------------------
    # 7. Salvar no histórico
    # ------------------------------------------------------------------
    if do_save:
        issuer_obj, analysis_obj = persist_analysis(
            session,
            issuer_info=issuer_info,
            scoring=scoring,
            movement=movement,
            watchlist=watchlist,
            executive_summary=executive_summary,
            key_positives=key_positives,
            key_risks=key_risks,
            relevant_news=relevant_news,
            sources=sources,
        )
        console.print(
            f"\n[green]✓ Análise salva no histórico.[/green] "
            f"(ID: {analysis_obj.id}, Emissor ID: {issuer_obj.id})"
        )

    console.print()


# ---------------------------------------------------------------------------
# Comando: history
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query", metavar="EMISSOR_OU_TICKER")
@click.option("--limit", default=10, show_default=True, help="Número máximo de registros.")
def history(query: str, limit: int):
    """Exibe o histórico de análises de um emissor."""
    session = get_session()
    try:
        issuer_info, candidates = identify_issuer(query, db_session=session)
        if not candidates:
            console.print(f"[red]Emissor não encontrado:[/red] {query}")
            return
        if issuer_info is None:
            issuer_info = candidates[0]

        from credit_analysis.database.manager import find_issuer_by_ticker
        existing = find_issuer_by_ticker(session, issuer_info.ticker)
        if not existing:
            console.print(f"[yellow]Nenhuma análise registrada para {issuer_info.name}.[/yellow]")
            return

        analyses = get_full_history(session, existing.id, limit=limit)
        rows     = format_history_table(analyses)
        print_history_table(issuer_info.name, rows)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Comando: list
# ---------------------------------------------------------------------------

@cli.command("list")
def list_all():
    """Lista todos os emissores já analisados."""
    session = get_session()
    try:
        issuers = list_issuers(session)
        if not issuers:
            console.print("[dim]Nenhum emissor analisado ainda.[/dim]")
            return

        from rich.table import Table
        from rich import box as rbox
        table = Table(
            title="Emissores Analisados",
            header_style="bold cyan",
            box=rbox.SIMPLE_HEAVY,
        )
        table.add_column("Ticker")
        table.add_column("Nome")
        table.add_column("Setor")
        table.add_column("Análises", justify="right")
        table.add_column("Última Nota", justify="center")

        for iss in issuers:
            last = get_last_analysis(session, iss.id)
            count = len(iss.analyses)
            note = str(last.final_grade) if last and last.final_grade else "—"
            table.add_row(iss.ticker or "—", iss.name, iss.sector or "—", str(count), note)

        console.print(table)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Comando: edit
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query", metavar="EMISSOR_OU_TICKER")
@click.option("--analysis-id", type=int, default=None,
              help="ID da análise a editar (padrão: mais recente).")
def edit(query: str, analysis_id: Optional[int]):
    """Ajuste manual de notas e comentários de uma análise existente."""
    session = get_session()
    try:
        issuer_info, candidates = identify_issuer(query, db_session=session)
        if not candidates:
            console.print(f"[red]Emissor não encontrado:[/red] {query}")
            return
        if issuer_info is None:
            issuer_info = candidates[0]

        from credit_analysis.database.manager import find_issuer_by_ticker
        existing = find_issuer_by_ticker(session, issuer_info.ticker)
        if not existing:
            console.print(f"[yellow]Nenhuma análise registrada para {issuer_info.name}.[/yellow]")
            return

        if analysis_id:
            target = session.query(
                __import__(
                    "credit_analysis.database.models",
                    fromlist=["Analysis"]
                ).Analysis
            ).filter_by(id=analysis_id, issuer_id=existing.id).first()
        else:
            target = get_last_analysis(session, existing.id)

        if not target:
            console.print("[red]Análise não encontrada.[/red]")
            return

        console.print(
            f"\n[bold]Editando análise ID {target.id}[/bold] — "
            f"{target.analysis_date.strftime('%d/%m/%Y')}"
        )
        console.print(
            f"Nota final atual: [bold]{target.final_grade}[/bold]  "
            f"(score {target.weighted_score:.3f})\n"
        )

        updates: dict = {}
        for key, label in CRITERIA_LABELS.items():
            score_attr   = f"score_{key}"
            comment_attr = f"comment_{key}"
            current_score = getattr(target, score_attr, None)
            console.print(f"[cyan]{label}[/cyan]  atual: [bold]{current_score}[/bold]")
            raw = input(f"  Nova nota (1-5) ou Enter para manter: ").strip()
            if raw:
                try:
                    val = float(raw)
                    if 1 <= val <= 5:
                        updates[score_attr] = val
                except ValueError:
                    pass
            raw_c = input(f"  Novo comentário (Enter para manter): ").strip()
            if raw_c:
                updates[comment_attr] = raw_c

        # Notas de override
        notes = input("\nObservação manual geral (Enter para pular): ").strip()
        if notes:
            updates["manual_notes"] = notes

        if updates:
            # Recalcula nota final se scores foram alterados
            from credit_analysis.config import WEIGHTS, GRADE_THRESHOLDS
            from credit_analysis.utils.helpers import weighted_average, score_to_grade

            score_keys = {
                k.replace("score_", ""): v
                for k, v in updates.items()
                if k.startswith("score_")
            }
            # Merge com scores existentes
            all_scores = target.scores_dict()
            all_scores.update(score_keys)
            valid_scores = {k: v for k, v in all_scores.items() if v}
            ws = weighted_average(valid_scores, WEIGHTS)
            grade = score_to_grade(ws, GRADE_THRESHOLDS)
            updates["weighted_score"] = round(ws, 3)
            updates["final_grade"]    = grade
            updates["manual_override"] = True

            updated = update_analysis(session, target.id, updates)
            console.print(
                f"\n[green]✓ Análise ID {updated.id} atualizada.[/green]  "
                f"Nova nota: [bold]{updated.final_grade}[/bold]  "
                f"(score {updated.weighted_score:.3f})"
            )
        else:
            console.print("[dim]Nenhuma alteração realizada.[/dim]")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helpers de narrativa automática
# ---------------------------------------------------------------------------

def _build_executive_summary(
    issuer: IssuerInfo,
    scoring: ScoringResult,
    movement: str,
    watchlist: str,
) -> str:
    from credit_analysis.config import GRADE_RISK_LABELS, GRADE_RECOMMENDATIONS
    risk  = GRADE_RISK_LABELS.get(scoring.final_grade, "")
    rec   = GRADE_RECOMMENDATIONS.get(scoring.final_grade, "")
    mov_label = {
        "upgrade":          "apresentou melhora em relação à análise anterior",
        "downgrade":        "apresentou deterioração em relação à análise anterior",
        "manutenção":       "manteve perfil de risco estável",
        "primeira_análise": "foi analisado pela primeira vez neste sistema",
    }.get(movement, "")

    lines = [
        f"{issuer.name} ({issuer.ticker}) — Setor: {issuer.sector}.",
        f"Nota final: {scoring.final_grade}/5 ({risk}). {rec}.",
        f"O emissor {mov_label}.",
    ]
    if watchlist != "nenhum":
        wl = "tendência de melhora" if watchlist == "positivo" else "sinal de deterioração"
        lines.append(f"Watch: {wl} identificada nos indicadores.")

    return " ".join(lines)


def _build_positives(scoring: ScoringResult) -> str:
    positives = []
    for key, cr in scoring.criteria.items():
        if cr.score and cr.score >= 4:
            positives.append(f"• {CRITERIA_LABELS.get(key, key)}: nota {cr.score:.0f}/5")
    return "\n".join(positives) if positives else "Nenhum critério com destaque positivo."


def _build_risks(scoring: ScoringResult) -> str:
    risks = []
    for key, cr in scoring.criteria.items():
        if cr.score and cr.score <= 2:
            risks.append(f"• {CRITERIA_LABELS.get(key, key)}: nota {cr.score:.0f}/5")
    return "\n".join(risks) if risks else "Nenhum critério com risco crítico identificado."


def _format_news_text(news: list[dict]) -> str:
    if not news:
        return ""
    lines = []
    for n in news[:6]:
        lines.append(f"• {n.get('title', '')} ({n.get('source', '')})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    cli()


if __name__ == "__main__":
    main()
