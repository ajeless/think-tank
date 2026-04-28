import json

from think_tank.cli import app

from cli_helpers import runner


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
