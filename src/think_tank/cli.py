"""Command-line adapter for Think Tank."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import questionary
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
    ProviderAuthNotReadyError,
    default_config_path,
    detect_provider_statuses,
    list_model_profiles,
    provider_auth_method_options,
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
from .setup import SetupAuthSelection, SetupModelProfileInput, initialize_setup
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


@app.command("init")
def init_setup(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to write non-secret Think Tank config."),
    ] = None,
) -> None:
    """Run guided setup for auth metadata, model profiles, and explicit defaults."""

    config_path = config or default_config_path(os.environ)
    auth_selections = _selected_init_auth_paths(config_path=config_path)
    model_profiles = _selected_init_model_profiles()
    default_model_profile = _selected_init_default_model_profile(
        config_path=config_path,
        model_profiles=model_profiles,
    )

    try:
        result = initialize_setup(
            config_path,
            env=os.environ,
            auth_selections=auth_selections,
            model_profiles=model_profiles,
            default_model_profile=default_model_profile,
        )
    except (
        ConfigFormatError,
        ModelProfileNotFoundError,
        ProviderAuthNotReadyError,
        ValueError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(f"Wrote config: {result['config_path']}")
    if result["auth_paths"]:
        console.print(
            "Enabled auth paths: "
            + ", ".join(
                f"{path['provider']}:{path['auth_kind']}"
                for path in result["auth_paths"]
            )
        )
    else:
        console.print("No provider auth paths enabled.")
    for profile in result["model_profiles"]:
        console.print(f"Model profile: {profile['name']} = {profile['model']}")
    if result["default_model_profile"]:
        console.print(f"Explicit default model profile: {result['default_model_profile']}")
    console.print("Secret values were not stored.")
    console.print("Work commands do not use defaults automatically yet.")


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


def _selected_init_auth_paths(*, config_path: Path) -> list[SetupAuthSelection]:
    choices = _init_auth_path_choices()
    selected = questionary.checkbox(
        f"Enable implemented ready auth paths in {config_path}?",
        choices=choices,
    ).ask()
    if selected is None:
        raise typer.Abort()
    return selected


def _init_auth_path_choices() -> list[questionary.Choice]:
    choices: list[questionary.Choice] = []
    for status in detect_provider_statuses(os.environ):
        for option in provider_auth_method_options(status["provider"], env=os.environ):
            if not option["selectable"]:
                continue
            choices.append(
                questionary.Choice(
                    title=_init_auth_path_choice_title(option),
                    value={
                        "provider": option["provider"],
                        "auth_kind": option["auth_kind"],
                    },
                    checked=option["selectable"],
                    disabled=None,
                )
            )
    return choices


def _init_auth_path_choice_title(option: dict[str, object]) -> str:
    env_vars = option.get("detected_env_vars", [])
    env_text = ", ".join(env_vars) if isinstance(env_vars, list) and env_vars else "-"
    return (
        f"{option['display_name']} ({option['provider']}) - "
        f"{option['auth_kind']}; env vars: {env_text}"
    )


def _selected_init_model_profiles() -> list[SetupModelProfileInput]:
    model_profiles: list[SetupModelProfileInput] = []
    create_profile = questionary.confirm(
        "Create a named model profile?",
        default=False,
    ).ask()
    if create_profile is None:
        raise typer.Abort()

    while create_profile:
        model_profiles.append(_entered_init_model_profile())
        create_profile = questionary.confirm(
            "Add another model profile?",
            default=False,
        ).ask()
        if create_profile is None:
            raise typer.Abort()
    return model_profiles


def _entered_init_model_profile() -> SetupModelProfileInput:
    name = questionary.text("Profile name:").ask()
    if name is None:
        raise typer.Abort()
    model = questionary.text("Model string (provider:model):").ask()
    if model is None:
        raise typer.Abort()
    return {"name": name, "model": model}


def _selected_init_default_model_profile(
    *,
    config_path: Path,
    model_profiles: list[SetupModelProfileInput],
) -> str | None:
    profile_names = _init_default_model_profile_names(
        config_path=config_path,
        model_profiles=model_profiles,
    )
    if not profile_names:
        return None

    set_default = questionary.confirm(
        "Set an explicit default model profile?",
        default=False,
    ).ask()
    if set_default is None:
        raise typer.Abort()
    if not set_default:
        return None

    selected = questionary.select(
        "Default model profile:",
        choices=profile_names,
    ).ask()
    if selected is None:
        raise typer.Abort()
    return selected


def _init_default_model_profile_names(
    *,
    config_path: Path,
    model_profiles: list[SetupModelProfileInput],
) -> list[str]:
    names: list[str] = []
    try:
        existing_profiles = list_model_profiles(config_path)["profiles"]
    except ConfigNotFoundError:
        existing_profiles = []
    except ConfigFormatError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for profile in existing_profiles:
        if profile["name"] not in names:
            names.append(profile["name"])
    for profile in model_profiles:
        name = profile["name"].strip()
        if name and name not in names:
            names.append(name)
    return names
