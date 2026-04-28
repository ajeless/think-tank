import json
from pathlib import Path

from typer.testing import CliRunner

from think_tank.cli import app
from think_tank.model_client import (
    ModelClientAuthenticationError,
    ModelClientCallError,
    ModelMessage,
    ModelResponse,
)
from think_tank.workspace import init_workspace


runner = CliRunner()


class FakeAisuiteModelClient:
    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(content=f"response from {model}: {messages[-1]['role']}")


class FailingAisuiteModelClient:
    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        raise ModelClientCallError("openai", "provider quota failed")


class AuthFailingAisuiteModelClient:
    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        raise ModelClientAuthenticationError("openai", "invalid API key")


class FakeOllamaHttpModelRegistry:
    def __init__(self, models: list[str]) -> None:
        self.models = models

    @classmethod
    def from_env(cls, env):
        return cls(models=["llama3.1:8b"])

    def list_models(self) -> list[str]:
        return self.models


class FakeQuestionaryResponse:
    def __init__(self, answer) -> None:
        self.answer = answer

    def ask(self):
        return self.answer


def test_cli_help_exits_successfully() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Usage: think" in result.output
    assert "Think Tank local-first idea workspace." in result.output
    assert "new" in result.output


def test_cli_status_exits_successfully() -> None:
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Think Tank engine ready: True" in result.output


def test_cli_new_creates_workspace() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["new", "idea", "--name", "Test Idea"])

    assert result.exit_code == 0
    assert "Created Think Tank workspace:" in result.output
    assert "Initialized state:" in result.output


def test_cli_new_requires_name() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["new", "idea"])

    assert result.exit_code != 0
    assert "Missing option" in result.output


def test_cli_project_init_is_not_registered() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["project", "init", "idea", "--name", "Test Idea"])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_cli_ask_records_response(monkeypatch) -> None:
    monkeypatch.setattr("think_tank.cli.AisuiteModelClient", FakeAisuiteModelClient)
    with runner.isolated_filesystem():
        init_workspace(Path("idea"), name="Test Idea")
        result = runner.invoke(
            app,
            ["ask", "What next?", "--project", "idea", "--model", "test:model"],
        )

    assert result.exit_code == 0
    assert "response from test:model: user" in result.output


def test_cli_ask_uses_model_profile(monkeypatch) -> None:
    monkeypatch.setattr("think_tank.cli.AisuiteModelClient", FakeAisuiteModelClient)
    with runner.isolated_filesystem():
        init_workspace(Path("idea"), name="Test Idea")
        add_result = runner.invoke(
            app,
            [
                "config",
                "model",
                "add",
                "fast",
                "--model",
                "groq:llama-3.1-8b",
                "--config",
                "config.toml",
            ],
        )
        result = runner.invoke(
            app,
            [
                "ask",
                "What next?",
                "--project",
                "idea",
                "--model-profile",
                "fast",
                "--config",
                "config.toml",
            ],
        )

    assert add_result.exit_code == 0
    assert result.exit_code == 0
    assert "response from groq:llama-3.1-8b: user" in result.output


def test_cli_ask_rejects_model_and_profile_together(monkeypatch) -> None:
    monkeypatch.setattr("think_tank.cli.AisuiteModelClient", FakeAisuiteModelClient)
    with runner.isolated_filesystem():
        init_workspace(Path("idea"), name="Test Idea")
        result = runner.invoke(
            app,
            [
                "ask",
                "What next?",
                "--project",
                "idea",
                "--model",
                "openai:gpt-4o",
                "--model-profile",
                "fast",
            ],
        )

    assert result.exit_code != 0
    assert "use either --model or --model-profile" in result.output
    assert "Traceback" not in result.output


def test_cli_ask_reports_missing_model_profile_without_traceback(monkeypatch) -> None:
    monkeypatch.setattr("think_tank.cli.AisuiteModelClient", FakeAisuiteModelClient)
    with runner.isolated_filesystem():
        init_workspace(Path("idea"), name="Test Idea")
        runner.invoke(
            app,
            [
                "config",
                "model",
                "add",
                "fast",
                "--model",
                "groq:llama-3.1-8b",
                "--config",
                "config.toml",
            ],
        )
        result = runner.invoke(
            app,
            [
                "ask",
                "What next?",
                "--project",
                "idea",
                "--model-profile",
                "missing",
                "--config",
                "config.toml",
            ],
        )

    assert result.exit_code != 0
    assert "model profile not found: missing" in result.output
    assert "Traceback" not in result.output


def test_cli_ask_requires_project() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["ask", "What next?", "--model", "test:model"])

    assert result.exit_code != 0
    assert "Missing option" in result.output


def test_cli_ask_requires_model() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["ask", "What next?", "--project", "idea"])

    assert result.exit_code != 0
    assert "--model <provider:model>" in result.output
    assert "--model-profile" in result.output
    assert "Traceback" not in result.output


def test_cli_ask_requires_prompt() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["ask", "--project", "idea", "--model", "test:model"])

    assert result.exit_code != 0
    assert "Missing argument" in result.output


def test_cli_ask_reports_missing_project_state(monkeypatch) -> None:
    monkeypatch.setattr("think_tank.cli.AisuiteModelClient", FakeAisuiteModelClient)
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["ask", "What next?", "--project", "missing", "--model", "test:model"],
        )

    assert result.exit_code != 0
    assert "project state not found" in result.output


def test_cli_ask_reports_provider_error_without_traceback(monkeypatch) -> None:
    monkeypatch.setattr("think_tank.cli.AisuiteModelClient", FailingAisuiteModelClient)
    with runner.isolated_filesystem():
        init_workspace(Path("idea"), name="Test Idea")
        result = runner.invoke(
            app,
            ["ask", "What next?", "--project", "idea", "--model", "openai:gpt-4o"],
        )

    assert result.exit_code != 0
    assert "provider quota failed" in result.output
    assert "Traceback" not in result.output


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


def test_cli_config_model_add_list_remove() -> None:
    with runner.isolated_filesystem():
        add_result = runner.invoke(
            app,
            [
                "config",
                "model",
                "add",
                "fast",
                "--model",
                "groq:llama-3.1-8b",
                "--config",
                "config.toml",
            ],
        )
        list_result = runner.invoke(
            app,
            ["config", "model", "list", "--config", "config.toml", "--json"],
        )
        remove_result = runner.invoke(
            app,
            ["config", "model", "remove", "fast", "--config", "config.toml"],
        )
        final_list_result = runner.invoke(
            app,
            ["config", "model", "list", "--config", "config.toml", "--json"],
        )

    assert add_result.exit_code == 0
    assert "Added model profile fast" in add_result.output
    assert "Model: groq:llama-3.1-8b" in add_result.output
    assert "default model" in add_result.output
    payload = json.loads(list_result.output)
    assert payload["profiles"] == [
        {
            "name": "fast",
            "model": "groq:llama-3.1-8b",
        }
    ]
    assert remove_result.exit_code == 0
    assert "Removed model profile fast" in remove_result.output
    assert json.loads(final_list_result.output)["profiles"] == []


def test_cli_config_model_add_rejects_unknown_provider_without_traceback() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "config",
                "model",
                "add",
                "future",
                "--model",
                "futureai:model",
                "--config",
                "config.toml",
            ],
        )

    assert result.exit_code != 0
    assert "unsupported model provider: futureai" in result.output
    assert "Traceback" not in result.output


def test_cli_config_model_list_reports_missing_config() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["config", "model", "list", "--config", "missing.toml"],
        )

    assert result.exit_code != 0
    assert "config not found" in result.output
    assert "Traceback" not in result.output


def test_cli_config_defaults_set_list_remove() -> None:
    with runner.isolated_filesystem():
        add_result = runner.invoke(
            app,
            [
                "config",
                "model",
                "add",
                "fast",
                "--model",
                "groq:llama-3.1-8b",
                "--config",
                "config.toml",
            ],
        )
        set_result = runner.invoke(
            app,
            [
                "config",
                "defaults",
                "set",
                "--model-profile",
                "fast",
                "--config",
                "config.toml",
            ],
        )
        list_result = runner.invoke(
            app,
            ["config", "defaults", "list", "--config", "config.toml", "--json"],
        )
        remove_result = runner.invoke(
            app,
            ["config", "defaults", "remove", "model-profile", "--config", "config.toml"],
        )
        final_list_result = runner.invoke(
            app,
            ["config", "defaults", "list", "--config", "config.toml", "--json"],
        )

    assert add_result.exit_code == 0
    assert set_result.exit_code == 0
    assert "Updated defaults" in set_result.output
    assert "Model profile: fast" in set_result.output
    assert "work commands do not use them automatically" in set_result.output
    assert json.loads(list_result.output)["defaults"] == {
        "model_profile": "fast",
    }
    assert remove_result.exit_code == 0
    assert "Removed default model-profile" in remove_result.output
    assert json.loads(final_list_result.output)["defaults"] == {
        "model_profile": None,
    }


def test_cli_config_defaults_set_requires_existing_profile() -> None:
    with runner.isolated_filesystem():
        runner.invoke(
            app,
            [
                "config",
                "model",
                "add",
                "fast",
                "--model",
                "groq:llama-3.1-8b",
                "--config",
                "config.toml",
            ],
        )
        result = runner.invoke(
            app,
            [
                "config",
                "defaults",
                "set",
                "--model-profile",
                "missing",
                "--config",
                "config.toml",
            ],
        )

    assert result.exit_code != 0
    assert "model profile not found: missing" in result.output
    assert "Traceback" not in result.output


def test_cli_ask_does_not_use_config_defaults(monkeypatch) -> None:
    monkeypatch.setattr("think_tank.cli.AisuiteModelClient", FakeAisuiteModelClient)
    with runner.isolated_filesystem():
        init_workspace(Path("idea"), name="Test Idea")
        runner.invoke(
            app,
            [
                "config",
                "model",
                "add",
                "fast",
                "--model",
                "groq:llama-3.1-8b",
                "--config",
                "config.toml",
            ],
        )
        runner.invoke(
            app,
            [
                "config",
                "defaults",
                "set",
                "--model-profile",
                "fast",
                "--config",
                "config.toml",
            ],
        )
        result = runner.invoke(
            app,
            ["ask", "What next?", "--project", "idea", "--config", "config.toml"],
        )

    assert result.exit_code != 0
    assert "--model <provider:model>" in result.output
    assert "--model-profile" in result.output
    assert "Traceback" not in result.output


def test_cli_config_auth_list_reports_metadata_without_secret_values() -> None:
    with runner.isolated_filesystem():
        init_result = runner.invoke(
            app,
            ["config", "init", "--yes", "--config", "config.toml"],
            env={
                "OPENAI_API_KEY": "sk-secret",
                "ANTHROPIC_API_KEY": "",
                "GROQ_API_KEY": "gsk-secret",
                "OPENROUTER_API_KEY": "",
            },
        )
        result = runner.invoke(app, ["config", "auth", "list", "--config", "config.toml"])

    assert init_result.exit_code == 0
    assert result.exit_code == 0
    assert "openai: auth_kind=api_key_env; env_vars=OPENAI_API_KEY" in result.output
    assert "groq: auth_kind=api_key_env; env_vars=GROQ_API_KEY" in result.output
    assert "sk-secret" not in result.output
    assert "gsk-secret" not in result.output


def test_cli_config_auth_doctor_reports_detection_without_config() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["config", "auth", "doctor", "--config", "missing.toml"],
            env={
                "OPENAI_API_KEY": "",
                "ANTHROPIC_API_KEY": "",
                "GROQ_API_KEY": "gsk-secret",
                "OPENROUTER_API_KEY": "",
            },
        )

    assert result.exit_code == 0
    assert "Config: missing.toml (not found)" in result.output
    assert "Groq (groq): configured=no; detected=yes; ready=yes" in result.output
    assert "detected_env_vars=GROQ_API_KEY" in result.output
    assert "gsk-secret" not in result.output


def test_cli_config_auth_doctor_json_combines_config_and_detection() -> None:
    with runner.isolated_filesystem():
        runner.invoke(
            app,
            ["config", "init", "--yes", "--config", "config.toml"],
            env={
                "OPENAI_API_KEY": "sk-secret",
                "ANTHROPIC_API_KEY": "",
                "GROQ_API_KEY": "gsk-secret",
                "OPENROUTER_API_KEY": "",
            },
        )
        result = runner.invoke(
            app,
            ["config", "auth", "doctor", "--config", "config.toml", "--json"],
            env={
                "OPENAI_API_KEY": "",
                "ANTHROPIC_API_KEY": "",
                "GROQ_API_KEY": "gsk-secret",
                "OPENROUTER_API_KEY": "",
            },
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_found"] is True
    openai = _doctor_provider(payload, "openai")
    assert openai["configured"] is True
    assert openai["detected"] is False
    assert openai["configured_env_vars"] == ["OPENAI_API_KEY"]
    assert openai["missing_env_vars"] == ["OPENAI_API_KEY"]
    groq = _doctor_provider(payload, "groq")
    assert groq["configured"] is True
    assert groq["detected"] is True
    assert groq["detected_env_vars"] == ["GROQ_API_KEY"]
    assert "sk-secret" not in result.output
    assert "gsk-secret" not in result.output


def test_cli_config_auth_list_json_reports_metadata_without_secret_values() -> None:
    with runner.isolated_filesystem():
        runner.invoke(
            app,
            ["config", "init", "--yes", "--config", "config.toml"],
            env={
                "OPENAI_API_KEY": "",
                "ANTHROPIC_API_KEY": "",
                "GROQ_API_KEY": "gsk-secret",
                "OPENROUTER_API_KEY": "",
            },
        )
        result = runner.invoke(
            app,
            ["config", "auth", "list", "--config", "config.toml", "--json"],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["providers"] == [
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
        }
    ]
    assert "gsk-secret" not in result.output


def test_cli_config_auth_list_reports_missing_config() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["config", "auth", "list", "--config", "missing.toml"],
        )

    assert result.exit_code != 0
    assert "config not found" in result.output
    assert "Traceback" not in result.output


def test_cli_config_auth_add_yes_creates_config_without_secret_values() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["config", "auth", "add", "groq", "--yes", "--config", "config.toml"],
            env={"GROQ_API_KEY": "gsk-secret"},
        )
        config_text = Path("config.toml").read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert "Added auth metadata for groq" in result.output
    assert "Auth kind: api_key_env" in result.output
    assert "Env vars: GROQ_API_KEY" in result.output
    assert "Secret values were not stored." in result.output
    assert "gsk-secret" not in result.output
    assert "gsk-secret" not in config_text
    assert "GROQ_API_KEY" in config_text


def test_cli_config_auth_add_yes_reports_missing_env_without_traceback() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["config", "auth", "add", "openai", "--yes", "--config", "config.toml"],
            env={"OPENAI_API_KEY": ""},
        )
        config_exists = Path("config.toml").exists()

    assert result.exit_code != 0
    assert "missing required environment variable(s): OPENAI_API_KEY" in result.output
    assert "Traceback" not in result.output
    assert not config_exists


def test_cli_config_auth_add_yes_adds_ollama_without_secret_values() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["config", "auth", "add", "ollama", "--yes", "--config", "config.toml"],
        )
        payload = json.loads(
            runner.invoke(
                app,
                ["config", "auth", "list", "--config", "config.toml", "--json"],
            ).output
        )

    assert result.exit_code == 0
    assert "Added auth metadata for ollama" in result.output
    assert "Auth kind: local_server" in result.output
    assert "Env vars: -" in result.output
    assert payload["providers"] == [
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
        }
    ]


def test_cli_config_auth_add_interactive_confirms_single_ready_method(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "think_tank.cli.questionary.confirm",
        lambda *args, **kwargs: FakeQuestionaryResponse(True),
    )

    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["config", "auth", "add", "ollama", "--config", "config.toml"],
        )
        payload = json.loads(
            runner.invoke(
                app,
                ["config", "auth", "list", "--config", "config.toml", "--json"],
            ).output
        )

    assert result.exit_code == 0
    assert "Added auth metadata for ollama" in result.output
    assert payload["providers"][0]["auth_kind"] == "local_server"
    assert payload["providers"][0]["auth_methods"] == [
        {
            "auth_kind": "local_server",
            "env_vars": [],
        }
    ]


def test_cli_config_auth_add_interactive_selects_between_ready_methods(
    monkeypatch,
) -> None:
    captured = {}

    def fake_add_config_auth(config_path, provider, *, env, auth_kind=None):
        captured["auth_kind"] = auth_kind
        return {
            "config_path": str(config_path),
            "provider": provider,
            "added": True,
            "auth_kind": auth_kind,
            "env_vars": ["TESTAI_URL"],
            "enabled_providers": [provider],
        }

    monkeypatch.setattr(
        "think_tank.cli.provider_auth_method_options",
        lambda provider, *, env: [
            {
                "provider": provider,
                "display_name": "Test AI",
                "auth_kind": "api_key_env",
                "ready": True,
                "detected_env_vars": ["TESTAI_API_KEY"],
                "required_env_vars": ["TESTAI_API_KEY"],
                "missing_env_vars": [],
                "notes": [],
            },
            {
                "provider": provider,
                "display_name": "Test AI",
                "auth_kind": "local_server",
                "ready": True,
                "detected_env_vars": ["TESTAI_URL"],
                "required_env_vars": [],
                "missing_env_vars": [],
                "notes": [],
            },
        ],
    )
    monkeypatch.setattr(
        "think_tank.cli.questionary.select",
        lambda *args, **kwargs: FakeQuestionaryResponse("local_server"),
    )
    monkeypatch.setattr("think_tank.cli.add_config_auth", fake_add_config_auth)

    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["config", "auth", "add", "testai", "--config", "config.toml"],
            env={"TESTAI_API_KEY": "secret-key", "TESTAI_URL": "http://localhost"},
        )

    assert result.exit_code == 0
    assert captured["auth_kind"] == "local_server"
    assert "Auth kind: local_server" in result.output
    assert "Env vars: TESTAI_URL" in result.output
    assert "secret-key" not in result.output


def test_cli_config_auth_remove_updates_config_without_touching_secrets() -> None:
    with runner.isolated_filesystem():
        runner.invoke(
            app,
            ["config", "init", "--yes", "--config", "config.toml"],
            env={
                "OPENAI_API_KEY": "sk-secret",
                "ANTHROPIC_API_KEY": "",
                "GROQ_API_KEY": "gsk-secret",
                "OPENROUTER_API_KEY": "",
            },
        )
        result = runner.invoke(
            app,
            ["config", "auth", "remove", "groq", "--config", "config.toml"],
        )
        list_result = runner.invoke(
            app,
            ["config", "auth", "list", "--config", "config.toml", "--json"],
        )

    assert result.exit_code == 0
    assert "Removed auth metadata for groq" in result.output
    assert "No environment files" in result.output
    assert "provider accounts" in result.output
    assert "local models" in result.output
    assert "gsk-secret" not in result.output
    payload = json.loads(list_result.output)
    assert [provider["provider"] for provider in payload["providers"]] == [
        "openai",
        "ollama",
    ]


def test_cli_config_auth_remove_is_idempotent_for_absent_provider() -> None:
    with runner.isolated_filesystem():
        runner.invoke(
            app,
            ["config", "init", "--yes", "--config", "config.toml"],
            env={
                "OPENAI_API_KEY": "sk-secret",
                "ANTHROPIC_API_KEY": "",
                "GROQ_API_KEY": "",
                "OPENROUTER_API_KEY": "",
            },
        )
        result = runner.invoke(
            app,
            ["config", "auth", "remove", "groq", "--config", "config.toml"],
        )

    assert result.exit_code == 0
    assert "No auth metadata for groq was present" in result.output


def test_cli_config_validate_reports_success_without_secret_values(monkeypatch) -> None:
    monkeypatch.setattr("think_tank.cli.AisuiteModelClient", FakeAisuiteModelClient)

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
        "think_tank.cli.AisuiteModelClient",
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
        "think_tank.cli.OllamaHttpModelRegistry",
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


def _doctor_provider(payload, provider: str):
    return next(item for item in payload["providers"] if item["provider"] == provider)
