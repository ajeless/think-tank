"""Command-line adapter for Think Tank."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .cli_config import config_app
from .cli_config_auth import config_auth_app
from .cli_config_defaults import config_defaults_app
from .cli_config_models import config_model_app
from .config import (
    ConfigFormatError,
    ConfigNotFoundError,
    ModelProfileNotFoundError,
    default_config_path,
    resolve_model_profile,
)
from .engine import (
    MissingModelError,
    MissingPromptError,
    ProjectStateNotFoundError,
    ask_project,
    get_engine_status,
)
from .model_client import (
    AisuiteModelClient,
    ModelClientCallError,
    ModelClientConfigurationError,
)
from .workspace import WorkspaceAlreadyExistsError, init_workspace


app = typer.Typer(
    name="think",
    help="Think Tank local-first idea workspace.",
    no_args_is_help=True,
)
config_app.add_typer(config_auth_app, name="auth")
config_app.add_typer(config_model_app, name="model")
config_app.add_typer(config_defaults_app, name="defaults")
app.add_typer(config_app, name="config")
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
    model: Annotated[
        str | None,
        typer.Option("--model", help="Explicit provider:model identifier."),
    ] = None,
    model_profile: Annotated[
        str | None,
        typer.Option("--model-profile", help="Named model profile from Think Tank config."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to read non-secret Think Tank config."),
    ] = None,
) -> None:
    """Run one non-interactive model interaction and record its transcript."""

    try:
        selected_model = _selected_ask_model(
            model=model,
            model_profile=model_profile,
            config_path=config or default_config_path(os.environ),
        )
        result = ask_project(
            project,
            prompt=prompt,
            model=selected_model,
            client=AisuiteModelClient(),
        )
    except (
        ConfigNotFoundError,
        ConfigFormatError,
        MissingModelError,
        MissingPromptError,
        ModelProfileNotFoundError,
        ProjectStateNotFoundError,
        ModelClientConfigurationError,
        ModelClientCallError,
        ValueError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(result["response"])


def _selected_ask_model(
    *,
    model: str | None,
    model_profile: str | None,
    config_path: Path,
) -> str | None:
    if model and model.strip() and model_profile and model_profile.strip():
        raise ValueError("use either --model or --model-profile, not both")
    if model_profile and model_profile.strip():
        return resolve_model_profile(config_path, model_profile)["model"]
    return model
