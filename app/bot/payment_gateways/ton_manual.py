import logging
import uuid
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.utils.i18n import I18n
from aiogram.utils.i18n import lazy_gettext as __
from aiohttp.web import Application
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.payment_gateways import PaymentGateway
from app.bot.utils.constants import Currency, PaymentType, TransactionStatus
from app.bot.utils.navigation import NavSubscription
from app.config import Config
from app.db.models import Transaction

logger = logging.getLogger(__name__)


class TonManual(PaymentGateway):
    name = ""
    currency = Currency.USD
    callback = NavSubscription.PAY_TON
    is_manual = True
    payment_type = PaymentType.TON_MANUAL.value

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
        self.name = __("payment:gateway:ton")
        self.app = app
        self.config = config
        self.session = session
        self.storage = storage
        self.bot = bot
        self.i18n = i18n
        self.services = services
        logger.info("TON manual payment gateway initialized.")

    async def create_payment(self, data: SubscriptionData) -> str:
        payment_id = f"ton_{uuid.uuid4().hex[:16]}"
        expires_at = datetime.utcnow() + timedelta(
            days=self.config.shop.PENDING_PAYMENT_TTL_DAYS
        )

        async with self.session() as session:
            await Transaction.create(
                session=session,
                tg_id=data.user_id,
                subscription=data.pack(),
                payment_id=payment_id,
                status=TransactionStatus.PENDING,
                payment_type=self.payment_type,
                expires_at=expires_at,
            )

        logger.info(f"TON pending payment created for user {data.user_id}: {payment_id}")
        return payment_id

    async def handle_payment_succeeded(self, payment_id: str) -> None:
        await self._on_payment_succeeded(payment_id)

    async def handle_payment_canceled(self, payment_id: str) -> None:
        await self._on_payment_canceled(payment_id)

    def get_requisites(self) -> dict[str, str | float | None]:
        return {
            "address": self.config.shop.TON_ADDRESS,
            "account": self.config.shop.TON_ACCOUNT,
            "price_usdt": self.config.shop.TON_PRICE_USDT,
        }
