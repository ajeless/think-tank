import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from think_tank.workspace import (
    WORKSPACE_DIRECTORIES,
    WorkspaceAlreadyExistsError,
    init_workspace,
)


def test_init_workspace_creates_layout_and_initial_state(tmp_path: Path) -> None:
    root = tmp_path / "idea"
    result = init_workspace(
        root,
        name="Test Idea",
        now=datetime(2026, 4, 27, 12, 30, tzinfo=timezone.utc),
    )

    assert result["root"] == str(root)
    assert result["state_path"] == str(root / "state.json")
    assert result["created_directories"] == list(WORKSPACE_DIRECTORIES)
    for relative_path in WORKSPACE_DIRECTORIES:
        assert (root / relative_path).is_dir()

    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert state == {
        "schema_version": 1,
        "project": {
            "name": "Test Idea",
            "created_at": "2026-04-27T12:30:00Z",
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


def test_init_workspace_refuses_existing_state_file(tmp_path: Path) -> None:
    root = tmp_path / "idea"
    root.mkdir()
    (root / "state.json").write_text("{}", encoding="utf-8")

    with pytest.raises(WorkspaceAlreadyExistsError):
        init_workspace(root, name="Test Idea")

