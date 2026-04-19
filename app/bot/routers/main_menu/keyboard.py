from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.utils.navigation import (
    NavAdminTools,
    NavDownload,
    NavProfile,
    NavReferral,
    NavSubscription,
    NavSupport,
)


def main_menu_keyboard(
    is_admin: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=_("main_menu:button:profile"),
            callback_data=NavProfile.MAIN,
        ),
        InlineKeyboardButton(
            text=_("main_menu:button:subscription"),
            callback_data=NavSubscription.MAIN,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=_("main_menu:button:pay"),
            callback_data=NavSubscription.PAY,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=_("main_menu:button:referral"),
            callback_data=NavReferral.MAIN,
        ),
        InlineKeyboardButton(
            text=_("main_menu:button:support"),
            callback_data=NavSupport.WRITE_US,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=_("main_menu:button:instructions"),
            callback_data=NavDownload.MAIN,
        ),
    )

    if is_admin:
        builder.row(
            InlineKeyboardButton(
                text=_("main_menu:button:admin_tools"),
                callback_data=NavAdminTools.MAIN,
            )
        )

    return builder.as_markup()
