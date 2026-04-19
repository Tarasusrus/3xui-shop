import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import IsAdmin
from app.bot.models import ServicesContainer
from app.bot.payment_gateways import GatewayFactory
from app.bot.utils.constants import TransactionStatus
from app.bot.utils.navigation import NavAdminTools, NavSubscription
from app.db.models import Transaction, User

logger = logging.getLogger(__name__)
router = Router(name=__name__)

_PAYMENT_TYPE_TO_CALLBACK = {
    "sbp_manual": NavSubscription.PAY_SBP,
    "ton_manual": NavSubscription.PAY_TON,
}


@router.callback_query(F.data.startswith(NavAdminTools.CONFIRM_PAYMENT), IsAdmin())
async def callback_confirm_payment(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    services: ServicesContainer,
    gateway_factory: GatewayFactory,
) -> None:
    payment_id = callback.data.split(":", 1)[1]
    logger.info(f"Admin {user.tg_id} confirming payment {payment_id}")

    transaction = await Transaction.get_by_id(session=session, payment_id=payment_id)

    if not transaction:
        await services.notification.show_popup(
            callback=callback, text=_("admin:popup:payment_not_found")
        )
        return

    if transaction.status != TransactionStatus.PENDING:
        await services.notification.show_popup(
            callback=callback, text=_("admin:popup:payment_already_processed")
        )
        return

    callback_name = _PAYMENT_TYPE_TO_CALLBACK.get(transaction.payment_type)
    if not callback_name:
        logger.error(f"Unknown payment_type {transaction.payment_type} for {payment_id}")
        await services.notification.show_popup(
            callback=callback, text=_("admin:popup:payment_not_found")
        )
        return

    gateway = gateway_factory.get_gateway(callback_name)
    await gateway.handle_payment_succeeded(payment_id)
    await services.notification.show_popup(
        callback=callback, text=_("admin:popup:payment_confirmed")
    )
    logger.info(f"Admin {user.tg_id} confirmed payment {payment_id}")


@router.callback_query(F.data.startswith(NavAdminTools.REJECT_PAYMENT), IsAdmin())
async def callback_reject_payment(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    services: ServicesContainer,
) -> None:
    payment_id = callback.data.split(":", 1)[1]
    logger.info(f"Admin {user.tg_id} rejecting payment {payment_id}")

    transaction = await Transaction.get_by_id(session=session, payment_id=payment_id)

    if not transaction:
        await services.notification.show_popup(
            callback=callback, text=_("admin:popup:payment_not_found")
        )
        return

    if transaction.status != TransactionStatus.PENDING:
        await services.notification.show_popup(
            callback=callback, text=_("admin:popup:payment_already_processed")
        )
        return

    await Transaction.update(
        session=session,
        payment_id=payment_id,
        status=TransactionStatus.REJECTED,
    )

    await services.notification.notify_by_id(
        chat_id=transaction.tg_id,
        text=_("payment:message:rejected").format(payment_id=payment_id),
    )
    await services.notification.show_popup(
        callback=callback, text=_("admin:popup:payment_rejected")
    )
    logger.info(f"Admin {user.tg_id} rejected payment {payment_id}")
