"""
Regression tests for 3xui-shop-41.

Bug: pressing «Купить подписку» (NavSubscription.PROCESS) returned the
"no available servers" popup instead of the payment/duration form.

Invariant: choosing a plan and paying must NOT depend on server availability.
A server is required only when the VPN client is actually created
(VPNService.create_client → assign_server_to_user), never when showing the
duration/payment form.

These tests exercise the real callback_subscription_process handler with a
mocked services container whose server pool is empty.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.routers.subscription import subscription_handler as sh
from app.bot.utils.navigation import NavSubscription


@pytest.fixture(autouse=True)
def _patch_i18n_and_keyboard(monkeypatch):
    """Isolate the handler from gettext context and keyboard building."""
    monkeypatch.setattr(sh, "_", lambda s: s)
    monkeypatch.setattr(sh, "duration_keyboard", lambda **kwargs: MagicMock(name="markup"))


def _make_callback():
    callback = MagicMock(name="callback")
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    return callback


def _make_services(server):
    services = MagicMock(name="services")
    services.server_pool.get_available_server = AsyncMock(return_value=server)
    services.notification.show_popup = AsyncMock()
    return services


@pytest.mark.asyncio
async def test_process_with_no_server_still_shows_form():
    """No server in pool → must show duration form, not the popup."""
    callback = _make_callback()
    services = _make_services(server=None)
    config = SimpleNamespace(shop=SimpleNamespace(CURRENCY="RUB"))
    callback_data = SimpleNamespace(devices=0, state=None)
    user = SimpleNamespace(tg_id=123)

    await sh.callback_subscription_process(
        callback=callback,
        user=user,
        callback_data=callback_data,
        config=config,
        services=services,
    )

    services.notification.show_popup.assert_not_called()
    callback.message.edit_text.assert_awaited_once()
    assert callback_data.state == NavSubscription.DURATION
    assert callback_data.devices == 1


@pytest.mark.asyncio
async def test_process_with_server_shows_form_too():
    """Server present → same form is shown (behavior unchanged for happy path)."""
    callback = _make_callback()
    services = _make_services(server=MagicMock(name="server"))
    config = SimpleNamespace(shop=SimpleNamespace(CURRENCY="RUB"))
    callback_data = SimpleNamespace(devices=0, state=None)
    user = SimpleNamespace(tg_id=123)

    await sh.callback_subscription_process(
        callback=callback,
        user=user,
        callback_data=callback_data,
        config=config,
        services=services,
    )

    services.notification.show_popup.assert_not_called()
    callback.message.edit_text.assert_awaited_once()
    assert callback_data.state == NavSubscription.DURATION
