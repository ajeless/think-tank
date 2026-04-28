from pathlib import Path

import pytest

from think_tank.config_store import load_config
from think_tank.setup import initialize_setup


def test_initialize_setup_writes_auth_profile_and_default_without_secrets(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"

    result = initialize_setup(
        config_path,
        env={"OPENAI_API_KEY": "sk-secret"},
        auth_selections=[
            {"provider": "openai", "auth_kind": "api_key_env"},
            {"provider": "ollama", "auth_kind": "local_server"},
        ],
        model_profiles=[
            {
                "name": "fast",
                "model": "openai:gpt-4o",
            },
            {
                "name": "local",
                "model": "ollama:llama3.2:latest",
            },
        ],
        default_model_profile="fast",
    )

    assert result["config_path"] == str(config_path)
    assert result["auth_paths"] == [
        {
            "provider": "openai",
            "auth_kind": "api_key_env",
            "env_vars": ["OPENAI_API_KEY"],
            "auth_methods": [
                {
                    "auth_kind": "api_key_env",
                    "env_vars": ["OPENAI_API_KEY"],
                }
            ],
        },
        {
            "provider": "ollama",
            "auth_kind": "local_server",
            "env_vars": [],
            "auth_methods": [
                {
                    "auth_kind": "local_server",
                    "env_vars": [],
                }
            ],
        },
    ]
    assert result["model_profiles"] == [
        {
            "config_path": str(config_path),
            "name": "fast",
            "model": "openai:gpt-4o",
            "added": True,
        },
        {
            "config_path": str(config_path),
            "name": "local",
            "model": "ollama:llama3.2:latest",
            "added": True,
        },
    ]
    assert result["default_model_profile"] == "fast"

    config_text = config_path.read_text(encoding="utf-8")
    assert "sk-secret" not in config_text
    assert "OPENAI_API_KEY" in config_text
    parsed = load_config(config_path)
    assert parsed["enabled_providers"] == ["openai", "ollama"]
    assert parsed["models"]["fast"]["model"] == "openai:gpt-4o"
    assert parsed["models"]["local"]["model"] == "ollama:llama3.2:latest"
    assert parsed["defaults"]["model_profile"] == "fast"


def test_initialize_setup_can_write_empty_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = initialize_setup(config_path, env={}, auth_selections=[])

    assert result == {
        "config_path": str(config_path),
        "auth_paths": [],
        "model_profiles": [],
        "default_model_profile": None,
    }
    assert load_config(config_path)["enabled_providers"] == []


def test_initialize_setup_rejects_duplicate_provider_auth_paths(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="select only one auth path for provider"):
        initialize_setup(
            tmp_path / "config.toml",
            env={"OPENAI_API_KEY": "sk-secret"},
            auth_selections=[
                {"provider": "openai", "auth_kind": "api_key_env"},
                {"provider": "openai", "auth_kind": "api_key_env"},
            ],
        )


def test_initialize_setup_rejects_planned_official_auth_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not implemented yet"):
        initialize_setup(
            tmp_path / "config.toml",
            env={"OPENAI_API_KEY": "sk-secret"},
            auth_selections=[
                {"provider": "openai", "auth_kind": "subscription_official"},
            ],
        )


def test_initialize_setup_rejects_incomplete_model_profile(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="requires a name and provider:model"):
        initialize_setup(
            tmp_path / "config.toml",
            env={},
            auth_selections=[],
            model_profiles=[{"name": "fast"}],
        )
