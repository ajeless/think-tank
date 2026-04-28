"""Top-level `think config ...` CLI commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console

from .config import default_config_path, detect_provider_statuses, write_detected_provider_config
from .engine import MissingModelError, ProviderValidationInputError, validate_provider
from .model_client import AisuiteModelClient, OllamaHttpModelRegistry


config_app = typer.Typer(help="Configure non-secret Think Tank preferences.")
console = Console()


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


@config_app.command("validate")
def config_validate(
    provider: Annotated[
        str,
        typer.Option("--provider", help="Provider name to validate."),
    ],
    model: Annotated[
        str,
        typer.Option("--model", help="Explicit provider:model identifier to validate."),
    ],
) -> None:
    """Explicitly validate provider credentials and model availability."""

    try:
        result = validate_provider(
            provider=provider,
            model=model,
            client=AisuiteModelClient(),
            env=os.environ,
            ollama_registry=OllamaHttpModelRegistry.from_env(os.environ),
        )
    except (MissingModelError, ProviderValidationInputError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(f"Provider: {result['provider']}")
    console.print(f"Model: {result['model']}")
    console.print(f"Status: {_validation_status_label(result['status'])}")
    console.print(result["message"])
    if not result["ok"]:
        raise typer.Exit(1)


def _validation_status_label(status: str) -> str:
    labels = {
        "success": "success",
        "missing_credentials": "missing credentials",
        "auth_failure": "auth failure",
        "quota_or_rate_limit": "quota/rate limit",
        "provider_config_error": "provider SDK/config issue",
        "provider_failure": "provider failure",
    }
    return labels[status]
