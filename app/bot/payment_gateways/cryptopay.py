import logging
from datetime import UTC, datetime, timedelta

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

from .cryptopay_api import CryptoPayAPI

logger = logging.getLogger(__name__)

PAYMENT_ID_PREFIX = "cryptopay_"

# DB transaction outlives the invoice by this margin so a last-second payment is
# still catchable by the poller before the cleanup task cancels the row.
_DB_EXPIRY_GRACE_SEC = 3600


def make_payment_id(invoice_id: int | str) -> str:
    return f"{PAYMENT_ID_PREFIX}{invoice_id}"


def invoice_id_from_payment_id(payment_id: str) -> str | None:
    """Extract the Crypto Pay invoice_id from a cryptopay payment_id, or None."""
    if not payment_id.startswith(PAYMENT_ID_PREFIX):
        return None
    return payment_id[len(PAYMENT_ID_PREFIX):]


class CryptoPayGateway(PaymentGateway):
    name = ""
    currency = Currency.RUB
    callback = NavSubscription.PAY_CRYPTOPAY
    is_manual = False
    payment_type = PaymentType.CRYPTOPAY.value

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
        self.name = __("payment:gateway:cryptopay")
        self.app = app
        self.config = config
        self.session = session
        self.storage = storage
        self.bot = bot
        self.i18n = i18n
        self.services = services
        self.api = CryptoPayAPI(
            token=config.shop.CRYPTOPAY_TOKEN,
            testnet=config.shop.CRYPTOPAY_TESTNET,
        )
        logger.info("CryptoPay payment gateway initialized.")

    async def create_payment(self, data: SubscriptionData) -> str:
        ttl_days = self.config.shop.PENDING_PAYMENT_TTL_DAYS
        invoice_ttl_sec = ttl_days * 86400
        # DB transaction lives a grace margin LONGER than the Crypto Pay invoice.
        # A payment is only possible while the invoice is active; keeping the DB
        # row PENDING past the invoice expiry guarantees the poller can still see
        # and activate a last-second payment before the cleanup task cancels it.
        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            seconds=invoice_ttl_sec + _DB_EXPIRY_GRACE_SEC
        )

        invoice = await self.api.create_invoice(
            amount=data.price,
            fiat=self.currency.code,
            payload=str(data.user_id),
            expires_in=invoice_ttl_sec,
        )
        invoice_id = invoice["invoice_id"]
        payment_id = make_payment_id(invoice_id)

        async with self.session() as session:
            transaction = await Transaction.create(
                session=session,
                tg_id=data.user_id,
                subscription=data.pack(),
                payment_id=payment_id,
                status=TransactionStatus.PENDING,
                payment_type=self.payment_type,
                expires_at=expires_at,
            )

        if transaction is None:
            # No PENDING row → the poller would never activate this invoice, so a
            # paid user would get nothing. Fail loudly instead of returning a URL.
            logger.error(
                f"CryptoPay: failed to persist transaction for invoice {invoice_id} "
                f"(user {data.user_id}); aborting payment."
            )
            raise RuntimeError(f"Could not create transaction for invoice {invoice_id}")

        logger.info(
            f"CryptoPay invoice {invoice_id} created for user {data.user_id}: {payment_id}"
        )
        return invoice["bot_invoice_url"]

    async def close(self) -> None:
        await self.api.close()

    async def handle_payment_succeeded(self, payment_id: str) -> None:
        await self._on_payment_succeeded(payment_id)

    async def handle_payment_canceled(self, payment_id: str) -> None:
        await self._on_payment_canceled(payment_id)
