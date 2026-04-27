from typer.testing import CliRunner

from think_tank.cli import app


runner = CliRunner()


def test_cli_help_exits_successfully() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Usage: think" in result.output
    assert "Think Tank local-first idea workspace." in result.output


def test_cli_status_exits_successfully() -> None:
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Think Tank engine ready: True" in result.output


def test_cli_project_init_creates_workspace() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["project", "init", "idea", "--name", "Test Idea"])

    assert result.exit_code == 0
    assert "Created Think Tank workspace:" in result.output
    assert "Initialized state:" in result.output


def test_cli_project_init_requires_name() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["project", "init", "idea"])

    assert result.exit_code != 0
    assert "Missing option" in result.output
