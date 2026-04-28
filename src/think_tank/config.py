"""Provider onboarding and non-secret Think Tank configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, TypedDict

from .config_store import (
    ConfigFormatError,
    ConfigNotFoundError,
    default_config_path,
    load_config,
    toml_string,
    write_config_text,
)
from .provider_registry import (
    PROVIDER_SPECS,
    ProviderAuthMethodOption,
    ProviderAuthMethodSpec,
    ProviderSpec,
    ProviderStatus,
    detect_provider_statuses,
    provider_auth_method_options,
    supported_provider_names,
)


class ConfigInitResult(TypedDict):
    config_path: str
    enabled_providers: list[str]


class AuthMethodConfig(TypedDict):
    auth_kind: str
    env_vars: list[str]


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


class DefaultsConfig(TypedDict):
    model_profile: str | None


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


class ProviderAuthNotReadyError(ValueError):
    """Raised when a provider auth path is known but not ready to record."""


class ModelProfileNotFoundError(LookupError):
    """Raised when a requested model profile is not configured."""


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
    provider_tables = {
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
        config = {"schema_version": 1, "secrets": "environment"}

    _write_loaded_config(
        config_path,
        config,
        enabled_providers=list(selected),
        provider_tables=provider_tables,
    )

    return {
        "config_path": str(config_path),
        "enabled_providers": list(selected),
    }

def add_model_profile(config_path: Path, name: str, model: str) -> ModelAddResult:
    resolved_path = config_path.expanduser()
    name = _model_profile_name(name)
    model = _model_string(model)

    if resolved_path.exists():
        config = load_config(resolved_path)
        enabled_providers = _enabled_providers(config)
        provider_tables = _provider_tables(config)
        model_tables = _model_tables(config)
    else:
        config = {"schema_version": 1, "secrets": "environment"}
        enabled_providers = []
        provider_tables = {}
        model_tables = {}

    added = name not in model_tables
    updated_model_tables = dict(model_tables)
    updated_model_tables[name] = {"model": model}

    _write_loaded_config(
        resolved_path,
        config,
        enabled_providers=enabled_providers,
        provider_tables=provider_tables,
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
    config = _load_existing_config(resolved_path)
    model_tables = _model_tables(config)
    return {
        "config_path": str(resolved_path),
        "profiles": [
            {
                "name": name,
                "model": _profile_model(name, model_tables),
            }
            for name in model_tables
        ],
    }


def remove_model_profile(config_path: Path, name: str) -> ModelRemoveResult:
    resolved_path = config_path.expanduser()
    name = _model_profile_name(name)
    config = _load_existing_config(resolved_path)
    enabled_providers = _enabled_providers(config)
    provider_tables = _provider_tables(config)
    model_tables = _model_tables(config)
    defaults = _defaults_table(config)

    removed = name in model_tables
    updated_model_tables = {
        profile_name: table
        for profile_name, table in model_tables.items()
        if profile_name != name
    }
    updated_defaults = dict(defaults)
    if updated_defaults.get("model_profile") == name:
        del updated_defaults["model_profile"]
    _write_loaded_config(
        resolved_path,
        config,
        enabled_providers=enabled_providers,
        provider_tables=provider_tables,
        model_tables=updated_model_tables,
        defaults_table=updated_defaults,
    )

    return {
        "config_path": str(resolved_path),
        "removed_profile": name,
        "removed": removed,
    }


def set_config_defaults(
    config_path: Path,
    *,
    model_profile: str | None = None,
) -> DefaultsSetResult:
    resolved_path = config_path.expanduser()
    if model_profile is None:
        raise ValueError("defaults set requires --model-profile <name>")

    model_profile = _model_profile_name(model_profile)
    config = _load_existing_config(resolved_path)
    enabled_providers = _enabled_providers(config)
    provider_tables = _provider_tables(config)
    model_tables = _model_tables(config)
    defaults = _defaults_table(config)

    if model_profile not in model_tables:
        raise ModelProfileNotFoundError(f"model profile not found: {model_profile}")

    updated_defaults = dict(defaults)
    updated_defaults["model_profile"] = model_profile
    _write_loaded_config(
        resolved_path,
        config,
        enabled_providers=enabled_providers,
        provider_tables=provider_tables,
        model_tables=model_tables,
        defaults_table=updated_defaults,
    )

    return {
        "config_path": str(resolved_path),
        "defaults": _defaults_result(updated_defaults),
    }


def list_config_defaults(config_path: Path) -> DefaultsListResult:
    resolved_path = config_path.expanduser()
    config = _load_existing_config(resolved_path)
    defaults = _defaults_table(config)
    return {
        "config_path": str(resolved_path),
        "defaults": _defaults_result(defaults),
    }


def remove_config_default(config_path: Path, default_name: str) -> DefaultRemoveResult:
    resolved_path = config_path.expanduser()
    default_name = _default_name(default_name)
    config = _load_existing_config(resolved_path)
    enabled_providers = _enabled_providers(config)
    provider_tables = _provider_tables(config)
    model_tables = _model_tables(config)
    defaults = _defaults_table(config)

    removed = default_name in defaults
    updated_defaults = {
        name: value
        for name, value in defaults.items()
        if name != default_name
    }
    _write_loaded_config(
        resolved_path,
        config,
        enabled_providers=enabled_providers,
        provider_tables=provider_tables,
        model_tables=model_tables,
        defaults_table=updated_defaults,
    )

    return {
        "config_path": str(resolved_path),
        "removed_default": default_name,
        "removed": removed,
        "defaults": _defaults_result(updated_defaults),
    }


def resolve_model_profile(config_path: Path, name: str) -> ModelProfile:
    resolved_path = config_path.expanduser()
    name = _model_profile_name(name)
    config = _load_existing_config(resolved_path)
    model_tables = _model_tables(config)
    if name not in model_tables:
        raise ModelProfileNotFoundError(f"model profile not found: {name}")
    return {
        "name": name,
        "model": _profile_model(name, model_tables),
    }


def list_config_auth(config_path: Path) -> AuthListResult:
    resolved_path = config_path.expanduser()
    config = _load_existing_config(resolved_path)
    provider_tables = _provider_tables(config)
    providers = [
        {
            "provider": provider,
            "auth_kind": _auth_kind(provider, provider_tables),
            "env_vars": _env_vars(provider, provider_tables),
            "auth_methods": _auth_methods(provider, provider_tables),
        }
        for provider in _enabled_providers(config)
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
        enabled_providers = _enabled_providers(config)
        provider_tables = _provider_tables(config)
    else:
        config = {"schema_version": 1, "secrets": "environment"}
        enabled_providers = []
        provider_tables = {}

    added = provider not in enabled_providers or provider not in provider_tables
    updated_enabled = list(enabled_providers)
    if provider not in updated_enabled:
        updated_enabled.append(provider)

    updated_provider_tables = dict(provider_tables)
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

    _write_loaded_config(
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

    config = _load_existing_config(resolved_path)
    enabled_providers = _enabled_providers(config)
    provider_tables = _provider_tables(config)

    removed = provider in enabled_providers or provider in provider_tables
    updated_enabled = [name for name in enabled_providers if name != provider]
    updated_provider_tables = {
        name: table for name, table in provider_tables.items() if name != provider
    }
    _write_loaded_config(
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
        enabled_providers = set(_enabled_providers(config))
        provider_tables = _provider_tables(config)
    else:
        enabled_providers = set()
        provider_tables = {}

    configured_provider_names = set(provider_tables)
    detected_statuses = detect_provider_statuses(env)
    provider_names = _doctor_provider_names(
        detected_statuses,
        configured_provider_names | enabled_providers,
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
                enabled_providers=enabled_providers,
                provider_tables=provider_tables,
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
        return options[0]

    auth_kind = auth_kind.strip()
    if not auth_kind:
        raise ValueError("auth kind is required")

    for option in options:
        if option["auth_kind"] == auth_kind:
            return option
    supported = ", ".join(option["auth_kind"] for option in options)
    raise ValueError(
        f"unsupported auth kind for {provider}: {auth_kind} (supported: {supported})"
    )

def _model_profile_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("model profile name is required")
    return name


def _model_string(model: str) -> str:
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


def _load_existing_config(config_path: Path) -> dict[str, object]:
    if not config_path.exists():
        raise ConfigNotFoundError(f"config not found: {config_path}")
    return load_config(config_path)


def _write_loaded_config(
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
        _render_loaded_config(
            config,
            enabled_providers=enabled_providers,
            provider_tables=provider_tables,
            model_tables=model_tables,
            defaults_table=defaults_table,
        ),
    )


def _enabled_providers(config: Mapping[str, object]) -> list[str]:
    enabled = config.get("enabled_providers", [])
    if not isinstance(enabled, list) or not all(
        isinstance(provider, str) for provider in enabled
    ):
        raise ConfigFormatError("config enabled_providers must be a list of strings")
    return enabled


def _provider_tables(config: Mapping[str, object]) -> dict[str, dict[str, object]]:
    providers = config.get("providers", {})
    if not isinstance(providers, dict):
        raise ConfigFormatError("config providers must be a table")

    tables: dict[str, dict[str, object]] = {}
    for provider, table in providers.items():
        if not isinstance(provider, str) or not isinstance(table, dict):
            raise ConfigFormatError("config providers entries must be tables")
        tables[provider] = table
    return tables


def _model_tables(config: Mapping[str, object]) -> dict[str, dict[str, object]]:
    models = config.get("models", {})
    if not isinstance(models, dict):
        raise ConfigFormatError("config models must be a table")

    tables: dict[str, dict[str, object]] = {}
    for name, table in models.items():
        if not isinstance(name, str) or not isinstance(table, dict):
            raise ConfigFormatError("config models entries must be tables")
        tables[name] = table
    return tables


def _defaults_table(config: Mapping[str, object]) -> dict[str, str]:
    defaults = config.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ConfigFormatError("config defaults must be a table")

    table: dict[str, str] = {}
    if "model_profile" in defaults:
        value = defaults["model_profile"]
        if not isinstance(value, str):
            raise ConfigFormatError("config defaults model_profile must be a string")
        table["model_profile"] = _model_profile_name(value)
    return table


def _defaults_result(defaults: Mapping[str, str]) -> DefaultsConfig:
    return {
        "model_profile": defaults.get("model_profile"),
    }


def _default_name(name: str) -> str:
    name = name.strip().replace("-", "_")
    if name == "model_profile":
        return name
    raise ValueError(f"unknown default: {name or '-'} (supported: model-profile)")


def _auth_kind(provider: str, provider_tables: Mapping[str, Mapping[str, object]]) -> str:
    value = provider_tables.get(provider, {}).get("auth_kind", "")
    if value == "":
        methods = _auth_methods(provider, provider_tables)
        return methods[0]["auth_kind"] if methods else ""
    if not isinstance(value, str):
        raise ConfigFormatError(f"provider {provider} auth_kind must be a string")
    return value


def _env_vars(provider: str, provider_tables: Mapping[str, Mapping[str, object]]) -> list[str]:
    value = provider_tables.get(provider, {}).get("env_vars", [])
    if value == []:
        methods = _auth_methods(provider, provider_tables)
        return methods[0]["env_vars"] if methods else []
    if not isinstance(value, list) or not all(
        isinstance(env_var, str) for env_var in value
    ):
        raise ConfigFormatError(f"provider {provider} env_vars must be a list of strings")
    return value


def _auth_methods(
    provider: str,
    provider_tables: Mapping[str, Mapping[str, object]],
) -> list[AuthMethodConfig]:
    table = provider_tables.get(provider, {})
    value = table.get("auth_methods")
    if value is None:
        auth_kind = table.get("auth_kind", "")
        env_vars = table.get("env_vars", [])
        if not auth_kind and not env_vars:
            return []
        if not isinstance(auth_kind, str):
            raise ConfigFormatError(f"provider {provider} auth_kind must be a string")
        if not isinstance(env_vars, list) or not all(
            isinstance(env_var, str) for env_var in env_vars
        ):
            raise ConfigFormatError(
                f"provider {provider} env_vars must be a list of strings"
            )
        return [{"auth_kind": auth_kind, "env_vars": env_vars}]

    if not isinstance(value, list):
        raise ConfigFormatError(f"provider {provider} auth_methods must be a list")

    methods: list[AuthMethodConfig] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ConfigFormatError(
                f"provider {provider} auth_methods entry {index} must be a table"
            )
        auth_kind = item.get("auth_kind", "")
        env_vars = item.get("env_vars", [])
        if not isinstance(auth_kind, str) or not auth_kind:
            raise ConfigFormatError(
                f"provider {provider} auth_methods entry {index} auth_kind must be a string"
            )
        if not isinstance(env_vars, list) or not all(
            isinstance(env_var, str) for env_var in env_vars
        ):
            raise ConfigFormatError(
                f"provider {provider} auth_methods entry {index} env_vars must be a list of strings"
            )
        methods.append({"auth_kind": auth_kind, "env_vars": env_vars})
    return methods


def _profile_model(name: str, model_tables: Mapping[str, Mapping[str, object]]) -> str:
    value = model_tables.get(name, {}).get("model", "")
    if not isinstance(value, str):
        raise ConfigFormatError(f"model profile {name} model must be a string")
    return _model_string(value)


def _render_loaded_config(
    config: Mapping[str, object],
    *,
    enabled_providers: list[str],
    provider_tables: Mapping[str, Mapping[str, object]],
    model_tables: Mapping[str, Mapping[str, object]] | None = None,
    defaults_table: Mapping[str, str] | None = None,
) -> str:
    if model_tables is None:
        model_tables = _model_tables(config)
    if defaults_table is None:
        defaults_table = _defaults_table(config)

    lines = [
        f"schema_version = {_schema_version(config)}",
        f"secrets = {_toml_string(_secrets(config))}",
        "",
        "enabled_providers = [",
    ]
    for provider in enabled_providers:
        lines.append(f"  {_toml_string(provider)},")
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
                f"auth_kind = {_toml_string(_auth_kind(provider, provider_tables))}",
                "env_vars = [",
            ]
        )
        for env_var in _env_vars(provider, provider_tables):
            lines.append(f"  {_toml_string(env_var)},")
        lines.extend([
            "]",
            "",
        ])
        for method in _auth_methods(provider, provider_tables):
            lines.extend(
                [
                    f"[[providers.{provider}.auth_methods]]",
                    f"auth_kind = {_toml_string(method['auth_kind'])}",
                    "env_vars = [",
                ]
            )
            for env_var in method["env_vars"]:
                lines.append(f"  {_toml_string(env_var)},")
            lines.extend([
                "]",
                "",
            ])

    for name in model_tables:
        lines.extend(
            [
                f"[models.{_toml_string(name)}]",
                f"model = {_toml_string(_profile_model(name, model_tables))}",
                "",
            ]
        )

    if defaults_table:
        lines.extend([
            "[defaults]",
        ])
        if model_profile := defaults_table.get("model_profile"):
            lines.append(f"model_profile = {_toml_string(model_profile)}")
        lines.append("")

    return "\n".join(lines)


def _schema_version(config: Mapping[str, object]) -> int:
    value = config.get("schema_version", 1)
    if not isinstance(value, int):
        raise ConfigFormatError("config schema_version must be an integer")
    return value


def _secrets(config: Mapping[str, object]) -> str:
    value = config.get("secrets", "environment")
    if not isinstance(value, str):
        raise ConfigFormatError("config secrets must be a string")
    return value


def _toml_string(value: str) -> str:
    return toml_string(value)


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
    configured_env_vars = _env_vars(provider, provider_tables)
    configured_auth_kind = _auth_kind(provider, provider_tables)
    configured_auth_methods = _auth_methods(provider, provider_tables)

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
