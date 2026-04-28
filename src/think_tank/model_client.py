"""Model client boundary for Think Tank engine calls."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any, Mapping, Protocol, TypedDict


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OLLAMA_API_URL = "http://localhost:11434"


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


class ModelClientAuthenticationError(ModelClientCallError):
    """Raised when provider credentials are present but rejected."""


class ModelClientQuotaOrRateLimitError(ModelClientCallError):
    """Raised when a provider rejects a call due to quota or rate limits."""


class OllamaModelRegistry(Protocol):
    """Minimal Ollama model-registry interface the engine can fake in tests."""

    def list_models(self) -> list[str]:
        """Return locally available Ollama model names."""


class OllamaRegistryError(RuntimeError):
    """Raised when the local Ollama registry cannot be queried."""


class OllamaHttpModelRegistry:
    """HTTP-backed Ollama registry probe."""

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_API_URL,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "OllamaHttpModelRegistry":
        env = os.environ if env is None else env
        return cls(base_url=env.get("OLLAMA_API_URL", DEFAULT_OLLAMA_API_URL))

    def list_models(self) -> list[str]:
        request = Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise OllamaRegistryError(
                f"Ollama server is not reachable at {self.base_url}."
            ) from exc
        except json.JSONDecodeError as exc:
            raise OllamaRegistryError(
                f"Ollama server at {self.base_url} returned invalid JSON."
            ) from exc

        models = payload.get("models")
        if not isinstance(models, list):
            raise OllamaRegistryError(
                f"Ollama server at {self.base_url} returned an unexpected model list."
            )

        names: list[str] = []
        for model in models:
            if isinstance(model, dict) and isinstance(model.get("name"), str):
                names.append(model["name"])
        return names


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
            raise _provider_call_error(provider, exc) from exc
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


def _provider_call_error(provider: str, exc: Exception) -> ModelClientCallError:
    message = str(exc)
    error_text = f"{type(exc).__name__} {message}".lower()
    if any(
        marker in error_text
        for marker in (
            "authentication",
            "unauthorized",
            "invalid api key",
            "invalid_api_key",
            "permission denied",
            "permission_denied",
            "401",
            "403",
        )
    ):
        return ModelClientAuthenticationError(provider, message)
    if any(
        marker in error_text
        for marker in (
            "rate limit",
            "ratelimit",
            "quota",
            "insufficient_quota",
            "billing",
            "too many requests",
            "429",
        )
    ):
        return ModelClientQuotaOrRateLimitError(provider, message)
    return ModelClientCallError(provider, message)


def _patch_python_314_ast_compatibility() -> None:
    """Keep aisuite's docstring-parser dependency importable on Python 3.14."""

    import ast

    for removed_name in ("NameConstant", "Num", "Str"):
        if not hasattr(ast, removed_name):
            setattr(ast, removed_name, ast.Constant)
