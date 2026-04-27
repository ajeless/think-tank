"""Local Think Tank workspace creation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict


ARTIFACT_DIRECTORIES = (
    "artifacts/diagrams",
    "artifacts/charts",
    "artifacts/mindmaps",
    "artifacts/flows",
    "artifacts/mocks",
    "artifacts/data",
)

WORKSPACE_DIRECTORIES = (
    "transcripts",
    "notes",
    *ARTIFACT_DIRECTORIES,
)


class WorkspaceInitResult(TypedDict):
    root: str
    state_path: str
    created_directories: list[str]


class WorkspaceAlreadyExistsError(FileExistsError):
    """Raised when a workspace already has a state file."""


def init_workspace(root: Path, *, name: str, now: datetime | None = None) -> WorkspaceInitResult:
    """Create a local Think Tank workspace and initial state file."""

    workspace_root = root.expanduser()
    if workspace_root.exists() and not workspace_root.is_dir():
        raise NotADirectoryError(f"workspace path exists and is not a directory: {workspace_root}")

    state_path = workspace_root / "state.json"
    if state_path.exists():
        raise WorkspaceAlreadyExistsError(f"workspace already contains state.json: {state_path}")

    timestamp = _format_timestamp(now or datetime.now(timezone.utc))
    workspace_root.mkdir(parents=True, exist_ok=True)

    created_directories: list[str] = []
    for relative_path in WORKSPACE_DIRECTORIES:
        directory = workspace_root / relative_path
        directory.mkdir(parents=True, exist_ok=True)
        created_directories.append(relative_path)

    state_path.write_text(
        json.dumps(_initial_state(name=name, created_at=timestamp), indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "root": str(workspace_root),
        "state_path": str(state_path),
        "created_directories": created_directories,
    }


def _initial_state(*, name: str, created_at: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project": {
            "name": name,
            "created_at": created_at,
            "status": "exploring",
        },
        "claims": [],
        "questions": [],
        "assumptions": [],
        "decisions": [],
        "disagreements": [],
        "evidence": [],
        "glossary": [],
        "artifacts": [],
        "next_actions": [],
        "change_log": [],
    }


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("workspace timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

