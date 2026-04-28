from pathlib import Path

import pytest

from think_tank.config_auth import (
    ProviderAuthNotReadyError,
    add_config_auth,
    doctor_config_auth,
    list_config_auth,
    list_provider_auth_methods,
    remove_config_auth,
    write_detected_provider_config,
)
from think_tank.config_store import ConfigNotFoundError, load_config
from think_tank.provider_registry import ProviderAuthMethodSpec, ProviderSpec


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


def test_list_provider_auth_methods_reports_capabilities_without_secrets() -> None:
    result = list_provider_auth_methods(
        env={
            "OPENAI_API_KEY": "sk-secret",
        },
        provider="openai",
    )

    assert result["providers"][0]["provider"] == "openai"
    methods = result["providers"][0]["auth_methods"]
    api_key = _auth_method(methods, "api_key_env")
    assert api_key["implemented"] is True
    assert api_key["official"] is True
    assert api_key["ready"] is True
    assert api_key["selectable"] is True
    assert api_key["support_status"] == "implemented"
    assert api_key["detected_env_vars"] == ["OPENAI_API_KEY"]
    assert "subscription_official" not in [
        method["auth_kind"] for method in methods
    ]

    assert "sk-secret" not in str(result)


def test_list_provider_auth_methods_reports_all_packaged_providers() -> None:
    result = list_provider_auth_methods(env={})

    assert [provider["provider"] for provider in result["providers"]] == [
        "openai",
        "anthropic",
        "google",
        "ollama",
        "openrouter",
        "groq",
    ]


def test_list_provider_auth_methods_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unknown provider: futureai"):
        list_provider_auth_methods(env={}, provider="futureai")


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
        "think_tank.provider_registry.PROVIDER_SPECS",
        (
            ProviderSpec(
                name="testai",
                display_name="Test AI",
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
        "think_tank.provider_registry.PROVIDER_SPECS",
        (
            ProviderSpec(
                name="testai",
                display_name="Test AI",
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


def test_add_config_auth_rejects_unimplemented_auth_kind(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "think_tank.provider_registry.PROVIDER_SPECS",
        (
            ProviderSpec(
                name="testai",
                display_name="Test AI",
                auth_methods=(
                    ProviderAuthMethodSpec(
                        auth_kind="api_key_env",
                        env_vars=("TESTAI_API_KEY",),
                        required_env_vars=("TESTAI_API_KEY",),
                    ),
                    ProviderAuthMethodSpec(
                        auth_kind="future_api_key_env",
                        env_vars=("TESTAI_NEXT_KEY",),
                        implemented=False,
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(ValueError, match="not implemented yet"):
        add_config_auth(
            tmp_path / "config.toml",
            "testai",
            env={"TESTAI_API_KEY": "secret-key"},
            auth_kind="future_api_key_env",
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


def _doctor_provider(result, provider: str):
    return next(item for item in result["providers"] if item["provider"] == provider)


def _auth_method(methods, auth_kind: str):
    return next(method for method in methods if method["auth_kind"] == auth_kind)
