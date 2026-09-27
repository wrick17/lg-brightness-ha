"""Exercise the LG automation with Home Assistant's real Script runner.

Run on a host with Home Assistant installed:
    python test_recovery.py automations.yaml
"""

import asyncio
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from homeassistant.core import Context, HomeAssistant, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script, async_validate_actions_config


TV = "media_player.lg_tv"
HELPER = "input_select.lg_g5_energy_saver_homekit"


async def scenario(actions, *, initial, desired, trigger, fail_create=0, fail_create_at=None, apply=True, change_helper=None, tv_state="on"):
    with TemporaryDirectory(prefix="lg-g5-script-") as config_dir:
        hass = HomeAssistant(config_dir)
        hass.states.async_set(TV, tv_state)
        hass.states.async_set(HELPER, desired)
        physical = initial
        create_count = 0
        calls = []
        notifications = []

        async def command(call):
            nonlocal physical, fail_create, create_count
            name = call.data["command"]
            calls.append(name)
            if name == "settings/getSystemSettings":
                return {TV: {"returnValue": True, "settings": {"energySaving": physical}}}
            if name == "system.notifications/createAlert":
                create_count += 1
                if fail_create or create_count == fail_create_at:
                    if fail_create:
                        fail_create -= 1
                    raise HomeAssistantError("temporary connection failure")
                return {TV: {"returnValue": True, "alertId": "test-alert"}}
            if name == "system.notifications/closeAlert":
                if change_helper:
                    hass.states.async_set(HELPER, change_helper)
                if apply:
                    physical = {"Off": "off", "Minimum": "min", "Medium": "med", "Maximum": "max", "Auto": "auto"}[desired]
                return {TV: {"returnValue": True}}
            raise AssertionError(name)

        async def notification(call):
            notifications.append((call.service, call.data))

        async def select_option(call):
            raise AssertionError("Automation overwrote the requested helper value")

        hass.services.async_register("webostv", "command", command, supports_response=SupportsResponse.ONLY)
        hass.services.async_register("persistent_notification", "create", notification)
        hass.services.async_register("persistent_notification", "dismiss", notification)
        hass.services.async_register("input_select", "select_option", select_option)

        validated_actions = await async_validate_actions_config(hass, cv.SCRIPT_SCHEMA(actions))
        script = Script(hass, validated_actions, "LG test", "automation", script_mode="queued", max_runs=2)
        await script.async_run({"trigger": {"id": trigger}}, context=Context())
        return physical, hass.states.get(HELPER).state, calls, notifications


async def main(path):
    automations = yaml.safe_load(Path(path).read_text())
    assert len(automations) == 1
    automation = next(a for a in automations if a.get("id") == "lg_g5_energy_saver_home_control")
    assert any(t.get("id") == "reconcile" and t.get("trigger") == "time_pattern" and t.get("minutes") == "/1" for t in automation["triggers"])
    assert any(t.get("id") == "helper" and t.get("for") == {"milliseconds": 200} for t in automation["triggers"])

    actions = automation["actions"]

    # A failed command leaves the helper alone; a later timer run repairs the TV.
    physical, helper, calls, notices = await scenario(actions, initial="min", desired="Medium", trigger="helper", fail_create=1)
    assert (physical, helper) == ("min", "Medium")
    assert calls.count("system.notifications/closeAlert") == 0
    assert any(service == "create" for service, _ in notices)
    physical, helper, calls, notices = await scenario(actions, initial=physical, desired=helper, trigger="reconcile")
    assert (physical, helper) == ("med", "Medium"), (physical, helper, calls, notices)
    assert calls.count("system.notifications/closeAlert") == 1

    # The TV can report an active playback state instead of literal "on".
    for active_state in ("playing", "paused", "idle"):
        physical, helper, calls, notices = await scenario(actions, initial="min", desired="Medium", trigger="reconcile", tv_state=active_state)
        assert (physical, helper) == ("med", "Medium"), (active_state, physical, helper, calls)

    # An older in-flight run must not roll back a newer slider selection.
    physical, helper, calls, notices = await scenario(actions, initial="min", desired="Medium", trigger="helper", apply=False, change_helper="Maximum")
    assert (physical, helper) == ("min", "Maximum")
    assert calls.count("system.notifications/createAlert") == 2
    assert any("Maximum" in data.get("message", "") for service, data in notices if service == "create")

    # A failed second create must not reuse the first create's alert ID.
    physical, helper, calls, notices = await scenario(actions, initial="min", desired="Medium", trigger="helper", apply=False, fail_create_at=2)
    assert (physical, helper) == ("min", "Medium")
    assert calls.count("system.notifications/createAlert") == 2
    assert calls.count("system.notifications/closeAlert") == 1

    # A reconciled TV needs only one read, no setter or helper write.
    physical, helper, calls, notices = await scenario(actions, initial="med", desired="Medium", trigger="reconcile")
    assert (physical, helper) == ("med", "Medium")
    assert calls == ["settings/getSystemSettings"]

    # Periodic reconciliation stays quiet while the TV is offline.
    for offline_state in ("off", "unknown", "unavailable"):
        physical, helper, calls, notices = await scenario(actions, initial="min", desired="Medium", trigger="reconcile", tv_state=offline_state)
        assert (physical, helper, calls, notices) == ("min", "Medium", [], []), offline_state

    print("LG recovery Script scenarios passed")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
