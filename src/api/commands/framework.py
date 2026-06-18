# -*- coding: utf-8 -*-
"""Click command group for framework management.

Orchestrates FrameworkRepository, ControlRepository, and FrameworkLoader —
contains zero business logic.  All file paths validated through ``safe_path()``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from sqlalchemy.exc import OperationalError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.exceptions import FrameworkNotFoundError, ValidationError
from src.core.framework_loader import FrameworkLoader
from src.core.gap_analyzer import ALLOWED_FRAMEWORKS
from src.data.database import get_engine, get_session
from src.data.repositories.control_repository import ControlRepository
from src.data.repositories.framework_repository import FrameworkRepository
from src.utils.logger import get_logger
from src.utils.security import SecurityError, safe_path

logger = get_logger(__name__)
console = Console()

MISSING_SCHEMA_HINT = (
    "Database schema is not initialized.\n"
    "Run [bold]alembic upgrade head[/bold] from the project root, "
    "then retry."
)


def _is_missing_schema_error(exc: Exception) -> bool:
    """Return True when DB failure indicates missing tables."""
    if not isinstance(exc, OperationalError):
        return False
    return "no such table" in str(exc).lower()


@click.group("framework")
def framework() -> None:
    """Framework management commands."""


@framework.command("list")
def list_frameworks() -> None:
    """List all loaded compliance frameworks."""
    try:
        engine = get_engine()
        with get_session(engine) as session:
            repo = FrameworkRepository(session)
            frameworks = repo.get_all()

            if not frameworks:
                console.print(Panel(
                    "[yellow]No frameworks loaded[/yellow]\n"
                    "Use [bold]framework load --path <file>[/bold] to load one.",
                    title="📋 Frameworks",
                    border_style="yellow",
                ))
                return

            table = Table(title="Loaded Frameworks", show_lines=True)
            table.add_column("Name", style="bold cyan")
            table.add_column("Control Count", justify="right")
            table.add_column("Loaded At")

            for fw in frameworks:
                # Count controls across all families
                control_count = sum(len(fam.controls) for fam in fw.families)
                loaded_at = fw.created_at.strftime("%Y-%m-%d %H:%M:%S") if fw.created_at else "N/A"
                table.add_row(fw.name, str(control_count), loaded_at)

            console.print(table)

    except Exception as exc:
        if _is_missing_schema_error(exc):
            console.print(Panel(
                f"[red]Error:[/red] {exc}\n\n[yellow]{MISSING_SCHEMA_HINT}[/yellow]",
                title="❌ Failed to List Frameworks",
                border_style="red",
            ))
            sys.exit(1)
        console.print(Panel(
            f"[red]Error:[/red] {exc}",
            title="❌ Failed to List Frameworks",
            border_style="red",
        ))
        sys.exit(1)


@framework.command("load")
@click.option(
    "--path",
    required=True,
    type=click.Path(exists=True),
    help="Path to a framework JSON file.",
)
def load_framework(path: str) -> None:
    """Load a compliance framework from a JSON file."""
    try:
        # Validate file path through safe_path
        validated_path = safe_path(Path.cwd(), path)

        # Load framework from JSON using FrameworkLoader
        loader = FrameworkLoader(Path("data/frameworks"))
        framework_data = loader.load(validated_path.stem)

        # Persist to database via FrameworkRepository
        engine = get_engine()
        already_loaded = False
        with get_session(engine) as session:
            repo = FrameworkRepository(session)
            existing = repo.get_by_name(framework_data.name)
            if existing is not None and existing.version == framework_data.version:
                already_loaded = True
            else:
                # Convert Pydantic model to ORM table for persistence
                from src.data.schema import ControlFamilyTable, ControlTable, FrameworkTable

                fw_row = FrameworkTable(
                    name=framework_data.name,
                    version=framework_data.version,
                    description=framework_data.description,
                )
                for family in framework_data.families:
                    fam_row = ControlFamilyTable(
                        function_name=family.function_name,
                        function_id=family.function_id,
                        description=family.description,
                    )
                    for ctrl in family.controls:
                        ctrl_row = ControlTable(
                            control_id=ctrl.id,
                            title=ctrl.title,
                            description=ctrl.description,
                            priority=ctrl.priority.value,
                        )
                        fam_row.controls.append(ctrl_row)
                    fw_row.families.append(fam_row)

                repo.save(fw_row)

        if already_loaded:
            console.print(Panel(
                f"[yellow]Framework already loaded:[/yellow] [bold]{framework_data.name}[/bold]\n"
                f"Version: {framework_data.version}",
                title="ℹ️ Framework Already Loaded",
                border_style="yellow",
            ))
        else:
            console.print(Panel(
                f"[green]Successfully loaded framework:[/green] [bold]{framework_data.name}[/bold]\n"
                f"Version: {framework_data.version}\n"
                f"Total Controls: {framework_data.total_controls}",
                title="✅ Framework Loaded",
                border_style="green",
            ))

    except SecurityError as exc:
        console.print(Panel(
            f"[red]Security Error:[/red] {exc}",
            title="⛔ Access Denied",
            border_style="red",
        ))
        sys.exit(1)
    except Exception as exc:
        if _is_missing_schema_error(exc):
            console.print(Panel(
                f"[red]Error:[/red] {exc}\n\n[yellow]{MISSING_SCHEMA_HINT}[/yellow]",
                title="❌ Failed to Load Framework",
                border_style="red",
            ))
            sys.exit(1)
        console.print(Panel(
            f"[red]Error:[/red] {exc}",
            title="❌ Failed to Load Framework",
            border_style="red",
        ))
        sys.exit(1)


def _validate_framework_name(
    ctx: click.Context,
    param: click.Parameter,
    value: str,
) -> str:
    """Validate --name against the allowed whitelist."""
    cleaned = value.strip().upper()
    if cleaned not in ALLOWED_FRAMEWORKS:
        msg = (
            f"Invalid framework '{cleaned}'. "
            f"Allowed: {sorted(ALLOWED_FRAMEWORKS)}"
        )
        raise click.BadParameter(msg)
    return cleaned


@framework.command("show")
@click.option(
    "--name",
    required=True,
    type=str,
    callback=_validate_framework_name,
    expose_value=True,
    help="Framework name to show controls for.",
)
def show_framework(name: str) -> None:
    """Show all controls for a specific framework."""
    try:
        engine = get_engine()
        with get_session(engine) as session:
            fw_repo = FrameworkRepository(session)
            ctrl_repo = ControlRepository(session)

            fw = fw_repo.get_by_name(name)
            if fw is None:
                raise FrameworkNotFoundError(
                    f"Framework '{name}' not found in the database",
                )

            controls = ctrl_repo.get_by_framework(fw.id)

        if not controls:
            console.print(Panel(
                f"[yellow]No controls found for framework '{name}'[/yellow]",
                title="📋 Controls",
                border_style="yellow",
            ))
            return

        table = Table(
            title=f"Controls — {name}",
            show_lines=True,
        )
        table.add_column("ID", style="bold cyan")
        table.add_column("Name")
        table.add_column("Family")
        table.add_column("Description", max_width=60)

        for ctrl in controls:
            description = ctrl.description or ""
            truncated = description[:60] + "…" if len(description) > 60 else description
            family_id = ctrl.family.function_id if ctrl.family else "N/A"
            table.add_row(ctrl.control_id, ctrl.title, family_id, truncated)

        # Use pager for large output
        with console.pager():
            console.print(table)

    except (FrameworkNotFoundError, ValidationError) as exc:
        console.print(Panel(
            f"[yellow]Error:[/yellow] {exc}",
            title="⚠️ Framework Not Found",
            border_style="yellow",
        ))
        sys.exit(1)
    except Exception as exc:
        if _is_missing_schema_error(exc):
            console.print(Panel(
                f"[red]Error:[/red] {exc}\n\n[yellow]{MISSING_SCHEMA_HINT}[/yellow]",
                title="❌ Failed to Show Framework",
                border_style="red",
            ))
            sys.exit(1)
        console.print(Panel(
            f"[red]Error:[/red] {exc}",
            title="❌ Failed to Show Framework",
            border_style="red",
        ))
        sys.exit(1)
