import json
from pathlib import Path

from think_tank.cli import app

from cli_helpers import FakeQuestionaryResponse, runner


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
        "think_tank.cli_config_auth.questionary.confirm",
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
        "think_tank.cli_config_auth.provider_auth_method_options",
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
        "think_tank.cli_config_auth.questionary.select",
        lambda *args, **kwargs: FakeQuestionaryResponse("local_server"),
    )
    monkeypatch.setattr("think_tank.cli_config_auth.add_config_auth", fake_add_config_auth)

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


def _doctor_provider(payload, provider: str):
    return next(item for item in payload["providers"] if item["provider"] == provider)
