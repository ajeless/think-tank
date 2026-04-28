"""Guided setup orchestration for Think Tank config."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, TypedDict

from .config_auth import ProviderAuthNotReadyError
from .config_common import (
    AuthMethodConfig,
    empty_config,
    write_loaded_config,
)
from .config_defaults import set_config_defaults
from .config_models import ModelAddResult, add_model_profile
from .config_store import load_config
from .provider_registry import provider_auth_method_options


class SetupAuthSelection(TypedDict):
    provider: str
    auth_kind: str


class SetupAuthConfig(TypedDict):
    provider: str
    auth_kind: str
    env_vars: list[str]
    auth_methods: list[AuthMethodConfig]


class SetupInitResult(TypedDict):
    config_path: str
    auth_paths: list[SetupAuthConfig]
    model_profile: ModelAddResult | None
    default_model_profile: str | None


def initialize_setup(
    config_path: Path,
    *,
    env: Mapping[str, str],
    auth_selections: list[SetupAuthSelection],
    model_profile_name: str | None = None,
    model: str | None = None,
    set_default_model_profile: bool = False,
) -> SetupInitResult:
    """Apply guided setup choices to non-secret user config."""

    resolved_path = config_path.expanduser()
    auth_paths = _write_selected_auth_metadata(
        resolved_path,
        env=env,
        auth_selections=auth_selections,
    )

    profile_result: ModelAddResult | None = None
    if model_profile_name is not None or model is not None:
        if model_profile_name is None or model is None:
            raise ValueError("model profile setup requires a name and provider:model")
        profile_result = add_model_profile(
            resolved_path,
            name=model_profile_name,
            model=model,
        )

    default_model_profile: str | None = None
    if set_default_model_profile:
        if profile_result is None:
            raise ValueError("default model profile setup requires a model profile")
        defaults_result = set_config_defaults(
            resolved_path,
            model_profile=profile_result["name"],
        )
        default_model_profile = defaults_result["defaults"]["model_profile"]

    return {
        "config_path": str(resolved_path),
        "auth_paths": auth_paths,
        "model_profile": profile_result,
        "default_model_profile": default_model_profile,
    }


def _write_selected_auth_metadata(
    config_path: Path,
    *,
    env: Mapping[str, str],
    auth_selections: list[SetupAuthSelection],
) -> list[SetupAuthConfig]:
    selected_providers: list[str] = []
    current_provider_tables: dict[str, dict[str, object]] = {}
    auth_paths: list[SetupAuthConfig] = []

    for selection in auth_selections:
        provider = selection["provider"].strip().lower()
        auth_kind = selection["auth_kind"].strip()
        if not provider:
            raise ValueError("provider name is required")
        if not auth_kind:
            raise ValueError(f"auth kind is required for provider: {provider}")
        if provider in selected_providers:
            raise ValueError(f"select only one auth path for provider: {provider}")

        option = _ready_auth_option(provider, auth_kind=auth_kind, env=env)
        selected_providers.append(provider)
        table = {
            "auth_kind": option["auth_kind"],
            "env_vars": option["detected_env_vars"],
            "auth_methods": [
                {
                    "auth_kind": option["auth_kind"],
                    "env_vars": option["detected_env_vars"],
                }
            ],
        }
        current_provider_tables[provider] = table
        auth_paths.append(
            {
                "provider": provider,
                "auth_kind": option["auth_kind"],
                "env_vars": option["detected_env_vars"],
                "auth_methods": [
                    {
                        "auth_kind": option["auth_kind"],
                        "env_vars": option["detected_env_vars"],
                    }
                ],
            }
        )

    if config_path.exists():
        config = load_config(config_path)
    else:
        config = empty_config()

    write_loaded_config(
        config_path,
        config,
        enabled_providers=selected_providers,
        provider_tables=current_provider_tables,
    )
    return auth_paths


def _ready_auth_option(
    provider: str,
    *,
    auth_kind: str,
    env: Mapping[str, str],
) -> dict[str, object]:
    for option in provider_auth_method_options(provider, env=env):
        if option["auth_kind"] == auth_kind:
            if option["missing_env_vars"]:
                raise ProviderAuthNotReadyError(
                    "missing required environment variable(s): "
                    + ", ".join(option["missing_env_vars"])
                )
            return option
    raise ValueError(f"unsupported auth kind for {provider}: {auth_kind}")
