from types import SimpleNamespace

import pytest

from think_tank.model_client import (
    AisuiteModelClient,
    ModelClientCallError,
    ModelClientConfigurationError,
    _new_aisuite_client,
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


class FailingCompletions:
    def create(self, *, model: str, messages: list[dict[str, str]]):
        raise RuntimeError("quota failed")


class FailingAisuiteClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FailingCompletions())


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


def test_openrouter_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(ModelClientConfigurationError, match="OPENROUTER_API_KEY"):
        _new_openrouter_client()


def test_aisuite_model_client_wraps_provider_call_errors() -> None:
    client = AisuiteModelClient(client=FailingAisuiteClient())

    with pytest.raises(ModelClientCallError, match="Model call failed for openai"):
        client.complete(
            model="openai:gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )
