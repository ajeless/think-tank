from pathlib import Path

from typer.testing import CliRunner

from think_tank.cli import app
from think_tank.model_client import ModelMessage, ModelResponse
from think_tank.workspace import init_workspace


runner = CliRunner()


class FakeAisuiteModelClient:
    def complete(self, *, model: str, messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(content=f"response from {model}: {messages[-1]['role']}")


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
