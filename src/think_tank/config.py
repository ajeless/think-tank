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

    config_path = config_path.expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_render_config(statuses, selected), encoding="utf-8")

    return {
        "config_path": str(config_path),
        "enabled_providers": list(selected),
    }


def load_config(config_path: Path) -> dict[str, object]:
    return tomllib.loads(config_path.expanduser().read_text(encoding="utf-8"))


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
