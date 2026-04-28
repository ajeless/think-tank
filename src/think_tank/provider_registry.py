"""Packaged provider metadata and environment-based auth detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, TypedDict


class ProviderStatus(TypedDict):
    provider: str
    display_name: str
    ready: bool
    implemented: bool
    official: bool
    selectable: bool
    support_status: str
    auth_kind: str
    detected_env_vars: list[str]
    required_env_vars: list[str]
    missing_env_vars: list[str]
    notes: list[str]


class ProviderAuthMethodOption(TypedDict):
    provider: str
    display_name: str
    auth_kind: str
    ready: bool
    implemented: bool
    official: bool
    selectable: bool
    support_status: str
    detected_env_vars: list[str]
    required_env_vars: list[str]
    missing_env_vars: list[str]
    notes: list[str]


@dataclass(frozen=True)
class ProviderAuthMethodSpec:
    auth_kind: str
    env_vars: tuple[str, ...] = ()
    required_env_vars: tuple[str, ...] = ()
    required_any_env_vars: tuple[str, ...] = ()
    implemented: bool = True
    official: bool = True
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    display_name: str
    auth_methods: tuple[ProviderAuthMethodSpec, ...]

    def __post_init__(self) -> None:
        if not self.auth_methods:
            raise ValueError(f"provider {self.name} must define at least one auth method")


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        name="openai",
        display_name="OpenAI",
        auth_methods=(
            ProviderAuthMethodSpec(
                auth_kind="api_key_env",
                env_vars=("OPENAI_API_KEY",),
                required_env_vars=("OPENAI_API_KEY",),
                notes=(
                    "Use an environment API key for general OpenAI API calls.",
                    "ChatGPT subscription login is out of scope for provider auth.",
                ),
            ),
        ),
    ),
    ProviderSpec(
        name="anthropic",
        display_name="Anthropic",
        auth_methods=(
            ProviderAuthMethodSpec(
                auth_kind="api_key_env",
                env_vars=("ANTHROPIC_API_KEY",),
                required_env_vars=("ANTHROPIC_API_KEY",),
                notes=(
                    "Use an environment API key for direct Anthropic API calls.",
                    "Claude.ai subscription login is out of scope for provider auth.",
                ),
            ),
        ),
    ),
    ProviderSpec(
        name="google",
        display_name="Google Vertex AI",
        auth_methods=(
            ProviderAuthMethodSpec(
                auth_kind="service_account_env",
                env_vars=(
                    "GOOGLE_PROJECT_ID",
                    "GOOGLE_REGION",
                    "GOOGLE_APPLICATION_CREDENTIALS",
                ),
                required_env_vars=(
                    "GOOGLE_PROJECT_ID",
                    "GOOGLE_REGION",
                    "GOOGLE_APPLICATION_CREDENTIALS",
                ),
                notes=(
                    "The current aisuite Google provider uses Vertex AI credentials.",
                ),
            ),
        ),
    ),
    ProviderSpec(
        name="gemini",
        display_name="Gemini API",
        auth_methods=(
            ProviderAuthMethodSpec(
                auth_kind="api_key_env",
                env_vars=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
                required_any_env_vars=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
                notes=(
                    "Use GOOGLE_API_KEY or GEMINI_API_KEY for Gemini Developer API calls.",
                ),
            ),
        ),
    ),
    ProviderSpec(
        name="ollama",
        display_name="Ollama",
        auth_methods=(
            ProviderAuthMethodSpec(
                auth_kind="local_server",
                env_vars=("OLLAMA_API_URL",),
                notes=("No API key is required. OLLAMA_API_URL is optional.",),
            ),
        ),
    ),
    ProviderSpec(
        name="openrouter",
        display_name="OpenRouter",
        auth_methods=(
            ProviderAuthMethodSpec(
                auth_kind="api_key_env",
                env_vars=("OPENROUTER_API_KEY",),
                required_env_vars=("OPENROUTER_API_KEY",),
                notes=("OpenRouter is routed through its OpenAI-compatible API.",),
            ),
        ),
    ),
    ProviderSpec(
        name="groq",
        display_name="Groq",
        auth_methods=(
            ProviderAuthMethodSpec(
                auth_kind="api_key_env",
                env_vars=("GROQ_API_KEY",),
                required_env_vars=("GROQ_API_KEY",),
                notes=("Groq is routed through its OpenAI-compatible API.",),
            ),
        ),
    ),
)


def detect_provider_statuses(env: Mapping[str, str]) -> list[ProviderStatus]:
    return [_provider_status(spec, env) for spec in PROVIDER_SPECS]


def provider_auth_method_options(
    provider: str,
    *,
    env: Mapping[str, str],
) -> list[ProviderAuthMethodOption]:
    provider = provider.strip().lower()
    if not provider:
        raise ValueError("provider name is required")
    spec = provider_spec(provider)
    return [
        _provider_auth_method_option(spec, method, env)
        for method in provider_auth_method_specs(spec)
    ]


def provider_spec(provider: str) -> ProviderSpec:
    for spec in PROVIDER_SPECS:
        if spec.name == provider:
            return spec
    raise ValueError(f"unknown provider: {provider}")


def supported_provider_names() -> set[str]:
    return {spec.name for spec in PROVIDER_SPECS}


def provider_env_var_names(spec: ProviderSpec) -> tuple[str, ...]:
    env_vars: list[str] = []
    for method in spec.auth_methods:
        for name in method.env_vars:
            if name not in env_vars:
                env_vars.append(name)
    return tuple(env_vars)


def provider_auth_method_specs(
    spec: ProviderSpec,
) -> tuple[ProviderAuthMethodSpec, ...]:
    if not spec.auth_methods:
        raise ValueError(f"provider {spec.name} has no auth methods")
    return spec.auth_methods


def _provider_status(spec: ProviderSpec, env: Mapping[str, str]) -> ProviderStatus:
    method = provider_auth_method_specs(spec)[0]
    detected = [name for name in method.env_vars if env.get(name)]
    missing = _missing_required_env_vars(method, env)
    ready = method.implemented and not missing
    return {
        "provider": spec.name,
        "display_name": spec.display_name,
        "ready": ready,
        "implemented": method.implemented,
        "official": method.official,
        "selectable": ready,
        "support_status": _support_status(method),
        "auth_kind": method.auth_kind,
        "detected_env_vars": detected,
        "required_env_vars": _required_env_var_names(method),
        "missing_env_vars": missing,
        "notes": list(method.notes),
    }


def _provider_auth_method_option(
    spec: ProviderSpec,
    method: ProviderAuthMethodSpec,
    env: Mapping[str, str],
) -> ProviderAuthMethodOption:
    detected = [name for name in method.env_vars if env.get(name)]
    missing = _missing_required_env_vars(method, env)
    ready = method.implemented and not missing
    return {
        "provider": spec.name,
        "display_name": spec.display_name,
        "auth_kind": method.auth_kind,
        "ready": ready,
        "implemented": method.implemented,
        "official": method.official,
        "selectable": ready,
        "support_status": _support_status(method),
        "detected_env_vars": detected,
        "required_env_vars": _required_env_var_names(method),
        "missing_env_vars": missing,
        "notes": list(method.notes),
    }


def _missing_required_env_vars(
    method: ProviderAuthMethodSpec,
    env: Mapping[str, str],
) -> list[str]:
    missing = [name for name in method.required_env_vars if not env.get(name)]
    if method.required_any_env_vars and not any(
        env.get(name) for name in method.required_any_env_vars
    ):
        missing.extend(method.required_any_env_vars)
    return missing


def _required_env_var_names(method: ProviderAuthMethodSpec) -> list[str]:
    return [*method.required_env_vars, *method.required_any_env_vars]


def _support_status(method: ProviderAuthMethodSpec) -> str:
    if method.implemented:
        return "implemented"
    if method.official:
        return "planned_official"
    return "unsupported"
