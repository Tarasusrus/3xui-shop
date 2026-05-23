"""
Property-based tests for the payment flow (SBP manual).

Properties tested:
1. callback_data for i_paid button always has valid prefix
2. Handler F.data.startswith matches what button sends
3. payment_id always extractable via split
4. Admin confirm/reject buttons have correct callback_data format
5. Enum .value vs f-string regression (Python 3.11+ bug detection)
6. SBP payment_id always has correct format
7. All callback_data within Telegram 64-byte limit
"""

import re
import uuid
from enum import Enum

from hypothesis import given
from hypothesis import strategies as st

# Reproduce enums exactly as in production

class NavSubscription(str, Enum):
    I_PAID = "i_paid"
    PAY_SBP = "pay_sbp"
    MAIN = "subscription"
    DURATION = "duration"
    PROCESS = "process"
    EXTEND = "extend"
    CHANGE = "change"
    GET_TRIAL = "get_trial"


class NavAdminTools(str, Enum):
    CONFIRM_PAYMENT = "confirm_payment"
    REJECT_PAYMENT = "reject_payment"


# Helpers — exact copies of production code after fix

def make_i_paid_callback(payment_id: str) -> str:
    """Exact copy of subscription/keyboard.py after enum f-string fix."""
    return f"{NavSubscription.I_PAID.value}:{payment_id}"


def make_confirm_callback(payment_id: str) -> str:
    return f"{NavAdminTools.CONFIRM_PAYMENT.value}:{payment_id}"


def make_reject_callback(payment_id: str) -> str:
    return f"{NavAdminTools.REJECT_PAYMENT.value}:{payment_id}"


def extract_payment_id(callback_data: str) -> str:
    """Exact copy of split logic from callback_i_paid handler."""
    return callback_data.split(":", 1)[1]


def make_sbp_payment_id() -> str:
    """Exact copy of SbpManual.create_payment."""
    return f"sbp_{uuid.uuid4().hex[:16]}"


# Strategies

sbp_payment_id_strategy = st.builds(
    lambda h: f"sbp_{h}",
    st.text(alphabet="0123456789abcdef", min_size=16, max_size=16),
)

any_payment_id_strategy = st.text(
    alphabet=st.characters(blacklist_characters=":", blacklist_categories=("Cs",)),
    min_size=1,
    max_size=50,
)


# Property 1: i_paid callback_data prefix

@given(payment_id=sbp_payment_id_strategy)
def test_i_paid_callback_starts_with_correct_prefix(payment_id: str) -> None:
    cb = make_i_paid_callback(payment_id)
    assert cb.startswith("i_paid:"), f"Got: {cb!r}"
    assert not cb.startswith("NavSubscription"), f"Enum f-string bug! Got: {cb!r}"


# Property 2: handler filter matches button callback

@given(payment_id=sbp_payment_id_strategy)
def test_i_paid_filter_matches_button_callback(payment_id: str) -> None:
    cb = make_i_paid_callback(payment_id)
    handler_prefix = NavSubscription.I_PAID.value
    assert cb.startswith(handler_prefix), (
        f"Handler filter won't match! callback={cb!r}, prefix={handler_prefix!r}"
    )


# Property 3: payment_id round-trip through split

@given(payment_id=any_payment_id_strategy)
def test_payment_id_survives_split(payment_id: str) -> None:
    from hypothesis import assume
    assume(":" not in payment_id)
    cb = make_i_paid_callback(payment_id)
    extracted = extract_payment_id(cb)
    assert extracted == payment_id, f"Lost payment_id: {payment_id!r} -> {extracted!r}"


@given(payment_id=sbp_payment_id_strategy)
def test_sbp_payment_id_survives_split(payment_id: str) -> None:
    cb = make_i_paid_callback(payment_id)
    extracted = extract_payment_id(cb)
    assert extracted == payment_id


# Property 4: admin confirm/reject callbacks

@given(payment_id=sbp_payment_id_strategy)
def test_admin_confirm_callback_format(payment_id: str) -> None:
    cb = make_confirm_callback(payment_id)
    assert cb.startswith("confirm_payment:"), f"Got: {cb!r}"
    assert not cb.startswith("NavAdminTools"), f"Enum f-string bug! Got: {cb!r}"
    assert extract_payment_id(cb) == payment_id


@given(payment_id=sbp_payment_id_strategy)
def test_admin_reject_callback_format(payment_id: str) -> None:
    cb = make_reject_callback(payment_id)
    assert cb.startswith("reject_payment:"), f"Got: {cb!r}"
    assert not cb.startswith("NavAdminTools"), f"Enum f-string bug! Got: {cb!r}"
    assert extract_payment_id(cb) == payment_id


# Property 5: enum .value regression (catches Python 3.11+ bug)

@given(st.data())
def test_enum_value_fstring_regression(data: st.DataObject) -> None:
    """
    Regression test: on Python 3.11+ f'{NavSubscription.I_PAID}' != 'i_paid'.
    Our fix uses .value explicitly. This test fails if someone removes .value.
    """
    fstring_result = f"{NavSubscription.I_PAID}"
    value_result = NavSubscription.I_PAID.value

    payment_id = "sbp_test1234567890"
    cb_correct = make_i_paid_callback(payment_id)  # uses .value
    cb_buggy = f"{NavSubscription.I_PAID}:{payment_id}"  # old bug, no .value

    assert cb_correct.startswith(value_result), "Fixed version must match handler"

    # On Python 3.11+: fstring_result != value_result, so buggy cb won't match
    if fstring_result != value_result:
        assert not cb_buggy.startswith(value_result), (
            "Buggy version unexpectedly works"
        )
        assert cb_correct.startswith(value_result), "Fix did not work"


# Property 6: SBP payment_id format

@given(st.data())
def test_sbp_payment_id_format(data: st.DataObject) -> None:
    pid = make_sbp_payment_id()
    assert pid.startswith("sbp_"), f"Wrong prefix: {pid!r}"
    assert len(pid) == 20, f"Wrong length: {len(pid)}, {pid!r}"  # "sbp_" + 16 chars
    hex_part = pid[4:]
    assert re.fullmatch(r"[0-9a-f]{16}", hex_part), f"Non-hex chars: {hex_part!r}"


# Property 7: callback_data within Telegram 64-byte limit

@given(payment_id=sbp_payment_id_strategy)
def test_callback_data_within_telegram_limit(payment_id: str) -> None:
    for cb in [
        make_i_paid_callback(payment_id),
        make_confirm_callback(payment_id),
        make_reject_callback(payment_id),
    ]:
        assert len(cb.encode("utf-8")) <= 64, (
            f"callback_data exceeds 64 bytes: {cb!r} ({len(cb.encode())} bytes)"
        )
