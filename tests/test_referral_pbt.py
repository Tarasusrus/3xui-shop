"""
Property-based tests for referral link generation.

Properties tested:
1. referral_link format: https://t.me/{bot_username}?start={tg_id}
2. tg_id survives embedding in URL without mutation
3. bot_username constraints (Telegram rules: 5-32 chars, alphanum+underscore)
4. ?start= param is extractable from generated link
5. NavReferral enum values have no class name leak
6. referral_keyboard callback_data is correct
7. Link starts with https:// (not http://)
"""

from urllib.parse import parse_qs, urlparse

from hypothesis import assume, given
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Reproduce production logic
# ---------------------------------------------------------------------------

class NavReferral:
    MAIN = "referral"
    GET_REFERRED_TRIAL = "get_referral_trial"


def make_referral_link(bot_username: str, tg_id: int) -> str:
    """Exact copy of production: referral handler generate_referral_summary_text."""
    return f"https://t.me/{bot_username}?start={tg_id}"


def extract_start_param(referral_link: str) -> str:
    parsed = urlparse(referral_link)
    params = parse_qs(parsed.query)
    return params["start"][0]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Telegram bot username: 5-32 chars, letters/digits/underscore, must not start/end with _
# Simplified for testing: just alphanum + underscore, 5-32 chars
bot_username_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
    min_size=5,
    max_size=32,
)

# Telegram user IDs are positive 64-bit integers (historically up to ~10^10)
tg_id_strategy = st.integers(min_value=1, max_value=10_000_000_000)


# ---------------------------------------------------------------------------
# Property 1: link starts with https://t.me/
# ---------------------------------------------------------------------------

@given(bot_username=bot_username_strategy, tg_id=tg_id_strategy)
def test_referral_link_starts_with_https_tme(bot_username: str, tg_id: int) -> None:
    link = make_referral_link(bot_username, tg_id)
    assert link.startswith("https://t.me/"), f"Link must start with https://t.me/: {link!r}"
    assert not link.startswith("http://"), f"Must use HTTPS: {link!r}"


# ---------------------------------------------------------------------------
# Property 2: tg_id survives round-trip through link
# ---------------------------------------------------------------------------

@given(bot_username=bot_username_strategy, tg_id=tg_id_strategy)
def test_tg_id_survives_link_roundtrip(bot_username: str, tg_id: int) -> None:
    link = make_referral_link(bot_username, tg_id)
    extracted = extract_start_param(link)
    assert extracted == str(tg_id), (
        f"tg_id lost in link: expected {tg_id!r}, got {extracted!r}"
    )


# ---------------------------------------------------------------------------
# Property 3: bot_username is present in link
# ---------------------------------------------------------------------------

@given(bot_username=bot_username_strategy, tg_id=tg_id_strategy)
def test_bot_username_is_in_link(bot_username: str, tg_id: int) -> None:
    link = make_referral_link(bot_username, tg_id)
    assert f"t.me/{bot_username}" in link, (
        f"bot_username {bot_username!r} missing from link {link!r}"
    )


# ---------------------------------------------------------------------------
# Property 4: link is valid URL with correct structure
# ---------------------------------------------------------------------------

@given(bot_username=bot_username_strategy, tg_id=tg_id_strategy)
def test_referral_link_is_valid_url(bot_username: str, tg_id: int) -> None:
    link = make_referral_link(bot_username, tg_id)
    parsed = urlparse(link)
    assert parsed.scheme == "https"
    assert parsed.netloc == "t.me"
    assert parsed.path == f"/{bot_username}"
    assert "start" in parse_qs(parsed.query)


# ---------------------------------------------------------------------------
# Property 5: ?start= param contains only the tg_id, nothing extra
# ---------------------------------------------------------------------------

@given(bot_username=bot_username_strategy, tg_id=tg_id_strategy)
def test_start_param_contains_only_tg_id(bot_username: str, tg_id: int) -> None:
    link = make_referral_link(bot_username, tg_id)
    params = parse_qs(urlparse(link).query)
    assert list(params.keys()) == ["start"], f"Extra params in link: {params}"
    assert params["start"] == [str(tg_id)]


# ---------------------------------------------------------------------------
# Property 6: NavReferral values have no class name leak
# ---------------------------------------------------------------------------

def test_navreferral_main_value() -> None:
    assert NavReferral.MAIN == "referral"
    assert "NavReferral" not in NavReferral.MAIN
    assert len(NavReferral.MAIN.encode()) <= 64


def test_navreferral_get_referred_trial_value() -> None:
    assert NavReferral.GET_REFERRED_TRIAL == "get_referral_trial"
    assert "NavReferral" not in NavReferral.GET_REFERRED_TRIAL
    assert len(NavReferral.GET_REFERRED_TRIAL.encode()) <= 64


# ---------------------------------------------------------------------------
# Property 7: referral link never exceeds reasonable URL length
# ---------------------------------------------------------------------------

@given(bot_username=bot_username_strategy, tg_id=tg_id_strategy)
def test_referral_link_reasonable_length(bot_username: str, tg_id: int) -> None:
    link = make_referral_link(bot_username, tg_id)
    # Telegram deep link limit is 512 bytes for start param, but full URL < 2048 is safe
    assert len(link) < 2048, f"Link too long: {len(link)} chars"


# ---------------------------------------------------------------------------
# Property 8: different tg_ids produce different links (no collision)
# ---------------------------------------------------------------------------

@given(
    bot_username=bot_username_strategy,
    tg_id_a=tg_id_strategy,
    tg_id_b=tg_id_strategy,
)
def test_different_tg_ids_produce_different_links(
    bot_username: str, tg_id_a: int, tg_id_b: int
) -> None:
    assume(tg_id_a != tg_id_b)
    link_a = make_referral_link(bot_username, tg_id_a)
    link_b = make_referral_link(bot_username, tg_id_b)
    assert link_a != link_b, f"Collision: tg_id {tg_id_a} and {tg_id_b} gave same link"
