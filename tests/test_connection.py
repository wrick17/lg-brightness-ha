"""Verify plain-port timeout recovery for setup, reconnect, and pairing."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import aiohttp

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))

from custom_components import webostv as integration  # noqa: E402
from custom_components.webostv import WebOsClient, config_flow, media_player  # noqa: E402
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST  # noqa: E402
from custom_components.webostv.config_flow import WebOsClient as PairingClient  # noqa: E402


async def main():
    assert PairingClient is WebOsClient
    for failure in (
        TimeoutError(),
        aiohttp.ClientConnectionError(),
        aiohttp.WSServerHandshakeError(None, (), status=400),
    ):
        client = WebOsClient("tv.example", client_key="test-key")
        socket = object()
        client._ws_connect = AsyncMock(side_effect=[failure, socket])
        assert await client._create_main_ws() is socket
        assert [call.args[0] for call in client._ws_connect.call_args_list] == [
            "ws://tv.example:3000", "wss://tv.example:3001"
        ]
        assert client.client_key == "test-key"

    client = WebOsClient("tv.example", client_key="test-key")
    socket = object()
    client._ws_connect = AsyncMock(return_value=socket)
    assert await client._create_main_ws() is socket
    assert client._ws_connect.await_count == 1

    client._ws_connect = AsyncMock(side_effect=[TimeoutError(), TimeoutError()])
    try:
        await client._create_main_ws()
    except TimeoutError:
        pass
    else:
        raise AssertionError("Both ports failing must propagate the failure")
    assert client._ws_connect.await_count == 2

    client._ws_connect = AsyncMock(side_effect=asyncio.CancelledError())
    try:
        await client._create_main_ws()
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("Cancellation must propagate")
    assert client._ws_connect.await_count == 1
    # Exercise the actual constructors, then the media player's reconnect caller.
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()),
        async_create_task=lambda coroutine: coroutine.close(),
        bus=SimpleNamespace(async_listen_once=Mock()),
        data={integration.DOMAIN: {integration.DATA_HASS_CONFIG: {}}},
    )
    entry = SimpleNamespace(
        data={CONF_HOST: "tv.example", CONF_CLIENT_SECRET: "test-key"},
        title="Test TV", unique_id="test-tv", entry_id="test-entry",
        options={}, async_on_unload=Mock(),
    )
    with (
        patch.object(WebOsClient, "connect", new_callable=AsyncMock) as connect,
        patch.object(integration, "async_get_clientsession", return_value=object()),
        patch.object(integration, "update_client_key"),
        patch.object(integration, "_async_register_ssdp_callback", new_callable=AsyncMock),
        patch.object(config_flow, "async_get_clientsession", return_value=object()),
        patch.object(media_player, "update_client_key"),
    ):
        assert await integration.async_setup_entry(hass, entry)
        assert type(entry.runtime_data) is WebOsClient
        paired = await config_flow.async_control_connect(hass, "tv.example", "test-key")
        assert type(paired) is WebOsClient
        entity = media_player.LgWebOSMediaPlayerEntity(entry)
        entity.hass = hass
        await entity.async_update()
        assert connect.await_count == 3
        assert entity.available
    print("webOS connection timeout recovery passed")


if __name__ == "__main__":
    asyncio.run(main())
