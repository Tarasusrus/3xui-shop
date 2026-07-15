import logging
from abc import ABC, abstractmethod

from aiogram import Bot
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.utils.i18n import I18n
from aiogram.utils.i18n import gettext as _
from aiohttp.web import Application
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.utils.constants import (
    EVENT_PAYMENT_CANCELED_TAG,
    EVENT_PAYMENT_SUCCEEDED_TAG,
    Currency,
    TransactionStatus,
)
from app.bot.utils.formatting import format_device_count, format_subscription_period
from app.config import Config
from app.db.models import Transaction, User

logger = logging.getLogger(__name__)



class PaymentGateway(ABC):
    name: str
    currency: Currency
    callback: str
    is_manual: bool = False
    payment_type: str | None = None

    def __init__(
        self,
        app: Application,
        config: Config,
        session: async_sessionmaker,
        storage: RedisStorage,
        bot: Bot,
        i18n: I18n,
        services: ServicesContainer,
    ) -> None:
        self.app = app
        self.config = config
        self.session = session
        self.storage = storage
        self.bot = bot
        self.i18n = i18n
        self.services = services

    @abstractmethod
    async def create_payment(self, data: SubscriptionData) -> str:
        pass

    @abstractmethod
    async def handle_payment_succeeded(self, payment_id: str) -> None:
        pass

    @abstractmethod
    async def handle_payment_canceled(self, payment_id: str) -> None:
        pass

    async def close(self) -> None:
        """Release any long-lived resources (e.g. HTTP sessions). No-op by default."""
        return

    async def _activate_subscription(self, user: User, data: SubscriptionData) -> bool:
        """Provision/extend/change the VPN. Returns True on confirmed success.

        For a new subscription, `create_subscription` returns False both on a
        real failure (3x-ui down / empty pool) and when the client already
        exists. An existing client is an idempotent success, so a re-delivered
        payment does not loop forever — we fall back to `is_client_exists`.
        """
        if data.is_extend:
            ok = await self.services.vpn.extend_subscription(
                user=user, devices=data.devices, duration=data.duration
            )
            if ok:
                logger.info(f"Subscription extended for user {user.tg_id}")
            return ok
        if data.is_change:
            ok = await self.services.vpn.change_subscription(
                user=user, devices=data.devices, duration=data.duration
            )
            if ok:
                logger.info(f"Subscription changed for user {user.tg_id}")
            return ok

        created = await self.services.vpn.create_subscription(
            user=user, devices=data.devices, duration=data.duration
        )
        if created:
            logger.info(f"Subscription created for user {user.tg_id}")
            return True
        if await self.services.vpn.is_client_exists(user):
            logger.info(f"Subscription client already exists for user {user.tg_id}; treating as success.")
            return True
        return False

    async def _mark_retry_notified(self, payment_id: str) -> None:
        """Persist that the user/dev have been told about a stalled activation.

        Gates the failure-path notifications so a PENDING transaction re-polled
        every 60s does not spam the user and developer each cycle. Set only
        after the notifications were sent. See 3xui-shop-67.
        """
        async with self.session() as session:
            await Transaction.update(
                session=session, payment_id=payment_id, retry_notified=True
            )

    async def _notify_activation_success(self, user: User, data: SubscriptionData) -> None:
        if data.is_extend:
            await self.services.notification.notify_extend_success(user_id=user.tg_id, data=data)
        elif data.is_change:
            await self.services.notification.notify_change_success(user_id=user.tg_id, data=data)
        else:
            key = await self.services.vpn.get_key(user)
            await self.services.notification.notify_purchase_success(user_id=user.tg_id, key=key)

    async def _on_payment_succeeded(self, payment_id: str) -> None:
        logger.info(f"Payment succeeded {payment_id}")

        async with self.session() as session:
            transaction = await Transaction.get_by_id(session=session, payment_id=payment_id)
            if transaction.status == TransactionStatus.COMPLETED:
                logger.warning(f"Payment {payment_id} already completed, skipping.")
                return
            data = SubscriptionData.unpack(transaction.subscription)
            logger.debug(f"Subscription data unpacked: {data}")
            user = await User.get(session=session, tg_id=data.user_id)

        # A paid transaction whose user row is missing (deleted account / desync)
        # cannot be activated. Do NOT dereference `user` further — abort with a
        # developer alert and leave the transaction PENDING for manual review,
        # otherwise the poller would AttributeError-loop forever. See 3xui-shop-66.
        if user is None:
            logger.error(
                f"Payment {payment_id}: user {data.user_id} not found in DB; "
                f"cannot activate. Transaction left PENDING for manual review."
            )
            if not transaction.retry_notified:
                await self.services.notification.notify_developer(
                    text=f"{EVENT_PAYMENT_SUCCEEDED_TAG}\n\n"
                    f"⚠️ Payment <code>{payment_id}</code>: user <code>{data.user_id}</code> "
                    f"not found in DB — activation skipped, transaction left PENDING.",
                )
                await self._mark_retry_notified(payment_id)
            return

        locale = user.language_code

        # Provision the VPN BEFORE marking the transaction COMPLETED. If 3x-ui is
        # unavailable or the pool is empty, activation fails and the transaction
        # stays PENDING, so the CryptoPay poller (or an admin re-confirm for SBP)
        # retries it — instead of leaving a paid-but-keyless COMPLETED record.
        # All exactly-once side effects (COMPLETED, referral rewards, success
        # notification) run only after confirmed activation. See 3xui-shop-64.
        with self.i18n.use_locale(locale):
            activated = await self._activate_subscription(user=user, data=data)

        if not activated:
            logger.error(
                f"Activation failed for payment {payment_id} "
                f"(3x-ui unavailable / empty pool); transaction left PENDING for retry."
            )
            if not transaction.retry_notified:
                with self.i18n.use_locale(locale):
                    await self.services.notification.notify_developer(
                        text=EVENT_PAYMENT_SUCCEEDED_TAG
                        + "\n\n"
                        + _("payment:event:activation_failed").format(
                            payment_id=payment_id,
                            user_id=user.tg_id,
                        ),
                    )
                    await self.services.notification.notify_by_id(
                        chat_id=user.tg_id,
                        text=_("payment:message:activation_pending"),
                    )
                await self._mark_retry_notified(payment_id)
            return

        async with self.session() as session:
            await Transaction.update(
                session=session,
                payment_id=payment_id,
                status=TransactionStatus.COMPLETED,
            )

        if self.config.shop.REFERRER_REWARD_ENABLED:
            await self.services.referral.add_referrers_rewards_on_payment(
                referred_tg_id=data.user_id,
                payment_amount=data.price,  # TODO: (!) add currency unified processing
                payment_id=payment_id,
                duration=data.duration,
            )

        from app.bot.routers.main_menu.handler import redirect_to_main_menu

        with self.i18n.use_locale(locale):
            await self.services.notification.notify_developer(
                text=EVENT_PAYMENT_SUCCEEDED_TAG
                + "\n\n"
                + _("payment:event:payment_succeeded").format(
                    payment_id=payment_id,
                    user_id=user.tg_id,
                    devices=format_device_count(data.devices),
                    duration=format_subscription_period(data.duration),
                ),
            )
            await redirect_to_main_menu(
                bot=self.bot,
                user=user,
                services=self.services,
                config=self.config,
                storage=self.storage,
            )
            await self._notify_activation_success(user=user, data=data)

    async def _on_payment_canceled(self, payment_id: str) -> None:
        logger.info(f"Payment canceled {payment_id}")
        async with self.session() as session:
            transaction = await Transaction.get_by_id(session=session, payment_id=payment_id)
            data = SubscriptionData.unpack(transaction.subscription)

            await Transaction.update(
                session=session,
                payment_id=payment_id,
                status=TransactionStatus.CANCELED,
            )

        await self.services.notification.notify_developer(
            text=EVENT_PAYMENT_CANCELED_TAG
            + "\n\n"
            + _("payment:event:payment_canceled").format(
                payment_id=payment_id,
                user_id=data.user_id,
                devices=format_device_count(data.devices),
                duration=format_subscription_period(data.duration),
            ),
        )
