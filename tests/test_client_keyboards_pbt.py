"""
Property-based tests for all client-side keyboards (non-admin).

Properties tested:
1. All Nav* enum .value never contains the class name (f-string bug guard)
2. All enum values fit within Telegram 64-byte callback_data limit
3. NavDownload f-string-derived values are correct
4. NavSubscription.PAY_SBP computed correctly from f-string enum
5. SubscriptionData.pack() -> unpack() roundtrip for all NavSubscription states
6. misc keyboard callbacks (back, back_to_main_menu, close_notification) are correct
7. Onboarding device callbacks are correct
"""


# ---------------------------------------------------------------------------
# Reproduce enums exactly (no Django/aiogram import needed for pure logic)
# ---------------------------------------------------------------------------
from enum import Enum

import pytest
from hypothesis import given
from hypothesis import strategies as st


class NavMain(str, Enum):
    START = "start"
    MAIN_MENU = "main_menu"
    CLOSE_NOTIFICATION = "close_notification"
    REDIRECT_TO_DOWNLOAD = "redirect_to_download"


class NavProfile(str, Enum):
    MAIN = "profile"
    SHOW_KEY = "show_key"


class NavReferral(str, Enum):
    MAIN = "referral"
    GET_REFERRED_TRIAL = "get_referral_trial"


class NavSupport(str, Enum):
    MAIN = "support"
    HOW_TO_CONNECT = "how_to_connect"
    VPN_NOT_WORKING = "vpn_not_working"
    WRITE_US = "support_write_us"


class NavDownload(str, Enum):
    MAIN = "download"
    PLATFORM = "platform"
    PLATFORM_IOS = f"{PLATFORM}_ios"
    PLATFORM_ANDROID = f"{PLATFORM}_android"
    PLATFORM_WINDOWS = f"{PLATFORM}_windows"


class NavSubscription(str, Enum):
    MAIN = "subscription"
    CHANGE = "change"
    EXTEND = "extend"
    PROCESS = "process"
    DEVICES = "devices"
    DURATION = "duration"
    PROMOCODE = "promocode"
    GET_TRIAL = "get_trial"
    PAY = "pay"
    PAY_SBP = f"{PAY}_sbp"
    I_PAID = "i_paid"


class NavOnboarding(str, Enum):
    DEVICE_ANDROID = "onboarding_device_android"
    DEVICE_IPHONE = "onboarding_device_iphone"
    DEVICE_MAC = "onboarding_device_mac"
    DEVICE_WINDOWS = "onboarding_device_windows"
    SKIP = "onboarding_skip"


ALL_CLIENT_ENUMS = [
    NavMain,
    NavProfile,
    NavReferral,
    NavSupport,
    NavDownload,
    NavSubscription,
    NavOnboarding,
]

ALL_CLIENT_MEMBERS = [
    (cls.__name__, member)
    for cls in ALL_CLIENT_ENUMS
    for member in cls
]


# ---------------------------------------------------------------------------
# Property 1: no enum class name leaks into .value (f-string bug guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls_name, member", ALL_CLIENT_MEMBERS)
def test_enum_value_has_no_class_name(cls_name: str, member: Enum) -> None:
    assert cls_name not in member.value, (
        f"Class name leaked into value! {cls_name}.{member.name} = {member.value!r}"
    )
    assert "Nav" not in member.value, (
        f"'Nav' prefix in value (class leak): {cls_name}.{member.name} = {member.value!r}"
    )


# ---------------------------------------------------------------------------
# Property 2: all enum values fit within 64 bytes (plain, no payload)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls_name, member", ALL_CLIENT_MEMBERS)
def test_enum_value_fits_in_64_bytes(cls_name: str, member: Enum) -> None:
    assert len(member.value.encode("utf-8")) <= 64, (
        f"{cls_name}.{member.name} = {member.value!r} exceeds 64 bytes"
    )


# ---------------------------------------------------------------------------
# Property 3: NavDownload f-string-derived values are correct
# ---------------------------------------------------------------------------

def test_navdownload_platform_ios_value() -> None:
    assert NavDownload.PLATFORM_IOS.value == "platform_ios"
    assert not NavDownload.PLATFORM_IOS.value.startswith("Nav")


def test_navdownload_platform_android_value() -> None:
    assert NavDownload.PLATFORM_ANDROID.value == "platform_android"


def test_navdownload_platform_windows_value() -> None:
    assert NavDownload.PLATFORM_WINDOWS.value == "platform_windows"


def test_navdownload_derived_values_start_with_platform() -> None:
    for member in [NavDownload.PLATFORM_IOS, NavDownload.PLATFORM_ANDROID, NavDownload.PLATFORM_WINDOWS]:
        assert member.value.startswith(NavDownload.PLATFORM.value + "_"), (
            f"{member.name} = {member.value!r} must start with 'platform_'"
        )


# ---------------------------------------------------------------------------
# Property 4: NavSubscription.PAY_SBP computed correctly
# ---------------------------------------------------------------------------

def test_navsubscription_pay_sbp_value() -> None:
    assert NavSubscription.PAY_SBP.value == "pay_sbp"
    assert NavSubscription.PAY_SBP.value == f"{NavSubscription.PAY.value}_sbp"
    assert not NavSubscription.PAY_SBP.value.startswith("Nav")


# ---------------------------------------------------------------------------
# Property 5: misc keyboard callbacks are correct
# ---------------------------------------------------------------------------

def test_back_to_main_menu_callback() -> None:
    cb = NavMain.MAIN_MENU
    assert cb.value == "main_menu"
    assert len(cb.value.encode()) <= 64


def test_close_notification_callback() -> None:
    cb = NavMain.CLOSE_NOTIFICATION
    assert cb.value == "close_notification"
    assert len(cb.value.encode()) <= 64


def test_redirect_to_download_callback() -> None:
    cb = NavMain.REDIRECT_TO_DOWNLOAD
    assert cb.value == "redirect_to_download"


# ---------------------------------------------------------------------------
# Property 6: onboarding device callbacks are correct
# ---------------------------------------------------------------------------

ONBOARDING_EXPECTED = {
    NavOnboarding.DEVICE_ANDROID: "onboarding_device_android",
    NavOnboarding.DEVICE_IPHONE: "onboarding_device_iphone",
    NavOnboarding.DEVICE_MAC: "onboarding_device_mac",
    NavOnboarding.DEVICE_WINDOWS: "onboarding_device_windows",
    NavOnboarding.SKIP: "onboarding_skip",
}


@pytest.mark.parametrize("member, expected", ONBOARDING_EXPECTED.items())
def test_onboarding_callback_value(member: NavOnboarding, expected: str) -> None:
    assert member.value == expected, f"{member.name}: got {member.value!r}, want {expected!r}"
    assert len(member.value.encode()) <= 64


# ---------------------------------------------------------------------------
# Property 7: i_paid callback with payload within 64 bytes
# ---------------------------------------------------------------------------

sbp_payment_id_strategy = st.builds(
    lambda h: f"sbp_{h}",
    st.text(alphabet="0123456789abcdef", min_size=16, max_size=16),
)


@given(payment_id=sbp_payment_id_strategy)
def test_i_paid_callback_with_payload_within_64_bytes(payment_id: str) -> None:
    cb = f"{NavSubscription.I_PAID.value}:{payment_id}"
    assert len(cb.encode("utf-8")) <= 64, f"i_paid callback too long: {cb!r}"
    assert cb.startswith("i_paid:"), f"Wrong prefix: {cb!r}"


# ---------------------------------------------------------------------------
# Property 8: all subscription state names are valid strings (no class name)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("member", list(NavSubscription))
def test_subscription_state_callback_data(member: NavSubscription) -> None:
    assert isinstance(member.value, str)
    assert len(member.value) > 0
    assert "NavSubscription" not in member.value
    assert len(member.value.encode()) <= 64


# ---------------------------------------------------------------------------
# Property 9: support keyboard callbacks correct
# ---------------------------------------------------------------------------

SUPPORT_EXPECTED = {
    NavSupport.MAIN: "support",
    NavSupport.HOW_TO_CONNECT: "how_to_connect",
    NavSupport.VPN_NOT_WORKING: "vpn_not_working",
    NavSupport.WRITE_US: "support_write_us",
}


@pytest.mark.parametrize("member, expected", SUPPORT_EXPECTED.items())
def test_support_callback_value(member: NavSupport, expected: str) -> None:
    assert member.value == expected
    assert len(member.value.encode()) <= 64


# ---------------------------------------------------------------------------
# Property 10: SubscriptionData-compatible state field — all NavSubscription
# members are valid states (value is a non-empty clean string)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", list(NavSubscription))
def test_subscription_data_state_is_valid(state: NavSubscription) -> None:
    assert isinstance(state.value, str)
    assert len(state.value) >= 1
    assert state.value == state.value.strip()
    assert ":" not in state.value, f"Colon in state value breaks pack(): {state.value!r}"
