"""Named model profile config behavior."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from .config_common import (
    ModelProfileNotFoundError,
    defaults_table,
    empty_config,
    enabled_providers,
    load_existing_config,
    model_profile_name,
    model_string,
    model_tables,
    profile_model,
    provider_tables,
    write_loaded_config,
)
from .config_store import load_config


class ModelProfile(TypedDict):
    name: str
    model: str


class ModelAddResult(TypedDict):
    config_path: str
    name: str
    model: str
    added: bool


class ModelListResult(TypedDict):
    config_path: str
    profiles: list[ModelProfile]


class ModelRemoveResult(TypedDict):
    config_path: str
    removed_profile: str
    removed: bool


def add_model_profile(config_path: Path, name: str, model: str) -> ModelAddResult:
    resolved_path = config_path.expanduser()
    name = model_profile_name(name)
    model = model_string(model)

    if resolved_path.exists():
        config = load_config(resolved_path)
        current_enabled_providers = enabled_providers(config)
        current_provider_tables = provider_tables(config)
        current_model_tables = model_tables(config)
    else:
        config = empty_config()
        current_enabled_providers = []
        current_provider_tables = {}
        current_model_tables = {}

    added = name not in current_model_tables
    updated_model_tables = dict(current_model_tables)
    updated_model_tables[name] = {"model": model}

    write_loaded_config(
        resolved_path,
        config,
        enabled_providers=current_enabled_providers,
        provider_tables=current_provider_tables,
        model_tables=updated_model_tables,
    )

    return {
        "config_path": str(resolved_path),
        "name": name,
        "model": model,
        "added": added,
    }


def list_model_profiles(config_path: Path) -> ModelListResult:
    resolved_path = config_path.expanduser()
    config = load_existing_config(resolved_path)
    current_model_tables = model_tables(config)
    return {
        "config_path": str(resolved_path),
        "profiles": [
            {
                "name": name,
                "model": profile_model(name, current_model_tables),
            }
            for name in current_model_tables
        ],
    }


def remove_model_profile(config_path: Path, name: str) -> ModelRemoveResult:
    resolved_path = config_path.expanduser()
    name = model_profile_name(name)
    config = load_existing_config(resolved_path)
    current_enabled_providers = enabled_providers(config)
    current_provider_tables = provider_tables(config)
    current_model_tables = model_tables(config)
    current_defaults = defaults_table(config)

    removed = name in current_model_tables
    updated_model_tables = {
        profile_name: table
        for profile_name, table in current_model_tables.items()
        if profile_name != name
    }
    updated_defaults = dict(current_defaults)
    if updated_defaults.get("model_profile") == name:
        del updated_defaults["model_profile"]
    write_loaded_config(
        resolved_path,
        config,
        enabled_providers=current_enabled_providers,
        provider_tables=current_provider_tables,
        model_tables=updated_model_tables,
        defaults_table=updated_defaults,
    )

    return {
        "config_path": str(resolved_path),
        "removed_profile": name,
        "removed": removed,
    }


def resolve_model_profile(config_path: Path, name: str) -> ModelProfile:
    resolved_path = config_path.expanduser()
    name = model_profile_name(name)
    config = load_existing_config(resolved_path)
    current_model_tables = model_tables(config)
    if name not in current_model_tables:
        raise ModelProfileNotFoundError(f"model profile not found: {name}")
    return {
        "name": name,
        "model": profile_model(name, current_model_tables),
    }
