from pathlib import Path

from think_tank.cli import app
from think_tank.workspace import init_workspace

from cli_helpers import (
    FakeAisuiteModelClient,
    FailingAisuiteModelClient,
    runner,
)


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
