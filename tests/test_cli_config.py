import json
from pathlib import Path

from think_tank.cli import app

from cli_helpers import (
    AuthFailingAisuiteModelClient,
    FakeAisuiteModelClient,
    FakeGeminiModelRegistry,
    FakeOllamaHttpModelRegistry,
    runner,
)


def test_cli_config_doctor_reports_env_names_without_secret_values() -> None:
    result = runner.invoke(
        app,
        ["config", "doctor"],
        env={
            "OPENAI_API_KEY": "sk-secret",
            "ANTHROPIC_API_KEY": "anthropic-secret",
        },
    )

    assert result.exit_code == 0
    assert "OPENAI_API_KEY" in result.output
    assert "ANTHROPIC_API_KEY" in result.output
    assert "sk-secret" not in result.output
    assert "anthropic-secret" not in result.output


def test_cli_config_doctor_does_not_warn_about_unconfigured_vertex_for_gemini() -> None:
    result = runner.invoke(
        app,
        ["config", "doctor"],
        env={
            "GEMINI_API_KEY": "gemini-secret",
            "GOOGLE_PROJECT_ID": "",
            "GOOGLE_REGION": "",
            "GOOGLE_APPLICATION_CREDENTIALS": "",
        },
    )

    assert result.exit_code == 0
    assert "Gemini API: ready=yes" in result.output
    assert "GEMINI_API_KEY" in result.output
    assert "Google Vertex AI" not in result.output
    assert "GOOGLE_PROJECT_ID" not in result.output
    assert "gemini-secret" not in result.output


def test_cli_config_doctor_json_reports_ready_status_without_secret_values() -> None:
    result = runner.invoke(
        app,
        ["config", "doctor", "--json"],
        env={"OPENROUTER_API_KEY": "or-secret"},
    )

    assert result.exit_code == 0
    statuses = json.loads(result.output)
    openrouter = next(status for status in statuses if status["provider"] == "openrouter")
    assert openrouter["ready"] is True
    assert openrouter["detected_env_vars"] == ["OPENROUTER_API_KEY"]
    assert '"provider": "openrouter"' in result.output
    assert "or-secret" not in result.output


def test_cli_config_init_yes_writes_non_secret_config() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["config", "init", "--yes", "--config", "config.toml"],
            env={"OPENAI_API_KEY": "sk-secret"},
        )
        config_text = Path("config.toml").read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert "Wrote config:" in result.output
    assert "openai" in result.output
    assert "sk-secret" not in config_text
    assert "OPENAI_API_KEY" in config_text


def test_cli_config_validate_reports_success_without_secret_values(monkeypatch) -> None:
    monkeypatch.setattr("think_tank.cli_config.AisuiteModelClient", FakeAisuiteModelClient)

    result = runner.invoke(
        app,
        [
            "config",
            "validate",
            "--provider",
            "openai",
            "--model",
            "openai:gpt-4o",
        ],
        env={"OPENAI_API_KEY": "sk-secret"},
    )

    assert result.exit_code == 0
    assert "Provider: openai" in result.output
    assert "Model: openai:gpt-4o" in result.output
    assert "Status: success" in result.output
    assert "sk-secret" not in result.output


def test_cli_config_validate_supports_gemini_api_key(monkeypatch) -> None:
    monkeypatch.setattr("think_tank.cli_config.AisuiteModelClient", FakeAisuiteModelClient)

    result = runner.invoke(
        app,
        [
            "config",
            "validate",
            "--provider",
            "gemini",
            "--model",
            "gemini:gemini-3.1-pro-preview",
        ],
        env={"GEMINI_API_KEY": "gemini-secret"},
    )

    assert result.exit_code == 0
    assert "Provider: gemini" in result.output
    assert "Model: gemini:gemini-3.1-pro-preview" in result.output
    assert "Status: success" in result.output
    assert "gemini-secret" not in result.output


def test_cli_config_validate_reports_missing_credentials_without_traceback() -> None:
    result = runner.invoke(
        app,
        [
            "config",
            "validate",
            "--provider",
            "openai",
            "--model",
            "openai:gpt-4o",
        ],
        env={"OPENAI_API_KEY": ""},
    )

    assert result.exit_code == 1
    assert "Status: missing credentials" in result.output
    assert "OPENAI_API_KEY" in result.output
    assert "Traceback" not in result.output


def test_cli_config_validate_reports_auth_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "think_tank.cli_config.AisuiteModelClient",
        AuthFailingAisuiteModelClient,
    )

    result = runner.invoke(
        app,
        [
            "config",
            "validate",
            "--provider",
            "openai",
            "--model",
            "openai:gpt-4o",
        ],
        env={"OPENAI_API_KEY": "sk-secret"},
    )

    assert result.exit_code == 1
    assert "Status: auth failure" in result.output
    assert "invalid API key" in result.output
    assert "sk-secret" not in result.output


def test_cli_config_validate_checks_ollama_model_with_fake_registry(monkeypatch) -> None:
    monkeypatch.setattr(
        "think_tank.cli_config.OllamaHttpModelRegistry",
        FakeOllamaHttpModelRegistry,
    )

    result = runner.invoke(
        app,
        [
            "config",
            "validate",
            "--provider",
            "ollama",
            "--model",
            "ollama:llama3.1:8b",
        ],
    )

    assert result.exit_code == 0
    assert "Provider: ollama" in result.output
    assert "Status: success" in result.output


def test_cli_config_models_list_reports_gemini_ids_without_secret_values(monkeypatch) -> None:
    monkeypatch.setattr(
        "think_tank.cli_config_available_models.GeminiModelRegistry",
        FakeGeminiModelRegistry,
    )

    result = runner.invoke(
        app,
        ["config", "models", "list", "--provider", "gemini"],
        env={"GEMINI_API_KEY": "gemini-secret"},
    )

    assert result.exit_code == 0
    assert "Provider: gemini" in result.output
    assert "Status: success" in result.output
    assert "gemini:gemini-3-flash-preview" in result.output
    assert "Gemini 3 Flash Preview" in result.output
    assert "generateContent" in result.output
    assert "gemini-secret" not in result.output


def test_cli_config_models_list_json_reports_gemini_ids(monkeypatch) -> None:
    monkeypatch.setattr(
        "think_tank.cli_config_available_models.GeminiModelRegistry",
        FakeGeminiModelRegistry,
    )

    result = runner.invoke(
        app,
        ["config", "models", "list", "--provider", "gemini", "--json"],
        env={"GOOGLE_API_KEY": "google-secret"},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["models"][0]["model"] == "gemini:gemini-3-flash-preview"
    assert payload["models"][0]["supported_actions"] == [
        "generateContent",
        "countTokens",
    ]
    assert "google-secret" not in result.output


def test_cli_config_models_list_reports_missing_credentials_without_traceback() -> None:
    result = runner.invoke(
        app,
        ["config", "models", "list", "--provider", "gemini"],
        env={"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""},
    )

    assert result.exit_code == 1
    assert "Status: missing credentials" in result.output
    assert "GEMINI_API_KEY" in result.output
    assert "Traceback" not in result.output


def test_cli_config_models_list_reports_unsupported_provider_without_traceback() -> None:
    result = runner.invoke(
        app,
        ["config", "models", "list", "--provider", "openai"],
        env={"OPENAI_API_KEY": "sk-secret"},
    )

    assert result.exit_code == 1
    assert "Status: not supported" in result.output
    assert "openai" in result.output
    assert "sk-secret" not in result.output
    assert "Traceback" not in result.output
