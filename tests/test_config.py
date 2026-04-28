from pathlib import Path

import pytest

from think_tank.config import ConfigFormatError, default_config_path, load_config


def test_load_config_wraps_invalid_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("enabled_providers = [", encoding="utf-8")

    with pytest.raises(ConfigFormatError, match="config TOML is invalid"):
        load_config(config_path)


def test_default_config_path_uses_xdg_config_home() -> None:
    assert default_config_path({"XDG_CONFIG_HOME": "/tmp/config"}) == Path(
        "/tmp/config/think-tank/config.toml"
    )
