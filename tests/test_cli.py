import json
from pathlib import Path

from typer.testing import CliRunner

from think_tank.cli import app
from think_tank.model_client import ModelClientCallError, ModelMessage, ModelResponse
from think_tank.workspace import init_workspace


runner = CliRunner()


class FakeAisuiteModelClient:
    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(content=f"response from {model}: {messages[-1]['role']}")


class FailingAisuiteModelClient:
    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        raise ModelClientCallError("openai", "provider quota failed")


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


def test_cli_ask_requires_project() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["ask", "What next?", "--model", "test:model"])

    assert result.exit_code != 0
    assert "Missing option" in result.output


def test_cli_ask_requires_model() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["ask", "What next?", "--project", "idea"])

    assert result.exit_code != 0
    assert "Missing option" in result.output


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
