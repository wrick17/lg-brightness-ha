"""Exercise the patched webOS host update against an unpacked override checkout."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))

from homeassistant.components import ssdp  # noqa: E402
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST  # noqa: E402
from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_UDN, SsdpServiceInfo  # noqa: E402
from custom_components.webostv import (  # noqa: E402
    WEBOSTV_SSDP_ST,
    _async_register_ssdp_callback,
    _update_host_from_ssdp,
)

UUID = "00000000-0000-0000-0000-000000000001"
OLD_HOST = "old.example"
NEW_HOST = "new.example"


class ConfigEntries:
    def __init__(self):
        self.reloads = []

    def async_update_entry(self, entry, *, data):
        entry.data = data

    def async_schedule_reload(self, entry_id):
        self.reloads.append(entry_id)


def setup():
    entries = ConfigEntries()
    hass = SimpleNamespace(config_entries=entries)
    entry = SimpleNamespace(
        unique_id=UUID,
        entry_id="entry-id",
        data={CONF_HOST: OLD_HOST, CONF_CLIENT_SECRET: "test-key"},
        async_on_unload=Mock(),
    )
    return hass, entry, entries


def discovery(uuid=UUID, host=NEW_HOST, st=WEBOSTV_SSDP_ST):
    return SsdpServiceInfo(
        ssdp_usn=f"uuid:{uuid}::{st}",
        ssdp_st=st,
        ssdp_location=f"http://{host}:1303/",
        upnp={ATTR_UPNP_UDN: f"uuid:{uuid}"},
    )


async def main():
    hass, entry, entries = setup()
    remove_callback = Mock()

    async def register(hass_arg, callback, match):
        assert hass_arg is hass
        assert match == {"st": WEBOSTV_SSDP_ST}
        callback(discovery(), ssdp.SsdpChange.ALIVE)
        return remove_callback

    with patch.object(ssdp, "async_register_callback", side_effect=register):
        await _async_register_ssdp_callback(hass, entry)

    assert entry.data == {CONF_HOST: NEW_HOST, CONF_CLIENT_SECRET: "test-key"}
    assert entries.reloads == [entry.entry_id]
    entry.async_on_unload.assert_called_once_with(remove_callback)
    entry.async_on_unload.call_args.args[0]()
    remove_callback.assert_called_once_with()

    for info, change in (
        (discovery(host=OLD_HOST), ssdp.SsdpChange.ALIVE),
        (discovery(uuid="another-tv"), ssdp.SsdpChange.ALIVE),
        (discovery(), ssdp.SsdpChange.BYEBYE),
        (discovery(st="urn:other-service"), ssdp.SsdpChange.ALIVE),
    ):
        other_hass, other_entry, other_entries = setup()
        _update_host_from_ssdp(other_hass, other_entry, info, change)
        assert other_entry.data[CONF_HOST] == OLD_HOST
        assert other_entries.reloads == []

    malformed_hass, malformed_entry, malformed_entries = setup()
    malformed = discovery()
    malformed.ssdp_location = "http://[invalid/"
    _update_host_from_ssdp(malformed_hass, malformed_entry, malformed, ssdp.SsdpChange.ALIVE)
    assert malformed_entry.data[CONF_HOST] == OLD_HOST
    assert malformed_entries.reloads == []
    print("webOS SSDP host recovery passed")


if __name__ == "__main__":
    asyncio.run(main())
