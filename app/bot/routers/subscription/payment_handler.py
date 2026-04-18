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

from .keyboard import pay_keyboard

logger = logging.getLogger(__name__)
router = Router(name=__name__)


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

        pay_url = await gateway.create_payment(callback_data)

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
            reply_markup=pay_keyboard(pay_url=pay_url, callback_data=callback_data),
        )
    except Exception as exception:
        logger.error(f"Error processing payment: {exception}")
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
    finally:
        await state.set_state(None)


