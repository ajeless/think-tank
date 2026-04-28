from types import SimpleNamespace

import pytest

from think_tank.model_client import (
    AisuiteModelClient,
    DEFAULT_OLLAMA_API_URL,
    GROQ_BASE_URL,
    ModelClientCallError,
    ModelClientAuthenticationError,
    ModelClientConfigurationError,
    ModelClientQuotaOrRateLimitError,
    OPENROUTER_BASE_URL,
    OllamaHttpModelRegistry,
    OllamaRegistryError,
    _new_aisuite_client,
    _new_groq_client,
    _new_openai_compatible_client,
    _new_openrouter_client,
)


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, *, model: str, messages: list[dict[str, str]]):
        self.calls.append({"model": model, "messages": messages})
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="fake completion")),
            ],
        )


class FakeAisuiteClient:
    def __init__(self) -> None:
        self.completions = FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


class FakeGeminiModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_content(self, *, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return SimpleNamespace(text="gemini ok")


class FakeGeminiClient:
    def __init__(self) -> None:
        self.models = FakeGeminiModels()


class FailingCompletions:
    def __init__(self, message: str = "quota failed") -> None:
        self.message = message

    def create(self, *, model: str, messages: list[dict[str, str]]):
        raise RuntimeError(self.message)


class FailingAisuiteClient:
    def __init__(self, message: str = "quota failed") -> None:
        self.chat = SimpleNamespace(completions=FailingCompletions(message))


class FakeHttpResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return self.payload


def test_aisuite_client_can_be_constructed_without_model_call() -> None:
    client = _new_aisuite_client()

    assert hasattr(client, "chat")


def test_aisuite_model_client_passes_normal_model_to_aisuite_client() -> None:
    fake_client = FakeAisuiteClient()
    client = AisuiteModelClient(client=fake_client)

    response = client.complete(
        model="openai:gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )

    assert response.content == "fake completion"
    assert fake_client.completions.calls == [
        {
            "model": "openai:gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
        }
    ]


def test_aisuite_model_client_routes_openrouter_to_openai_compatible_provider() -> None:
    fake_client = FakeAisuiteClient()
    client = AisuiteModelClient(client=fake_client)

    response = client.complete(
        model="openrouter:openai/gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )

    assert response.content == "fake completion"
    assert fake_client.completions.calls == [
        {
            "model": "openai:openai/gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
        }
    ]


def test_aisuite_model_client_routes_groq_to_openai_compatible_provider() -> None:
    fake_client = FakeAisuiteClient()
    client = AisuiteModelClient(client=fake_client)

    response = client.complete(
        model="groq:llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "Hello"}],
    )

    assert response.content == "fake completion"
    assert fake_client.completions.calls == [
        {
            "model": "openai:llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": "Hello"}],
        }
    ]


def test_aisuite_model_client_routes_gemini_to_developer_api(
) -> None:
    fake_gemini_client = FakeGeminiClient()
    client = AisuiteModelClient(gemini_client=fake_gemini_client)
    response = client.complete(
        model="gemini:gemini-3.1-pro-preview",
        messages=[
            {"role": "system", "content": "System rules"},
            {"role": "user", "content": "Hello"},
        ],
    )

    assert response.content == "gemini ok"
    assert fake_gemini_client.models.calls[0]["model"] == "gemini-3.1-pro-preview"
    contents = fake_gemini_client.models.calls[0]["contents"]
    assert len(contents) == 1
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "Hello"
    config = fake_gemini_client.models.calls[0]["config"]
    assert config.system_instruction == "System rules"


def test_gemini_client_prefers_google_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str | None] = []

    def fake_genai_client(*, api_key):
        calls.append(api_key)
        return FakeGeminiClient()

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-secret")
    monkeypatch.setattr(
        "google.genai.Client",
        fake_genai_client,
    )

    AisuiteModelClient().complete(
        model="gemini:gemini-3.1-pro-preview",
        messages=[{"role": "user", "content": "Hello"}],
    )

    assert calls == ["google-secret"]


def test_gemini_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ModelClientConfigurationError, match="GOOGLE_API_KEY"):
        AisuiteModelClient().complete(
            model="gemini:gemini-3.1-pro-preview",
            messages=[{"role": "user", "content": "Hello"}],
        )


def test_openrouter_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(ModelClientConfigurationError, match="OPENROUTER_API_KEY"):
        _new_openrouter_client()


def test_groq_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ModelClientConfigurationError, match="GROQ_API_KEY"):
        _new_groq_client()


def test_openai_compatible_client_uses_supplied_api_key_and_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_new_aisuite_client(provider_configs):
        calls.append(provider_configs)
        return FakeAisuiteClient()

    monkeypatch.setenv("TEST_API_KEY", "secret")
    monkeypatch.setattr(
        "think_tank.model_client._new_aisuite_client",
        fake_new_aisuite_client,
    )

    _new_openai_compatible_client(
        provider="TestProvider",
        api_key_env_var="TEST_API_KEY",
        base_url="https://example.test/v1",
    )

    assert calls == [
        {
            "openai": {
                "api_key": "secret",
                "base_url": "https://example.test/v1",
            }
        }
    ]


def test_openrouter_and_groq_clients_use_distinct_base_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_new_aisuite_client(provider_configs):
        calls.append(provider_configs)
        return FakeAisuiteClient()

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-secret")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-secret")
    monkeypatch.setattr(
        "think_tank.model_client._new_aisuite_client",
        fake_new_aisuite_client,
    )

    _new_openrouter_client()
    _new_groq_client()

    assert calls == [
        {
            "openai": {
                "api_key": "or-secret",
                "base_url": OPENROUTER_BASE_URL,
            }
        },
        {
            "openai": {
                "api_key": "gsk-secret",
                "base_url": GROQ_BASE_URL,
            }
        },
    ]


def test_aisuite_model_client_wraps_provider_call_errors() -> None:
    client = AisuiteModelClient(client=FailingAisuiteClient())

    with pytest.raises(
        ModelClientQuotaOrRateLimitError,
        match="Model call failed for openai",
    ):
        client.complete(
            model="openai:gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )


def test_aisuite_model_client_classifies_authentication_errors() -> None:
    client = AisuiteModelClient(client=FailingAisuiteClient("401 invalid API key"))

    with pytest.raises(ModelClientAuthenticationError):
        client.complete(
            model="openai:gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )


def test_aisuite_model_client_leaves_unclassified_errors_generic() -> None:
    client = AisuiteModelClient(client=FailingAisuiteClient("temporary outage"))

    with pytest.raises(ModelClientCallError) as exc_info:
        client.complete(
            model="openai:gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )

    assert not isinstance(exc_info.value, ModelClientAuthenticationError)
    assert not isinstance(exc_info.value, ModelClientQuotaOrRateLimitError)


def test_ollama_registry_uses_env_or_default(monkeypatch: pytest.MonkeyPatch) -> None:
    assert OllamaHttpModelRegistry.from_env({}).base_url == DEFAULT_OLLAMA_API_URL
    assert (
        OllamaHttpModelRegistry.from_env(
            {"OLLAMA_API_URL": "http://localhost:9999"}
        ).base_url
        == "http://localhost:9999"
    )


def test_ollama_registry_lists_model_names(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout):
        assert request.full_url == "http://localhost:11434/api/tags"
        assert timeout == 5.0
        return FakeHttpResponse(
            b'{"models": [{"name": "llama3.1:8b"}, {"name": "mistral"}]}'
        )

    monkeypatch.setattr("think_tank.model_client.urlopen", fake_urlopen)

    assert OllamaHttpModelRegistry().list_models() == ["llama3.1:8b", "mistral"]


def test_ollama_registry_wraps_invalid_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeHttpResponse(b'{"unexpected": []}')

    monkeypatch.setattr("think_tank.model_client.urlopen", fake_urlopen)

    with pytest.raises(OllamaRegistryError, match="unexpected model list"):
        OllamaHttpModelRegistry().list_models()
