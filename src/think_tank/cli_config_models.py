"""`think config model ...` CLI commands."""

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
    add_model_profile,
    default_config_path,
    list_model_profiles,
    remove_model_profile,
)


config_model_app = typer.Typer(help="Manage non-secret named model profiles.")
console = Console()


@config_model_app.command("add")
def config_model_add(
    name: Annotated[str, typer.Argument(help="Name for the model profile.")],
    model: Annotated[
        str,
        typer.Option("--model", help="Explicit provider:model identifier to store."),
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to update non-secret Think Tank config."),
    ] = None,
) -> None:
    """Add or update a named non-secret model profile."""

    config_path = config or default_config_path(os.environ)
    try:
        result = add_model_profile(config_path, name=name, model=model)
    except (ConfigFormatError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    action = "Added" if result["added"] else "Updated"
    console.print(
        f"{action} model profile {result['name']} in {result['config_path']}."
    )
    console.print(f"Model: {result['model']}")
    console.print("No provider secrets or default model were stored.")


@config_model_app.command("list")
def config_model_list(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to read non-secret Think Tank config."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON output.")] = False,
) -> None:
    """List named model profiles without provider secrets."""

    config_path = config or default_config_path(os.environ)
    try:
        result = list_model_profiles(config_path)
    except (ConfigNotFoundError, ConfigFormatError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return

    console.print(f"Config: {result['config_path']}")
    if not result["profiles"]:
        console.print("No model profiles are configured.")
    for profile in result["profiles"]:
        console.print(f"{profile['name']}: {profile['model']}")
    console.print("Model profiles do not create a default model or fallback policy.")


@config_model_app.command("remove")
def config_model_remove(
    name: Annotated[str, typer.Argument(help="Model profile to remove.")],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to update non-secret Think Tank config."),
    ] = None,
) -> None:
    """Remove a named model profile from Think Tank config."""

    config_path = config or default_config_path(os.environ)
    try:
        result = remove_model_profile(config_path, name)
    except (ConfigNotFoundError, ConfigFormatError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    if result["removed"]:
        console.print(
            f"Removed model profile {result['removed_profile']} from "
            f"{result['config_path']}."
        )
    else:
        console.print(
            f"No model profile {result['removed_profile']} was present in "
            f"{result['config_path']}."
        )
    console.print("No provider secrets, auth metadata, or project transcripts were modified.")
