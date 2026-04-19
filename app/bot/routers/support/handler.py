import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _

from app.bot.utils.navigation import NavSupport
from app.config import Config
from app.db.models import User

from .keyboard import contact_keyboard, how_to_connect_keyboard, support_keyboard


class SupportState(StatesGroup):
    waiting_support_message = State()

logger = logging.getLogger(__name__)
router = Router(name=__name__)


@router.callback_query(F.data == NavSupport.MAIN)
async def callback_support(callback: CallbackQuery, user: User, config: Config) -> None:
    logger.info(f"User {user.tg_id} opened support page.")
    await callback.message.edit_text(
        text=_("support:message:main"),
        reply_markup=support_keyboard(config.bot.SUPPORT_ID),
    )


@router.callback_query(F.data == NavSupport.HOW_TO_CONNECT)
async def callback_how_to_connect(callback: CallbackQuery, user: User, config: Config) -> None:
    logger.info(f"User {user.tg_id} opened how to connect page.")
    await callback.message.edit_text(
        text=_("support:message:how_to_connect"),
        reply_markup=how_to_connect_keyboard(config.bot.SUPPORT_ID),
    )


@router.callback_query(F.data == NavSupport.VPN_NOT_WORKING)
async def callback_vpn_not_working(callback: CallbackQuery, user: User, config: Config) -> None:
    logger.info(f"User {user.tg_id} opened vpn not working page.")
    await callback.message.edit_text(
        text=_("support:message:vpn_not_working"),
        reply_markup=contact_keyboard(config.bot.SUPPORT_ID),
    )


@router.callback_query(F.data == NavSupport.WRITE_US)
async def callback_write_us(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
) -> None:
    logger.info(f"User {user.tg_id} initiated write to support.")
    await state.set_state(SupportState.waiting_support_message)
    await callback.message.edit_text(text=_("support:message:enter_text"))


@router.message(SupportState.waiting_support_message)
async def handle_support_message(
    message: Message,
    user: User,
    state: FSMContext,
    config: Config,
) -> None:
    await state.clear()
    try:
        await message.bot.send_message(
            chat_id=config.bot.SUPPORT_ID,
            text=f"[Support] User {user.tg_id} (@{user.username}):\n\n{message.text}",
        )
        await message.answer(text=_("support:message:sent"))
    except Exception as e:
        logger.error(f"Failed to forward support message from user {user.tg_id}: {e}")
        await message.answer(text=_("support:message:error"))
