"""Rich terminal display for human review and status output."""

from __future__ import annotations


from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_status(message: str):
    """Print a status message."""
    console.print(f"[bold blue]>>>[/bold blue] {message}")


def print_api_status(status: dict[str, str]):
    """Print API availability status."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("API", style="bold")
    table.add_column("Status")

    for api, stat in status.items():
        style = "green" if stat not in ("missing (REQUIRED)",) and "free" not in stat.lower() else (
            "red" if "REQUIRED" in stat else "yellow"
        )
        table.add_row(api, f"[{style}]{stat}[/{style}]")

    console.print(Panel(table, title="API Status", border_style="blue"))


def review_accounts(stage: str, accounts: list) -> list[int]:
    """Display accounts for review and get user selection."""
    table = Table(title="Discovered Accounts", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Company", style="bold")
    table.add_column("Domain")
    table.add_column("Industry")
    table.add_column("Size")
    table.add_column("Location")
    table.add_column("Reasoning", max_width=40)

    for i, account in enumerate(accounts, 1):
        table.add_row(
            str(i),
            account.company_name,
            account.domain,
            account.industry or "-",
            account.employee_count or "-",
            account.location or "-",
            (account.relevance_reasoning[:80] + "...") if len(account.relevance_reasoning) > 80 else account.relevance_reasoning,
        )

    console.print(table)
    return _get_selection(accounts)


def review_contacts(stage: str, contacts: list) -> list[int]:
    """Display contacts for review and get user selection."""
    table = Table(title="Discovered Contacts", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="bold")
    table.add_column("Title")
    table.add_column("Email")
    table.add_column("Confidence")
    table.add_column("Verified")
    table.add_column("Source")

    for i, contact in enumerate(contacts, 1):
        conf = contact.email_confidence
        conf_style = "green" if conf and conf >= 70 else ("yellow" if conf and conf >= 40 else "red")
        verified = "[green]Yes[/green]" if contact.email_verified else "[red]No[/red]"

        table.add_row(
            str(i),
            contact.full_name,
            contact.title or "-",
            contact.email or "-",
            f"[{conf_style}]{conf or '-'}[/{conf_style}]",
            verified,
            contact.email_source or "-",
        )

    console.print(table)
    return _get_selection(contacts)


def review_research(stage: str, items: list[dict]) -> list[int]:
    """Display research dossiers for review."""
    for i, item in enumerate(items, 1):
        contact = item["contact"]
        dossier = item.get("dossier")

        console.print(f"\n[bold]--- Contact {i}: {contact.full_name} ---[/bold]")

        if dossier:
            parts = []
            if dossier.github_username:
                parts.append(f"  GitHub: github.com/{dossier.github_username}")
            if dossier.github_repos:
                parts.append(f"  Repos: {', '.join(dossier.github_repos[:3])}")
            if dossier.github_languages:
                parts.append(f"  Languages: {', '.join(dossier.github_languages[:5])}")
            if dossier.interests:
                parts.append(f"  Interests: {', '.join(dossier.interests[:5])}")
            if dossier.recent_posts:
                parts.append(f"  Posts: {', '.join(dossier.recent_posts[:2])}")
            if dossier.education:
                parts.append(f"  Education: {dossier.education}")
            if dossier.raw_research_notes:
                parts.append(f"  Notes: {dossier.raw_research_notes[:200]}")

            if parts:
                console.print("\n".join(parts))
            else:
                console.print("  [dim]No significant research findings.[/dim]")
        else:
            console.print("  [dim]No dossier available.[/dim]")

    # For research review, default to approving all - it's mostly informational
    return [item["contact"].id for item in items if item["contact"].id]


def review_emails(stage: str, items: list[dict]) -> list[int]:
    """Display draft emails for review and get user selection."""
    for i, item in enumerate(items, 1):
        contact = item.get("contact")
        email = item.get("email")

        name = contact.full_name if contact else "Unknown"
        console.print(f"\n[bold]--- Email {i}: To {name} ---[/bold]")

        if email:
            console.print(Panel(
                f"[bold]Subject:[/bold] {email.subject_line}\n\n{email.body}",
                border_style="green" if email.includes_unsubscribe else "yellow",
            ))
            if email.personalization_hooks:
                console.print(f"  Hooks: {', '.join(email.personalization_hooks)}")
            if not email.includes_unsubscribe:
                console.print("  [yellow]Warning: Missing unsubscribe text[/yellow]")
        else:
            console.print("  [red]No email draft available.[/red]")

    return _get_email_selection(items)


def _get_selection(items: list) -> list[int]:
    """Interactive selection prompt. Returns list of approved item IDs."""
    console.print(
        "\n[bold]Options:[/bold] "
        "[a] Approve all  "
        "[s] Select rows (e.g. 1,3,5-8)  "
        "[r] Reject all  "
        "[q] Quit pipeline"
    )

    while True:
        choice = console.input("[bold]> [/bold]").strip().lower()

        if choice == "a":
            return [item.id for item in items if item.id]

        elif choice == "r":
            return []

        elif choice == "q":
            raise KeyboardInterrupt("User quit pipeline")

        elif choice.startswith("s"):
            # Parse selection like "s 1,3,5-8" or just "1,3,5-8"
            sel_text = choice[1:].strip() if choice.startswith("s") else choice
            if not sel_text:
                sel_text = console.input("Enter row numbers (e.g. 1,3,5-8): ").strip()
            try:
                indices = _parse_selection(sel_text, len(items))
                return [items[i - 1].id for i in indices if items[i - 1].id]
            except ValueError as e:
                console.print(f"[red]Invalid selection: {e}[/red]")

        else:
            # Try parsing as direct selection
            try:
                indices = _parse_selection(choice, len(items))
                return [items[i - 1].id for i in indices if items[i - 1].id]
            except ValueError:
                console.print("[red]Invalid option. Use a/s/r/q or row numbers.[/red]")


def _get_email_selection(items: list[dict]) -> list[int]:
    """Interactive selection for emails. Returns list of approved email IDs."""
    console.print(
        "\n[bold]Options:[/bold] "
        "[a] Approve all  "
        "[s] Select emails (e.g. 1,3,5-8)  "
        "[r] Reject all  "
        "[q] Quit pipeline"
    )

    while True:
        choice = console.input("[bold]> [/bold]").strip().lower()

        if choice == "a":
            return [item["email"].id for item in items if item.get("email") and item["email"].id]

        elif choice == "r":
            return []

        elif choice == "q":
            raise KeyboardInterrupt("User quit pipeline")

        elif choice.startswith("s"):
            sel_text = choice[1:].strip() if choice.startswith("s") else choice
            if not sel_text:
                sel_text = console.input("Enter email numbers (e.g. 1,3,5-8): ").strip()
            try:
                indices = _parse_selection(sel_text, len(items))
                return [
                    items[i - 1]["email"].id
                    for i in indices
                    if items[i - 1].get("email") and items[i - 1]["email"].id
                ]
            except ValueError as e:
                console.print(f"[red]Invalid selection: {e}[/red]")

        else:
            try:
                indices = _parse_selection(choice, len(items))
                return [
                    items[i - 1]["email"].id
                    for i in indices
                    if items[i - 1].get("email") and items[i - 1]["email"].id
                ]
            except ValueError:
                console.print("[red]Invalid option. Use a/s/r/q or email numbers.[/red]")


def _parse_selection(text: str, max_val: int) -> list[int]:
    """Parse a selection string like '1,3,5-8' into a list of 1-based indices."""
    indices = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start, end = int(start.strip()), int(end.strip())
            if start < 1 or end > max_val:
                raise ValueError(f"Range {start}-{end} out of bounds (1-{max_val})")
            indices.update(range(start, end + 1))
        else:
            val = int(part)
            if val < 1 or val > max_val:
                raise ValueError(f"Index {val} out of bounds (1-{max_val})")
            indices.add(val)
    return sorted(indices)
