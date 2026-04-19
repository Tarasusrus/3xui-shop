import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.utils.i18n import I18n
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.services import ReferralService
from app.db.models import ReferrerReward, User

logger = logging.getLogger(__name__)


async def reward_pending_referrals_after_payment(
    session_factory: async_sessionmaker,
    referral_service: ReferralService,
    bot: Bot,
    i18n: I18n,
) -> None:
    async with session_factory() as session:
        stmt = select(ReferrerReward).where(ReferrerReward.rewarded_at.is_(None))
        result = await session.execute(stmt)
        pending_rewards = result.scalars().all()

        logger.info(f"[Background check] Found {len(pending_rewards)} not proceed rewards.")

        for reward in pending_rewards:
            success = await referral_service.process_referrer_rewards_after_payment(reward=reward)
            if not success:
                logger.warning(
                    f"[Background check] Reward {reward.id} was NOT proceed successfully."
                )
                continue

            user = await User.get(session=session, tg_id=reward.user_tg_id)
            if not user:
                continue

            days = int(reward.amount)
            try:
                await bot.send_message(
                    chat_id=reward.user_tg_id,
                    text=i18n.gettext(
                        "referral:ntf:bonus_received",
                        locale=user.language_code,
                    ).format(days=days),
                )
            except TelegramAPIError as e:
                logger.warning(
                    f"[Background check] Failed to notify user {reward.user_tg_id} about referral reward: {e}"
                )

        logger.info("[Background check] Referrer rewards check finished.")


def start_scheduler(
    session_factory: async_sessionmaker,
    referral_service: ReferralService,
    bot: Bot,
    i18n: I18n,
) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        reward_pending_referrals_after_payment,
        "interval",
        minutes=15,
        args=[session_factory, referral_service, bot, i18n],
        next_run_time=datetime.now(),
    )
    scheduler.start()
