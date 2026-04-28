import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from think_tank.engine import (
    MissingModelError,
    MissingPromptError,
    ProjectStateNotFoundError,
    ProviderModelListingInputError,
    ProviderValidationInputError,
    VALIDATION_PROMPT,
    ask_project,
    get_engine_status,
    list_provider_models,
    validate_provider,
)
from think_tank.model_client import (
    ModelClientAuthenticationError,
    ModelClientCallError,
    ModelClientConfigurationError,
    ModelClientQuotaOrRateLimitError,
    ModelMessage,
    ModelResponse,
    OllamaRegistryError,
    ProviderModelInfo,
    ProviderModelRegistryError,
)
from think_tank.workspace import init_workspace


class FakeModelClient:
    def __init__(self, content: str = "fake response") -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        self.calls.append({"model": model, "messages": messages})
        return ModelResponse(content=self.content)


class FailingModelClient:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls: list[dict[str, object]] = []

    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        self.calls.append({"model": model, "messages": messages})
        raise self.exc


class FakeOllamaRegistry:
    def __init__(
        self,
        models: list[str] | None = None,
        exc: OllamaRegistryError | None = None,
    ) -> None:
        self.models = models or []
        self.exc = exc
        self.calls = 0

    def list_models(self) -> list[str]:
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.models


class FakeProviderModelRegistry:
    def __init__(
        self,
        models: list[ProviderModelInfo] | None = None,
        exc: ProviderModelRegistryError | None = None,
    ) -> None:
        self.models = models or []
        self.exc = exc
        self.calls = 0

    def list_models(self) -> list[ProviderModelInfo]:
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.models


def test_get_engine_status_returns_structured_data() -> None:
    assert get_engine_status() == {
        "product": "Think Tank",
        "ready": True,
    }


def test_ask_project_calls_model_and_returns_structured_result(tmp_path: Path) -> None:
    project = tmp_path / "idea"
    init_workspace(project, name="Test Idea")
    client = FakeModelClient("consider the tradeoffs")

    result = ask_project(
        project,
        prompt="What should we evaluate first?",
        model="test:model",
        client=client,
        now=datetime(2026, 4, 27, 13, 0, tzinfo=timezone.utc),
    )

    assert result == {
        "project_root": str(project),
        "state_path": str(project / "state.json"),
        "transcript_path": str(project / "transcripts" / "ask.jsonl"),
        "model": "test:model",
        "prompt": "What should we evaluate first?",
        "response": "consider the tradeoffs",
        "recorded_at": "2026-04-27T13:00:00Z",
    }
    assert client.calls[0]["model"] == "test:model"
    messages = client.calls[0]["messages"]
    assert isinstance(messages, list)
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Test Idea" in messages[1]["content"]
    assert "What should we evaluate first?" in messages[1]["content"]


def test_ask_project_appends_transcript_row(tmp_path: Path) -> None:
    project = tmp_path / "idea"
    init_workspace(project, name="Test Idea")
    client = FakeModelClient("first response")

    ask_project(
        project,
        prompt="Capture this",
        model="provider:model-a",
        client=client,
        now=datetime(2026, 4, 27, 14, 0, tzinfo=timezone.utc),
    )
    client.content = "second response"
    ask_project(
        project,
        prompt="Capture this too",
        model="provider:model-b",
        client=client,
        now=datetime(2026, 4, 27, 14, 1, tzinfo=timezone.utc),
    )

    transcript_path = project / "transcripts" / "ask.jsonl"
    rows = [
        json.loads(line)
        for line in transcript_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["model"] for row in rows] == ["provider:model-a", "provider:model-b"]
    assert [row["prompt"] for row in rows] == ["Capture this", "Capture this too"]
    assert rows[0]["response"] == {"content": "first response"}
    assert rows[1]["response"] == {"content": "second response"}


def test_ask_project_requires_explicit_model(tmp_path: Path) -> None:
    project = tmp_path / "idea"
    init_workspace(project, name="Test Idea")
    client = FakeModelClient()

    with pytest.raises(MissingModelError, match="--model <provider:model>"):
        ask_project(project, prompt="Hello", model=None, client=client)

    assert client.calls == []


def test_validate_provider_sends_tiny_prompt_and_returns_success() -> None:
    client = FakeModelClient("OK")

    result = validate_provider(
        provider="openai",
        model="openai:gpt-4o",
        client=client,
        env={"OPENAI_API_KEY": "sk-secret"},
    )

    assert result == {
        "provider": "openai",
        "model": "openai:gpt-4o",
        "ok": True,
        "status": "success",
        "message": "Provider validation succeeded.",
    }
    assert client.calls == [
        {
            "model": "openai:gpt-4o",
            "messages": [{"role": "user", "content": VALIDATION_PROMPT}],
        }
    ]


def test_list_provider_models_returns_gemini_model_ids_without_secrets() -> None:
    registry = FakeProviderModelRegistry(
        models=[
            {
                "provider_model": "gemini-3-flash-preview",
                "display_name": "Gemini 3 Flash Preview",
                "supported_actions": ["generateContent", "countTokens"],
            }
        ]
    )

    result = list_provider_models(
        provider="gemini",
        env={"GEMINI_API_KEY": "gemini-secret"},
        gemini_registry=registry,
    )

    assert result == {
        "provider": "gemini",
        "ok": True,
        "status": "success",
        "message": "Discovered 1 model(s).",
        "models": [
            {
                "provider": "gemini",
                "provider_model": "gemini-3-flash-preview",
                "model": "gemini:gemini-3-flash-preview",
                "display_name": "Gemini 3 Flash Preview",
                "supported_actions": ["generateContent", "countTokens"],
            }
        ],
    }
    assert registry.calls == 1
    assert "gemini-secret" not in str(result)


def test_list_provider_models_reports_missing_credentials_without_querying_registry() -> None:
    registry = FakeProviderModelRegistry()

    result = list_provider_models(
        provider="gemini",
        env={"GEMINI_API_KEY": ""},
        gemini_registry=registry,
    )

    assert result["ok"] is False
    assert result["status"] == "missing_credentials"
    assert "GEMINI_API_KEY" in result["message"]
    assert registry.calls == 0


def test_list_provider_models_reports_unsupported_provider() -> None:
    result = list_provider_models(
        provider="openai",
        env={"OPENAI_API_KEY": "sk-secret"},
    )

    assert result["ok"] is False
    assert result["status"] == "not_supported"
    assert "openai" in result["message"]
    assert "sk-secret" not in str(result)


def test_list_provider_models_requires_gemini_registry() -> None:
    with pytest.raises(ProviderModelListingInputError, match="registry"):
        list_provider_models(
            provider="gemini",
            env={"GEMINI_API_KEY": "gemini-secret"},
        )


def test_list_provider_models_reports_registry_error_without_secret_values() -> None:
    registry = FakeProviderModelRegistry(
        exc=ProviderModelRegistryError("failure with gemini-secret")
    )

    result = list_provider_models(
        provider="gemini",
        env={"GEMINI_API_KEY": "gemini-secret"},
        gemini_registry=registry,
    )

    assert result["ok"] is False
    assert result["status"] == "provider_failure"
    assert "gemini-secret" not in result["message"]


def test_validate_provider_reports_missing_credentials_without_calling_client() -> None:
    client = FakeModelClient("OK")

    result = validate_provider(
        provider="anthropic",
        model="anthropic:claude-sonnet-4-5",
        client=client,
        env={},
    )

    assert result["ok"] is False
    assert result["status"] == "missing_credentials"
    assert "ANTHROPIC_API_KEY" in result["message"]
    assert client.calls == []


@pytest.mark.parametrize(
    ("exc", "status"),
    [
        (
            ModelClientAuthenticationError("openai", "invalid API key sk-secret"),
            "auth_failure",
        ),
        (
            ModelClientQuotaOrRateLimitError("openai", "rate limit exceeded"),
            "quota_or_rate_limit",
        ),
        (
            ModelClientConfigurationError("provider dependency missing"),
            "provider_config_error",
        ),
        (ModelClientCallError("openai", "provider unavailable"), "provider_failure"),
    ],
)
def test_validate_provider_classifies_provider_errors(
    exc: Exception,
    status: str,
) -> None:
    client = FailingModelClient(exc)

    result = validate_provider(
        provider="openai",
        model="openai:gpt-4o",
        client=client,
        env={"OPENAI_API_KEY": "sk-secret"},
    )

    assert result["ok"] is False
    assert result["status"] == status
    assert "sk-secret" not in result["message"]
    assert client.calls[0]["model"] == "openai:gpt-4o"


def test_validate_provider_rejects_model_provider_mismatch() -> None:
    client = FakeModelClient("OK")

    with pytest.raises(ProviderValidationInputError, match="must match"):
        validate_provider(
            provider="openai",
            model="anthropic:claude-sonnet-4-5",
            client=client,
            env={"OPENAI_API_KEY": "sk-secret"},
        )

    assert client.calls == []


def test_validate_provider_checks_ollama_registry_for_requested_model() -> None:
    client = FakeModelClient("unused")
    registry = FakeOllamaRegistry(models=["llama3.1:8b"])

    result = validate_provider(
        provider="ollama",
        model="ollama:llama3.1:8b",
        client=client,
        env={},
        ollama_registry=registry,
    )

    assert result["ok"] is True
    assert result["status"] == "success"
    assert registry.calls == 1
    assert client.calls == []


def test_validate_provider_reports_missing_ollama_model() -> None:
    client = FakeModelClient("unused")

    result = validate_provider(
        provider="ollama",
        model="ollama:missing-model",
        client=client,
        env={},
        ollama_registry=FakeOllamaRegistry(models=["llama3.1:8b"]),
    )

    assert result["ok"] is False
    assert result["status"] == "provider_config_error"
    assert "missing-model" in result["message"]
    assert client.calls == []


def test_validate_provider_reports_ollama_registry_errors() -> None:
    client = FakeModelClient("unused")

    result = validate_provider(
        provider="ollama",
        model="ollama:llama3.1:8b",
        client=client,
        env={},
        ollama_registry=FakeOllamaRegistry(
            exc=OllamaRegistryError("Ollama server is not reachable.")
        ),
    )

    assert result["ok"] is False
    assert result["status"] == "provider_config_error"
    assert "not reachable" in result["message"]
    assert client.calls == []


def test_ask_project_requires_non_empty_prompt(tmp_path: Path) -> None:
    project = tmp_path / "idea"
    init_workspace(project, name="Test Idea")
    client = FakeModelClient()

    with pytest.raises(MissingPromptError, match="non-empty prompt"):
        ask_project(project, prompt=" ", model="test:model", client=client)

    assert client.calls == []


def test_ask_project_rejects_blank_model_without_defaulting(tmp_path: Path) -> None:
    project = tmp_path / "idea"
    init_workspace(project, name="Test Idea")
    client = FakeModelClient()

    with pytest.raises(MissingModelError):
        ask_project(project, prompt="Hello", model=" ", client=client)

    assert client.calls == []


def test_ask_project_requires_project_state(tmp_path: Path) -> None:
    client = FakeModelClient()

    with pytest.raises(ProjectStateNotFoundError, match="project state not found"):
        ask_project(
            tmp_path / "missing",
            prompt="Hello",
            model="test:model",
            client=client,
        )

    assert client.calls == []
