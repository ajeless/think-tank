import pytest

from think_tank.provider_registry import (
    ProviderAuthMethodSpec,
    ProviderSpec,
    detect_provider_statuses,
    provider_auth_method_options,
    provider_env_var_names,
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


def test_provider_env_var_names_deduplicates_auth_method_env_vars() -> None:
    spec = ProviderSpec(
        name="testai",
        display_name="Test AI",
        auth_methods=(
            ProviderAuthMethodSpec(
                auth_kind="api_key_env",
                env_vars=("TESTAI_API_KEY", "TESTAI_URL"),
            ),
            ProviderAuthMethodSpec(
                auth_kind="local_server",
                env_vars=("TESTAI_URL",),
            ),
        ),
    )

    assert provider_env_var_names(spec) == ("TESTAI_API_KEY", "TESTAI_URL")


def test_provider_spec_requires_auth_method() -> None:
    with pytest.raises(ValueError, match="must define at least one auth method"):
        ProviderSpec(name="testai", display_name="Test AI", auth_methods=())


def _status(statuses, provider: str):
    return next(status for status in statuses if status["provider"] == provider)
