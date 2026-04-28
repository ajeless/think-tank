"""`think config auth ...` CLI commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console

from .config import (
    ConfigFormatError,
    ConfigNotFoundError,
    ProviderAuthNotReadyError,
    add_config_auth,
    default_config_path,
    doctor_config_auth,
    list_config_auth,
    list_provider_auth_methods,
    provider_auth_method_options,
    remove_config_auth,
)


config_auth_app = typer.Typer(help="Manage non-secret provider auth metadata.")
console = Console()


@config_auth_app.command("add")
def config_auth_add(
    provider: Annotated[
        str,
        typer.Argument(help="Provider auth metadata to add to Think Tank config."),
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to update non-secret Think Tank config."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Add ready provider auth metadata without prompting."),
    ] = False,
) -> None:
    """Add provider auth metadata to Think Tank config without storing secrets."""

    config_path = config or default_config_path(os.environ)
    selected_auth_kind: str | None = None
    if not yes:
        try:
            selected_auth_kind = _selected_auth_kind_for_auth_add(
                provider=provider,
                config_path=config_path,
                env=os.environ,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    try:
        result = add_config_auth(
            config_path,
            provider,
            env=os.environ,
            auth_kind=selected_auth_kind,
        )
    except (ProviderAuthNotReadyError, ConfigFormatError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    action = "Added" if result["added"] else "Updated"
    console.print(
        f"{action} auth metadata for {result['provider']} in {result['config_path']}."
    )
    console.print(f"Auth kind: {result['auth_kind']}")
    console.print(f"Env vars: {', '.join(result['env_vars']) or '-'}")
    console.print("Secret values were not stored.")


@config_auth_app.command("doctor")
def config_auth_doctor(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to read non-secret Think Tank config."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON output.")] = False,
) -> None:
    """Inspect configured and detected auth metadata without provider API calls."""

    config_path = config or default_config_path(os.environ)
    try:
        result = doctor_config_auth(config_path, env=os.environ)
    except ConfigFormatError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return

    console.print(
        f"Config: {result['config_path']} "
        f"({'found' if result['config_found'] else 'not found'})"
    )
    for provider in result["providers"]:
        console.print(
            f"{provider['display_name']} ({provider['provider']}): "
            f"configured={'yes' if provider['configured'] else 'no'}; "
            f"detected={'yes' if provider['detected'] else 'no'}; "
            f"ready={'yes' if provider['ready'] else 'no'}; "
            f"configured_env_vars={', '.join(provider['configured_env_vars']) or '-'}; "
            f"detected_env_vars={', '.join(provider['detected_env_vars']) or '-'}; "
            f"missing_env_vars={', '.join(provider['missing_env_vars']) or '-'}"
        )
        for note in provider["notes"]:
            console.print(f"  note: {note}")
    console.print("Secret values are read from the environment and are never printed.")


@config_auth_app.command("list")
def config_auth_list(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to read non-secret Think Tank config."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON output.")] = False,
) -> None:
    """List enabled provider auth metadata without printing secret values."""

    config_path = config or default_config_path(os.environ)
    try:
        result = list_config_auth(config_path)
    except (ConfigNotFoundError, ConfigFormatError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return

    console.print(f"Config: {result['config_path']}")
    if not result["providers"]:
        console.print("No provider auth metadata is enabled.")
    for provider in result["providers"]:
        console.print(
            f"{provider['provider']}: "
            f"auth_kind={provider['auth_kind'] or '-'}; "
            f"env_vars={', '.join(provider['env_vars']) or '-'}"
        )
    console.print("Secret values are not stored in Think Tank config.")


@config_auth_app.command("methods")
def config_auth_methods(
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="Limit output to one provider."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON output.")] = False,
) -> None:
    """List known provider auth method capabilities without storing secrets."""

    try:
        result = list_provider_auth_methods(env=os.environ, provider=provider)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return

    for provider_result in result["providers"]:
        console.print(
            f"{provider_result['display_name']} ({provider_result['provider']}):"
        )
        for method in provider_result["auth_methods"]:
            console.print(
                f"  {method['auth_kind']}: "
                f"status={method['support_status']}; "
                f"implemented={'yes' if method['implemented'] else 'no'}; "
                f"official={'yes' if method['official'] else 'no'}; "
                f"selectable={'yes' if method['selectable'] else 'no'}; "
                f"ready={'yes' if method['ready'] else 'no'}; "
                f"required_env_vars={', '.join(method['required_env_vars']) or '-'}; "
                f"detected_env_vars={', '.join(method['detected_env_vars']) or '-'}; "
                f"missing_env_vars={', '.join(method['missing_env_vars']) or '-'}"
            )
            for note in method["notes"]:
                console.print(f"    note: {note}")
    console.print("Secret values are read from the environment and are never printed.")


@config_auth_app.command("remove")
def config_auth_remove(
    provider: Annotated[
        str,
        typer.Argument(help="Provider auth metadata to remove from Think Tank config."),
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to update non-secret Think Tank config."),
    ] = None,
) -> None:
    """Remove provider auth metadata from Think Tank config only."""

    config_path = config or default_config_path(os.environ)
    try:
        result = remove_config_auth(config_path, provider)
    except (ConfigNotFoundError, ConfigFormatError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    if result["removed"]:
        console.print(
            f"Removed auth metadata for {result['removed_provider']} from "
            f"{result['config_path']}."
        )
    else:
        console.print(
            f"No auth metadata for {result['removed_provider']} was present in "
            f"{result['config_path']}."
        )
    console.print("No environment files, keychains, provider accounts, or local models were modified.")


def _selected_auth_kind_for_auth_add(
    *,
    provider: str,
    config_path: Path,
    env: dict[str, str],
) -> str | None:
    options = provider_auth_method_options(provider, env=env)
    ready_options = [option for option in options if option["selectable"]]

    if len(ready_options) > 1:
        selected = questionary.select(
            f"Select auth method for {provider}:",
            choices=[
                questionary.Choice(
                    title=_auth_method_choice_title(option),
                    value=option["auth_kind"],
                )
                for option in ready_options
            ],
        ).ask()
        if selected is None:
            raise typer.Abort()
        return selected

    confirmed = questionary.confirm(
        f"Add non-secret auth metadata for {provider} to {config_path}?",
        default=False,
    ).ask()
    if not confirmed:
        raise typer.Abort()
    return ready_options[0]["auth_kind"] if ready_options else None


def _auth_method_choice_title(option: dict[str, object]) -> str:
    env_vars = option.get("detected_env_vars", [])
    env_text = ", ".join(env_vars) if isinstance(env_vars, list) and env_vars else "-"
    return f"{option['auth_kind']} (env vars: {env_text})"
