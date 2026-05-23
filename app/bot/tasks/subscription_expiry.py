import logging
from datetime import UTC, datetime, timedelta

from aiogram.utils.i18n import I18n
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.services import NotificationService, VPNService
from app.db.models import User

logger = logging.getLogger(__name__)


async def notify_users_with_expiring_subscription(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    vpn_service: VPNService,
    notification_service: NotificationService,
) -> None:
    session: AsyncSession
    async with session_factory() as session:
        users = await User.get_all(session=session)

        logger.info(
            f"[Background task] Starting subscription expiration check for {len(users)} users."
        )

        for user in users:
            user_notified_key = f"user:notified:{user.tg_id}"

            # Check if user was recently notified
            if await redis.get(user_notified_key):
                continue

            try:
                client_data = await vpn_service.get_client_data(user)
            except Exception as e:
                logger.warning(f"[Background task] Failed to get client data for user {user.tg_id}: {e}")
                continue

            # Skip if no client data or subscription is unlimited
            if not client_data or client_data._expiry_time == -1:
                continue

            now = datetime.now(UTC)
            expiry_datetime = datetime.fromtimestamp(
                client_data._expiry_time / 1000, UTC
            )
            time_left = expiry_datetime - now

            # Skip if not within the notification threshold
            if not (timedelta(0) < time_left <= timedelta(hours=24)):
                continue

            try:
                await notification_service.notify_by_id(
                    chat_id=user.tg_id,
                    text=i18n.gettext(
                        "task:message:subscription_expiry",
                        locale=user.language_code,
                    ).format(
                        devices=client_data.max_devices,
                        expiry_time=client_data.expiry_time,
                    ),
                )
                await redis.set(user_notified_key, "true", ex=timedelta(hours=24))
                logger.info(f"[Background task] Sent expiry notification to user {user.tg_id}.")
            except Exception as e:
                logger.warning(f"[Background task] Failed to notify user {user.tg_id}: {e}")
        logger.info("[Background task] Subscription check finished.")


def start_scheduler(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    vpn_service: VPNService,
    notification_service: NotificationService,
) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        notify_users_with_expiring_subscription,
        "interval",
        minutes=15,
        args=[session_factory, redis, i18n, vpn_service, notification_service],
        next_run_time=datetime.now(tz=UTC),
    )
    scheduler.start()
