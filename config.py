"""
Party Check-In System — Configuration
Single source of truth for secret access and hardcoded event details.

Event date/venue/name strings and ticket-price/Zelle secret access used to be
duplicated across utils.py (email body, Postgres views) and streamlit_app.py
(hero banner, Terms & Conditions text, EVENT_DATE). This module centralizes
both so there is exactly one place to update them.
"""

import os
from datetime import datetime, timedelta, timezone

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit should always be installed
    st = None

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - zoneinfo is stdlib on 3.9+, but the tz
    # database itself can be missing on some minimal deploy images.
    ZoneInfo = None


def get_secret(key: str, default: str = "") -> str:
    """Read a secret: st.secrets first, then env var, then default.

    Must never raise. st.secrets raises StreamlitSecretsFileNotFoundError when
    no secrets file exists at all (e.g. a fresh deploy that hasn't set any
    secrets yet), so every path here is wrapped in try/except.
    """
    try:
        if st is not None:
            return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        pass
    return os.getenv(key, default)


def get_secret_int(key: str, default: int) -> int:
    """Like get_secret, but coerces to int and tolerates bad/missing values."""
    try:
        return int(get_secret(key, str(default)))
    except Exception:
        return default


# ── Event Details ────────────────────────────────────────────────────────────

EVENT_NAME = "Dallas Boys Party"
EVENT_TAGLINE = "12th Year of Togetherness"
EVENT_DATE = datetime(2026, 10, 9)
EVENT_TIME_TEXT = "5:30 PM onwards"
EVENT_DATE_TEXT = "Friday, October 9, 2026"
EVENT_DATE_SHORT = "Fri, Oct 9, 2026"

VENUE_NAME = "Elegance Ballroom & Event Center"
VENUE_ADDRESS = "8740 Ohio Dr A1, Plano, TX 75024"

APP_VERSION = "3.0"

# Public URL of the deployed app, used to build links in outgoing email.
_DEFAULT_APP_URL = "https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app"
APP_URL = get_secret("APP_URL", _DEFAULT_APP_URL).rstrip("/")


def ticket_price_cents() -> int:
    """Return the configured ticket price in cents."""
    return get_secret_int("TICKET_PRICE_CENTS", 2000)


def ticket_price_dollars() -> float:
    """Return the configured ticket price in dollars."""
    return ticket_price_cents() / 100


_DEFAULT_ZELLE = "dallashudugaru@gmail.com"
_PLACEHOLDER_ZELLE = "your-zelle-phone@email.com or +1-234-567-8900"


def zelle_info() -> str:
    """Return the Zelle payment info to display, with placeholder fallback.

    Falls back to the default organiser Zelle handle when the secret is
    unset, blank, still set to the example placeholder value, or contains
    the "organizer will share" stand-in text.
    """
    value = get_secret("ZELLE_INFO", _DEFAULT_ZELLE).strip()
    if not value or value == _PLACEHOLDER_ZELLE or "organizer will share" in value.lower():
        return _DEFAULT_ZELLE
    return value


def days_until_event() -> int:
    """Return the number of whole days from now until the event. 0 if past."""
    delta = EVENT_DATE - datetime.now()
    return max(0, delta.days)


def qr_prefix() -> str:
    """Return the QR-code prefix derived from the event year, e.g. 'PARTY2026'."""
    return f"PARTY{EVENT_DATE.year}"


# ── Check-in window ──────────────────────────────────────────────────────────
# Guests must not be able to check in weeks before the party. Check-in opens
# CHECKIN_LEAD_HOURS before the event start by default (see utils.checkin_status
# for the persistent admin override that can force it open/closed).

EVENT_TIMEZONE = "America/Chicago"  # venue is Plano, TX
EVENT_START_LOCAL = datetime(2026, 10, 9, 17, 30)  # 5:30 PM local, matches EVENT_TIME_TEXT
CHECKIN_LEAD_HOURS = 2

# Used only if the system tz database is unavailable (see _event_start_local_aware).
# America/Chicago is UTC-5 (CDT) for the whole lead-up to an October event.
_FALLBACK_UTC_OFFSET_HOURS = 5


def _event_start_local_aware() -> datetime:
    """Return EVENT_START_LOCAL as a timezone-aware datetime in EVENT_TIMEZONE.

    Raises if zoneinfo/the tz database is unavailable. Callers must catch and
    fall back — this helper itself is allowed to raise so both public
    functions below can share one fallback story.
    """
    if ZoneInfo is None:
        raise RuntimeError("zoneinfo module unavailable")
    return EVENT_START_LOCAL.replace(tzinfo=ZoneInfo(EVENT_TIMEZONE))


def event_start_utc() -> datetime:
    """Return the event start time as a naive UTC datetime.

    Builds an aware local datetime in EVENT_TIMEZONE and converts to UTC
    (rather than hand-rolling a fixed offset) so this stays correct even if
    the event date is ever moved across a DST boundary. The result is naive
    (tzinfo dropped) to match _utc_now() in utils.py, which is how the DB
    stores timestamps.

    Must never raise: falls back to treating EVENT_START_LOCAL as already
    being UTC-5 if the tz database is unavailable.
    """
    try:
        aware = _event_start_local_aware()
        return aware.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception as e:
        print(f"config.event_start_utc: zoneinfo unavailable, falling back to UTC-{_FALLBACK_UTC_OFFSET_HOURS}: {e}")
        return EVENT_START_LOCAL + timedelta(hours=_FALLBACK_UTC_OFFSET_HOURS)


def checkin_opens_at_utc() -> datetime:
    """Return the naive UTC datetime at which check-in opens (auto mode)."""
    return event_start_utc() - timedelta(hours=CHECKIN_LEAD_HOURS)


def checkin_opens_at_text() -> str:
    """Return a human-readable LOCAL check-in-opens time for the UI.

    e.g. "Fri, Oct 9, 2026 at 3:30 PM CDT". Falls back to the same rendering
    without a timezone abbreviation if the tz database is unavailable. Never
    raises.
    """
    try:
        opens_local = _event_start_local_aware() - timedelta(hours=CHECKIN_LEAD_HOURS)
        tzname = opens_local.tzname() or ""
    except Exception as e:
        print(f"config.checkin_opens_at_text: zoneinfo unavailable, falling back: {e}")
        opens_local = EVENT_START_LOCAL - timedelta(hours=CHECKIN_LEAD_HOURS)
        tzname = ""

    hour12 = opens_local.strftime("%I").lstrip("0") or "12"
    text = (
        f"{opens_local.strftime('%a, %b')} {opens_local.day}, {opens_local.year} "
        f"at {hour12}:{opens_local.strftime('%M %p')}"
    )
    return f"{text} {tzname}".strip()
