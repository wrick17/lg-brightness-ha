"""Validate the new-install helper and fan with Home Assistant's schemas."""

import asyncio
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from homeassistant.components import input_select
from homeassistant.components.template.config import CONFIG_SECTION_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template


async def main(path):
    config = yaml.safe_load(Path(path).read_text())
    helper = config["input_select"]["lg_g5_energy_saver_homekit"]
    assert helper["options"] == ["Off", "Minimum", "Medium", "Maximum"]
    assert "initial" not in helper
    with TemporaryDirectory(prefix="lg-fan-config-") as config_dir:
        hass = HomeAssistant(config_dir)
        input_select.CONFIG_SCHEMA({"input_select": config["input_select"]})
        CONFIG_SECTION_SCHEMA(config["template"][0])
        # The slider is inverted: each option must round-trip through its percentage.
        fan = config["template"][0]["fan"][0]
        expected = {"Maximum": 0, "Medium": 33, "Minimum": 66, "Off": 100}
        for option, percent in expected.items():
            hass.states.async_set("input_select.lg_g5_energy_saver_homekit", option)
            assert int(Template(fan["percentage"], hass).async_render()) == percent, option
            assert Template(fan["state"], hass).async_render() == (option != "Maximum"), option
            assert Template(fan["set_percentage"]["data"]["option"], hass).async_render({"percentage": percent}) == option, option
        # HomeKit may send rounded or in-between values; each maps to the nearest step.
        for percent, option in {1: "Medium", 34: "Medium", 67: "Minimum", 82: "Minimum", 83: "Off", 99: "Off"}.items():
            assert Template(fan["set_percentage"]["data"]["option"], hass).async_render({"percentage": percent}) == option, percent
        assert fan["turn_off"]["data"]["option"] == "Maximum"
        await hass.async_stop(force=True)
    print("LG helper and template fan configuration passed")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
