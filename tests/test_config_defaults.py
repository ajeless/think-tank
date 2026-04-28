from pathlib import Path

import pytest

from think_tank.config_auth import add_config_auth, write_detected_provider_config
from think_tank.config_common import ModelProfileNotFoundError
from think_tank.config_defaults import (
    list_config_defaults,
    remove_config_default,
    set_config_defaults,
)
from think_tank.config_models import add_model_profile
from think_tank.config_store import ConfigNotFoundError, load_config


def test_config_defaults_crud_uses_existing_model_profile(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    add_config_auth(config_path, "ollama", env={})
    add_model_profile(
        config_path,
        name="local",
        model="ollama:llama3.2:latest",
    )

    set_result = set_config_defaults(config_path, model_profile="local")
    list_result = list_config_defaults(config_path)

    assert set_result == {
        "config_path": str(config_path),
        "defaults": {
            "model_profile": "local",
        },
    }
    assert list_result == set_result
    parsed = load_config(config_path)
    assert parsed["defaults"]["model_profile"] == "local"
    assert parsed["models"]["local"]["model"] == "ollama:llama3.2:latest"
    assert parsed["providers"]["ollama"]["auth_kind"] == "local_server"

    remove_result = remove_config_default(config_path, "model-profile")
    assert remove_result == {
        "config_path": str(config_path),
        "removed_default": "model_profile",
        "removed": True,
        "defaults": {
            "model_profile": None,
        },
    }
    assert "defaults" not in load_config(config_path)


def test_config_defaults_require_existing_model_profile(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    add_model_profile(config_path, name="fast", model="groq:llama-3.1-8b")

    with pytest.raises(ModelProfileNotFoundError, match="missing"):
        set_config_defaults(config_path, model_profile="missing")


def test_config_defaults_set_requires_existing_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigNotFoundError, match="config not found"):
        set_config_defaults(tmp_path / "missing.toml", model_profile="fast")


def test_config_defaults_reject_unknown_default_remove(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    add_model_profile(config_path, name="fast", model="groq:llama-3.1-8b")

    with pytest.raises(ValueError, match="unknown default"):
        remove_config_default(config_path, "provider")


def test_config_init_preserves_existing_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    add_model_profile(config_path, name="fast", model="groq:llama-3.1-8b")
    set_config_defaults(config_path, model_profile="fast")

    write_detected_provider_config(
        config_path,
        env={"OPENAI_API_KEY": "sk-secret"},
        enabled_providers=["openai"],
    )

    parsed = load_config(config_path)
    assert parsed["defaults"]["model_profile"] == "fast"
    assert parsed["models"]["fast"]["model"] == "groq:llama-3.1-8b"
    assert parsed["providers"]["openai"]["env_vars"] == ["OPENAI_API_KEY"]
    assert "sk-secret" not in config_path.read_text(encoding="utf-8")
