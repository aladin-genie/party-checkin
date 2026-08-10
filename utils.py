"""
Party Check-In System — Utilities
Database, QR generation, email, and helper functions.
Works with Streamlit (no Flask dependencies).
"""

import hashlib
import html
import os
import io
import base64
import csv
import re
import smtplib
import threading
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from hmac import compare_digest

import qrcode

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, func, inspect, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker, Session

import streamlit as st

import config

# ── Configuration ─────────────────────────────────────────────────────────────

Base = declarative_base()


def _utc_now():
    """Return a naive UTC datetime (replacement for deprecated datetime.utcnow())."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_secret(key: str, default="") -> str:
    """Read from st.secrets first, then env var, then default.

    NOTE: this is intentionally separate from config.get_secret(). It refers
    to this module's own `st` symbol so that tests which do
    `patch('utils.st')` correctly control every secret read that affects
    tested behavior (MAIL_*, ADMIN_PASSWORD, DATABASE_URL, TICKET_PRICE_CENTS).
    config.get_secret() reads the real streamlit module and is used only for
    values that aren't exercised by the mocked-secrets test suite (event
    strings, APP_URL, Zelle display info for the UI layer).
    """
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


# ── Database Models ───────────────────────────────────────────────────────────

class Guest(Base):
    __tablename__ = "guests"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False, index=True)
    phone = Column(String(30), default="")
    ticket_count = Column(Integer, default=1)
    plus_one_name = Column(String(1000), default="")  # Optional plus-one/bulk guest names (newline-separated)
    zelle_ref = Column(String(100), default="")  # Zelle transaction reference
    qr_code = Column(String(200), unique=True)
    checked_in = Column(Boolean, default=False, index=True)
    band_given = Column(Boolean, default=False)
    checkin_time = Column(DateTime)
    created_at = Column(DateTime, default=_utc_now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "ticket_count": self.ticket_count,
            "plus_one_name": self.plus_one_name,
            "zelle_ref": self.zelle_ref,
            "qr_code": self.qr_code,
            "checked_in": self.checked_in,
            "band_given": self.band_given,
            "checkin_time": self.checkin_time.isoformat() if self.checkin_time else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CheckInLog(Base):
    __tablename__ = "checkin_logs"

    id = Column(Integer, primary_key=True)
    guest_id = Column(Integer, ForeignKey("guests.id"))
    action = Column(String(50))  # 'checkin', 'band_given'
    timestamp = Column(DateTime, default=_utc_now)
    device_info = Column(String(200))


class PageVisit(Base):
    """Lightweight page-visit counter for fun traffic stats."""
    __tablename__ = "page_visits"

    id = Column(Integer, primary_key=True)
    visitor_token = Column(String(64), nullable=False, index=True)
    page = Column(String(50), default="Home")
    visited_at = Column(DateTime, default=_utc_now)


class SubmissionLog(Base):
    """Audit trail for every registration form submission attempt.

    Tracks both successful registrations and failed attempts (validation errors,
    duplicate emails, etc.) so organisers can see how many people tried to
    register, where they got stuck, and which entries succeeded.
    """
    __tablename__ = "submission_logs"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), default="")
    email = Column(String(120), default="")
    phone = Column(String(30), default="")
    ticket_count = Column(Integer, default=1)
    plus_one_name = Column(String(1000), default="")
    zelle_ref = Column(String(100), default="")
    status = Column(String(50), default="attempted")  # attempted, validation_error, duplicate_email, registered, email_failed
    errors = Column(String(500), default="")
    guest_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utc_now)


class AppSetting(Base):
    """Persistent key/value store for admin-controlled settings.

    Unlike st.session_state, rows here survive process restarts and are
    visible to every user/session — needed for things like the check-in
    window override, which must be a single organiser-wide switch.
    """
    __tablename__ = "app_settings"

    key = Column(String(50), primary_key=True)
    value = Column(String(200), default="")
    updated_at = Column(DateTime, default=_utc_now)


# ── Database Engine & Session ─────────────────────────────────────────────────

def _normalize_postgres_url(db_url: str) -> str:
    """Normalize any PostgreSQL URL to use the installed driver.

    Supabase and other providers supply URLs in several forms (postgres://,
    postgresql://, postgresql+psycopg://, postgresql+psycopg2://, etc.).
    This strips any existing driver suffix and applies a driver that we
    know is available in the deployed environment.
    """
    # Strip the protocol prefix, keeping user/pass/host/db
    if db_url.startswith("postgres://"):
        body = db_url[len("postgres://"):]
    elif db_url.startswith("postgresql://"):
        body = db_url[len("postgresql://"):]
    elif db_url.startswith("postgresql+"):
        # e.g. postgresql+psycopg:// or postgresql+psycopg2://
        body = db_url.split("://", 1)[1] if "://" in db_url else db_url.split("//", 1)[1]
    else:
        return db_url
    return f"postgresql+psycopg2://{body}"


def _get_engine_url_hash() -> str:
    """Return a stable hash of the configured DATABASE_URL for cache busting."""
    db_url = _get_secret("DATABASE_URL", "sqlite:///party_guests.db")
    db_url = _normalize_postgres_url(db_url)
    return hashlib.sha256(db_url.encode("utf-8")).hexdigest()[:16]


@st.cache_resource(show_spinner=False)
def _get_engine_cached(_db_url_hash: str = ""):
    """Create a cached SQLAlchemy engine keyed by the DATABASE_URL hash.

    Falls back to a local SQLite database if the configured DATABASE_URL
    cannot be reached (e.g., paused Supabase project or missing secret).
    """
    db_url = _get_secret("DATABASE_URL", "sqlite:///party_guests.db")
    db_url = _normalize_postgres_url(db_url)

    # Log safe diagnostics (driver only, never the password)
    print(f"DATABASE_URL driver prefix: {db_url.split('://')[0] if '://' in db_url else 'none'}")
    try:
        import importlib
        importlib.import_module("psycopg2")
        print("psycopg2 import: OK")
    except Exception as imp_err:
        print(f"psycopg2 import: FAILED - {imp_err}")

    # pool_size/max_overflow/pool_recycle are Postgres-pool-specific kwargs;
    # SQLite's pool (SingletonThreadPool/NullPool) rejects them, so only pass
    # them down the Postgres path.
    is_postgres = db_url.startswith("postgresql")
    engine_kwargs = {"pool_pre_ping": True, "echo": False}
    if is_postgres:
        engine_kwargs.update(pool_size=5, max_overflow=10, pool_recycle=1800)

    try:
        engine = create_engine(db_url, **engine_kwargs)
        # Validate the connection by listing table names
        inspector = inspect(engine)
        inspector.get_table_names()
        print("DATABASE_URL connection: OK")
        return engine
    except Exception as e:
        err_msg = str(e).lower()
        # Try the pure-Python pg8000 driver as a fallback if psycopg2 fails
        if "psycopg2" in err_msg and "pg8000" not in db_url:
            try:
                pg_url = db_url.replace("postgresql+psycopg2://", "postgresql+pg8000://", 1)
                print("psycopg2 failed, trying pg8000 driver")
                engine = create_engine(pg_url, **engine_kwargs)
                inspector = inspect(engine)
                inspector.get_table_names()
                print("DATABASE_URL connection via pg8000: OK")
                return engine
            except Exception as e2:
                print(f"pg8000 fallback also failed: {e2}")
        # Log the failure without exposing the full URL in the UI
        print(f"DATABASE_URL connection failed, falling back to SQLite: {e}")
        fallback_url = "sqlite:///party_guests.db"
        return create_engine(fallback_url, echo=False)


def get_engine():
    """Return the cached engine, automatically re-creating it if the DATABASE_URL secret changed."""
    return _get_engine_cached(_get_engine_url_hash())


def _using_fallback_db() -> bool:
    """Return True if the active engine is the SQLite fallback."""
    return get_engine().url.drivername.startswith("sqlite")


@st.cache_resource(show_spinner=False)
def get_session_factory():
    """Create a cached session factory."""
    return sessionmaker(bind=get_engine())


def _ensure_unique_email_index(engine) -> None:
    """Best-effort creation of a UNIQUE index on guests(email).

    Only attempted when no duplicate emails already exist in the table, so
    this never breaks startup against an existing production table that may
    already contain duplicates. Any failure is caught and logged, never
    raised.
    """
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            dup_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM ("
                    "SELECT email FROM guests GROUP BY email HAVING COUNT(*) > 1"
                    ") AS dupes"
                )
            ).scalar()
            if dup_count:
                print(f"Skipping unique email index: {dup_count} duplicate email(s) present")
                return
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_guests_email_unique ON guests (email)")
            )
            conn.commit()
    except Exception as e:
        print(f"Unique email index creation skipped: {e}")


def _ensure_secondary_indexes(engine) -> None:
    """Create the non-unique indexes the hot queries rely on, if missing.

    Columns declared `index=True` on the models only get their index when
    SQLAlchemy CREATEs the table. On a database whose tables already existed
    before those declarations were added (i.e. production), create_all() is a
    no-op and the indexes are silently absent — which is exactly what a live
    inspection of the Supabase database showed: guests had only the two unique
    indexes, while the admin dashboard filters on checked_in and orders by
    created_at on every load.

    CREATE INDEX IF NOT EXISTS is supported by both PostgreSQL and SQLite, so
    this is idempotent and cheap. Failures are logged, never raised — this
    runs at startup against the live database.
    """
    from sqlalchemy import text

    indexes = [
        ("ix_guests_checked_in", "guests", "checked_in"),
        ("ix_guests_created_at", "guests", "created_at"),
        ("ix_page_visits_visited_at", "page_visits", "visited_at"),
        ("ix_submission_logs_created_at", "submission_logs", "created_at"),
        ("ix_checkin_logs_guest_id", "checkin_logs", "guest_id"),
    ]
    for name, table, column in indexes:
        try:
            with engine.connect() as conn:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})"))
                conn.commit()
        except Exception as e:
            print(f"Index {name} creation skipped: {e}")


def init_db():
    """Create tables if they don't exist and set up reporting views on Postgres."""
    engine = get_engine()
    inspector = inspect(engine)
    existing = inspector.get_table_names()

    # Create any missing tables (idempotent)
    Base.metadata.create_all(engine)

    # Migration for existing DBs that pre-date the new columns
    if "guests" in existing:
        cols = [c["name"] for c in inspector.get_columns("guests")]
        if "zelle_ref" not in cols:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE guests ADD COLUMN zelle_ref VARCHAR(100) DEFAULT ''"))
                conn.commit()
        if "phone" not in cols:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE guests ADD COLUMN phone VARCHAR(30) DEFAULT ''"))
                conn.commit()
        if "plus_one_name" not in cols:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE guests ADD COLUMN plus_one_name VARCHAR(100) DEFAULT ''"))
                conn.commit()

    # Widen plus_one_name to fit bulk guest-name lists (up to 20 names).
    # Idempotent: re-running ALTER COLUMN ... TYPE VARCHAR(1000) on a column
    # that's already VARCHAR(1000) (or wider) is a harmless no-op on
    # PostgreSQL. SQLite doesn't enforce VARCHAR length at all, so there's
    # nothing to migrate there. Runs against the live production table, so
    # every failure is swallowed and logged rather than raised.
    if not _using_fallback_db():
        from sqlalchemy import text
        for table, column in (("guests", "plus_one_name"), ("submission_logs", "plus_one_name")):
            try:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR(1000)"))
                    conn.commit()
            except Exception as e:
                print(f"Migration skipped: widen {table}.{column} to VARCHAR(1000): {e}")

    _ensure_secondary_indexes(engine)

    # Enforce email uniqueness at the DB level when it's safe to do so.
    _ensure_unique_email_index(engine)

    # Create reporting views on PostgreSQL/Supabase only
    if not _using_fallback_db():
        try:
            _create_postgres_views(engine)
        except Exception as e:
            print(f"Postgres view creation skipped: {e}")


@st.cache_resource(show_spinner=False)
def ensure_db_ready() -> None:
    """Run init_db() exactly once per process.

    streamlit_app.py calls this at module top level instead of init_db()
    directly. Streamlit re-executes the whole script on every user
    interaction, so calling the uncached init_db() there would run
    inspect().get_table_names(), create_all(), and several
    CREATE OR REPLACE VIEW statements against the remote database on every
    single click. @st.cache_resource makes sure the real work happens once
    per process. Tests call init_db() directly and are unaffected.
    """
    init_db()


def get_db() -> Session:
    """Get a new DB session."""
    factory = get_session_factory()
    return factory()


# ── App Settings (persistent, organiser-wide) ──────────────────────────────
# Backed by the app_settings table rather than st.session_state so an admin
# override (e.g. forcing check-in open/closed) survives restarts and applies
# to every user's session, not just the admin's own browser tab.

def get_setting(key: str, default: str = "") -> str:
    """Return a persisted app setting's value, or `default` if unset/on error."""
    session = get_db()
    try:
        row = session.query(AppSetting).filter_by(key=key).first()
        return row.value if row is not None else default
    except Exception as e:
        print(f"get_setting({key!r}) failed: {e}")
        return default
    finally:
        session.close()


def set_setting(key: str, value: str) -> None:
    """Create or update a persisted app setting. Safe to call frequently."""
    session = get_db()
    try:
        row = session.query(AppSetting).filter_by(key=key).first()
        if row is None:
            session.add(AppSetting(key=key, value=value, updated_at=_utc_now()))
        else:
            row.value = value
            row.updated_at = _utc_now()
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"set_setting({key!r}) failed: {e}")
    finally:
        session.close()


CHECKIN_MODE_AUTO = "auto"      # open once now >= config.checkin_opens_at_utc()
CHECKIN_MODE_OPEN = "open"      # always open (admin forced it, e.g. for a rehearsal)
CHECKIN_MODE_CLOSED = "closed"  # always closed

_CHECKIN_MODE_SETTING_KEY = "checkin_mode"
_VALID_CHECKIN_MODES = (CHECKIN_MODE_AUTO, CHECKIN_MODE_OPEN, CHECKIN_MODE_CLOSED)


def get_checkin_mode() -> str:
    """Return the persisted check-in mode, defaulting to 'auto' when unset or invalid."""
    mode = get_setting(_CHECKIN_MODE_SETTING_KEY, CHECKIN_MODE_AUTO)
    return mode if mode in _VALID_CHECKIN_MODES else CHECKIN_MODE_AUTO


def set_checkin_mode(mode: str) -> None:
    """Persist the check-in mode.

    Raises ValueError if `mode` isn't one of CHECKIN_MODE_AUTO/OPEN/CLOSED.
    """
    if mode not in _VALID_CHECKIN_MODES:
        raise ValueError(f"Invalid checkin mode: {mode!r} (expected one of {_VALID_CHECKIN_MODES})")
    set_setting(_CHECKIN_MODE_SETTING_KEY, mode)


def checkin_status() -> dict:
    """Return the current check-in gate status.

    {"open": bool, "mode": str, "opens_at_utc": datetime, "opens_at_text": str,
     "message": str}

    - "auto"   -> open only once _utc_now() >= config.checkin_opens_at_utc().
    - "open"   -> always open (admin override for a rehearsal, early admits, etc).
    - "closed" -> always closed (admin override).

    `message` is a user-facing explanation for the Scanner page, populated
    whenever check-in is currently closed; empty string when open.
    """
    mode = get_checkin_mode()
    opens_at_utc = config.checkin_opens_at_utc()
    opens_at_text = config.checkin_opens_at_text()

    if mode == CHECKIN_MODE_OPEN:
        is_open = True
        message = ""
    elif mode == CHECKIN_MODE_CLOSED:
        is_open = False
        message = "Check-in is currently closed by the organiser."
    else:  # CHECKIN_MODE_AUTO
        is_open = _utc_now() >= opens_at_utc
        message = "" if is_open else f"Check-in opens {opens_at_text}."

    return {
        "open": is_open,
        "mode": mode,
        "opens_at_utc": opens_at_utc,
        "opens_at_text": opens_at_text,
        "message": message,
    }


def get_stats() -> dict:
    """Return current event statistics."""
    session = get_db()
    try:
        total = session.query(Guest).count()
        checked_in = session.query(Guest).filter_by(checked_in=True).count()
        bands = session.query(Guest).filter_by(band_given=True).count()
        tickets = session.query(func.sum(Guest.ticket_count)).scalar() or 0
        admitted_tickets = (
            session.query(func.sum(Guest.ticket_count))
            .filter(Guest.checked_in == True)
            .scalar()
            or 0
        )
        plus_one_count = session.query(Guest).filter(Guest.plus_one_name != "").count()

        # Average tickets per guest
        avg_tickets = round(tickets / total, 2) if total else 0.0

        # Check-in percentage
        checkin_pct = round(checked_in / total * 100, 1) if total else 0.0

        # Estimated revenue from ticket price
        try:
            ticket_price_cents = int(
                _get_secret("TICKET_PRICE_CENTS", "2000")
            )
        except Exception:
            ticket_price_cents = 2000
        revenue = round(tickets * (ticket_price_cents / 100), 2)

        return {
            "total_guests": total,
            "checked_in": checked_in,
            "bands_distributed": bands,
            "pending": total - checked_in,
            "total_tickets": tickets,
            "admitted_tickets": admitted_tickets,
            "plus_one_count": plus_one_count,
            "avg_tickets_per_guest": avg_tickets,
            "checkin_percentage": checkin_pct,
            "revenue": revenue,
        }
    finally:
        session.close()


# ── Page Visit Tracking ─────────────────────────────────────────────────────────

def record_visit(visitor_token: str, page: str = "Home") -> None:
    """Record a page visit for traffic stats. Safe to call frequently."""
    session = get_db()
    try:
        visit = PageVisit(visitor_token=visitor_token, page=page, visited_at=_utc_now())
        session.add(visit)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def get_visit_stats() -> dict:
    """Return traffic stats: total visits and unique visitors."""
    session = get_db()
    try:
        total_visits = session.query(PageVisit).count()
        unique_visitors = (
            session.query(func.count(func.distinct(PageVisit.visitor_token))).scalar() or 0
        )
        return {
            "total_visits": int(total_visits),
            "unique_visitors": int(unique_visitors),
        }
    finally:
        session.close()


def get_site_stats() -> dict:
    """Return public site-usage stats for the home page (v2)."""
    session = get_db()
    try:
        today = _utc_now().date()
        total_visits = session.query(PageVisit).count()
        unique_visitors = (
            session.query(func.count(func.distinct(PageVisit.visitor_token))).scalar() or 0
        )
        today_visits = (
            session.query(PageVisit).filter(func.date(PageVisit.visited_at) == today).count()
        )
        today_unique = (
            session.query(func.count(func.distinct(PageVisit.visitor_token)))
            .filter(func.date(PageVisit.visited_at) == today)
            .scalar()
            or 0
        )
        total_regs = session.query(Guest).count()
        today_regs = (
            session.query(Guest).filter(func.date(Guest.created_at) == today).count()
        )
        return {
            "total_visits": int(total_visits),
            "unique_visitors": int(unique_visitors),
            "today_visits": int(today_visits),
            "today_unique": int(today_unique),
            "total_regs": int(total_regs),
            "today_regs": int(today_regs),
        }
    finally:
        session.close()


def record_submission(
    name: str,
    email: str,
    phone: str,
    ticket_count: int,
    plus_one_name: str,
    zelle_ref: str,
    status: str = "attempted",
    errors: str = "",
    guest_id: int = None,
) -> None:
    """Persist a registration submission attempt to Supabase/Postgres.

    This creates an audit trail for every form submit, successful or not.
    Safe to call frequently — failures are caught and logged, not raised.
    """
    session = get_db()
    try:
        log = SubmissionLog(
            name=name[:100],
            email=email[:120].lower().strip(),
            phone=phone[:30],
            ticket_count=int(ticket_count) if ticket_count else 1,
            plus_one_name=plus_one_name[:1000],
            zelle_ref=zelle_ref[:100].upper(),
            status=status,
            errors=errors[:500],
            guest_id=guest_id,
        )
        session.add(log)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"SubmissionLog insert failed: {e}")
    finally:
        session.close()


def _create_postgres_views(engine) -> None:
    """Create/replace helpful reporting views on PostgreSQL (Supabase).

    These views are skipped on SQLite because they use PostgreSQL-specific
    date/time syntax. They give organisers ready-made dashboards in Supabase.
    """
    from sqlalchemy import text

    event_date = config.EVENT_DATE.strftime("%Y-%m-%d")
    views = {
        "vw_registrations_summary": f"""
            SELECT
                COUNT(*) AS total_guests,
                COALESCE(SUM(ticket_count), 0) AS total_tickets,
                COALESCE(SUM(CASE WHEN checked_in THEN 1 ELSE 0 END), 0) AS checked_in,
                COALESCE(SUM(CASE WHEN band_given THEN 1 ELSE 0 END), 0) AS bands_given,
                COALESCE(SUM(CASE WHEN checked_in THEN ticket_count ELSE 0 END), 0) AS admitted_tickets,
                COUNT(CASE WHEN NOT checked_in THEN 1 END) AS pending
            FROM guests
        """,
        "vw_registrations_by_day": """
            SELECT
                created_at::date AS registration_date,
                COUNT(*) AS guest_count,
                COALESCE(SUM(ticket_count), 0) AS ticket_count
            FROM guests
            GROUP BY created_at::date
            ORDER BY registration_date DESC
        """,
        "vw_checkins_by_hour": f"""
            SELECT
                EXTRACT(HOUR FROM checkin_time)::int AS hour,
                COUNT(*) AS checkin_count
            FROM guests
            WHERE checked_in = true AND checkin_time::date = '{event_date}'::date
            GROUP BY EXTRACT(HOUR FROM checkin_time)::int
            ORDER BY hour
        """,
        "vw_site_activity_summary": """
            SELECT
                (SELECT COUNT(*) FROM page_visits) AS total_visits,
                (SELECT COUNT(DISTINCT visitor_token) FROM page_visits) AS unique_visitors,
                (SELECT COUNT(*) FROM page_visits WHERE visited_at::date = CURRENT_DATE) AS today_visits,
                (SELECT COUNT(DISTINCT visitor_token) FROM page_visits WHERE visited_at::date = CURRENT_DATE) AS today_unique
        """,
        "vw_submissions_summary": """
            SELECT
                status,
                COUNT(*) AS count,
                MAX(created_at) AS last_seen
            FROM submission_logs
            GROUP BY status
            ORDER BY count DESC
        """,
        "vw_submissions_recent": """
            SELECT
                id, name, email, status, errors, guest_id, created_at
            FROM submission_logs
            ORDER BY created_at DESC
            LIMIT 100
        """,
    }
    with engine.connect() as conn:
        for view_name, sql in views.items():
            try:
                conn.execute(text(f"CREATE OR REPLACE VIEW {view_name} AS {sql}"))
            except Exception as e:
                print(f"View {view_name} creation failed: {e}")
        conn.commit()


# ── QR Code Generation ────────────────────────────────────────────────────────

def generate_qr_image(qr_data: str) -> bytes:
    """Generate a clean QR code PNG image with a generous white border.

    The image contains only the QR code (no text below) so email clients cannot
    clip or scale the code when displaying it inline. A large box size and high
    error correction make it easy to scan from phone screens and printouts.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=20,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    if img.mode != "RGB":
        img = img.convert("RGB")

    img_io = io.BytesIO()
    img.save(img_io, "PNG")
    img_io.seek(0)
    return img_io.getvalue()


def generate_qr_code() -> str:
    """Generate a unique QR code string for a new guest."""
    rand = base64.urlsafe_b64encode(os.urandom(8)).decode()[:10]
    return f"{config.qr_prefix()}-{datetime.now().strftime('%Y%m%d')}-{rand}"


# ── Email ─────────────────────────────────────────────────────────────────────
# send_qr_email() (sync) and send_qr_email_async() (fire-and-forget, off the
# request thread) both build their message via _build_qr_email_message() and
# send it via _smtp_send() so the two paths cannot drift apart.

def _read_mail_secrets() -> dict:
    """Read every MAIL_* secret needed to send an email, in one place.

    Must only ever be called from the main/calling thread — st.secrets access
    is not something a background thread should do. send_qr_email_async()
    calls this before spawning its worker thread and hands the plain dict
    result to the worker, which never touches _get_secret()/st.* itself.
    """
    mail_username = _get_secret("MAIL_USERNAME", "")
    mail_password = _get_secret("MAIL_PASSWORD", "")
    mail_server = _get_secret("MAIL_SERVER", "smtp.gmail.com")
    mail_sender = _get_secret("MAIL_DEFAULT_SENDER", "party@example.com")
    # Tolerate a blank/garbage MAIL_PORT: int("") raises ValueError, and this
    # runs inside the registration request, so it would surface as a raw
    # traceback to a guest who just paid.
    try:
        mail_port = int(_get_secret("MAIL_PORT", "587") or 587)
    except (TypeError, ValueError):
        mail_port = 587
    return {
        "mail_username": mail_username,
        "mail_password": mail_password,
        "mail_server": mail_server,
        "mail_sender": mail_sender,
        "mail_port": mail_port,
    }


def _build_qr_email_message(
    mail_sender: str,
    guest_id,
    guest_name: str,
    guest_email: str,
    ticket_count,
    plus_one_name: str,
    qr_code: str,
) -> MIMEMultipart:
    """Build the multipart QR-code email (HTML + plain-text + inline image).

    Pure function: no I/O, no secrets, no Streamlit — safe to call from any
    thread. Shared by send_qr_email (sync) and send_qr_email_async
    (background thread) so the two message bodies cannot drift apart.
    """
    qr_image = generate_qr_image(qr_code)

    # Escape every interpolated value before it goes into the HTML body.
    safe_name = html.escape(guest_name or "")
    safe_qr_code = html.escape(qr_code or "")
    safe_plus_one = html.escape(plus_one_name) if plus_one_name else ""

    event_year = config.EVENT_DATE.year
    event_title = f"{config.EVENT_NAME} {event_year}"

    msg = MIMEMultipart("related")
    msg["Subject"] = f"🎉 Your {event_title} QR Code!"
    msg["From"] = mail_sender
    msg["To"] = guest_email

    plus_one_line = f"<p>👤 Plus One: {safe_plus_one}</p>" if safe_plus_one else ""
    my_qr_url = f"{config.APP_URL}/?page=My%20QR&guest_id={guest_id}"
    safe_my_qr_url = html.escape(my_qr_url)

    # HTML body with inline QR image and a plain-text fallback
    html_body = f"""\
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <h2>Hi {safe_name}!</h2>
    <p>You're registered for <strong>{html.escape(event_title)} — {html.escape(config.EVENT_TAGLINE)}!</strong></p>
    <p>🎫 Tickets: {ticket_count}</p>
    {plus_one_line}
    <p>📅 Date: {html.escape(config.EVENT_DATE_TEXT)}<br>
       🕕 Time: {html.escape(config.EVENT_TIME_TEXT)}<br>
       📍 Venue: {html.escape(config.VENUE_NAME)}, {html.escape(config.VENUE_ADDRESS)}</p>
    <p>Your QR code is below. Please show it at the entrance for check-in.</p>
    <p style="text-align: center;"><img src="cid:party_qr" alt="Your QR Code" width="400" style="width: 100%; max-width: 420px; height: auto; border: 16px solid white; display: block; margin: 0 auto;"></p>
    <p style="font-size: 0.9em; color: #666;">
        If the QR code doesn't scan, show this code to the staff:<br>
        <code style="font-size: 1.1em; background: #f4f4f4; padding: 4px 8px; border-radius: 4px;">{safe_qr_code}</code>
    </p>
    <p><a href="{safe_my_qr_url}">Open your QR code on the website</a></p>
    <p>See you there!</p>
</body>
</html>
"""

    plain_body = f"""Hi {guest_name}!

You're registered for {event_title} — {config.EVENT_TAGLINE}!

🎫 Tickets: {ticket_count}
{('👤 Plus One: ' + plus_one_name) if plus_one_name else ''}
📅 Date: {config.EVENT_DATE_TEXT}
🕕 Time: {config.EVENT_TIME_TEXT}
📍 Venue: {config.VENUE_NAME}, {config.VENUE_ADDRESS}

Your QR code is attached (party_qr.png). Please show it at the entrance for check-in.

If the QR code doesn't scan, show this code to the staff:
{qr_code}

You can also view it here: {my_qr_url}

See you there!
"""

    msg_alternative = MIMEMultipart("alternative")
    msg_alternative.attach(MIMEText(plain_body, "plain"))
    msg_alternative.attach(MIMEText(html_body, "html"))
    msg.attach(msg_alternative)

    img_attachment = MIMEImage(qr_image, _subtype="png")
    img_attachment.add_header("Content-ID", "<party_qr>")
    img_attachment.add_header("Content-Disposition", "inline", filename="party_qr.png")
    msg.attach(img_attachment)

    return msg


def _smtp_send(mail_server: str, mail_port: int, mail_username: str, mail_password: str, msg: MIMEMultipart) -> bool:
    """Connect, authenticate, and send `msg`. Returns True on success.

    The actual blocking network I/O, factored out so both the synchronous
    and background-thread send paths share identical connect/TLS/login logic.
    """
    try:
        if mail_port == 465:
            # Implicit TLS
            with smtplib.SMTP_SSL(mail_server, mail_port, timeout=20) as server:
                server.login(mail_username, mail_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(mail_server, mail_port, timeout=20) as server:
                server.starttls()
                server.login(mail_username, mail_password)
                server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False


def send_qr_email(guest) -> bool:
    """Send QR code via email using SMTP, synchronously. Returns True on success.

    Blocks the calling thread for the full connect+TLS+login+send (often
    1-3s against Gmail). Kept for the "Resend" buttons and the test suite,
    where a synchronous result is actually wanted. For the registration hot
    path, use send_qr_email_async() instead so a slow SMTP server doesn't
    hold a request thread.

    Accepts a Guest ORM instance or anything exposing the same attributes
    (e.g. SimpleNamespace(**guest_dict)).
    """
    secrets = _read_mail_secrets()
    if not secrets["mail_username"] or not secrets["mail_password"]:
        return False

    msg = _build_qr_email_message(
        secrets["mail_sender"],
        guest.id,
        guest.name,
        guest.email,
        guest.ticket_count,
        guest.plus_one_name,
        guest.qr_code,
    )
    return _smtp_send(secrets["mail_server"], secrets["mail_port"], secrets["mail_username"], secrets["mail_password"], msg)


def send_qr_email_async(guest: dict) -> None:
    """Send the QR-code email in a background thread; returns immediately.

    Registration must not block a server thread on SMTP, so this snapshots
    every secret it needs (via _read_mail_secrets(), which reads st.secrets)
    in the CALLING thread, then hands off to a daemon thread that builds the
    message and sends it. The worker thread never reads st.secrets or calls
    any st.* function — only the plain values captured here.

    If nothing is configured (blank MAIL_USERNAME/MAIL_PASSWORD), returns
    immediately without spawning a thread — there's nothing it could send.

    On failure, the worker records a SubmissionLog row with
    status="email_failed" (so organisers can see it in the admin dashboard)
    and prints the error. There is no return value/exception surfaced to the
    caller by design — the whole point is to not make registration wait.
    """
    secrets = _read_mail_secrets()
    if not secrets["mail_username"] or not secrets["mail_password"]:
        return

    guest_id = guest.get("id")
    guest_name = guest.get("name", "")
    guest_email = guest.get("email", "")
    ticket_count = guest.get("ticket_count", 1)
    plus_one_name = guest.get("plus_one_name", "")
    qr_code = guest.get("qr_code", "")
    phone = guest.get("phone", "")
    zelle_ref = guest.get("zelle_ref", "")

    def _worker():
        error_text = ""
        try:
            msg = _build_qr_email_message(
                secrets["mail_sender"], guest_id, guest_name, guest_email,
                ticket_count, plus_one_name, qr_code,
            )
            sent = _smtp_send(
                secrets["mail_server"], secrets["mail_port"],
                secrets["mail_username"], secrets["mail_password"], msg,
            )
            if not sent:
                error_text = "Async QR email send failed (see server log)"
        except Exception as e:
            print(f"send_qr_email_async worker failed: {e}")
            error_text = str(e)

        if error_text:
            record_submission(
                name=guest_name,
                email=guest_email,
                phone=phone,
                ticket_count=ticket_count,
                plus_one_name=plus_one_name,
                zelle_ref=zelle_ref,
                status="email_failed",
                errors=error_text,
                guest_id=guest_id,
            )

    threading.Thread(target=_worker, daemon=True).start()


# ── Welcome Announcement ──────────────────────────────────────────────────────

def generate_welcome_announcement(name: str, ticket_count: int) -> str:
    """Generate welcome announcement text for speech synthesis."""
    if ticket_count == 1:
        return f"Welcome {name}! You have 1 ticket. Enjoy the party!"
    return f"Welcome {name}! You have {ticket_count} tickets. Enjoy the party!"


# ── Formatting Helpers ────────────────────────────────────────────────────────

def format_dt(dt, fmt: str = "%I:%M %p", fallback: str = "—") -> str:
    """Format a datetime, tolerating None.

    checkin_time can be NULL while checked_in is True (e.g. rows edited
    outside the app), so callers must not call .strftime() on it directly.
    """
    if dt is None:
        return fallback
    try:
        return dt.strftime(fmt)
    except Exception:
        return fallback


# ── CSV Export ──────────────────────────────────────────────────────────────────

def _sanitize_csv_field(value: str) -> str:
    """Prevent CSV injection by escaping formula characters."""
    if not value:
        return ""
    # Prefix with apostrophe if value starts with formula characters
    if value.strip() and value.strip()[0] in ('=', '+', '-', '@', '|', '%'):
        return "'" + value
    return value


def generate_csv() -> str:
    """Generate CSV content of all guests. Returns CSV string."""
    session = get_db()
    try:
        guests = session.query(Guest).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Name", "Email", "Phone", "Tickets", "Plus One", "Zelle Ref",
            "Checked In", "Band Given", "Check-in Time", "QR Code"
        ])
        for g in guests:
            writer.writerow([
                _sanitize_csv_field(g.name),
                _sanitize_csv_field(g.email),
                _sanitize_csv_field(g.phone),
                g.ticket_count,
                _sanitize_csv_field(g.plus_one_name),
                _sanitize_csv_field(g.zelle_ref),
                "Yes" if g.checked_in else "No",
                "Yes" if g.band_given else "No",
                format_dt(g.checkin_time, "%Y-%m-%d %H:%M:%S", ""),
                g.qr_code,
            ])
        return output.getvalue()
    finally:
        session.close()


# ── Admin Password ─────────────────────────────────────────────────────────────

def admin_password_is_configured() -> bool:
    """Return True if the ADMIN_PASSWORD secret has been set."""
    return bool(_get_secret("ADMIN_PASSWORD", ""))


def verify_admin_password(password: str) -> bool:
    """Verify admin password against secret using constant-time comparison.

    Fails CLOSED: if ADMIN_PASSWORD is not configured, no password is
    accepted (previously this returned True for any password, leaving the
    admin dashboard — guest PII and delete — wide open on any deploy that
    forgot to set the secret). Use admin_password_is_configured() to show a
    clear "not configured" message instead of a generic wrong-password error.
    """
    expected = _get_secret("ADMIN_PASSWORD", "")
    if not expected:
        return False
    # Encode to bytes first: compare_digest raises TypeError when given
    # non-ASCII str input.
    return compare_digest(str(password).encode("utf-8"), expected.encode("utf-8"))


# ── Audio Announcement (JavaScript) ─────────────────────────────────────────────

def audio_announcement_js(text: str) -> str:
    """Return HTML/JS snippet that speaks the given text using browser TTS.

    Uses proper HTML escaping to prevent XSS. Escapes </script> sequences
    so the embedded JS string cannot close the outer HTML script tag.
    """
    # Escape HTML entities first
    safe_text = html.escape(text)
    # Build JS string safely via JSON encoding
    import json as _json
    js_text = _json.dumps(safe_text)
    # Prevent </script> from closing the outer HTML script tag
    js_text = js_text.replace("</script>", "<\\/script>")
    js_text = js_text.replace("</SCRIPT>", "<\\/SCRIPT>")
    return f"""
    <script>
        (function() {{
            if ('speechSynthesis' in window) {{
                var u = new SpeechSynthesisUtterance({js_text});
                u.rate = 0.9;
                u.pitch = 1.0;
                window.speechSynthesis.speak(u);
            }}
        }})();
    </script>
    """


# ── Input Validation ───────────────────────────────────────────────────────────

def sanitize_email(email: str) -> str:
    """Sanitize and validate email address."""
    email = (email or "").strip().lower()
    # Reject anything the guests.email column (VARCHAR(120)) cannot hold.
    # Without this, Postgres raises a DataError on insert and the guest sees a
    # generic "database problem" instead of a fixable validation message.
    if len(email) > 120:
        return ""
    # Basic email regex
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return ""
    return email


def sanitize_name(name: str) -> str:
    """Sanitize and validate name: letters and spaces only."""
    name = name.strip()
    # Remove excessive whitespace and control characters
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', name)
    # Allow letters and spaces only
    if not re.match(r"^[A-Za-z\s]+$", name):
        return ""
    # Must contain at least one letter and be reasonable length
    if not re.search(r'[A-Za-z]', name) or len(name) < 2 or len(name) > 100:
        return ""
    return name[:100]


def sanitize_phone(phone: str) -> str:
    """Sanitize and validate US phone numbers.

    Accepts only digits and the formatting characters +, -, (, ), ., and space.
    A leading +1 country code is optional. The result is formatted as +1-XXX-XXX-XXXX.
    Returns an empty string if the input is blank/only-prefix or invalid.
    """
    phone = phone.strip()
    if not phone or phone in ("+", "+1", "+1-"):
        return ""

    # Reject anything that isn't a digit or allowed US formatting character
    if re.search(r"[^0-9+\-\(\)\.\s]", phone):
        return ""

    digits = re.sub(r"\D", "", phone)

    # 10 digits -> assume US number
    if len(digits) == 10:
        return f"+1-{digits[:3]}-{digits[3:6]}-{digits[6:]}"

    # 11 digits starting with 1 -> +1 US number
    if len(digits) == 11 and digits.startswith("1"):
        d = digits[1:]
        return f"+1-{d[:3]}-{d[3:6]}-{d[6:]}"

    return ""


def sanitize_guest_names(text: str, max_names: int = 20) -> str:
    """Sanitize a list of guest names (for bulk-ticket plus-ones).

    Accepts names separated by newlines and/or commas. Each entry is run
    through sanitize_name(). Returns the cleaned names normalized and
    newline-joined.

    Returns "" (signalling failure, consistent with the other sanitize_*
    functions) if ANY entry is invalid or there are more than `max_names`
    entries. Blank/whitespace-only input returns "" too, but that's the
    normal "not provided" case for this optional field, not a failure.
    """
    raw = (text or "").strip()
    if not raw:
        return ""

    parts = [p.strip() for p in re.split(r"[\n,]+", raw)]
    parts = [p for p in parts if p]

    if not parts or len(parts) > max_names:
        return ""

    cleaned = []
    for part in parts:
        name = sanitize_name(part)
        if not name:
            return ""
        cleaned.append(name)

    return "\n".join(cleaned)


def sanitize_zelle_ref(ref: str) -> str:
    """Sanitize and validate Zelle transaction reference.

    Zelle confirmation numbers vary by bank (e.g., 8-12 alphanumeric characters).
    Accepts 8-30 characters of letters, digits, and hyphens to allow variation.
    Examples: ABC-12345678, ZELLE9876543210, 1234567890
    """
    ref = ref.strip().upper()
    ref = re.sub(r'[^A-Z0-9\-]', '', ref)
    if len(ref) < 8 or len(ref) > 30:
        return ""
    return ref


# ── Service Layer ──────────────────────────────────────────────────────────────
# Business logic pulled out of the UI so it is unit-testable and reusable.
# Every function here opens its own session, always closes it in `finally`,
# and returns plain dicts/primitives — never detached ORM objects.

def validate_registration(
    name: str,
    email: str,
    phone: str,
    plus_one_name: str,
    zelle_ref: str,
    agree_terms: bool,
) -> tuple:
    """Validate and sanitize registration form fields.

    Returns (cleaned, errors): two dicts keyed by "name", "email", "phone",
    "plus_one_name", "zelle_ref", "terms". `cleaned` holds the sanitized
    value for every field (empty string/False if invalid or not provided).
    `errors` holds a user-facing message only for fields that failed
    validation (fields that passed are simply absent from `errors`).

    This replaces the validation that used to be duplicated twice in
    streamlit_app.page_register (once inside the st.form block, once after
    it, with subtly different phone/plus-one handling) — the rules and the
    exact wording below match what page_register used to render via
    _field_error.
    """
    errors = {}

    name_clean = sanitize_name(name or "")
    if not name_clean:
        errors["name"] = "Please enter a valid full name using letters and spaces only."

    email_clean = sanitize_email(email or "")
    if not email_clean:
        errors["email"] = "Please enter a valid email address."

    phone_raw = (phone or "").strip()
    phone_touched = bool(phone_raw) and phone_raw not in ("+", "+1", "+1-")
    phone_clean = sanitize_phone(phone_raw) if phone_touched else ""
    if phone_touched and not phone_clean:
        errors["phone"] = "Please enter a valid 10-digit US phone number (only numbers after +1-)."

    plus_one_raw = (plus_one_name or "").strip()
    plus_one_clean = sanitize_guest_names(plus_one_raw) if plus_one_raw else ""
    if plus_one_raw and not plus_one_clean:
        errors["plus_one_name"] = "Guest names must use letters and spaces only, one per line (max 20)."

    zelle_clean = sanitize_zelle_ref(zelle_ref or "")
    if not zelle_clean:
        errors["zelle_ref"] = "Zelle transaction reference is required (8-30 letters, digits, hyphens)."

    if not agree_terms:
        errors["terms"] = "Please check I/We Agree in the Terms & Conditions to continue."

    cleaned = {
        "name": name_clean,
        "email": email_clean,
        "phone": phone_clean,
        "plus_one_name": plus_one_clean,
        "zelle_ref": zelle_clean,
        "terms": bool(agree_terms),
    }
    return cleaned, errors


def register_guest(
    name: str,
    email: str,
    phone: str,
    ticket_count: int,
    plus_one_name: str,
    zelle_ref: str,
) -> dict:
    """Create a new guest registration.

    Assumes inputs are already validated/sanitized (see validate_registration).
    Does NOT send the QR email and does NOT record the submission log — the
    caller is responsible for both.

    Returns {"ok": True, "guest": {...}} on success, or
    {"ok": False, "reason": "duplicate_email"|"db_error", "message": str}.
    """
    session = get_db()
    try:
        existing = session.query(Guest).filter_by(email=email).first()
        if existing:
            return {
                "ok": False,
                "reason": "duplicate_email",
                "message": "This email is already registered. Check your email or use the 'My QR' page.",
            }

        guest = Guest(
            name=name,
            email=email,
            phone=phone,
            ticket_count=int(ticket_count) if ticket_count else 1,
            plus_one_name=plus_one_name,
            zelle_ref=zelle_ref,
            qr_code=generate_qr_code(),
        )
        session.add(guest)
        session.commit()
        return {"ok": True, "guest": guest.to_dict()}
    except IntegrityError:
        # Two concurrent submits with the same email both passed the
        # check above (TOCTOU) — the DB-level unique index closes the race.
        session.rollback()
        return {
            "ok": False,
            "reason": "duplicate_email",
            "message": "This email is already registered. Check your email or use the 'My QR' page.",
        }
    except Exception as e:
        session.rollback()
        return {"ok": False, "reason": "db_error", "message": f"Registration failed: {e}"}
    finally:
        session.close()


def check_in_by_code(code: str, bypass_window: bool = False) -> dict:
    """Resolve a scanned/typed code to a guest and check them in.

    Resolution order: qr_code, then email, then numeric id — mirrors the
    logic that used to live in streamlit_app._process_checkin. Resolved via
    a single query (sqlalchemy.or_ over all three conditions) rather than up
    to three sequential SELECTs; when more than one candidate row comes back
    the qr_code/email/id priority above is applied in Python since the DB
    makes no ordering guarantee across an OR of three different columns.

    Enforces the check-in window (see checkin_status()) server-side: this is
    the real control, not just a UI convenience gate. If check-in is not
    currently open, returns {"status": "not_open", "guest": None, "message":
    ...} immediately and does NOT touch any row — no guest lookup, no writes.

    bypass_window: when True, skips the window check entirely. This exists
    so the admin dashboard's manual "check in" button keeps working
    regardless of the window — organisers must always be able to admit
    someone by hand (e.g. a guest who lost their phone, an early arrival
    helping set up). Only pass True from an already-authenticated admin
    action; the public Scanner page must always call this with the default
    (False) so the window is enforced for guests.

    Returns {"status": "success"|"already"|"not_found"|"not_open",
    "guest": dict|None, "message": str}. The "already" message is null-safe
    about checkin_time.
    """
    if not bypass_window:
        status = checkin_status()
        if not status["open"]:
            return {"status": "not_open", "guest": None, "message": status["message"]}

    session = get_db()
    try:
        email_candidate = code.strip().lower()

        guest_id_candidate = None
        try:
            guest_id_candidate = int(code)
        except (ValueError, TypeError):
            guest_id_candidate = None

        conditions = [Guest.qr_code == code, Guest.email == email_candidate]
        if guest_id_candidate is not None:
            conditions.append(Guest.id == guest_id_candidate)

        candidates = session.query(Guest).filter(or_(*conditions)).all()

        guest = next((g for g in candidates if g.qr_code == code), None)
        if not guest:
            guest = next((g for g in candidates if g.email == email_candidate), None)
        if not guest and guest_id_candidate is not None:
            guest = next((g for g in candidates if g.id == guest_id_candidate), None)

        if not guest:
            return {
                "status": "not_found",
                "guest": None,
                "message": "Invalid ticket. Please try again or check your email.",
            }

        if guest.checked_in:
            time_str = format_dt(guest.checkin_time, "%H:%M")
            return {
                "status": "already",
                "guest": guest.to_dict(),
                "message": f"{guest.name} already checked in at {time_str}",
            }

        guest.checked_in = True
        guest.checkin_time = _utc_now()
        log = CheckInLog(guest_id=guest.id, action="checkin", device_info="Streamlit Scanner")
        session.add(log)
        session.commit()

        return {
            "status": "success",
            "guest": guest.to_dict(),
            "message": f"Welcome {guest.name}!",
        }
    finally:
        session.close()


def mark_band_given(guest_id: int) -> dict:
    """Mark a guest's wristband as given.

    Returns {"ok": bool, "message": str}, distinguishing "not found" from
    "already given" (the old streamlit_app._mark_band_given silently did
    nothing — and showed no message — in both of those cases).
    """
    session = get_db()
    try:
        guest = session.query(Guest).filter_by(id=guest_id).first()
        if not guest:
            return {"ok": False, "message": "Guest not found."}
        if guest.band_given:
            return {"ok": False, "message": f"Band was already given to {guest.name}."}

        guest.band_given = True
        log = CheckInLog(guest_id=guest.id, action="band_given", device_info="Streamlit Scanner")
        session.add(log)
        session.commit()
        return {"ok": True, "message": f"Band marked as given for {guest.name}."}
    finally:
        session.close()


def delete_guest(guest_id: int) -> bool:
    """Delete a guest by id. Returns True if a guest was deleted, False if not found."""
    session = get_db()
    try:
        guest = session.query(Guest).filter_by(id=guest_id).first()
        if not guest:
            return False
        session.delete(guest)
        session.commit()
        return True
    finally:
        session.close()


def get_guest(guest_id: int) -> dict:
    """Return a single guest as a plain dict, or None if not found.

    Use this instead of scanning list_guests() — the My QR page and the
    registration success screen only ever need one row, and they re-run on
    every Streamlit interaction.
    """
    session = get_db()
    try:
        guest = session.query(Guest).filter_by(id=guest_id).first()
        return guest.to_dict() if guest else None
    except Exception:
        return None
    finally:
        session.close()


def get_guest_by_email(email: str) -> dict:
    """Return a single guest by email as a plain dict, or None if not found."""
    session = get_db()
    try:
        guest = session.query(Guest).filter_by(email=(email or "").strip().lower()).first()
        return guest.to_dict() if guest else None
    finally:
        session.close()


def list_guests() -> list:
    """Return all guests, newest first, as plain dicts for the admin table."""
    session = get_db()
    try:
        guests = session.query(Guest).order_by(Guest.created_at.desc()).all()
        return [g.to_dict() for g in guests]
    finally:
        session.close()


def get_recent_checkins(limit: int = 10) -> list:
    """Return the most recent check-ins (newest first) as plain dicts."""
    session = get_db()
    try:
        recent = (
            session.query(Guest)
            .filter_by(checked_in=True)
            .order_by(Guest.checkin_time.desc())
            .limit(limit)
            .all()
        )
        return [g.to_dict() for g in recent]
    finally:
        session.close()


def get_registration_daily_counts() -> list:
    """Return [(date, count), ...] of registrations per day, oldest first.

    Used to drive the admin "registrations by day" bar chart.
    """
    session = get_db()
    try:
        guests = session.query(Guest).order_by(Guest.created_at).all()
        counts: dict = {}
        for g in guests:
            if not g.created_at:
                continue
            day = g.created_at.date()
            counts[day] = counts.get(day, 0) + 1
        return sorted(counts.items())
    finally:
        session.close()


def apply_guest_changes(updates: list) -> dict:
    """Apply a batch of admin spreadsheet edits (see the admin Guests tab) in
    one pass: check guests in, mark wristbands given, and delete guests.

    Each item in `updates` is a dict describing one guest row's desired end
    state: {"id": int, "checked_in": bool, "band_given": bool, "delete":
    bool}. This is the shape st.data_editor's edited dataframe gets mapped
    into by the caller.

    - "checked_in"/"band_given" are one-way: only a False -> True
      transition does anything (there is no "undo check-in"/"undo band"
      action here). Rows already in the desired state are a no-op and are
      not counted.
    - "delete" takes priority: a row marked for deletion is deleted and its
      checked_in/band_given flags are ignored (no point writing a check-in
      log for a guest that's about to disappear). The caller is responsible
      for getting explicit confirmation before any row reaches here with
      delete=True — this function performs the deletion immediately.
    - Every check-in goes through check_in_by_code(..., bypass_window=True),
      exactly like the old single-guest admin "Check In" button did —
      organisers must always be able to admit someone from this table
      regardless of whether the public check-in window is currently open.

    Returns {"checked_in": int, "band_given": int, "deleted": int}: counts
    of rows that actually changed, not the count of rows submitted.
    """
    checked_in_count = 0
    band_given_count = 0
    deleted_count = 0

    for u in updates or []:
        guest_id = u.get("id")
        if guest_id is None:
            continue

        if u.get("delete"):
            if delete_guest(guest_id):
                deleted_count += 1
            continue

        if u.get("checked_in"):
            result = check_in_by_code(str(guest_id), bypass_window=True)
            if result["status"] == "success":
                checked_in_count += 1

        if u.get("band_given"):
            result = mark_band_given(guest_id)
            if result["ok"]:
                band_given_count += 1

    return {
        "checked_in": checked_in_count,
        "band_given": band_given_count,
        "deleted": deleted_count,
    }


def get_event_day_hourly_checkins() -> list:
    """Return a list of 24 ints: check-in count per hour on the event day.

    Used to drive the admin "check-ins on event day" bar chart.
    """
    session = get_db()
    try:
        event_start = config.EVENT_DATE.replace(hour=0, minute=0, second=0, microsecond=0)
        event_end = event_start + timedelta(days=1)
        event_checkins = (
            session.query(Guest)
            .filter(
                Guest.checked_in == True,
                Guest.checkin_time >= event_start,
                Guest.checkin_time < event_end,
            )
            .all()
        )
        hourly = [0] * 24
        for g in event_checkins:
            if g.checkin_time:
                hourly[g.checkin_time.hour] += 1
        return hourly
    finally:
        session.close()


# ── Data Reset (Admin "Danger Zone") ─────────────────────────────────────────

def get_table_counts() -> dict:
    """Return current row counts for every table reset_all_data() can wipe.

    Used by the admin Danger Zone UI so the operator can see exactly what a
    reset is about to destroy before they confirm it.
    """
    session = get_db()
    try:
        return {
            "guests": session.query(Guest).count(),
            "checkin_logs": session.query(CheckInLog).count(),
            "page_visits": session.query(PageVisit).count(),
            "submission_logs": session.query(SubmissionLog).count(),
        }
    finally:
        session.close()


def reset_all_data(keep_settings: bool = True) -> dict:
    """Delete ALL rows from guests, checkin_logs, page_visits, submission_logs.

    Does NOT drop any table and does NOT touch the schema — this only empties
    tables that already exist. Everything happens in ONE transaction (a
    single session, committed once at the end): if anything fails partway
    through, the whole reset rolls back rather than leaving e.g. guests
    deleted with their checkin_logs orphaned. Children are deleted before
    parents — checkin_logs.guest_id references guests.id.

    Always resets the persisted check-in mode back to CHECKIN_MODE_AUTO —
    a clean slate should not leave check-in forced open/closed by a leftover
    testing override.

    keep_settings=False additionally clears app_settings entirely (including
    the checkin_mode row this function would otherwise write); with no rows
    left, get_checkin_mode() falls back to its own "auto" default, so the
    effective behavior is the same either way.

    Returns the per-table counts actually deleted, e.g.
    {"guests": 12, "checkin_logs": 9, "page_visits": 40, "submission_logs": 15}.
    Raises on failure (after rolling back) — callers must not report success
    without catching it.
    """
    session = get_db()
    try:
        # Children before parents: checkin_logs.guest_id references guests.id.
        # Query.delete() returns the number of rows actually removed, so the
        # reported counts reflect this transaction's DELETEs exactly rather
        # than a separate COUNT(*) that could race with a concurrent write.
        checkin_logs_deleted = session.query(CheckInLog).delete(synchronize_session=False)
        guests_deleted = session.query(Guest).delete(synchronize_session=False)
        page_visits_deleted = session.query(PageVisit).delete(synchronize_session=False)
        submission_logs_deleted = session.query(SubmissionLog).delete(synchronize_session=False)

        if keep_settings:
            row = session.query(AppSetting).filter_by(key=_CHECKIN_MODE_SETTING_KEY).first()
            if row is None:
                session.add(
                    AppSetting(
                        key=_CHECKIN_MODE_SETTING_KEY,
                        value=CHECKIN_MODE_AUTO,
                        updated_at=_utc_now(),
                    )
                )
            else:
                row.value = CHECKIN_MODE_AUTO
                row.updated_at = _utc_now()
        else:
            session.query(AppSetting).delete(synchronize_session=False)

        session.commit()
        return {
            "guests": guests_deleted,
            "checkin_logs": checkin_logs_deleted,
            "page_visits": page_visits_deleted,
            "submission_logs": submission_logs_deleted,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
