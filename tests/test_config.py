from pathlib import Path

import pytest

from think_tank.config import (
    ConfigNotFoundError,
    ModelProfileNotFoundError,
    ProviderAuthMethodSpec,
    ProviderAuthNotReadyError,
    ProviderSpec,
    add_config_auth,
    add_model_profile,
    default_config_path,
    detect_provider_statuses,
    doctor_config_auth,
    list_config_auth,
    list_model_profiles,
    load_config,
    provider_auth_method_options,
    remove_config_auth,
    remove_model_profile,
    resolve_model_profile,
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


def test_provider_auth_method_options_report_ready_methods_without_secrets(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "think_tank.config.PROVIDER_SPECS",
        (
            ProviderSpec(
                name="testai",
                display_name="Test AI",
                auth_kind="api_key_env",
                auth_methods=(
                    ProviderAuthMethodSpec(
                        auth_kind="api_key_env",
                        env_vars=("TESTAI_API_KEY",),
                        required_env_vars=("TESTAI_API_KEY",),
                    ),
                    ProviderAuthMethodSpec(
                        auth_kind="local_server",
                        env_vars=("TESTAI_URL",),
                    ),
                ),
            ),
        ),
    )

    options = provider_auth_method_options(
        "testai",
        env={"TESTAI_API_KEY": "secret-key", "TESTAI_URL": "http://localhost"},
    )

    assert options == [
        {
            "provider": "testai",
            "display_name": "Test AI",
            "auth_kind": "api_key_env",
            "ready": True,
            "detected_env_vars": ["TESTAI_API_KEY"],
            "required_env_vars": ["TESTAI_API_KEY"],
            "missing_env_vars": [],
            "notes": [],
        },
        {
            "provider": "testai",
            "display_name": "Test AI",
            "auth_kind": "local_server",
            "ready": True,
            "detected_env_vars": ["TESTAI_URL"],
            "required_env_vars": [],
            "missing_env_vars": [],
            "notes": [],
        },
    ]
    assert "secret-key" not in str(options)


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
    assert parsed["providers"]["openai"]["auth_methods"] == [
        {
            "auth_kind": "api_key_env",
            "env_vars": ["OPENAI_API_KEY"],
        }
    ]


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
                "auth_methods": [
                    {
                        "auth_kind": "api_key_env",
                        "env_vars": ["OPENAI_API_KEY"],
                    }
                ],
            },
            {
                "provider": "groq",
                "auth_kind": "api_key_env",
                "env_vars": ["GROQ_API_KEY"],
                "auth_methods": [
                    {
                        "auth_kind": "api_key_env",
                        "env_vars": ["GROQ_API_KEY"],
                    }
                ],
            },
        ],
    }
    assert "sk-secret" not in str(result)
    assert "gsk-secret" not in str(result)


def test_list_config_auth_requires_existing_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigNotFoundError, match="config not found"):
        list_config_auth(tmp_path / "missing.toml")


def test_add_config_auth_creates_config_for_ready_env_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "nested" / "config.toml"

    result = add_config_auth(
        config_path,
        "openai",
        env={"OPENAI_API_KEY": "sk-secret"},
    )

    assert result == {
        "config_path": str(config_path),
        "provider": "openai",
        "added": True,
        "auth_kind": "api_key_env",
        "env_vars": ["OPENAI_API_KEY"],
        "enabled_providers": ["openai"],
    }
    raw_config = config_path.read_text(encoding="utf-8")
    assert "sk-secret" not in raw_config
    assert "OPENAI_API_KEY" in raw_config
    parsed = load_config(config_path)
    assert parsed["enabled_providers"] == ["openai"]
    assert parsed["providers"]["openai"]["auth_kind"] == "api_key_env"
    assert parsed["providers"]["openai"]["auth_methods"] == [
        {
            "auth_kind": "api_key_env",
            "env_vars": ["OPENAI_API_KEY"],
        }
    ]


def test_add_config_auth_can_select_supported_auth_kind(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "think_tank.config.PROVIDER_SPECS",
        (
            ProviderSpec(
                name="testai",
                display_name="Test AI",
                auth_kind="api_key_env",
                auth_methods=(
                    ProviderAuthMethodSpec(
                        auth_kind="api_key_env",
                        env_vars=("TESTAI_API_KEY",),
                        required_env_vars=("TESTAI_API_KEY",),
                    ),
                    ProviderAuthMethodSpec(
                        auth_kind="local_server",
                        env_vars=("TESTAI_URL",),
                    ),
                ),
            ),
        ),
    )

    result = add_config_auth(
        tmp_path / "config.toml",
        "testai",
        env={"TESTAI_API_KEY": "secret-key", "TESTAI_URL": "http://localhost"},
        auth_kind="local_server",
    )

    assert result["auth_kind"] == "local_server"
    assert result["env_vars"] == ["TESTAI_URL"]
    raw_config = (tmp_path / "config.toml").read_text(encoding="utf-8")
    assert "secret-key" not in raw_config
    parsed = load_config(tmp_path / "config.toml")
    assert parsed["providers"]["testai"]["auth_methods"] == [
        {
            "auth_kind": "local_server",
            "env_vars": ["TESTAI_URL"],
        }
    ]


def test_add_config_auth_without_selection_uses_primary_method(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "think_tank.config.PROVIDER_SPECS",
        (
            ProviderSpec(
                name="testai",
                display_name="Test AI",
                auth_kind="api_key_env",
                auth_methods=(
                    ProviderAuthMethodSpec(
                        auth_kind="api_key_env",
                        env_vars=("TESTAI_API_KEY",),
                        required_env_vars=("TESTAI_API_KEY",),
                    ),
                    ProviderAuthMethodSpec(
                        auth_kind="local_server",
                        env_vars=("TESTAI_URL",),
                    ),
                ),
            ),
        ),
    )

    result = add_config_auth(
        tmp_path / "config.toml",
        "testai",
        env={"TESTAI_API_KEY": "secret-key", "TESTAI_URL": "http://localhost"},
    )

    assert result["auth_kind"] == "api_key_env"
    assert result["env_vars"] == ["TESTAI_API_KEY"]


def test_add_config_auth_rejects_unsupported_auth_kind(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="unsupported auth kind for openai"):
        add_config_auth(
            tmp_path / "config.toml",
            "openai",
            env={"OPENAI_API_KEY": "sk-secret"},
            auth_kind="official_oauth",
        )


def test_add_config_auth_adds_ollama_without_secret(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = add_config_auth(config_path, "ollama", env={})

    assert result["provider"] == "ollama"
    assert result["auth_kind"] == "local_server"
    assert result["env_vars"] == []
    parsed = load_config(config_path)
    assert parsed["enabled_providers"] == ["ollama"]
    assert parsed["providers"]["ollama"]["env_vars"] == []
    assert parsed["providers"]["ollama"]["auth_methods"] == [
        {
            "auth_kind": "local_server",
            "env_vars": [],
        }
    ]


def test_list_config_auth_reads_legacy_flat_provider_metadata(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version = 1",
                'secrets = "environment"',
                'enabled_providers = ["openai"]',
                "",
                "[providers.openai]",
                'auth_kind = "api_key_env"',
                'env_vars = ["OPENAI_API_KEY"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = list_config_auth(config_path)

    assert result["providers"] == [
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
        }
    ]


def test_list_config_auth_reads_multiple_provider_auth_methods(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version = 1",
                'secrets = "environment"',
                'enabled_providers = ["openai"]',
                "",
                "[providers.openai]",
                'auth_kind = "api_key_env"',
                'env_vars = ["OPENAI_API_KEY"]',
                "",
                "[[providers.openai.auth_methods]]",
                'auth_kind = "api_key_env"',
                'env_vars = ["OPENAI_API_KEY"]',
                "",
                "[[providers.openai.auth_methods]]",
                'auth_kind = "official_oauth"',
                "env_vars = []",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = list_config_auth(config_path)

    assert result["providers"] == [
        {
            "provider": "openai",
            "auth_kind": "api_key_env",
            "env_vars": ["OPENAI_API_KEY"],
            "auth_methods": [
                {
                    "auth_kind": "api_key_env",
                    "env_vars": ["OPENAI_API_KEY"],
                },
                {
                    "auth_kind": "official_oauth",
                    "env_vars": [],
                },
            ],
        }
    ]


def test_add_config_auth_updates_existing_provider_metadata(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    write_detected_provider_config(
        config_path,
        env={"OPENAI_API_KEY": "old-secret"},
        enabled_providers=["openai"],
    )

    result = add_config_auth(
        config_path,
        "openai",
        env={"OPENAI_API_KEY": "new-secret"},
    )

    assert result["added"] is False
    assert result["enabled_providers"] == ["openai"]
    assert load_config(config_path)["enabled_providers"] == ["openai"]
    raw_config = config_path.read_text(encoding="utf-8")
    assert "old-secret" not in raw_config
    assert "new-secret" not in raw_config


def test_add_config_auth_rejects_missing_required_env(tmp_path: Path) -> None:
    with pytest.raises(ProviderAuthNotReadyError, match="OPENAI_API_KEY"):
        add_config_auth(tmp_path / "config.toml", "openai", env={})


def test_add_config_auth_rejects_unknown_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown provider: futureai"):
        add_config_auth(tmp_path / "config.toml", "futureai", env={})


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
    assert openai["configured_auth_methods"] == [
        {
            "auth_kind": "api_key_env",
            "env_vars": ["OPENAI_API_KEY"],
        }
    ]
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
    assert futureai["configured_auth_methods"] == [
        {
            "auth_kind": "api_key_env",
            "env_vars": ["FUTUREAI_API_KEY"],
        }
    ]
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
