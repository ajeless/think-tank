"""Explicit user-authored config defaults behavior."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from .config_common import (
    DefaultsConfig,
    ModelProfileNotFoundError,
    default_name as parse_default_name,
    defaults_result,
    defaults_table,
    enabled_providers,
    load_existing_config,
    model_profile_name,
    model_tables,
    provider_tables,
    write_loaded_config,
)


class DefaultsSetResult(TypedDict):
    config_path: str
    defaults: DefaultsConfig


class DefaultsListResult(TypedDict):
    config_path: str
    defaults: DefaultsConfig


class DefaultRemoveResult(TypedDict):
    config_path: str
    removed_default: str
    removed: bool
    defaults: DefaultsConfig


def set_config_defaults(
    config_path: Path,
    *,
    model_profile: str | None = None,
) -> DefaultsSetResult:
    resolved_path = config_path.expanduser()
    if model_profile is None:
        raise ValueError("defaults set requires --model-profile <name>")

    model_profile = model_profile_name(model_profile)
    config = load_existing_config(resolved_path)
    current_enabled_providers = enabled_providers(config)
    current_provider_tables = provider_tables(config)
    current_model_tables = model_tables(config)
    current_defaults = defaults_table(config)

    if model_profile not in current_model_tables:
        raise ModelProfileNotFoundError(f"model profile not found: {model_profile}")

    updated_defaults = dict(current_defaults)
    updated_defaults["model_profile"] = model_profile
    write_loaded_config(
        resolved_path,
        config,
        enabled_providers=current_enabled_providers,
        provider_tables=current_provider_tables,
        model_tables=current_model_tables,
        defaults_table=updated_defaults,
    )

    return {
        "config_path": str(resolved_path),
        "defaults": defaults_result(updated_defaults),
    }


def list_config_defaults(config_path: Path) -> DefaultsListResult:
    resolved_path = config_path.expanduser()
    config = load_existing_config(resolved_path)
    current_defaults = defaults_table(config)
    return {
        "config_path": str(resolved_path),
        "defaults": defaults_result(current_defaults),
    }


def remove_config_default(config_path: Path, default_name: str) -> DefaultRemoveResult:
    resolved_path = config_path.expanduser()
    default_name = parse_default_name(default_name)
    config = load_existing_config(resolved_path)
    current_enabled_providers = enabled_providers(config)
    current_provider_tables = provider_tables(config)
    current_model_tables = model_tables(config)
    current_defaults = defaults_table(config)

    removed = default_name in current_defaults
    updated_defaults = {
        name: value
        for name, value in current_defaults.items()
        if name != default_name
    }
    write_loaded_config(
        resolved_path,
        config,
        enabled_providers=current_enabled_providers,
        provider_tables=current_provider_tables,
        model_tables=current_model_tables,
        defaults_table=updated_defaults,
    )

    return {
        "config_path": str(resolved_path),
        "removed_default": default_name,
        "removed": removed,
        "defaults": defaults_result(updated_defaults),
    }
