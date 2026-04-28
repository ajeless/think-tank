"""Engine-facing functions for Think Tank.

The engine returns data and leaves display, prompting, and process concerns to adapters.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, TypedDict

from .config import PROVIDER_SPECS, detect_provider_statuses
from .model_client import (
    ModelClient,
    ModelClientAuthenticationError,
    ModelClientCallError,
    ModelClientConfigurationError,
    ModelClientQuotaOrRateLimitError,
    ModelMessage,
    OllamaModelRegistry,
    OllamaRegistryError,
)


VALIDATION_PROMPT = "Reply with OK."
ValidationStatus = Literal[
    "success",
    "missing_credentials",
    "auth_failure",
    "quota_or_rate_limit",
    "provider_config_error",
    "provider_failure",
]


class EngineStatus(TypedDict):
    product: str
    ready: bool


class AskResult(TypedDict):
    project_root: str
    state_path: str
    transcript_path: str
    model: str
    prompt: str
    response: str
    recorded_at: str


class ProviderValidationResult(TypedDict):
    provider: str
    model: str
    ok: bool
    status: ValidationStatus
    message: str


class MissingModelError(ValueError):
    """Raised when a work command reaches the engine without a model."""


class MissingPromptError(ValueError):
    """Raised when a work command reaches the engine without a prompt."""


class ProjectStateNotFoundError(FileNotFoundError):
    """Raised when a project directory does not contain state.json."""


class ProviderValidationInputError(ValueError):
    """Raised when provider validation is called with invalid explicit input."""


def get_engine_status() -> EngineStatus:
    """Return a minimal structured status for the bootstrap skeleton."""

    return {
        "product": "Think Tank",
        "ready": True,
    }


def validate_provider(
    *,
    provider: str,
    model: str | None,
    client: ModelClient,
    env: Mapping[str, str],
    ollama_registry: OllamaModelRegistry | None = None,
) -> ProviderValidationResult:
    """Validate explicit provider/model configuration without mutating project state."""

    provider = provider.strip().lower()
    if not provider:
        raise ProviderValidationInputError(
            "config validate requires --provider <name>"
        )
    if provider not in {spec.name for spec in PROVIDER_SPECS}:
        raise ProviderValidationInputError(f"unsupported provider: {provider}")
    if model is None or not model.strip():
        raise MissingModelError("config validate requires --model <provider:model>")

    model = model.strip()
    model_provider, provider_model = _split_provider_model(model)
    if model_provider != provider:
        raise ProviderValidationInputError(
            f"--model provider '{model_provider}' must match --provider '{provider}'"
        )
    if not provider_model.strip():
        raise MissingModelError("config validate requires --model <provider:model>")

    if provider == "ollama":
        if ollama_registry is None:
            raise ProviderValidationInputError("ollama validation requires a registry")
        return _validate_ollama_provider(
            provider=provider,
            model=model,
            provider_model=provider_model,
            ollama_registry=ollama_registry,
        )

    provider_status = _provider_status(provider, env)
    if provider_status["missing_env_vars"]:
        missing = ", ".join(provider_status["missing_env_vars"])
        return _validation_result(
            provider=provider,
            model=model,
            status="missing_credentials",
            message=f"Missing required environment variable(s): {missing}.",
        )

    try:
        response = client.complete(
            model=model,
            messages=[{"role": "user", "content": VALIDATION_PROMPT}],
        )
    except ModelClientAuthenticationError as exc:
        return _validation_result(
            provider=provider,
            model=model,
            status="auth_failure",
            message=_safe_exception_message(exc, env),
        )
    except ModelClientQuotaOrRateLimitError as exc:
        return _validation_result(
            provider=provider,
            model=model,
            status="quota_or_rate_limit",
            message=_safe_exception_message(exc, env),
        )
    except ModelClientConfigurationError as exc:
        return _validation_result(
            provider=provider,
            model=model,
            status="provider_config_error",
            message=_safe_exception_message(exc, env),
        )
    except ModelClientCallError as exc:
        return _validation_result(
            provider=provider,
            model=model,
            status="provider_failure",
            message=_safe_exception_message(exc, env),
        )

    if not response.content.strip():
        return _validation_result(
            provider=provider,
            model=model,
            status="provider_failure",
            message="Provider returned an empty validation response.",
        )

    return _validation_result(
        provider=provider,
        model=model,
        status="success",
        message="Provider validation succeeded.",
    )


def ask_project(
    project_root: Path,
    *,
    prompt: str,
    model: str | None,
    client: ModelClient,
    now: datetime | None = None,
) -> AskResult:
    """Run one model interaction against a project and append its transcript row."""

    if not prompt.strip():
        raise MissingPromptError("ask requires a non-empty prompt argument")
    if model is None or not model.strip():
        raise MissingModelError("ask requires --model <provider:model>")

    resolved_root = project_root.expanduser()
    state_path = resolved_root / "state.json"
    if not state_path.exists():
        raise ProjectStateNotFoundError(f"project state not found: {state_path}")

    state = json.loads(state_path.read_text(encoding="utf-8"))
    messages = _ask_messages(state=state, prompt=prompt)
    response = client.complete(model=model, messages=messages)

    recorded_at = _format_timestamp(now or datetime.now(timezone.utc))
    transcript_path = resolved_root / "transcripts" / "ask.jsonl"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_row = {
        "schema_version": 1,
        "type": "ask",
        "recorded_at": recorded_at,
        "model": model,
        "prompt": prompt,
        "messages": messages,
        "response": {
            "content": response.content,
        },
    }
    with transcript_path.open("a", encoding="utf-8") as transcript:
        transcript.write(json.dumps(transcript_row, sort_keys=True) + "\n")

    return {
        "project_root": str(resolved_root),
        "state_path": str(state_path),
        "transcript_path": str(transcript_path),
        "model": model,
        "prompt": prompt,
        "response": response.content,
        "recorded_at": recorded_at,
    }


def _ask_messages(*, state: dict[str, Any], prompt: str) -> list[ModelMessage]:
    project_context = json.dumps(state, indent=2, sort_keys=True)
    return [
        {
            "role": "system",
            "content": (
                "You are participating in Think Tank, a local-first idea workspace. "
                "Respond directly to the user's prompt. Do not claim to update project "
                "state or write files; this first ask path records only the transcript."
            ),
        },
        {
            "role": "user",
            "content": (
                "Current project state follows as JSON context.\n\n"
                f"{project_context}\n\n"
                "User prompt:\n"
                f"{prompt}"
            ),
        },
    ]


def _validate_ollama_provider(
    *,
    provider: str,
    model: str,
    provider_model: str,
    ollama_registry: OllamaModelRegistry,
) -> ProviderValidationResult:
    try:
        available_models = ollama_registry.list_models()
    except OllamaRegistryError as exc:
        return _validation_result(
            provider=provider,
            model=model,
            status="provider_config_error",
            message=str(exc),
        )

    if provider_model not in available_models:
        return _validation_result(
            provider=provider,
            model=model,
            status="provider_config_error",
            message=(
                f"Ollama model '{provider_model}' is not available locally. "
                "Run `ollama pull` for that model or choose an installed model."
            ),
        )

    return _validation_result(
        provider=provider,
        model=model,
        status="success",
        message="Ollama server is reachable and the model is available.",
    )


def _split_provider_model(model: str) -> tuple[str, str]:
    if ":" not in model:
        raise MissingModelError("config validate requires --model <provider:model>")
    provider, provider_model = model.split(":", 1)
    return provider.strip().lower(), provider_model


def _provider_status(provider: str, env: Mapping[str, str]) -> dict[str, Any]:
    statuses = detect_provider_statuses(env)
    return next(status for status in statuses if status["provider"] == provider)


def _validation_result(
    *,
    provider: str,
    model: str,
    status: ValidationStatus,
    message: str,
) -> ProviderValidationResult:
    return {
        "provider": provider,
        "model": model,
        "ok": status == "success",
        "status": status,
        "message": message,
    }


def _safe_exception_message(exc: Exception, env: Mapping[str, str]) -> str:
    message = str(exc)
    for spec in PROVIDER_SPECS:
        for env_var in spec.env_vars:
            value = env.get(env_var)
            if value:
                message = message.replace(value, "[redacted]")
    return message


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("engine timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
