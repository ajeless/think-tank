from pathlib import Path

import pytest

from think_tank.config import (
    ConfigNotFoundError,
    default_config_path,
    detect_provider_statuses,
    doctor_config_auth,
    list_config_auth,
    load_config,
    remove_config_auth,
    write_detected_provider_config,
)


def test_detect_provider_statuses_reports_detected_env_var_names_only() -> None:
    statuses = detect_provider_statuses(
        {
            "OPENAI_API_KEY": "sk-secret",
            "OPENROUTER_API_KEY": "or-secret",
            "GROQ_API_KEY": "gsk-secret",
            "GOOGLE_PROJECT_ID": "project",
            "GOOGLE_REGION": "us-central1",
        }
    )

    openai = _status(statuses, "openai")
    assert openai["ready"] is True
    assert openai["detected_env_vars"] == ["OPENAI_API_KEY"]
    assert "sk-secret" not in str(openai)

    openrouter = _status(statuses, "openrouter")
    assert openrouter["ready"] is True
    assert openrouter["detected_env_vars"] == ["OPENROUTER_API_KEY"]
    assert "or-secret" not in str(openrouter)

    groq = _status(statuses, "groq")
    assert groq["ready"] is True
    assert groq["detected_env_vars"] == ["GROQ_API_KEY"]
    assert "gsk-secret" not in str(groq)

    google = _status(statuses, "google")
    assert google["ready"] is False
    assert google["missing_env_vars"] == ["GOOGLE_APPLICATION_CREDENTIALS"]


def test_ollama_is_ready_without_secret() -> None:
    statuses = detect_provider_statuses({})

    ollama = _status(statuses, "ollama")
    assert ollama["ready"] is True
    assert ollama["auth_kind"] == "local_server"
    assert ollama["detected_env_vars"] == []


def test_write_detected_provider_config_stores_no_secret_values(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    result = write_detected_provider_config(
        config_path,
        env={
            "OPENAI_API_KEY": "sk-secret",
            "ANTHROPIC_API_KEY": "anthropic-secret",
            "GROQ_API_KEY": "gsk-secret",
        },
        enabled_providers=["openai", "anthropic", "groq"],
    )

    assert result == {
        "config_path": str(config_path),
        "enabled_providers": ["openai", "anthropic", "groq"],
    }
    raw_config = config_path.read_text(encoding="utf-8")
    assert "sk-secret" not in raw_config
    assert "anthropic-secret" not in raw_config
    assert "gsk-secret" not in raw_config
    assert "OPENAI_API_KEY" in raw_config
    assert "ANTHROPIC_API_KEY" in raw_config
    assert "GROQ_API_KEY" in raw_config

    parsed = load_config(config_path)
    assert parsed["schema_version"] == 1
    assert parsed["secrets"] == "environment"
    assert parsed["enabled_providers"] == ["openai", "anthropic", "groq"]


def test_write_detected_provider_config_rejects_unknown_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        write_detected_provider_config(
            tmp_path / "config.toml",
            env={},
            enabled_providers=["unknown"],
        )


def test_list_config_auth_returns_enabled_provider_metadata(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    write_detected_provider_config(
        config_path,
        env={
            "OPENAI_API_KEY": "sk-secret",
            "GROQ_API_KEY": "gsk-secret",
        },
        enabled_providers=["openai", "groq"],
    )

    result = list_config_auth(config_path)

    assert result == {
        "config_path": str(config_path),
        "providers": [
            {
                "provider": "openai",
                "auth_kind": "api_key_env",
                "env_vars": ["OPENAI_API_KEY"],
            },
            {
                "provider": "groq",
                "auth_kind": "api_key_env",
                "env_vars": ["GROQ_API_KEY"],
            },
        ],
    }
    assert "sk-secret" not in str(result)
    assert "gsk-secret" not in str(result)


def test_list_config_auth_requires_existing_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigNotFoundError, match="config not found"):
        list_config_auth(tmp_path / "missing.toml")


def test_doctor_config_auth_reports_detection_without_config(tmp_path: Path) -> None:
    result = doctor_config_auth(
        tmp_path / "missing.toml",
        env={"GROQ_API_KEY": "gsk-secret"},
    )

    assert result["config_path"] == str(tmp_path / "missing.toml")
    assert result["config_found"] is False
    groq = _doctor_provider(result, "groq")
    assert groq["configured"] is False
    assert groq["detected"] is True
    assert groq["ready"] is True
    assert groq["detected_env_vars"] == ["GROQ_API_KEY"]
    assert "gsk-secret" not in str(result)


def test_doctor_config_auth_combines_configured_and_detected_metadata(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"
    write_detected_provider_config(
        config_path,
        env={
            "OPENAI_API_KEY": "sk-secret",
            "GROQ_API_KEY": "gsk-secret",
        },
        enabled_providers=["openai", "groq"],
    )

    result = doctor_config_auth(
        config_path,
        env={
            "GROQ_API_KEY": "gsk-secret",
        },
    )

    assert result["config_found"] is True
    openai = _doctor_provider(result, "openai")
    assert openai["configured"] is True
    assert openai["detected"] is False
    assert openai["ready"] is False
    assert openai["configured_env_vars"] == ["OPENAI_API_KEY"]
    assert openai["missing_env_vars"] == ["OPENAI_API_KEY"]

    groq = _doctor_provider(result, "groq")
    assert groq["configured"] is True
    assert groq["detected"] is True
    assert groq["ready"] is True
    assert groq["configured_env_vars"] == ["GROQ_API_KEY"]
    assert groq["detected_env_vars"] == ["GROQ_API_KEY"]
    assert "sk-secret" not in str(result)
    assert "gsk-secret" not in str(result)


def test_doctor_config_auth_includes_unknown_configured_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version = 1",
                'secrets = "environment"',
                'enabled_providers = ["futureai"]',
                "",
                "[providers.futureai]",
                'auth_kind = "api_key_env"',
                'env_vars = ["FUTUREAI_API_KEY"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = doctor_config_auth(config_path, env={})

    futureai = _doctor_provider(result, "futureai")
    assert futureai["configured"] is True
    assert futureai["detected"] is False
    assert futureai["ready"] is False
    assert futureai["configured_env_vars"] == ["FUTUREAI_API_KEY"]
    assert futureai["notes"] == [
        "Provider is configured but is not in the packaged provider set."
    ]


def test_remove_config_auth_removes_provider_metadata_only(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    write_detected_provider_config(
        config_path,
        env={
            "OPENAI_API_KEY": "sk-secret",
            "ANTHROPIC_API_KEY": "anthropic-secret",
            "GROQ_API_KEY": "gsk-secret",
        },
        enabled_providers=["openai", "anthropic", "groq"],
    )

    result = remove_config_auth(config_path, "anthropic")

    assert result == {
        "config_path": str(config_path),
        "removed_provider": "anthropic",
        "removed": True,
        "enabled_providers": ["openai", "groq"],
    }
    parsed = load_config(config_path)
    assert parsed["enabled_providers"] == ["openai", "groq"]
    assert "anthropic" not in parsed["providers"]
    assert parsed["providers"]["openai"]["env_vars"] == ["OPENAI_API_KEY"]
    assert parsed["providers"]["groq"]["env_vars"] == ["GROQ_API_KEY"]
    assert "anthropic-secret" not in config_path.read_text(encoding="utf-8")


def test_remove_config_auth_is_idempotent_for_absent_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    write_detected_provider_config(
        config_path,
        env={"OPENAI_API_KEY": "sk-secret"},
        enabled_providers=["openai"],
    )

    result = remove_config_auth(config_path, "groq")

    assert result["removed"] is False
    assert result["enabled_providers"] == ["openai"]
    assert load_config(config_path)["enabled_providers"] == ["openai"]


def test_default_config_path_uses_xdg_config_home() -> None:
    assert default_config_path({"XDG_CONFIG_HOME": "/tmp/config"}) == Path(
        "/tmp/config/think-tank/config.toml"
    )


def _status(statuses, provider: str):
    return next(status for status in statuses if status["provider"] == provider)


def _doctor_provider(result, provider: str):
    return next(item for item in result["providers"] if item["provider"] == provider)
