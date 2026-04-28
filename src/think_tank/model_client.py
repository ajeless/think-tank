"""Model client boundary for Think Tank engine calls."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any, Mapping, Protocol, TypedDict


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_OLLAMA_API_URL = "http://localhost:11434"


class ModelMessage(TypedDict):
    role: str
    content: str


@dataclass(frozen=True)
class ModelResponse:
    content: str


class ProviderModelInfo(TypedDict):
    provider_model: str
    display_name: str
    supported_actions: list[str]


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


class ProviderModelRegistry(Protocol):
    """Minimal provider model-listing interface the engine can fake in tests."""

    def list_models(self) -> list[ProviderModelInfo]:
        """Return provider-visible model metadata."""


class ProviderModelRegistryError(RuntimeError):
    """Raised when a provider model registry cannot be queried."""


class GeminiModelRegistry:
    """Google GenAI-backed Gemini model registry probe."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "GeminiModelRegistry":
        return cls(client=_new_gemini_client(env))

    def list_models(self) -> list[ProviderModelInfo]:
        client = self._client or _new_gemini_client()
        try:
            models = client.models.list()
        except Exception as exc:
            raise ProviderModelRegistryError(str(exc)) from exc

        discovered: list[ProviderModelInfo] = []
        for model in models:
            provider_model = _gemini_provider_model_name(getattr(model, "name", ""))
            if not provider_model:
                continue
            discovered.append(
                {
                    "provider_model": provider_model,
                    "display_name": _model_display_name(model),
                    "supported_actions": _string_list(
                        getattr(model, "supported_actions", None)
                    ),
                }
            )
        return discovered


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

    def __init__(
        self,
        client: Any | None = None,
        gemini_client: Any | None = None,
    ) -> None:
        self._client = client
        self._gemini_client = gemini_client

    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        if model.startswith("gemini:"):
            try:
                return _complete_gemini(
                    client=self._gemini_client or _new_gemini_client(),
                    model=model,
                    messages=messages,
                )
            except ModelClientConfigurationError:
                raise
            except Exception as exc:
                raise _provider_call_error("gemini", exc) from exc

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

        if model.startswith("groq:"):
            groq_model = model.split(":", 1)[1]
            client = self._client or _new_groq_client()
            return client, f"openai:{groq_model}"

        return self._client or _new_aisuite_client(), model


def _new_aisuite_client(provider_configs: dict[str, dict[str, Any]] | None = None) -> Any:
    _patch_python_314_ast_compatibility()

    import aisuite as ai

    return ai.Client(provider_configs=provider_configs or {})


def _new_openrouter_client() -> Any:
    return _new_openai_compatible_client(
        provider="OpenRouter",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url=OPENROUTER_BASE_URL,
    )


def _new_groq_client() -> Any:
    return _new_openai_compatible_client(
        provider="Groq",
        api_key_env_var="GROQ_API_KEY",
        base_url=GROQ_BASE_URL,
    )


def _new_gemini_client(env: Mapping[str, str] | None = None) -> Any:
    env = os.environ if env is None else env
    api_key = _gemini_api_key(env)
    if not api_key:
        raise ModelClientConfigurationError(
            "Gemini requires GOOGLE_API_KEY or GEMINI_API_KEY in the environment."
        )
    try:
        from google import genai
    except ImportError as exc:
        raise ModelClientConfigurationError(
            "Gemini requires the google-genai package."
        ) from exc
    return genai.Client(api_key=api_key)


def _gemini_provider_model_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    return name.removeprefix("models/").strip()


def _model_display_name(model: Any) -> str:
    display_name = getattr(model, "display_name", None)
    return display_name if isinstance(display_name, str) else ""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _complete_gemini(
    *,
    client: Any,
    model: str,
    messages: list[ModelMessage],
) -> ModelResponse:
    provider_model = model.split(":", 1)[1].strip()
    if not provider_model:
        raise ModelClientConfigurationError(
            "Gemini requires a model name after gemini:."
        )
    try:
        from google.genai import types
    except ImportError as exc:
        raise ModelClientConfigurationError(
            "Gemini requires the google-genai package."
        ) from exc

    response = client.models.generate_content(
        model=provider_model,
        contents=_gemini_contents(messages, types=types),
        config=_gemini_config(messages, types=types),
    )
    return ModelResponse(content=_gemini_response_text(response))


def _gemini_api_key(env: Mapping[str, str]) -> str | None:
    return env.get("GOOGLE_API_KEY") or env.get("GEMINI_API_KEY")


def _gemini_contents(messages: list[ModelMessage], *, types: Any) -> list[Any]:
    contents: list[Any] = []
    for message in messages:
        role = message["role"]
        if role == "system":
            continue
        contents.append(
            types.Content(
                role="model" if role == "assistant" else "user",
                parts=[types.Part.from_text(text=message["content"])],
            )
        )
    return contents


def _gemini_config(messages: list[ModelMessage], *, types: Any) -> Any | None:
    system_text = "\n\n".join(
        message["content"] for message in messages if message["role"] == "system"
    )
    if not system_text:
        return None
    return types.GenerateContentConfig(systemInstruction=system_text)


def _gemini_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text:
        raise RuntimeError("Gemini API returned no text content.")
    return text


def _new_openai_compatible_client(
    *,
    provider: str,
    api_key_env_var: str,
    base_url: str,
) -> Any:
    api_key = os.getenv(api_key_env_var)
    if not api_key:
        raise ModelClientConfigurationError(
            f"{provider} requires {api_key_env_var} in the environment."
        )

    return _new_aisuite_client(
        provider_configs={
            "openai": {
                "api_key": api_key,
                "base_url": base_url,
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
