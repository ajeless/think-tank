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
            "GEMINI_API_KEY": "gemini-secret",
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

    gemini = _status(statuses, "gemini")
    assert gemini["ready"] is True
    assert gemini["auth_kind"] == "api_key_env"
    assert gemini["detected_env_vars"] == ["GEMINI_API_KEY"]
    assert "gemini-secret" not in str(gemini)

    google = _status(statuses, "google")
    assert google["ready"] is False
    assert google["auth_kind"] == "service_account_env"
    assert google["missing_env_vars"] == ["GOOGLE_APPLICATION_CREDENTIALS"]


def test_ollama_is_ready_without_secret() -> None:
    statuses = detect_provider_statuses({})

    ollama = _status(statuses, "ollama")
    assert ollama["ready"] is True
    assert ollama["auth_kind"] == "local_server"
    assert ollama["detected_env_vars"] == []


def test_gemini_requires_one_api_key_env_var() -> None:
    statuses = detect_provider_statuses({})

    gemini = _status(statuses, "gemini")
    assert gemini["ready"] is False
    assert gemini["required_env_vars"] == ["GOOGLE_API_KEY", "GEMINI_API_KEY"]
    assert gemini["missing_env_vars"] == ["GOOGLE_API_KEY", "GEMINI_API_KEY"]


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
            "implemented": True,
            "official": True,
            "selectable": True,
            "support_status": "implemented",
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
            "implemented": True,
            "official": True,
            "selectable": True,
            "support_status": "implemented",
            "detected_env_vars": ["TESTAI_URL"],
            "required_env_vars": [],
            "missing_env_vars": [],
            "notes": [],
        },
    ]
    assert "secret-key" not in str(options)


def test_packaged_provider_auth_method_options_exclude_deferred_subscription_paths() -> None:
    options = provider_auth_method_options("openai", env={"OPENAI_API_KEY": "sk-secret"})

    api_key = _option(options, "api_key_env")
    assert api_key["implemented"] is True
    assert api_key["official"] is True
    assert api_key["ready"] is True
    assert api_key["selectable"] is True
    assert api_key["support_status"] == "implemented"
    assert "subscription_official" not in [
        option["auth_kind"] for option in options
    ]
    assert "sk-secret" not in str(options)


def test_provider_auth_method_options_can_report_unimplemented_official_paths(
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

    options = provider_auth_method_options("testai", env={})

    future = _option(options, "future_api_key_env")
    assert future["implemented"] is False
    assert future["official"] is True
    assert future["ready"] is False
    assert future["selectable"] is False
    assert future["support_status"] == "planned_official"


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


def _option(options, auth_kind: str):
    return next(option for option in options if option["auth_kind"] == auth_kind)
