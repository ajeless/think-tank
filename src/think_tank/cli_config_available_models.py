"""`think config models ...` CLI commands."""

from __future__ import annotations

import json
import os
from typing import Annotated

import typer
from rich.console import Console

from .engine import ProviderModelListingInputError, list_provider_models
from .model_client import GeminiModelRegistry


config_available_models_app = typer.Typer(
    help="Discover provider model IDs visible to current credentials."
)
console = Console()


@config_available_models_app.command("list")
def config_available_models_list(
    provider: Annotated[
        str,
        typer.Option("--provider", help="Provider name to query."),
    ],
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON output.")] = False,
) -> None:
    """List provider-visible model IDs without storing secrets or config."""

    try:
        result = list_provider_models(
            provider=provider,
            env=os.environ,
            gemini_registry=GeminiModelRegistry(),
        )
    except ProviderModelListingInputError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
    else:
        console.print(f"Provider: {result['provider']}")
        console.print(f"Status: {_model_listing_status_label(result['status'])}")
        console.print(result["message"])
        for model in result["models"]:
            suffix = ""
            if model["display_name"]:
                suffix += f" - {model['display_name']}"
            if model["supported_actions"]:
                suffix += f" ({', '.join(model['supported_actions'])})"
            console.print(f"{model['model']}{suffix}")
        console.print("Secret values were not stored or printed.")

    if not result["ok"]:
        raise typer.Exit(1)


def _model_listing_status_label(status: str) -> str:
    labels = {
        "success": "success",
        "missing_credentials": "missing credentials",
        "not_supported": "not supported",
        "provider_config_error": "provider SDK/config issue",
        "provider_failure": "provider failure",
    }
    return labels[status]
