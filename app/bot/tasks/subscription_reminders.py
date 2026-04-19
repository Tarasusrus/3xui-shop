import logging
from datetime import datetime, timedelta, timezone

from aiogram.utils.i18n import I18n
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.services import NotificationService, VPNService
from app.db.models import User

logger = logging.getLogger(__name__)

_7D_LOWER = timedelta(days=6, hours=12)
_7D_UPPER = timedelta(days=7, hours=12)
_3D_LOWER = timedelta(days=2, hours=12)
_3D_UPPER = timedelta(days=3, hours=12)


async def send_subscription_reminders(
    session_factory: async_sessionmaker,
    i18n: I18n,
    vpn_service: VPNService,
    notification_service: NotificationService,
) -> None:
    async with session_factory() as session:
        users = await User.get_all(session=session)

        logger.info(
            f"[Background task] Starting subscription reminder check for {len(users)} users."
        )

        for user in users:
            client_data = await vpn_service.get_client_data(user)

            if not client_data or client_data._expiry_time == -1:
                continue

            now = datetime.now(timezone.utc)
            expiry_datetime = datetime.fromtimestamp(
                client_data._expiry_time / 1000, timezone.utc
            )
            time_left = expiry_datetime - now

            if time_left <= timedelta(0):
                continue

            if _7D_LOWER < time_left <= _7D_UPPER and user.reminded_7d_at is None:
                await notification_service.notify_by_id(
                    chat_id=user.tg_id,
                    text=i18n.gettext(
                        "subscription:ntf:reminder_7d",
                        locale=user.language_code,
                    ).format(
                        devices=client_data.max_devices,
                        expiry_time=client_data.expiry_time,
                    ),
                )
                await User.update(
                    session=session,
                    tg_id=user.tg_id,
                    reminded_7d_at=now,
                )
                logger.info(f"[Background task] Sent 7d reminder to user {user.tg_id}.")

            elif _3D_LOWER < time_left <= _3D_UPPER and user.reminded_3d_at is None:
                await notification_service.notify_by_id(
                    chat_id=user.tg_id,
                    text=i18n.gettext(
                        "subscription:ntf:reminder_3d",
                        locale=user.language_code,
                    ).format(
                        devices=client_data.max_devices,
                        expiry_time=client_data.expiry_time,
                    ),
                )
                await User.update(
                    session=session,
                    tg_id=user.tg_id,
                    reminded_3d_at=now,
                )
                logger.info(f"[Background task] Sent 3d reminder to user {user.tg_id}.")

        logger.info("[Background task] Subscription reminder check finished.")


def start_scheduler(
    session_factory: async_sessionmaker,
    i18n: I18n,
    vpn_service: VPNService,
    notification_service: NotificationService,
) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_subscription_reminders,
        "interval",
        hours=1,
        args=[session_factory, i18n, vpn_service, notification_service],
        next_run_time=datetime.now(tz=timezone.utc),
    )
    scheduler.start()
