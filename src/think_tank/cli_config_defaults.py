"""`think config defaults ...` CLI commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .config import (
    ConfigFormatError,
    ConfigNotFoundError,
    ModelProfileNotFoundError,
    default_config_path,
    list_config_defaults,
    remove_config_default,
    set_config_defaults,
)


config_defaults_app = typer.Typer(help="Manage explicit user-authored defaults.")
console = Console()


@config_defaults_app.command("set")
def config_defaults_set(
    model_profile: Annotated[
        str | None,
        typer.Option("--model-profile", help="Default model profile name to record."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to update non-secret Think Tank config."),
    ] = None,
) -> None:
    """Record explicit user-authored defaults without changing work commands."""

    config_path = config or default_config_path(os.environ)
    try:
        result = set_config_defaults(config_path, model_profile=model_profile)
    except (
        ConfigNotFoundError,
        ConfigFormatError,
        ModelProfileNotFoundError,
        ValueError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(f"Updated defaults in {result['config_path']}.")
    if result["defaults"]["model_profile"]:
        console.print(f"Model profile: {result['defaults']['model_profile']}")
    console.print("Defaults are explicit user config; work commands do not use them automatically yet.")


@config_defaults_app.command("list")
def config_defaults_list(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to read non-secret Think Tank config."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON output.")] = False,
) -> None:
    """List explicit user-authored defaults."""

    config_path = config or default_config_path(os.environ)
    try:
        result = list_config_defaults(config_path)
    except (ConfigNotFoundError, ConfigFormatError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return

    console.print(f"Config: {result['config_path']}")
    if result["defaults"]["model_profile"]:
        console.print(f"model_profile: {result['defaults']['model_profile']}")
    else:
        console.print("No defaults are configured.")
    console.print("Defaults are explicit user config; work commands do not use them automatically yet.")


@config_defaults_app.command("remove")
def config_defaults_remove(
    default_name: Annotated[
        str,
        typer.Argument(help="Default to remove. Currently supported: model-profile."),
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to update non-secret Think Tank config."),
    ] = None,
) -> None:
    """Remove one explicit user-authored default."""

    config_path = config or default_config_path(os.environ)
    try:
        result = remove_config_default(config_path, default_name)
    except (ConfigNotFoundError, ConfigFormatError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    display_name = result["removed_default"].replace("_", "-")
    if result["removed"]:
        console.print(f"Removed default {display_name} from {result['config_path']}.")
    else:
        console.print(f"No default {display_name} was present in {result['config_path']}.")
    console.print("No model profiles, auth metadata, or project transcripts were modified.")
