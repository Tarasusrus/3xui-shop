from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.utils.navigation import NavOnboarding


def device_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Android", callback_data=NavOnboarding.DEVICE_ANDROID)
    builder.button(text="iPhone", callback_data=NavOnboarding.DEVICE_IPHONE)
    builder.button(text="Mac", callback_data=NavOnboarding.DEVICE_MAC)
    builder.button(text="Windows", callback_data=NavOnboarding.DEVICE_WINDOWS)
    builder.adjust(2)
    builder.row()
    builder.button(text=_("onboarding:button:skip"), callback_data=NavOnboarding.SKIP)
    return builder.as_markup()


def skip_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("onboarding:button:skip"), callback_data=NavOnboarding.SKIP)
    return builder.as_markup()
