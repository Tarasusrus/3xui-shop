import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _

from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.payment_gateways import GatewayFactory
from app.bot.utils.formatting import format_subscription_period
from app.bot.utils.navigation import NavSubscription
from app.db.models import User

from .keyboard import admin_confirm_payment_keyboard, manual_pay_keyboard, pay_keyboard

logger = logging.getLogger(__name__)
router = Router(name=__name__)


def _build_manual_payment_text(gateway, data: "SubscriptionData") -> str:
    req = gateway.get_requisites()
    from app.bot.payment_gateways.sbp_manual import SbpManual

    if isinstance(gateway, SbpManual):
        return _("payment:message:manual_sbp").format(
            phone=req.get("phone", ""),
            bank=req.get("bank", ""),
            price=data.price,
            currency=gateway.currency.symbol,
        )
    return _("payment:message:manual_ton").format(
        address=req.get("address", ""),
        account=req.get("account", ""),
        amount=req.get("price_usdt", ""),
    )


class PaymentState(StatesGroup):
    processing = State()


@router.callback_query(SubscriptionData.filter(F.state.startswith(NavSubscription.PAY)))
async def callback_payment_method_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
    bot: Bot,
    gateway_factory: GatewayFactory,
    state: FSMContext,
) -> None:
    if await state.get_state() == PaymentState.processing:
        logger.debug(f"User {user.tg_id} is already processing payment.")
        return

    await state.set_state(PaymentState.processing)

    try:
        method = callback_data.state
        devices = callback_data.devices
        duration = callback_data.duration
        logger.info(f"User {user.tg_id} selected payment method: {method}")
        logger.info(f"User {user.tg_id} selected {devices} devices and {duration} days.")
        gateway = gateway_factory.get_gateway(method)
        plan = services.plan.get_plan(devices)
        price = plan.get_price(currency=gateway.currency, duration=duration)
        callback_data.price = price

        pay_ref = await gateway.create_payment(callback_data)

        if getattr(gateway, "is_manual", False):
            text = _build_manual_payment_text(gateway, callback_data)
            await callback.message.edit_text(
                text=text,
                reply_markup=manual_pay_keyboard(
                    payment_id=pay_ref, callback_data=callback_data
                ),
            )
        else:
            if callback_data.is_extend:
                text = _("payment:message:order_extend")
            elif callback_data.is_change:
                text = _("payment:message:order_change")
            else:
                text = _("payment:message:order")

            await callback.message.edit_text(
                text=text.format(
                    devices=devices,
                    duration=format_subscription_period(duration),
                    price=price,
                    currency=gateway.currency.symbol,
                ),
                reply_markup=pay_keyboard(pay_url=pay_ref, callback_data=callback_data),
            )
    except Exception as exception:
        logger.error(f"Error processing payment: {exception}")
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
    finally:
        await state.set_state(None)


@router.callback_query(F.data.startswith(NavSubscription.I_PAID))
async def callback_i_paid(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
) -> None:
    payment_id = callback.data.split(":", 1)[1]
    logger.info(f"User {user.tg_id} claimed payment {payment_id}")

    await services.notification.notify_admins(
        text=_("payment:message:pending_review").format(
            user_id=user.tg_id,
            payment_id=payment_id,
        ),
        reply_markup=admin_confirm_payment_keyboard(payment_id),
    )
    await services.notification.show_popup(
        callback=callback,
        text=_("payment:popup:awaiting_review"),
    )

