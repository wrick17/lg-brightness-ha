# LG TV brightness control in Apple Home

This Home Assistant setup presents an LG TV's five Energy Saving settings as an Apple Home fan: Off (0%), Minimum (25%), Medium (50%), Maximum (75%), and Auto (100%). The fan writes a dropdown helper. An automation reads that request, applies it through the TV's webOS alert API, then reads the physical setting back. When the TV is on, a one-minute reconciliation repairs missed changes after a connection interruption or a repeated selection of the same value.

The tested setup used Home Assistant Core 2026.1.3 and an LG G5. Other webOS models or firmware may handle the alert API differently. The fan and helper show the requested setting; a `settings/getSystemSettings` readback is the proof of the TV's actual setting.

## Install

For an **existing installation**, keep the paired LG integration, HomeKit bridge, helper, and fan. Back up the current LG automation, then replace only that automation with [automations.yaml](automations.yaml). Replace every `media_player.lg_tv` in the file with your existing TV entity ID. If your helper has a different ID, replace `input_select.lg_g5_energy_saver_homekit` consistently in both files. Remove any `initial` setting from the existing dropdown so Home Assistant restores the last selection on restart. Do not create a second helper or fan with the same purpose.

For a **new installation**, merge the entries in [configuration.example.yaml](configuration.example.yaml) into `configuration.yaml` under its existing `input_select:` and `template:` sections, then add the one entry from [automations.yaml](automations.yaml) to `automations.yaml`. Avoid duplicate top-level YAML keys. Replace `media_player.lg_tv` throughout the automation with your TV entity ID. Expose the resulting fan, normally `fan.lg_g5_energy_saver_slider`, through your HomeKit bridge. Check the actual entity ID before adding it to an explicit bridge include list. The example deliberately omits `initial`; on the first startup the dropdown uses its first option, then restores its last state on later starts. [Home Assistant documents this restore behavior](https://www.home-assistant.io/integrations/input_select/#restore-state).

The webOS integration used here is [wrick17/ha-webostv-unsigned](https://github.com/wrick17/ha-webostv-unsigned) at commit `98bb01ba156fb4d49df4080f2c5d5e788c7b0ace`, an Apache-2.0 override of Home Assistant Core 2026.1.3's component that pins `aiowebostv==0.9.2`. This version includes the secure websocket fallback after a plain-port timeout and SSDP address recovery. Integration setup, reconnect, and pairing use the same fixed client. HACS downloads from the updated repository retain both repairs.

Use it on a trusted LAN; matching an SSDP UUID is not device authentication. Run these commands from this repository's root to obtain the tested component:

```sh
git clone https://github.com/wrick17/ha-webostv-unsigned.git ha-webostv-unsigned
git -C ha-webostv-unsigned checkout 98bb01ba156fb4d49df4080f2c5d5e788c7b0ace
```

Back up any existing `custom_components/webostv` before installing the component. Copy `ha-webostv-unsigned/custom_components/webostv` into your Home Assistant `custom_components` directory and restart Home Assistant after validating the configuration. The existing paired config entry does not need to be deleted. For an existing HACS installation, download the updated override from the same custom repository and restart Home Assistant.

[webostv-ssdp.patch](webostv-ssdp.patch) remains available for the older override at commit `29dc852bc450c73611b39faa8b74fc2a02eaa5d7`. CI applies it to that exact commit and checks that the resulting component matches the fixed version above. Do not apply it to the new version, which already contains the repairs.

The setter uses `system.notifications/createAlert` with a fixed `luna://com.webos.settingsservice/setSystemSettings` callback, closes the alert, and requires `settings/getSystemSettings` readback. It does not call the direct settings setter, which failed on the tested TV. Failed writes leave the requested slider position in place and post one persistent notification; successful readback clears it. The automation retains a 200 ms helper debounce, queued execution, two verified write attempts, and a one-minute online reconciliation. The reconciliation skips the TV while Home Assistant reports it off, unknown, or unavailable.

## Verify

Run these checks with Python from a Home Assistant 2026.1.3 installation. The SSDP and connection tests take the override checkout directory as their final argument:

```sh
python3 tests/test_configuration.py configuration.example.yaml
python3 tests/test_recovery.py automations.yaml
python3 tests/test_ssdp.py ha-webostv-unsigned
python3 tests/test_connection.py ha-webostv-unsigned
```

The GitHub Actions `regression` check runs these tests on pushes and pull requests. It is required on `main` in both repositories, including for administrators. The override also verifies its Core 2026.1.3 provenance and diagnostics redaction. A Home Assistant or dependency upgrade must update the supported pins and pass these checks before merging. These checks use fake responses; they cannot prove physical TV behavior.

After installation, check Home Assistant's configuration, change the Apple Home fan once, and read the TV's `energySaving` value through `webostv.command` using `settings/getSystemSettings`. Repeat after a TV wake or connection loss. A visible fan percentage alone does not verify the physical TV.

The [work log](WORK_LOG.md) records what passed on the original setup and what remains untested. The tests use fake device responses and do not change a TV.
