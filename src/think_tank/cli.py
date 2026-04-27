"""Command-line adapter for Think Tank."""

from __future__ import annotations

import typer
from rich.console import Console

from .engine import get_engine_status


app = typer.Typer(
    name="tt",
    help="Think Tank local-first idea workspace.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main() -> None:
    """Think Tank local-first idea workspace."""


@app.command()
def status() -> None:
    """Show whether the local Think Tank engine is available."""

    status_payload = get_engine_status()
    console.print(f"{status_payload['product']} engine ready: {status_payload['ready']}")
