"""Validate the new-install helper and fan with Home Assistant's schemas."""

import asyncio
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from homeassistant.components import input_select
from homeassistant.components.template.config import CONFIG_SECTION_SCHEMA
from homeassistant.core import HomeAssistant


async def main(path):
    config = yaml.safe_load(Path(path).read_text())
    helper = config["input_select"]["lg_g5_energy_saver_homekit"]
    assert helper["options"] == ["Off", "Minimum", "Medium", "Maximum", "Auto"]
    assert "initial" not in helper
    with TemporaryDirectory(prefix="lg-fan-config-") as config_dir:
        HomeAssistant(config_dir)
        input_select.CONFIG_SCHEMA({"input_select": config["input_select"]})
        CONFIG_SECTION_SCHEMA(config["template"][0])
    print("LG helper and template fan configuration passed")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
