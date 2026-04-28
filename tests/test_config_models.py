from pathlib import Path

import pytest

from think_tank.config_auth import add_config_auth, write_detected_provider_config
from think_tank.config_common import ModelProfileNotFoundError
from think_tank.config_defaults import list_config_defaults, set_config_defaults
from think_tank.config_models import (
    add_model_profile,
    list_model_profiles,
    remove_model_profile,
    resolve_model_profile,
)
from think_tank.config_store import load_config


def test_add_model_profile_creates_config_without_default_model(tmp_path: Path) -> None:
    config_path = tmp_path / "nested" / "config.toml"

    result = add_model_profile(config_path, name="fast", model="groq:llama-3.1-8b")

    assert result == {
        "config_path": str(config_path),
        "name": "fast",
        "model": "groq:llama-3.1-8b",
        "added": True,
    }
    raw_config = config_path.read_text(encoding="utf-8")
    assert '[models."fast"]' in raw_config
    assert 'model = "groq:llama-3.1-8b"' in raw_config
    assert "default_model" not in raw_config
    parsed = load_config(config_path)
    assert parsed["models"]["fast"]["model"] == "groq:llama-3.1-8b"


def test_add_model_profile_escapes_control_characters(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    add_model_profile(config_path, name="line\nname", model="openai:gpt\t4o")

    config_text = config_path.read_text(encoding="utf-8")
    assert '"line\\nname"' in config_text
    assert '"openai:gpt\\t4o"' in config_text
    assert load_config(config_path)["models"]["line\nname"]["model"] == "openai:gpt\t4o"


def test_model_profile_crud_preserves_auth_metadata(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    add_config_auth(config_path, "ollama", env={})

    add_result = add_model_profile(
        config_path,
        name="local",
        model="ollama:llama3.2:latest",
    )
    profiles = list_model_profiles(config_path)

    assert add_result["added"] is True
    assert profiles == {
        "config_path": str(config_path),
        "profiles": [
            {
                "name": "local",
                "model": "ollama:llama3.2:latest",
            }
        ],
    }
    parsed = load_config(config_path)
    assert parsed["enabled_providers"] == ["ollama"]
    assert parsed["providers"]["ollama"]["auth_kind"] == "local_server"

    update_result = add_model_profile(
        config_path,
        name="local",
        model="ollama:llama3.1:8b",
    )
    assert update_result["added"] is False
    assert resolve_model_profile(config_path, "local") == {
        "name": "local",
        "model": "ollama:llama3.1:8b",
    }

    remove_result = remove_model_profile(config_path, "local")
    assert remove_result == {
        "config_path": str(config_path),
        "removed_profile": "local",
        "removed": True,
    }
    assert list_model_profiles(config_path)["profiles"] == []
    parsed_after_remove = load_config(config_path)
    assert parsed_after_remove["enabled_providers"] == ["ollama"]
    assert parsed_after_remove["providers"]["ollama"]["auth_kind"] == "local_server"


def test_model_profile_remove_clears_matching_default(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    add_model_profile(config_path, name="fast", model="groq:llama-3.1-8b")
    set_config_defaults(config_path, model_profile="fast")

    remove_model_profile(config_path, "fast")

    parsed = load_config(config_path)
    assert "models" not in parsed
    assert "defaults" not in parsed
    assert list_config_defaults(config_path)["defaults"] == {
        "model_profile": None,
    }


def test_model_profile_add_preserves_existing_profiles_during_config_init(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"
    add_model_profile(config_path, name="fast", model="groq:llama-3.1-8b")

    write_detected_provider_config(
        config_path,
        env={"OPENAI_API_KEY": "sk-secret"},
        enabled_providers=["openai"],
    )

    assert resolve_model_profile(config_path, "fast") == {
        "name": "fast",
        "model": "groq:llama-3.1-8b",
    }
    parsed = load_config(config_path)
    assert parsed["enabled_providers"] == ["openai"]
    assert parsed["providers"]["openai"]["env_vars"] == ["OPENAI_API_KEY"]
    assert "sk-secret" not in config_path.read_text(encoding="utf-8")


def test_add_model_profile_rejects_invalid_model_string(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="<provider:model>"):
        add_model_profile(tmp_path / "config.toml", name="bad", model="gpt-4o")


def test_add_model_profile_rejects_unknown_model_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported model provider: futureai"):
        add_model_profile(
            tmp_path / "config.toml",
            name="future",
            model="futureai:model",
        )


def test_resolve_model_profile_requires_existing_profile(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    add_model_profile(config_path, name="fast", model="groq:llama-3.1-8b")

    with pytest.raises(ModelProfileNotFoundError, match="missing"):
        resolve_model_profile(config_path, "missing")
