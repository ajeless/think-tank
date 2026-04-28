from pathlib import Path

from think_tank.cli import app
from think_tank.workspace import init_workspace

from cli_helpers import FakeQuestionaryResponse, runner


def test_cli_init_guides_auth_profile_and_default_without_storing_secrets(
    monkeypatch,
) -> None:
    confirm_answers = iter([True, True])
    text_answers = iter(["fast", "openai:gpt-4o"])

    monkeypatch.setattr(
        "think_tank.cli.questionary.checkbox",
        lambda *args, **kwargs: FakeQuestionaryResponse(
            [
                {"provider": "openai", "auth_kind": "api_key_env"},
                {"provider": "ollama", "auth_kind": "local_server"},
            ]
        ),
    )
    monkeypatch.setattr(
        "think_tank.cli.questionary.confirm",
        lambda *args, **kwargs: FakeQuestionaryResponse(next(confirm_answers)),
    )
    monkeypatch.setattr(
        "think_tank.cli.questionary.text",
        lambda *args, **kwargs: FakeQuestionaryResponse(next(text_answers)),
    )

    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["init", "--config", "config.toml"],
            env={"OPENAI_API_KEY": "sk-secret"},
        )
        config_text = Path("config.toml").read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert "Wrote config:" in result.output
    assert "Enabled auth paths: openai:api_key_env, ollama:local_server" in result.output
    assert "Model profile: fast = openai:gpt-4o" in result.output
    assert "Explicit default model profile: fast" in result.output
    assert "Secret values were not stored." in result.output
    assert "Work commands do not use defaults automatically yet." in result.output
    assert "sk-secret" not in result.output
    assert "sk-secret" not in config_text
    assert "OPENAI_API_KEY" in config_text
    assert '[models."fast"]' in config_text
    assert "[defaults]" in config_text


def test_cli_init_can_skip_model_profile(monkeypatch) -> None:
    monkeypatch.setattr(
        "think_tank.cli.questionary.checkbox",
        lambda *args, **kwargs: FakeQuestionaryResponse(
            [{"provider": "ollama", "auth_kind": "local_server"}]
        ),
    )
    monkeypatch.setattr(
        "think_tank.cli.questionary.confirm",
        lambda *args, **kwargs: FakeQuestionaryResponse(False),
    )

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init", "--config", "config.toml"])
        config_text = Path("config.toml").read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert "Enabled auth paths: ollama:local_server" in result.output
    assert "Model profile:" not in result.output
    assert "[defaults]" not in config_text


def test_cli_init_default_does_not_make_ask_use_defaults(monkeypatch) -> None:
    confirm_answers = iter([True, True])
    text_answers = iter(["fast", "openai:gpt-4o"])

    monkeypatch.setattr(
        "think_tank.cli.questionary.checkbox",
        lambda *args, **kwargs: FakeQuestionaryResponse(
            [{"provider": "ollama", "auth_kind": "local_server"}]
        ),
    )
    monkeypatch.setattr(
        "think_tank.cli.questionary.confirm",
        lambda *args, **kwargs: FakeQuestionaryResponse(next(confirm_answers)),
    )
    monkeypatch.setattr(
        "think_tank.cli.questionary.text",
        lambda *args, **kwargs: FakeQuestionaryResponse(next(text_answers)),
    )

    with runner.isolated_filesystem():
        init_workspace(Path("idea"), name="Test Idea")
        init_result = runner.invoke(app, ["init", "--config", "config.toml"])
        ask_result = runner.invoke(
            app,
            ["ask", "What next?", "--project", "idea", "--config", "config.toml"],
        )

    assert init_result.exit_code == 0
    assert ask_result.exit_code != 0
    assert "--model <provider:model>" in ask_result.output
    assert "--model-profile" in ask_result.output
    assert "Traceback" not in ask_result.output
