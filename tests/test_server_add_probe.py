"""
Regression test for 3xui-shop-71.

Adding a server whose host is syntactically valid but does not actually accept
a 3x-ui login (bare http://IP without the panel base-path — the 3xui-shop-70
class) must be rejected before it is saved, so the pool never goes empty.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.bot.routers.admin_tools.server_handler as sh


def _make(monkeypatch, *, probe_ok):
    monkeypatch.setattr(sh, "_", lambda s: s)
    create_mock = AsyncMock(return_value=SimpleNamespace(name="Dallas"))
    monkeypatch.setattr(sh.Server, "create", create_mock)
    monkeypatch.setattr(sh, "callback_server_management", AsyncMock())

    callback = MagicMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={
        sh.SERVER_NAME_KEY: "Dallas",
        sh.SERVER_HOST_KEY: "http://172.86.123.156:37521",
        sh.SERVER_MAX_CLIENTS_KEY: "100",
    })
    state.set_state = AsyncMock()

    services = MagicMock()
    services.server_pool.probe_connection = AsyncMock(return_value=probe_ok)
    services.server_pool.sync_servers = AsyncMock()
    services.notification.show_popup = AsyncMock()

    return callback, state, services, create_mock


@pytest.mark.asyncio
async def test_bad_host_rejected_not_saved(monkeypatch):
    callback, state, services, create_mock = _make(monkeypatch, probe_ok=False)

    await sh.callback_confirmation(
        callback=callback, user=SimpleNamespace(tg_id=1),
        session=MagicMock(), state=state, services=services,
    )

    create_mock.assert_not_called()
    services.notification.show_popup.assert_awaited_once()
    assert services.notification.show_popup.await_args.kwargs["text"] == (
        "server_management:popup:host_unreachable"
    )


@pytest.mark.asyncio
async def test_good_host_is_saved(monkeypatch):
    callback, state, services, create_mock = _make(monkeypatch, probe_ok=True)

    await sh.callback_confirmation(
        callback=callback, user=SimpleNamespace(tg_id=1),
        session=MagicMock(), state=state, services=services,
    )

    create_mock.assert_awaited_once()
    services.server_pool.sync_servers.assert_awaited_once()
