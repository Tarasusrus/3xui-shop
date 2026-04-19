import logging
from datetime import datetime

from aiogram import Bot
from aiogram.utils.i18n import I18n
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.utils.constants import PaymentType, TransactionStatus
from app.db.models import Transaction

logger = logging.getLogger(__name__)

MANUAL_PAYMENT_TYPES = {PaymentType.SBP_MANUAL.value, PaymentType.TON_MANUAL.value}


async def cancel_expired_transactions(
    session_factory: async_sessionmaker,
    bot: Bot,
    i18n: I18n,
) -> None:
    session: AsyncSession
    async with session_factory() as session:
        now = datetime.utcnow()  # naive UTC — matches expires_at stored by payment gateways
        stmt = select(Transaction).where(
            Transaction.status == TransactionStatus.PENDING,
            Transaction.expires_at <= now,
        )
        result = await session.execute(stmt)
        expired_transactions = result.scalars().all()

        if not expired_transactions:
            logger.info("[Background check] No expired transactions found.")
            return

        logger.info(
            f"[Background check] Found {len(expired_transactions)} expired transactions."
        )

        for transaction in expired_transactions:
            if transaction.payment_type in MANUAL_PAYMENT_TYPES:
                transaction.status = TransactionStatus.EXPIRED
                try:
                    text = i18n.gettext("payment:event:payment_canceled", locale="ru")
                    await bot.send_message(chat_id=transaction.tg_id, text=text)
                except Exception as e:
                    logger.warning(
                        f"[Background check] Failed to notify user {transaction.tg_id}: {e}"
                    )
            else:
                transaction.status = TransactionStatus.CANCELED

        await session.commit()
        logger.info("[Background check] Expired transactions processed.")


def start_scheduler(
    session: async_sessionmaker,
    bot: Bot,
    i18n: I18n,
) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        cancel_expired_transactions,
        "interval",
        minutes=15,
        args=[session, bot, i18n],
        next_run_time=datetime.utcnow(),
    )
    scheduler.start()
