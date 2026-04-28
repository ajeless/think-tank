"""Model client boundary for Think Tank engine calls."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Protocol, TypedDict


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ModelMessage(TypedDict):
    role: str
    content: str


@dataclass(frozen=True)
class ModelResponse:
    content: str


class ModelClient(Protocol):
    """Minimal model-call interface the engine can fake in tests."""

    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        """Return one model completion for the supplied messages."""


class ModelClientConfigurationError(RuntimeError):
    """Raised when a selected model provider is not configured for real calls."""


class ModelClientCallError(RuntimeError):
    """Raised when a selected model provider rejects or fails a real call."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"Model call failed for {provider}: {message}")


class AisuiteModelClient:
    """aisuite-backed implementation of the model client boundary."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        client, provider_model = self._client_and_model(model)
        try:
            response = client.chat.completions.create(
                model=provider_model,
                messages=messages,
            )
        except ImportError as exc:
            provider = model.split(":", 1)[0]
            raise ModelClientConfigurationError(
                f"Model provider dependency missing for {provider}."
            ) from exc
        except Exception as exc:
            provider = model.split(":", 1)[0]
            raise ModelClientCallError(provider, str(exc)) from exc
        return ModelResponse(content=response.choices[0].message.content)

    def _client_and_model(self, model: str) -> tuple[Any, str]:
        if model.startswith("openrouter:"):
            openrouter_model = model.split(":", 1)[1]
            client = self._client or _new_openrouter_client()
            return client, f"openai:{openrouter_model}"

        return self._client or _new_aisuite_client(), model


def _new_aisuite_client(provider_configs: dict[str, dict[str, Any]] | None = None) -> Any:
    _patch_python_314_ast_compatibility()

    import aisuite as ai

    return ai.Client(provider_configs=provider_configs or {})


def _new_openrouter_client() -> Any:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ModelClientConfigurationError(
            "OpenRouter requires OPENROUTER_API_KEY in the environment."
        )

    return _new_aisuite_client(
        provider_configs={
            "openai": {
                "api_key": api_key,
                "base_url": OPENROUTER_BASE_URL,
            }
        }
    )


def _patch_python_314_ast_compatibility() -> None:
    """Keep aisuite's docstring-parser dependency importable on Python 3.14."""

    import ast

    for removed_name in ("NameConstant", "Num", "Str"):
        if not hasattr(ast, removed_name):
            setattr(ast, removed_name, ast.Constant)
