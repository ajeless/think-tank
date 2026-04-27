"""Engine-facing functions for Think Tank.

The engine returns data and leaves display, prompting, and process concerns to adapters.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from .model_client import ModelClient, ModelMessage


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


class MissingModelError(ValueError):
    """Raised when a work command reaches the engine without a model."""


class MissingPromptError(ValueError):
    """Raised when a work command reaches the engine without a prompt."""


class ProjectStateNotFoundError(FileNotFoundError):
    """Raised when a project directory does not contain state.json."""


def get_engine_status() -> EngineStatus:
    """Return a minimal structured status for the bootstrap skeleton."""

    return {
        "product": "Think Tank",
        "ready": True,
    }


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


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("engine timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
