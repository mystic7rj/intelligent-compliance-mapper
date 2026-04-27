"""Main CLI entry point for the Compliance Mapper.

Registers all command groups and provides global ``--verbose`` flag.
Reads ``APP_ENV`` from ``.env`` to control traceback visibility.
"""

from __future__ import annotations

import logging
import os
import sys

import click
from dotenv import load_dotenv
from rich.console import Console

from src.api.commands.analyze import analyze
from src.api.commands.analytics import analytics
from src.api.commands.batch import batch
from src.api.commands.compare import compare
from src.api.commands.framework import framework
from src.api.commands.report import report
from src.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)
console = Console()


@click.group()
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose (DEBUG) logging.",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Compliance Mapper — Enterprise GRC Automation CLI."""
    ctx.ensure_object(dict)

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        # Also update all compliance-mapper loggers
        for name in logging.Logger.manager.loggerDict:
            if name.startswith("src."):
                logging.getLogger(name).setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled — log level set to DEBUG")

    # Suppress tracebacks in production
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env == "production":
        sys.tracebacklimit = 0


# Register command groups
cli.add_command(analyze)
cli.add_command(analytics)
cli.add_command(batch)
cli.add_command(compare)
cli.add_command(framework)
cli.add_command(report)


if __name__ == "__main__":
    cli()
