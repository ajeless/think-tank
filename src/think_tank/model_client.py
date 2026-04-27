"""Model client boundary for Think Tank engine calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypedDict


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


class AisuiteModelClient:
    """aisuite-backed implementation of the model client boundary."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        client = self._client or _new_aisuite_client()
        response = client.chat.completions.create(model=model, messages=messages)
        return ModelResponse(content=response.choices[0].message.content)


def _new_aisuite_client() -> Any:
    _patch_python_314_ast_compatibility()

    import aisuite as ai

    return ai.Client()


def _patch_python_314_ast_compatibility() -> None:
    """Keep aisuite's docstring-parser dependency importable on Python 3.14."""

    import ast

    for removed_name in ("NameConstant", "Num", "Str"):
        if not hasattr(ast, removed_name):
            setattr(ast, removed_name, ast.Constant)
