"""Provider auth metadata config behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, TypedDict

from .config_common import (
    AuthMethodConfig,
    auth_kind,
    auth_methods,
    empty_config,
    enabled_providers,
    env_vars,
    load_existing_config,
    provider_tables,
    write_loaded_config,
)
from .config_store import load_config
from .provider_registry import (
    ProviderAuthMethodOption,
    ProviderStatus,
    detect_provider_statuses,
    provider_auth_method_options,
    supported_provider_names,
)


class ConfigInitResult(TypedDict):
    config_path: str
    enabled_providers: list[str]


class AuthProviderConfig(TypedDict):
    provider: str
    auth_kind: str
    env_vars: list[str]
    auth_methods: list[AuthMethodConfig]


class AuthListResult(TypedDict):
    config_path: str
    providers: list[AuthProviderConfig]


class AuthRemoveResult(TypedDict):
    config_path: str
    removed_provider: str
    removed: bool
    enabled_providers: list[str]


class AuthAddResult(TypedDict):
    config_path: str
    provider: str
    added: bool
    auth_kind: str
    env_vars: list[str]
    enabled_providers: list[str]


class AuthDoctorProvider(TypedDict):
    provider: str
    display_name: str
    configured: bool
    detected: bool
    ready: bool
    configured_auth_kind: str
    detected_auth_kind: str
    configured_auth_methods: list[AuthMethodConfig]
    configured_env_vars: list[str]
    detected_env_vars: list[str]
    missing_env_vars: list[str]
    notes: list[str]


class AuthDoctorResult(TypedDict):
    config_path: str
    config_found: bool
    providers: list[AuthDoctorProvider]


class ProviderAuthNotReadyError(ValueError):
    """Raised when a provider auth path is known but not ready to record."""


def write_detected_provider_config(
    config_path: Path,
    *,
    env: Mapping[str, str],
    enabled_providers: list[str] | None = None,
) -> ConfigInitResult:
    statuses = detect_provider_statuses(env)
    ready_provider_names = [
        status["provider"] for status in statuses if status["ready"]
    ]
    selected = enabled_providers if enabled_providers is not None else ready_provider_names
    unknown = sorted(set(selected) - supported_provider_names())
    if unknown:
        raise ValueError(f"unknown provider(s): {', '.join(unknown)}")

    status_by_name = {status["provider"]: status for status in statuses}
    current_provider_tables = {
        provider: {
            "auth_kind": status_by_name[provider]["auth_kind"],
            "env_vars": status_by_name[provider]["detected_env_vars"],
            "auth_methods": [
                {
                    "auth_kind": status_by_name[provider]["auth_kind"],
                    "env_vars": status_by_name[provider]["detected_env_vars"],
                }
            ],
        }
        for provider in selected
    }

    config_path = config_path.expanduser()
    if config_path.exists():
        config = load_config(config_path)
    else:
        config = empty_config()

    write_loaded_config(
        config_path,
        config,
        enabled_providers=list(selected),
        provider_tables=current_provider_tables,
    )

    return {
        "config_path": str(config_path),
        "enabled_providers": list(selected),
    }


def list_config_auth(config_path: Path) -> AuthListResult:
    resolved_path = config_path.expanduser()
    config = load_existing_config(resolved_path)
    current_provider_tables = provider_tables(config)
    providers = [
        {
            "provider": provider,
            "auth_kind": auth_kind(provider, current_provider_tables),
            "env_vars": env_vars(provider, current_provider_tables),
            "auth_methods": auth_methods(provider, current_provider_tables),
        }
        for provider in enabled_providers(config)
    ]
    return {
        "config_path": str(resolved_path),
        "providers": providers,
    }


def add_config_auth(
    config_path: Path,
    provider: str,
    *,
    env: Mapping[str, str],
    auth_kind: str | None = None,
) -> AuthAddResult:
    resolved_path = config_path.expanduser()
    provider = provider.strip().lower()
    if not provider:
        raise ValueError("auth add requires a provider name")

    option = _selected_auth_method_option(provider, auth_kind=auth_kind, env=env)
    if option["missing_env_vars"]:
        raise ProviderAuthNotReadyError(
            "missing required environment variable(s): "
            + ", ".join(option["missing_env_vars"])
        )

    if resolved_path.exists():
        config = load_config(resolved_path)
        current_enabled_providers = enabled_providers(config)
        current_provider_tables = provider_tables(config)
    else:
        config = empty_config()
        current_enabled_providers = []
        current_provider_tables = {}

    added = provider not in current_enabled_providers or provider not in current_provider_tables
    updated_enabled = list(current_enabled_providers)
    if provider not in updated_enabled:
        updated_enabled.append(provider)

    updated_provider_tables = dict(current_provider_tables)
    updated_provider_tables[provider] = {
        "auth_kind": option["auth_kind"],
        "env_vars": option["detected_env_vars"],
        "auth_methods": [
            {
                "auth_kind": option["auth_kind"],
                "env_vars": option["detected_env_vars"],
            }
        ],
    }

    write_loaded_config(
        resolved_path,
        config,
        enabled_providers=updated_enabled,
        provider_tables=updated_provider_tables,
    )

    return {
        "config_path": str(resolved_path),
        "provider": provider,
        "added": added,
        "auth_kind": option["auth_kind"],
        "env_vars": option["detected_env_vars"],
        "enabled_providers": updated_enabled,
    }


def remove_config_auth(config_path: Path, provider: str) -> AuthRemoveResult:
    resolved_path = config_path.expanduser()
    provider = provider.strip().lower()
    if not provider:
        raise ValueError("auth remove requires a provider name")

    config = load_existing_config(resolved_path)
    current_enabled_providers = enabled_providers(config)
    current_provider_tables = provider_tables(config)

    removed = provider in current_enabled_providers or provider in current_provider_tables
    updated_enabled = [name for name in current_enabled_providers if name != provider]
    updated_provider_tables = {
        name: table for name, table in current_provider_tables.items() if name != provider
    }
    write_loaded_config(
        resolved_path,
        config,
        enabled_providers=updated_enabled,
        provider_tables=updated_provider_tables,
    )

    return {
        "config_path": str(resolved_path),
        "removed_provider": provider,
        "removed": removed,
        "enabled_providers": updated_enabled,
    }


def doctor_config_auth(config_path: Path, *, env: Mapping[str, str]) -> AuthDoctorResult:
    resolved_path = config_path.expanduser()
    config_found = resolved_path.exists()
    if config_found:
        config = load_config(resolved_path)
        current_enabled_providers = set(enabled_providers(config))
        current_provider_tables = provider_tables(config)
    else:
        current_enabled_providers = set()
        current_provider_tables = {}

    configured_provider_names = set(current_provider_tables)
    detected_statuses = detect_provider_statuses(env)
    provider_names = _doctor_provider_names(
        detected_statuses,
        configured_provider_names | current_enabled_providers,
    )
    status_by_provider = {
        status["provider"]: status for status in detected_statuses
    }

    return {
        "config_path": str(resolved_path),
        "config_found": config_found,
        "providers": [
            _doctor_provider(
                provider,
                status_by_provider=status_by_provider,
                enabled_providers=current_enabled_providers,
                provider_tables=current_provider_tables,
            )
            for provider in provider_names
        ],
    }


def _selected_auth_method_option(
    provider: str,
    *,
    auth_kind: str | None,
    env: Mapping[str, str],
) -> ProviderAuthMethodOption:
    options = provider_auth_method_options(provider, env=env)
    if auth_kind is None:
        for option in options:
            if option["implemented"]:
                return option
        raise ValueError(f"provider has no implemented auth methods: {provider}")

    auth_kind = auth_kind.strip()
    if not auth_kind:
        raise ValueError("auth kind is required")

    for option in options:
        if option["auth_kind"] == auth_kind:
            if not option["implemented"]:
                raise ValueError(
                    f"auth kind for {provider} is not implemented yet: {auth_kind}"
                )
            return option
    supported = ", ".join(
        option["auth_kind"] for option in options if option["implemented"]
    )
    raise ValueError(
        f"unsupported auth kind for {provider}: {auth_kind} (supported: {supported})"
    )


def _doctor_provider_names(
    statuses: list[ProviderStatus],
    configured_providers: set[str],
) -> list[str]:
    names = [status["provider"] for status in statuses]
    for provider in sorted(configured_providers):
        if provider not in names:
            names.append(provider)
    return names


def _doctor_provider(
    provider: str,
    *,
    status_by_provider: Mapping[str, ProviderStatus],
    enabled_providers: set[str],
    provider_tables: Mapping[str, Mapping[str, object]],
) -> AuthDoctorProvider:
    status = status_by_provider.get(provider)
    configured = provider in enabled_providers or provider in provider_tables
    configured_env_vars = env_vars(provider, provider_tables)
    configured_auth_kind = auth_kind(provider, provider_tables)
    configured_auth_methods = auth_methods(provider, provider_tables)

    if status is None:
        return {
            "provider": provider,
            "display_name": provider,
            "configured": configured,
            "detected": False,
            "ready": False,
            "configured_auth_kind": configured_auth_kind,
            "detected_auth_kind": "",
            "configured_auth_methods": configured_auth_methods,
            "configured_env_vars": configured_env_vars,
            "detected_env_vars": [],
            "missing_env_vars": [],
            "notes": ["Provider is configured but is not in the packaged provider set."],
        }

    return {
        "provider": provider,
        "display_name": status["display_name"],
        "configured": configured,
        "detected": bool(status["detected_env_vars"]) or status["auth_kind"] == "local_server",
        "ready": status["ready"],
        "configured_auth_kind": configured_auth_kind,
        "detected_auth_kind": status["auth_kind"],
        "configured_auth_methods": configured_auth_methods,
        "configured_env_vars": configured_env_vars,
        "detected_env_vars": status["detected_env_vars"],
        "missing_env_vars": status["missing_env_vars"],
        "notes": status["notes"],
    }
