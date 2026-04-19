import logging
import re

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.models import ServicesContainer
from app.bot.utils.navigation import NavOnboarding
from app.config import Config
from app.db.models import User

from .keyboard import device_keyboard, skip_keyboard

logger = logging.getLogger(__name__)
router = Router(name=__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DEVICE_LABELS = {
    NavOnboarding.DEVICE_ANDROID: "Android",
    NavOnboarding.DEVICE_IPHONE: "iPhone",
    NavOnboarding.DEVICE_MAC: "Mac",
    NavOnboarding.DEVICE_WINDOWS: "Windows",
}


class OnboardingStates(StatesGroup):
    waiting_device = State()
    waiting_email = State()


async def start_onboarding(message: Message, state: FSMContext, config: Config) -> None:
    await state.set_state(OnboardingStates.waiting_device)
    await message.answer(
        text=_("onboarding:message:choose_device").format(days=config.shop.ONBOARDING_BONUS_DAYS),
        reply_markup=device_keyboard(),
    )


@router.callback_query(
    OnboardingStates.waiting_device,
    F.data.in_({
        NavOnboarding.DEVICE_ANDROID,
        NavOnboarding.DEVICE_IPHONE,
        NavOnboarding.DEVICE_MAC,
        NavOnboarding.DEVICE_WINDOWS,
    }),
)
async def callback_device_selected(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    session: AsyncSession,
    config: Config,
) -> None:
    device = DEVICE_LABELS[NavOnboarding(callback.data)]
    await User.update(session=session, tg_id=user.tg_id, device=device)
    logger.info(f"User {user.tg_id} selected device: {device}")

    await state.set_state(OnboardingStates.waiting_email)
    await callback.message.edit_text(
        text=_("onboarding:message:enter_email").format(days=config.shop.ONBOARDING_BONUS_DAYS),
        reply_markup=skip_keyboard(),
    )
    await callback.answer()


@router.message(OnboardingStates.waiting_email)
async def message_email_input(
    message: Message,
    user: User,
    state: FSMContext,
    services: ServicesContainer,
    config: Config,
    session: AsyncSession,
) -> None:
    email = message.text.strip() if message.text else ""

    if not EMAIL_RE.match(email):
        await message.answer(
            text=_("onboarding:message:invalid_email"),
            reply_markup=skip_keyboard(),
        )
        return

    await User.update(session=session, tg_id=user.tg_id, email=email)
    logger.info(f"User {user.tg_id} provided email: {email}")
    await state.clear()

    success = await services.vpn.process_bonus_days(
        user=user,
        duration=config.shop.ONBOARDING_BONUS_DAYS,
        devices=config.shop.BONUS_DEVICES_COUNT,
    )

    days = config.shop.ONBOARDING_BONUS_DAYS
    if success:
        logger.info(f"Gave +{days} bonus days to user {user.tg_id} for onboarding.")
        await message.answer(text=_("onboarding:message:bonus_granted").format(days=days))
    else:
        logger.warning(f"Failed to give +{days} bonus days to user {user.tg_id}.")
        await message.answer(text=_("onboarding:message:bonus_failed"))


@router.callback_query(
    StateFilter(OnboardingStates.waiting_device, OnboardingStates.waiting_email),
    F.data == NavOnboarding.SKIP,
)
async def callback_skip(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    await callback.message.edit_text(text=_("onboarding:message:skipped"))
    await callback.answer()
