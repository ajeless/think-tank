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


class SetupModelProfileInput(TypedDict):
    name: str
    model: str


class SetupInitResult(TypedDict):
    config_path: str
    auth_paths: list[SetupAuthConfig]
    model_profiles: list[ModelAddResult]
    default_model_profile: str | None


def initialize_setup(
    config_path: Path,
    *,
    env: Mapping[str, str],
    auth_selections: list[SetupAuthSelection],
    model_profiles: list[SetupModelProfileInput] | None = None,
    default_model_profile: str | None = None,
) -> SetupInitResult:
    """Apply guided setup choices to non-secret user config."""

    model_profiles = [] if model_profiles is None else model_profiles
    resolved_path = config_path.expanduser()
    auth_paths = _write_selected_auth_metadata(
        resolved_path,
        env=env,
        auth_selections=auth_selections,
    )

    profile_results = _add_model_profiles(resolved_path, model_profiles)

    selected_default_profile: str | None = None
    if default_model_profile:
        defaults_result = set_config_defaults(
            resolved_path,
            model_profile=default_model_profile,
        )
        selected_default_profile = defaults_result["defaults"]["model_profile"]

    return {
        "config_path": str(resolved_path),
        "auth_paths": auth_paths,
        "model_profiles": profile_results,
        "default_model_profile": selected_default_profile,
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


def _add_model_profiles(
    config_path: Path,
    model_profiles: list[SetupModelProfileInput],
) -> list[ModelAddResult]:
    results: list[ModelAddResult] = []
    for profile in model_profiles:
        name = profile.get("name")
        model = profile.get("model")
        if name is None or model is None:
            raise ValueError("model profile setup requires a name and provider:model")
        results.append(add_model_profile(config_path, name=name, model=model))
    return results


def _ready_auth_option(
    provider: str,
    *,
    auth_kind: str,
    env: Mapping[str, str],
) -> dict[str, object]:
    for option in provider_auth_method_options(provider, env=env):
        if option["auth_kind"] == auth_kind:
            if not option["implemented"]:
                raise ProviderAuthNotReadyError(
                    f"auth kind for {provider} is not implemented yet: {auth_kind}"
                )
            if option["missing_env_vars"]:
                raise ProviderAuthNotReadyError(
                    "missing required environment variable(s): "
                    + ", ".join(option["missing_env_vars"])
                )
            return option
    raise ValueError(f"unsupported auth kind for {provider}: {auth_kind}")
