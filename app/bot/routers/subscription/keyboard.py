from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bot.services import PlanService

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.models import SubscriptionData
from app.bot.routers.misc.keyboard import (
    back_button,
    back_to_main_menu_button,
    close_notification_button,
)
from app.bot.utils.constants import Currency
from app.bot.utils.formatting import format_subscription_period
from app.bot.utils.navigation import (
    NavAdminTools,
    NavDownload,
    NavMain,
    NavReferral,
    NavSubscription,
)


def change_subscription_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=_("subscription:button:change"),
        callback_data=NavSubscription.CHANGE,
    )


def subscription_keyboard(
    has_subscription: bool,
    callback_data: SubscriptionData,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if not has_subscription:
        builder.button(
            text=_("subscription:button:buy"),
            callback_data=callback_data,
        )
    else:
        callback_data.state = NavSubscription.EXTEND
        builder.button(
            text=_("subscription:button:extend"),
            callback_data=callback_data,
        )
        callback_data.state = NavSubscription.CHANGE
        builder.button(
            text=_("subscription:button:change"),
            callback_data=callback_data,
        )

    builder.button(
        text=_("subscription:button:invite_friend"),
        callback_data=NavReferral.MAIN,
    )
    builder.adjust(1)
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def duration_keyboard(
    plan_service: PlanService,
    callback_data: SubscriptionData,
    currency: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    durations = plan_service.get_durations()
    currency: Currency = Currency.from_code(currency)

    for duration in durations:
        callback_data.duration = duration
        period = format_subscription_period(duration)
        plan = plan_service.get_plan(callback_data.devices)
        price = plan.get_price(currency=currency, duration=duration)
        builder.button(
            text=f"{period} | {price} {currency.symbol}",
            callback_data=callback_data,
        )

    builder.adjust(2)

    if callback_data.is_extend:
        builder.row(back_button(NavSubscription.MAIN))
    else:
        builder.row(back_button(NavSubscription.MAIN))

    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def manual_pay_keyboard(
    payment_id: str, callback_data: SubscriptionData
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("subscription:button:i_paid"),
            callback_data=f"{NavSubscription.I_PAID}:{payment_id}",
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def admin_confirm_payment_keyboard(payment_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("admin:button:confirm_payment"),
            callback_data=f"{NavAdminTools.CONFIRM_PAYMENT}:{payment_id}",
        ),
        InlineKeyboardButton(
            text=_("admin:button:reject_payment"),
            callback_data=f"{NavAdminTools.REJECT_PAYMENT}:{payment_id}",
        ),
    )
    return builder.as_markup()


def pay_keyboard(pay_url: str, callback_data: SubscriptionData) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text=_("subscription:button:pay"), url=pay_url))

    callback_data.state = NavSubscription.DURATION
    builder.row(
        back_button(
            callback_data.pack(),
            text=_("subscription:button:change_payment_method"),
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def payment_success_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=_("subscription:button:download_app"),
            callback_data=NavMain.REDIRECT_TO_DOWNLOAD,
        )
    )

    builder.row(close_notification_button())
    return builder.as_markup()


def trial_success_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=_("subscription:button:connect"),
            callback_data=NavDownload.MAIN,
        )
    )

    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def promocode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(back_button(NavSubscription.MAIN))
    builder.row(back_to_main_menu_button())
    return builder.as_markup()
