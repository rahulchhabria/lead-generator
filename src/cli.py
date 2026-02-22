"""CLI interface using Typer + Rich."""

from __future__ import annotations

import logging

import typer
from rich.logging import RichHandler

from src.config import load_api_config, load_campaign_config, load_domains, load_icp
from src.database import Database
from src.display import (
    console,
    print_api_status,
    print_status,
    review_accounts,
    review_contacts,
    review_emails,
    review_research,
)
from src.export import export_csv
from src.models import CampaignConfig, PipelineStage
from src.pipeline import Pipeline

app = typer.Typer(
    name="leadgen",
    help="Multi-agent lead generation pipeline powered by Claude.",
    no_args_is_help=True,
)


def _setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


def _review_callback(stage: str, items: list) -> list[int]:
    """Route review callbacks to the appropriate display function."""
    if stage == "accounts":
        return review_accounts(stage, items)
    elif stage == "contacts":
        return review_contacts(stage, items)
    elif stage == "research":
        return review_research(stage, items)
    elif stage == "emails":
        return review_emails(stage, items)
    return [item.id for item in items if hasattr(item, "id") and item.id]


@app.command()
def run(
    icp_file: str = typer.Argument(None, help="Path to ICP YAML file"),
    domains: str = typer.Option(None, "--domains", "-d", help="Path to domain list (YAML or CSV)"),
    config: str = typer.Option(None, "--config", "-c", help="Path to campaign config YAML"),
    auto_approve: bool = typer.Option(False, "--auto", help="Auto-approve all stages (no review)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Start a new lead generation campaign."""
    _setup_logging(verbose)

    if not icp_file and not domains:
        console.print("[red]Error: Provide either an ICP file or --domains flag.[/red]")
        raise typer.Exit(1)

    api_config = load_api_config()

    if not api_config.has_anthropic:
        console.print("[red]Error: ANTHROPIC_API_KEY is required. Set it in .env[/red]")
        raise typer.Exit(1)

    print_api_status(api_config.api_status_line())

    # Load inputs
    icp = load_icp(icp_file) if icp_file else None
    domain_list = load_domains(domains) if domains else None

    # Load campaign config
    campaign_config = CampaignConfig()
    if config:
        campaign_config = load_campaign_config(config)

    db = Database(api_config.db_path)

    try:
        pipeline = Pipeline(
            api_config=api_config,
            db=db,
            campaign_config=campaign_config,
            on_status=print_status,
            on_review=None if auto_approve else _review_callback,
        )

        campaign_id = pipeline.run_new(icp=icp, domains=domain_list)

        # Auto-export
        csv_path = export_csv(db, campaign_id)
        if csv_path:
            console.print(f"\n[bold green]Exported to: {csv_path}[/bold green]")
        else:
            console.print("\n[yellow]No approved leads to export.[/yellow]")

        console.print(f"\nCampaign ID: [bold]{campaign_id}[/bold]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted. Use 'leadgen resume' to continue.[/yellow]")
    finally:
        db.close()


@app.command()
def resume(
    campaign_id: str = typer.Argument(..., help="Campaign ID to resume"),
    auto_approve: bool = typer.Option(False, "--auto", help="Auto-approve all stages"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Resume a pipeline from its last checkpoint."""
    _setup_logging(verbose)

    api_config = load_api_config()

    if not api_config.has_anthropic:
        console.print("[red]Error: ANTHROPIC_API_KEY is required.[/red]")
        raise typer.Exit(1)

    db = Database(api_config.db_path)

    try:
        campaign = db.get_campaign(campaign_id)
        if not campaign:
            console.print(f"[red]Campaign {campaign_id} not found.[/red]")
            raise typer.Exit(1)

        console.print(f"Resuming campaign [bold]{campaign_id}[/bold] from stage: {campaign.current_stage.value}")

        campaign_config = CampaignConfig.model_validate_json(campaign.config_json)

        pipeline = Pipeline(
            api_config=api_config,
            db=db,
            campaign_config=campaign_config,
            on_status=print_status,
            on_review=None if auto_approve else _review_callback,
        )

        pipeline.resume(campaign_id)

        csv_path = export_csv(db, campaign_id)
        if csv_path:
            console.print(f"\n[bold green]Exported to: {csv_path}[/bold green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted.[/yellow]")
    finally:
        db.close()


@app.command(name="export")
def export_cmd(
    campaign_id: str = typer.Argument(..., help="Campaign ID to export"),
    output: str = typer.Option(None, "--output", "-o", help="Output CSV path"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Export approved leads to CSV."""
    _setup_logging(verbose)

    api_config = load_api_config()
    db = Database(api_config.db_path)

    try:
        csv_path = export_csv(db, campaign_id, output)
        if csv_path:
            console.print(f"[bold green]Exported to: {csv_path}[/bold green]")
        else:
            console.print("[yellow]No approved leads to export.[/yellow]")
    finally:
        db.close()


@app.command(name="list")
def list_campaigns(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """List all campaigns and their status."""
    _setup_logging(verbose)

    api_config = load_api_config()
    db = Database(api_config.db_path)

    try:
        from rich.table import Table

        campaigns = db.list_campaigns()

        if not campaigns:
            console.print("[dim]No campaigns found.[/dim]")
            return

        table = Table(title="Campaigns")
        table.add_column("ID", style="bold")
        table.add_column("Stage")
        table.add_column("Created")

        for c in campaigns:
            stage_style = "green" if c.current_stage == PipelineStage.COMPLETED else "yellow"
            table.add_row(
                c.id,
                f"[{stage_style}]{c.current_stage.value}[/{stage_style}]",
                c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "-",
            )

        console.print(table)
    finally:
        db.close()


@app.command()
def forget(
    email: str = typer.Argument(..., help="Email address to delete all data for"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """GDPR right-to-be-forgotten: delete all data for an email."""
    _setup_logging(verbose)

    api_config = load_api_config()
    db = Database(api_config.db_path)

    try:
        db.forget_contact(email)
        console.print(f"[green]All data for {email} has been deleted and added to suppression list.[/green]")
    finally:
        db.close()


@app.command()
def suppress(
    email: str = typer.Argument(..., help="Email to add to suppression list"),
    reason: str = typer.Option("manual", "--reason", "-r", help="Reason for suppression"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Add an email to the suppression list."""
    _setup_logging(verbose)

    api_config = load_api_config()
    db = Database(api_config.db_path)

    try:
        db.add_to_suppression(email, reason)
        console.print(f"[green]{email} added to suppression list.[/green]")
    finally:
        db.close()


if __name__ == "__main__":
    app()
