"""Provider onboarding and non-secret Think Tank configuration."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, TypedDict


CONFIG_DIR_NAME = "think-tank"
CONFIG_FILE_NAME = "config.toml"


class ProviderStatus(TypedDict):
    provider: str
    display_name: str
    ready: bool
    auth_kind: str
    detected_env_vars: list[str]
    required_env_vars: list[str]
    missing_env_vars: list[str]
    notes: list[str]


class ConfigInitResult(TypedDict):
    config_path: str
    enabled_providers: list[str]


class AuthProviderConfig(TypedDict):
    provider: str
    auth_kind: str
    env_vars: list[str]


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


class ConfigNotFoundError(FileNotFoundError):
    """Raised when a requested Think Tank config file does not exist."""


class ConfigFormatError(ValueError):
    """Raised when a Think Tank config file has an unsupported shape."""


class ProviderAuthNotReadyError(ValueError):
    """Raised when a provider auth path is known but not ready to record."""


class ModelProfileNotFoundError(LookupError):
    """Raised when a requested model profile is not configured."""


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    display_name: str
    auth_kind: str
    env_vars: tuple[str, ...] = ()
    required_env_vars: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        name="openai",
        display_name="OpenAI",
        auth_kind="api_key_env",
        env_vars=("OPENAI_API_KEY",),
        required_env_vars=("OPENAI_API_KEY",),
        notes=("Subscription login is not implemented; use an environment API key.",),
    ),
    ProviderSpec(
        name="anthropic",
        display_name="Anthropic",
        auth_kind="api_key_env",
        env_vars=("ANTHROPIC_API_KEY",),
        required_env_vars=("ANTHROPIC_API_KEY",),
        notes=("Subscription login is not implemented; use an environment API key.",),
    ),
    ProviderSpec(
        name="google",
        display_name="Google Vertex AI",
        auth_kind="vertex_env",
        env_vars=(
            "GOOGLE_PROJECT_ID",
            "GOOGLE_REGION",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
        ),
        required_env_vars=(
            "GOOGLE_PROJECT_ID",
            "GOOGLE_REGION",
            "GOOGLE_APPLICATION_CREDENTIALS",
        ),
        notes=(
            "The current aisuite Google provider uses Vertex AI credentials.",
            "GEMINI_API_KEY and GOOGLE_API_KEY are detected but not used by this provider path yet.",
        ),
    ),
    ProviderSpec(
        name="ollama",
        display_name="Ollama",
        auth_kind="local_server",
        env_vars=("OLLAMA_API_URL",),
        required_env_vars=(),
        notes=("No API key is required. OLLAMA_API_URL is optional.",),
    ),
    ProviderSpec(
        name="openrouter",
        display_name="OpenRouter",
        auth_kind="api_key_env",
        env_vars=("OPENROUTER_API_KEY",),
        required_env_vars=("OPENROUTER_API_KEY",),
        notes=("OpenRouter is routed through its OpenAI-compatible API.",),
    ),
    ProviderSpec(
        name="groq",
        display_name="Groq",
        auth_kind="api_key_env",
        env_vars=("GROQ_API_KEY",),
        required_env_vars=("GROQ_API_KEY",),
        notes=("Groq is routed through its OpenAI-compatible API.",),
    ),
)


def default_config_path(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    if xdg_config_home := env.get("XDG_CONFIG_HOME"):
        return Path(xdg_config_home) / CONFIG_DIR_NAME / CONFIG_FILE_NAME
    return Path.home() / ".config" / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def detect_provider_statuses(env: Mapping[str, str]) -> list[ProviderStatus]:
    return [_provider_status(spec, env) for spec in PROVIDER_SPECS]


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
    unknown = sorted(set(selected) - {spec.name for spec in PROVIDER_SPECS})
    if unknown:
        raise ValueError(f"unknown provider(s): {', '.join(unknown)}")

    status_by_name = {status["provider"]: status for status in statuses}
    provider_tables = {
        provider: {
            "auth_kind": status_by_name[provider]["auth_kind"],
            "env_vars": status_by_name[provider]["detected_env_vars"],
        }
        for provider in selected
    }

    config_path = config_path.expanduser()
    if config_path.exists():
        config = load_config(config_path)
    else:
        config = {"schema_version": 1, "secrets": "environment"}

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        _render_loaded_config(
            config,
            enabled_providers=list(selected),
            provider_tables=provider_tables,
        ),
        encoding="utf-8",
    )

    return {
        "config_path": str(config_path),
        "enabled_providers": list(selected),
    }


def load_config(config_path: Path) -> dict[str, object]:
    return tomllib.loads(config_path.expanduser().read_text(encoding="utf-8"))


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

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        _render_loaded_config(
            config,
            enabled_providers=enabled_providers,
            provider_tables=provider_tables,
            model_tables=updated_model_tables,
        ),
        encoding="utf-8",
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

    removed = name in model_tables
    updated_model_tables = {
        profile_name: table
        for profile_name, table in model_tables.items()
        if profile_name != name
    }
    resolved_path.write_text(
        _render_loaded_config(
            config,
            enabled_providers=enabled_providers,
            provider_tables=provider_tables,
            model_tables=updated_model_tables,
        ),
        encoding="utf-8",
    )

    return {
        "config_path": str(resolved_path),
        "removed_profile": name,
        "removed": removed,
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
) -> AuthAddResult:
    resolved_path = config_path.expanduser()
    provider = provider.strip().lower()
    if not provider:
        raise ValueError("auth add requires a provider name")

    spec = _provider_spec(provider)
    status = _provider_status(spec, env)
    if status["missing_env_vars"]:
        raise ProviderAuthNotReadyError(
            "missing required environment variable(s): "
            + ", ".join(status["missing_env_vars"])
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
        "auth_kind": status["auth_kind"],
        "env_vars": status["detected_env_vars"],
    }

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        _render_loaded_config(
            config,
            enabled_providers=updated_enabled,
            provider_tables=updated_provider_tables,
        ),
        encoding="utf-8",
    )

    return {
        "config_path": str(resolved_path),
        "provider": provider,
        "added": added,
        "auth_kind": status["auth_kind"],
        "env_vars": status["detected_env_vars"],
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
    resolved_path.write_text(
        _render_loaded_config(
            config,
            enabled_providers=updated_enabled,
            provider_tables=updated_provider_tables,
        ),
        encoding="utf-8",
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


def _provider_status(spec: ProviderSpec, env: Mapping[str, str]) -> ProviderStatus:
    detected = [name for name in spec.env_vars if env.get(name)]
    missing = [name for name in spec.required_env_vars if not env.get(name)]
    return {
        "provider": spec.name,
        "display_name": spec.display_name,
        "ready": not missing,
        "auth_kind": spec.auth_kind,
        "detected_env_vars": detected,
        "required_env_vars": list(spec.required_env_vars),
        "missing_env_vars": missing,
        "notes": list(spec.notes),
    }


def _provider_spec(provider: str) -> ProviderSpec:
    for spec in PROVIDER_SPECS:
        if spec.name == provider:
            return spec
    raise ValueError(f"unknown provider: {provider}")


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
    if provider not in {spec.name for spec in PROVIDER_SPECS}:
        raise ValueError(f"unsupported model provider: {provider}")
    return f"{provider}:{provider_model}"


def _render_config(statuses: list[ProviderStatus], enabled_providers: list[str]) -> str:
    lines = [
        "schema_version = 1",
        "secrets = \"environment\"",
        "",
        "enabled_providers = ["
    ]
    for provider in enabled_providers:
        lines.append(f"  \"{provider}\",")
    lines.extend([
        "]",
        "",
    ])

    status_by_name = {status["provider"]: status for status in statuses}
    for provider in enabled_providers:
        status = status_by_name[provider]
        lines.extend(
            [
                f"[providers.{provider}]",
                f"auth_kind = \"{status['auth_kind']}\"",
                "env_vars = [",
            ]
        )
        for env_var in status["detected_env_vars"]:
            lines.append(f"  \"{env_var}\",")
        lines.extend([
            "]",
            "",
        ])

    return "\n".join(lines)


def _load_existing_config(config_path: Path) -> dict[str, object]:
    if not config_path.exists():
        raise ConfigNotFoundError(f"config not found: {config_path}")
    return load_config(config_path)


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


def _auth_kind(provider: str, provider_tables: Mapping[str, Mapping[str, object]]) -> str:
    value = provider_tables.get(provider, {}).get("auth_kind", "")
    if not isinstance(value, str):
        raise ConfigFormatError(f"provider {provider} auth_kind must be a string")
    return value


def _env_vars(provider: str, provider_tables: Mapping[str, Mapping[str, object]]) -> list[str]:
    value = provider_tables.get(provider, {}).get("env_vars", [])
    if not isinstance(value, list) or not all(
        isinstance(env_var, str) for env_var in value
    ):
        raise ConfigFormatError(f"provider {provider} env_vars must be a list of strings")
    return value


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
) -> str:
    if model_tables is None:
        model_tables = _model_tables(config)

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

    for name in model_tables:
        lines.extend(
            [
                f"[models.{_toml_string(name)}]",
                f"model = {_toml_string(_profile_model(name, model_tables))}",
                "",
            ]
        )

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
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


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

    if status is None:
        return {
            "provider": provider,
            "display_name": provider,
            "configured": configured,
            "detected": False,
            "ready": False,
            "configured_auth_kind": configured_auth_kind,
            "detected_auth_kind": "",
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
        "configured_env_vars": configured_env_vars,
        "detected_env_vars": status["detected_env_vars"],
        "missing_env_vars": status["missing_env_vars"],
        "notes": status["notes"],
    }
