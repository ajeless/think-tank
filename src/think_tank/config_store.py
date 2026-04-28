"""Filesystem and TOML helpers for Think Tank user configuration."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Mapping


CONFIG_DIR_NAME = "think-tank"
CONFIG_FILE_NAME = "config.toml"


class ConfigNotFoundError(FileNotFoundError):
    """Raised when a requested Think Tank config file does not exist."""


class ConfigFormatError(ValueError):
    """Raised when a Think Tank config file has an unsupported shape."""


def default_config_path(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    if xdg_config_home := env.get("XDG_CONFIG_HOME"):
        return Path(xdg_config_home) / CONFIG_DIR_NAME / CONFIG_FILE_NAME
    return Path.home() / ".config" / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def load_config(config_path: Path) -> dict[str, object]:
    resolved_path = config_path.expanduser()
    try:
        return tomllib.loads(resolved_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigFormatError(f"config TOML is invalid: {resolved_path}: {exc}") from exc


def write_config_text(config_path: Path, text: str) -> None:
    resolved_path = config_path.expanduser()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(text, encoding="utf-8")


def toml_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\b", "\\b")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\f", "\\f")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'
