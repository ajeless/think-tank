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
    ConfigFormatError,
    ConfigNotFoundError,
    ProviderAuthNotReadyError,
    add_config_auth,
    default_config_path,
    detect_provider_statuses,
    doctor_config_auth,
    list_config_auth,
    remove_config_auth,
    write_detected_provider_config,
)
from .engine import (
    MissingModelError,
    MissingPromptError,
    ProjectStateNotFoundError,
    ProviderValidationInputError,
    ask_project,
    get_engine_status,
    validate_provider,
)
from .model_client import (
    AisuiteModelClient,
    ModelClientCallError,
    ModelClientConfigurationError,
    OllamaHttpModelRegistry,
)
from .workspace import WorkspaceAlreadyExistsError, init_workspace


app = typer.Typer(
    name="think",
    help="Think Tank local-first idea workspace.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Configure non-secret Think Tank preferences.")
config_auth_app = typer.Typer(help="Manage non-secret provider auth metadata.")
app.add_typer(config_app, name="config")
config_app.add_typer(config_auth_app, name="auth")
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
    if not yes:
        confirmed = questionary.confirm(
            f"Add non-secret auth metadata for {provider} to {config_path}?",
            default=False,
        ).ask()
        if not confirmed:
            raise typer.Abort()

    try:
        result = add_config_auth(config_path, provider, env=os.environ)
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
