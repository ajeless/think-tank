import json

from think_tank.cli import app

from cli_helpers import runner


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
