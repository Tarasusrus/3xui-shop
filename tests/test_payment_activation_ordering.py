"""
Regression tests for 3xui-shop-64.

Bug: PaymentGateway._on_payment_succeeded marked Transaction -> COMPLETED
*before* provisioning the VPN and ignored the provisioning result. If 3x-ui was
unavailable or the server pool was empty, the user was charged, the transaction
was COMPLETED, but no key was ever issued and there was no retry.

Invariants under test (architect decision, variant A):
1. Transaction -> COMPLETED happens ONLY after activation actually succeeds.
2. All exactly-once side effects (referral rewards, success notification) fire
   ONLY after COMPLETED — never on a failed/retried activation.
3. On failure the transaction stays PENDING (poller / admin can retry) and a
   developer alert is sent.
4. "Client already exists" counts as success (idempotent retry), not failure.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.utils.i18n import I18n

import app.bot.payment_gateways._gateway as gw
from app.bot.utils.constants import TransactionStatus


@pytest.fixture
def i18n():
    """Real I18n over the project locales so gettext calls resolve."""
    inst = I18n(path=Path("app/locales"), default_locale="ru", domain="bot")
    I18n.set_current(inst)
    return inst


class _ConcreteGateway(gw.PaymentGateway):
    async def create_payment(self, data):  # pragma: no cover - not exercised
        return "id"

    async def handle_payment_succeeded(self, payment_id):  # pragma: no cover
        await self._on_payment_succeeded(payment_id)

    async def handle_payment_canceled(self, payment_id):  # pragma: no cover
        return


class _FakeTxn:
    def __init__(self, status=TransactionStatus.PENDING):
        self.status = status
        self.subscription = "packed"
        self.retry_notified = False


def _make_gateway(monkeypatch, i18n, *, create_ok, exists, is_extend=False, is_change=False):
    """Build a PaymentGateway with all external deps mocked."""
    txn = _FakeTxn()
    user = SimpleNamespace(tg_id=42, language_code="ru")
    data = SimpleNamespace(
        user_id=42, price=100, duration=30, devices=1,
        is_extend=is_extend, is_change=is_change,
    )

    # DB model classmethods.
    monkeypatch.setattr(gw.Transaction, "get_by_id", AsyncMock(return_value=txn))

    async def _update(session, payment_id, **kwargs):
        for field, value in kwargs.items():
            setattr(txn, field, value)
    update_mock = AsyncMock(side_effect=_update)
    monkeypatch.setattr(gw.Transaction, "update", update_mock)
    monkeypatch.setattr(gw.User, "get", AsyncMock(return_value=user))
    monkeypatch.setattr(gw.SubscriptionData, "unpack", staticmethod(lambda s: data))

    # redirect_to_main_menu is imported lazily inside the method.
    import app.bot.routers.main_menu.handler as mm
    monkeypatch.setattr(mm, "redirect_to_main_menu", AsyncMock())

    # Session context manager.
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    session_cm.__aexit__ = AsyncMock(return_value=False)
    session_factory = MagicMock(return_value=session_cm)

    gateway = _ConcreteGateway.__new__(_ConcreteGateway)
    gateway.session = session_factory
    gateway.config = SimpleNamespace(
        shop=SimpleNamespace(REFERRER_REWARD_ENABLED=True),
    )
    gateway.bot = MagicMock()
    gateway.storage = MagicMock()
    gateway.i18n = i18n

    services = MagicMock()
    services.vpn.create_subscription = AsyncMock(return_value=create_ok)
    services.vpn.extend_subscription = AsyncMock(return_value=create_ok)
    services.vpn.change_subscription = AsyncMock(return_value=create_ok)
    services.vpn.is_client_exists = AsyncMock(return_value=exists)
    services.vpn.get_key = AsyncMock(return_value="vless://key")
    services.referral.add_referrers_rewards_on_payment = AsyncMock()
    services.notification.notify_developer = AsyncMock()
    services.notification.notify_purchase_success = AsyncMock()
    services.notification.notify_extend_success = AsyncMock()
    services.notification.notify_change_success = AsyncMock()
    services.notification.notify_by_id = AsyncMock()
    gateway.services = services

    return gateway, txn, update_mock, services


def _completed_calls(update_mock):
    return [
        c for c in update_mock.call_args_list
        if c.kwargs.get("status") == TransactionStatus.COMPLETED
    ]


@pytest.mark.asyncio
async def test_activation_failure_keeps_pending_and_grants_nothing(monkeypatch, i18n):
    """Empty pool / 3x-ui down: no COMPLETED, no rewards, no success notice."""
    gateway, txn, update_mock, services = _make_gateway(
        monkeypatch, i18n, create_ok=False, exists=False,
    )

    await gateway._on_payment_succeeded("cryptopay_1")

    assert txn.status == TransactionStatus.PENDING
    assert _completed_calls(update_mock) == []
    services.referral.add_referrers_rewards_on_payment.assert_not_called()
    services.notification.notify_purchase_success.assert_not_called()
    services.notification.notify_developer.assert_awaited()  # dev alert


@pytest.mark.asyncio
async def test_activation_success_completes_and_grants_once(monkeypatch, i18n):
    """Happy path: COMPLETED set, rewards + success notice fire exactly once."""
    gateway, txn, update_mock, services = _make_gateway(
        monkeypatch, i18n, create_ok=True, exists=False,
    )

    await gateway._on_payment_succeeded("cryptopay_2")

    assert txn.status == TransactionStatus.COMPLETED
    assert len(_completed_calls(update_mock)) == 1
    services.referral.add_referrers_rewards_on_payment.assert_awaited_once()
    services.notification.notify_purchase_success.assert_awaited_once()


@pytest.mark.asyncio
async def test_existing_client_counts_as_success(monkeypatch, i18n):
    """create returns False but client already exists -> idempotent success."""
    gateway, txn, update_mock, services = _make_gateway(
        monkeypatch, i18n, create_ok=False, exists=True,
    )

    await gateway._on_payment_succeeded("cryptopay_3")

    assert txn.status == TransactionStatus.COMPLETED
    assert len(_completed_calls(update_mock)) == 1
    services.referral.add_referrers_rewards_on_payment.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_user_does_not_crash_and_alerts_dev(monkeypatch, i18n):
    """user=None (deleted/desynced) must not crash the poller (3xui-shop-66)."""
    gateway, txn, update_mock, services = _make_gateway(
        monkeypatch, i18n, create_ok=True, exists=False,
    )
    monkeypatch.setattr(gw.User, "get", AsyncMock(return_value=None))

    # Must not raise AttributeError.
    await gateway._on_payment_succeeded("cryptopay_5")

    assert txn.status == TransactionStatus.PENDING
    assert _completed_calls(update_mock) == []
    services.vpn.create_subscription.assert_not_called()
    services.notification.notify_developer.assert_awaited_once()
    services.notification.notify_purchase_success.assert_not_called()


@pytest.mark.asyncio
async def test_activation_failure_notifies_once_across_retries(monkeypatch, i18n):
    """5 failed poll cycles → exactly one user + one dev notice (3xui-shop-67)."""
    gateway, txn, _update_mock, services = _make_gateway(
        monkeypatch, i18n, create_ok=False, exists=False,
    )

    for _ in range(5):
        await gateway._on_payment_succeeded("cryptopay_6")

    assert txn.status == TransactionStatus.PENDING
    assert txn.retry_notified is True
    assert services.notification.notify_by_id.await_count == 1
    assert services.notification.notify_developer.await_count == 1


@pytest.mark.asyncio
async def test_missing_user_notifies_dev_once_across_retries(monkeypatch, i18n):
    """user=None over 5 cycles → exactly one dev alert, no spam (3xui-shop-67)."""
    gateway, txn, _update_mock, services = _make_gateway(
        monkeypatch, i18n, create_ok=True, exists=False,
    )
    monkeypatch.setattr(gw.User, "get", AsyncMock(return_value=None))

    for _ in range(5):
        await gateway._on_payment_succeeded("cryptopay_7")

    assert txn.retry_notified is True
    assert services.notification.notify_developer.await_count == 1


@pytest.mark.asyncio
async def test_already_completed_is_noop(monkeypatch, i18n):
    """Idempotency: re-delivery of a COMPLETED payment does nothing."""
    gateway, txn, update_mock, services = _make_gateway(
        monkeypatch, i18n, create_ok=True, exists=False,
    )
    txn.status = TransactionStatus.COMPLETED

    await gateway._on_payment_succeeded("cryptopay_4")

    assert _completed_calls(update_mock) == []
    services.vpn.create_subscription.assert_not_called()
    services.referral.add_referrers_rewards_on_payment.assert_not_called()
    services.notification.notify_purchase_success.assert_not_called()
