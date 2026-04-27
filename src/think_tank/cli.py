"""Command-line adapter for Think Tank."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .engine import (
    MissingModelError,
    MissingPromptError,
    ProjectStateNotFoundError,
    ask_project,
    get_engine_status,
)
from .model_client import AisuiteModelClient
from .workspace import WorkspaceAlreadyExistsError, init_workspace


app = typer.Typer(
    name="think",
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


@app.command("new")
def new_workspace(
    path: Annotated[Path, typer.Argument(help="Directory where the workspace should be created.")],
    name: Annotated[str, typer.Option("--name", help="Human-supplied project name.")],
) -> None:
    """Create a local Think Tank workspace."""

    try:
        result = init_workspace(path, name=name)
    except WorkspaceAlreadyExistsError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except NotADirectoryError as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(f"Created Think Tank workspace: {result['root']}")
    console.print(f"Initialized state: {result['state_path']}")


@app.command("ask")
def ask(
    prompt: Annotated[str, typer.Argument(help="Prompt to send to the selected model.")],
    project: Annotated[Path, typer.Option("--project", help="Think Tank project path.")],
    model: Annotated[str, typer.Option("--model", help="Explicit provider:model identifier.")],
) -> None:
    """Run one non-interactive model interaction and record its transcript."""

    try:
        result = ask_project(
            project,
            prompt=prompt,
            model=model,
            client=AisuiteModelClient(),
        )
    except (MissingModelError, MissingPromptError, ProjectStateNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(result["response"])
