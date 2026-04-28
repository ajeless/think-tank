from typer.testing import CliRunner

from think_tank.model_client import (
    ModelClientAuthenticationError,
    ModelClientCallError,
    ModelMessage,
    ModelResponse,
    ProviderModelInfo,
)


runner = CliRunner()


class FakeAisuiteModelClient:
    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(content=f"response from {model}: {messages[-1]['role']}")


class FailingAisuiteModelClient:
    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        raise ModelClientCallError("openai", "provider quota failed")


class AuthFailingAisuiteModelClient:
    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        raise ModelClientAuthenticationError("openai", "invalid API key")


class FakeOllamaHttpModelRegistry:
    def __init__(self, models: list[str]) -> None:
        self.models = models

    @classmethod
    def from_env(cls, env):
        return cls(models=["llama3.1:8b"])

    def list_models(self) -> list[str]:
        return self.models


class FakeGeminiModelRegistry:
    def list_models(self) -> list[ProviderModelInfo]:
        return [
            {
                "provider_model": "gemini-3-flash-preview",
                "display_name": "Gemini 3 Flash Preview",
                "supported_actions": ["generateContent", "countTokens"],
            },
            {
                "provider_model": "gemini-embedding-001",
                "display_name": "Gemini Embedding",
                "supported_actions": ["embedContent"],
            },
        ]


class FakeQuestionaryResponse:
    def __init__(self, answer) -> None:
        self.answer = answer

    def ask(self):
        return self.answer
