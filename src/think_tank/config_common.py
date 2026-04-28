"""Shared config parsing, validation, and rendering helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, TypedDict

from .config_store import (
    ConfigFormatError,
    ConfigNotFoundError,
    load_config,
    toml_string,
    write_config_text,
)
from .provider_registry import supported_provider_names


class AuthMethodConfig(TypedDict):
    auth_kind: str
    env_vars: list[str]


class DefaultsConfig(TypedDict):
    model_profile: str | None


class ModelProfileNotFoundError(LookupError):
    """Raised when a requested model profile is not configured."""


def empty_config() -> dict[str, object]:
    return {"schema_version": 1, "secrets": "environment"}


def model_profile_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("model profile name is required")
    return name


def model_string(model: str) -> str:
    model = model.strip()
    if ":" not in model:
        raise ValueError("model profile requires --model <provider:model>")
    provider, provider_model = model.split(":", 1)
    provider = provider.strip().lower()
    provider_model = provider_model.strip()
    if not provider or not provider_model:
        raise ValueError("model profile requires --model <provider:model>")
    if provider not in supported_provider_names():
        raise ValueError(f"unsupported model provider: {provider}")
    return f"{provider}:{provider_model}"


def load_existing_config(config_path: Path) -> dict[str, object]:
    if not config_path.exists():
        raise ConfigNotFoundError(f"config not found: {config_path}")
    return load_config(config_path)


def write_loaded_config(
    config_path: Path,
    config: Mapping[str, object],
    *,
    enabled_providers: list[str],
    provider_tables: Mapping[str, Mapping[str, object]],
    model_tables: Mapping[str, Mapping[str, object]] | None = None,
    defaults_table: Mapping[str, str] | None = None,
) -> None:
    write_config_text(
        config_path,
        render_loaded_config(
            config,
            enabled_providers=enabled_providers,
            provider_tables=provider_tables,
            model_table_map=model_tables,
            defaults=defaults_table,
        ),
    )


def enabled_providers(config: Mapping[str, object]) -> list[str]:
    enabled = config.get("enabled_providers", [])
    if not isinstance(enabled, list) or not all(
        isinstance(provider, str) for provider in enabled
    ):
        raise ConfigFormatError("config enabled_providers must be a list of strings")
    return enabled


def provider_tables(config: Mapping[str, object]) -> dict[str, dict[str, object]]:
    providers = config.get("providers", {})
    if not isinstance(providers, dict):
        raise ConfigFormatError("config providers must be a table")

    tables: dict[str, dict[str, object]] = {}
    for provider, table in providers.items():
        if not isinstance(provider, str) or not isinstance(table, dict):
            raise ConfigFormatError("config providers entries must be tables")
        tables[provider] = table
    return tables


def model_tables(config: Mapping[str, object]) -> dict[str, dict[str, object]]:
    models = config.get("models", {})
    if not isinstance(models, dict):
        raise ConfigFormatError("config models must be a table")

    tables: dict[str, dict[str, object]] = {}
    for name, table in models.items():
        if not isinstance(name, str) or not isinstance(table, dict):
            raise ConfigFormatError("config models entries must be tables")
        tables[name] = table
    return tables


def defaults_table(config: Mapping[str, object]) -> dict[str, str]:
    defaults = config.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ConfigFormatError("config defaults must be a table")

    table: dict[str, str] = {}
    if "model_profile" in defaults:
        value = defaults["model_profile"]
        if not isinstance(value, str):
            raise ConfigFormatError("config defaults model_profile must be a string")
        table["model_profile"] = model_profile_name(value)
    return table


def defaults_result(defaults: Mapping[str, str]) -> DefaultsConfig:
    return {
        "model_profile": defaults.get("model_profile"),
    }


def default_name(name: str) -> str:
    name = name.strip().replace("-", "_")
    if name == "model_profile":
        return name
    raise ValueError(f"unknown default: {name or '-'} (supported: model-profile)")


def auth_kind(provider: str, provider_tables: Mapping[str, Mapping[str, object]]) -> str:
    value = provider_tables.get(provider, {}).get("auth_kind", "")
    if value == "":
        methods = auth_methods(provider, provider_tables)
        return methods[0]["auth_kind"] if methods else ""
    if not isinstance(value, str):
        raise ConfigFormatError(f"provider {provider} auth_kind must be a string")
    return value


def env_vars(provider: str, provider_tables: Mapping[str, Mapping[str, object]]) -> list[str]:
    value = provider_tables.get(provider, {}).get("env_vars", [])
    if value == []:
        methods = auth_methods(provider, provider_tables)
        return methods[0]["env_vars"] if methods else []
    if not isinstance(value, list) or not all(
        isinstance(env_var, str) for env_var in value
    ):
        raise ConfigFormatError(f"provider {provider} env_vars must be a list of strings")
    return value


def auth_methods(
    provider: str,
    provider_tables: Mapping[str, Mapping[str, object]],
) -> list[AuthMethodConfig]:
    table = provider_tables.get(provider, {})
    value = table.get("auth_methods")
    if value is None:
        auth_kind_value = table.get("auth_kind", "")
        env_var_names = table.get("env_vars", [])
        if not auth_kind_value and not env_var_names:
            return []
        if not isinstance(auth_kind_value, str):
            raise ConfigFormatError(f"provider {provider} auth_kind must be a string")
        if not isinstance(env_var_names, list) or not all(
            isinstance(env_var, str) for env_var in env_var_names
        ):
            raise ConfigFormatError(
                f"provider {provider} env_vars must be a list of strings"
            )
        return [{"auth_kind": auth_kind_value, "env_vars": env_var_names}]

    if not isinstance(value, list):
        raise ConfigFormatError(f"provider {provider} auth_methods must be a list")

    methods: list[AuthMethodConfig] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ConfigFormatError(
                f"provider {provider} auth_methods entry {index} must be a table"
            )
        auth_kind_value = item.get("auth_kind", "")
        env_var_names = item.get("env_vars", [])
        if not isinstance(auth_kind_value, str) or not auth_kind_value:
            raise ConfigFormatError(
                f"provider {provider} auth_methods entry {index} auth_kind must be a string"
            )
        if not isinstance(env_var_names, list) or not all(
            isinstance(env_var, str) for env_var in env_var_names
        ):
            raise ConfigFormatError(
                f"provider {provider} auth_methods entry {index} env_vars must be a list of strings"
            )
        methods.append({"auth_kind": auth_kind_value, "env_vars": env_var_names})
    return methods


def profile_model(name: str, model_table_map: Mapping[str, Mapping[str, object]]) -> str:
    value = model_table_map.get(name, {}).get("model", "")
    if not isinstance(value, str):
        raise ConfigFormatError(f"model profile {name} model must be a string")
    return model_string(value)


def render_loaded_config(
    config: Mapping[str, object],
    *,
    enabled_providers: list[str],
    provider_tables: Mapping[str, Mapping[str, object]],
    model_table_map: Mapping[str, Mapping[str, object]] | None = None,
    defaults: Mapping[str, str] | None = None,
) -> str:
    if model_table_map is None:
        model_table_map = model_tables(config)
    if defaults is None:
        defaults = defaults_table(config)

    lines = [
        f"schema_version = {schema_version(config)}",
        f"secrets = {toml_string(secrets(config))}",
        "",
        "enabled_providers = [",
    ]
    for provider in enabled_providers:
        lines.append(f"  {toml_string(provider)},")
    lines.extend([
        "]",
        "",
    ])

    for provider in enabled_providers:
        table = provider_tables.get(provider)
        if table is None:
            continue
        lines.extend(
            [
                f"[providers.{provider}]",
                f"auth_kind = {toml_string(auth_kind(provider, provider_tables))}",
                "env_vars = [",
            ]
        )
        for env_var in env_vars(provider, provider_tables):
            lines.append(f"  {toml_string(env_var)},")
        lines.extend([
            "]",
            "",
        ])
        for method in auth_methods(provider, provider_tables):
            lines.extend(
                [
                    f"[[providers.{provider}.auth_methods]]",
                    f"auth_kind = {toml_string(method['auth_kind'])}",
                    "env_vars = [",
                ]
            )
            for env_var in method["env_vars"]:
                lines.append(f"  {toml_string(env_var)},")
            lines.extend([
                "]",
                "",
            ])

    for name in model_table_map:
        lines.extend(
            [
                f"[models.{toml_string(name)}]",
                f"model = {toml_string(profile_model(name, model_table_map))}",
                "",
            ]
        )

    if defaults:
        lines.extend([
            "[defaults]",
        ])
        if model_profile := defaults.get("model_profile"):
            lines.append(f"model_profile = {toml_string(model_profile)}")
        lines.append("")

    return "\n".join(lines)


def schema_version(config: Mapping[str, object]) -> int:
    value = config.get("schema_version", 1)
    if not isinstance(value, int):
        raise ConfigFormatError("config schema_version must be an integer")
    return value


def secrets(config: Mapping[str, object]) -> str:
    value = config.get("secrets", "environment")
    if not isinstance(value, str):
        raise ConfigFormatError("config secrets must be a string")
    return value
