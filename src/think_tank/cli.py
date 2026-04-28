"""Command-line adapter for Think Tank."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console

from .config import (
    default_config_path,
    detect_provider_statuses,
    write_detected_provider_config,
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
config_app = typer.Typer(help="Configure non-secret Think Tank preferences.")
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
    except (
        MissingModelError,
        MissingPromptError,
        ProjectStateNotFoundError,
        ModelClientConfigurationError,
        ModelClientCallError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(result["response"])


@config_app.command("doctor")
def config_doctor(
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON output.")] = False,
) -> None:
    """Show detected provider credentials without printing secret values."""

    statuses = detect_provider_statuses(os.environ)
    if json_output:
        typer.echo(json.dumps(statuses, indent=2, sort_keys=True))
        return

    for status in statuses:
        console.print(
            f"{status['display_name']}: "
            f"ready={'yes' if status['ready'] else 'no'}; "
            f"detected={', '.join(status['detected_env_vars']) or '-'}; "
            f"missing={', '.join(status['missing_env_vars']) or '-'}"
        )
        for note in status["notes"]:
            console.print(f"  note: {note}")
    console.print("Secrets are read from environment variables and are never printed.")


@config_app.command("init")
def config_init(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to write non-secret Think Tank config."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Enable all currently ready providers without prompting."),
    ] = False,
) -> None:
    """Write non-secret provider configuration from detected credentials."""

    statuses = detect_provider_statuses(os.environ)
    ready_providers = [status["provider"] for status in statuses if status["ready"]]
    config_path = config or default_config_path(os.environ)

    if yes:
        enabled_providers = ready_providers
    else:
        enabled_providers = questionary.checkbox(
            "Enable detected providers:",
            choices=[
                questionary.Choice(
                    title=f"{status['display_name']} ({status['provider']})",
                    value=status["provider"],
                    checked=status["ready"],
                    disabled=None if status["ready"] else "missing required environment",
                )
                for status in statuses
            ],
        ).ask()
        if enabled_providers is None:
            raise typer.Abort()

    result = write_detected_provider_config(
        config_path,
        env=os.environ,
        enabled_providers=enabled_providers,
    )
    console.print(f"Wrote config: {result['config_path']}")
    if result["enabled_providers"]:
        console.print("Enabled providers: " + ", ".join(result["enabled_providers"]))
    else:
        console.print("No providers enabled. Run `think config doctor` for setup details.")
