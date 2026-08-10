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
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from hmac import compare_digest

import qrcode
from PIL import Image, ImageDraw, ImageFont

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, func, inspect
from sqlalchemy.orm import declarative_base, sessionmaker, Session

import streamlit as st

# ── Configuration ─────────────────────────────────────────────────────────────

Base = declarative_base()


def _utc_now():
    """Return a naive UTC datetime (replacement for deprecated datetime.utcnow())."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_secret(key: str, default="") -> str:
    """Read from st.secrets first, then env var, then default."""
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


# ── Database Models ───────────────────────────────────────────────────────────

class Guest(Base):
    __tablename__ = "guests"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False)
    phone = Column(String(30), default="")
    ticket_count = Column(Integer, default=1)
    plus_one_name = Column(String(100), default="")  # Optional plus-one guest name
    zelle_ref = Column(String(100), default="")  # Zelle transaction reference
    qr_code = Column(String(200), unique=True)
    checked_in = Column(Boolean, default=False)
    band_given = Column(Boolean, default=False)
    checkin_time = Column(DateTime)
    created_at = Column(DateTime, default=_utc_now)

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

    try:
        engine = create_engine(db_url, pool_pre_ping=True, echo=False)
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
                print(f"psycopg2 failed, trying pg8000 driver")
                engine = create_engine(pg_url, pool_pre_ping=True, echo=False)
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
    return get_engine().url.drivername == "sqlite"


@st.cache_resource(show_spinner=False)
def get_session_factory():
    """Create a cached session factory."""
    return sessionmaker(bind=get_engine())


def init_db():
    """Create tables if they don't exist."""
    engine = get_engine()
    inspector = inspect(engine)
    existing = inspector.get_table_names()
    if (
        "guests" not in existing
        or "checkin_logs" not in existing
        or "page_visits" not in existing
    ):
        Base.metadata.create_all(engine)
    # Check if guests table has zelle_ref column (migration for existing DBs)
    elif "guests" in existing:
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


def get_db() -> Session:
    """Get a new DB session."""
    factory = get_session_factory()
    return factory()


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


# ── QR Code Generation ────────────────────────────────────────────────────────

def generate_qr_image(qr_data: str, guest_name: str) -> bytes:
    """Generate a QR code PNG image with guest name below."""
    qr = qrcode.QRCode(
        version=3,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    if img.mode != "RGB":
        img = img.convert("RGB")

    # Try system fonts, fallback to default
    font = None
    for font_path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]:
        try:
            font = ImageFont.truetype(font_path, 24)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    width, height = img.size
    new_img = Image.new("RGB", (width, height + 80), "white")
    new_img.paste(img, (0, 0))

    draw = ImageDraw.Draw(new_img)
    text = f"Dallas Boys Party 2026 - {guest_name}"

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (width - text_width) // 2

    draw.text((x, height + 20), text, fill="black", font=font)
    draw.text((x, height + 48), "Show this at the entrance", fill="#666666", font=font)

    img_io = io.BytesIO()
    new_img.save(img_io, "PNG")
    img_io.seek(0)
    return img_io.getvalue()


def generate_qr_code_for_guest(name: str, email: str) -> str:
    """Generate a unique QR code string for a new guest."""
    rand = base64.urlsafe_b64encode(os.urandom(8)).decode()[:10]
    return f"PARTY2026-{datetime.now().strftime('%Y%m%d')}-{rand}"


# ── Email ─────────────────────────────────────────────────────────────────────

def send_qr_email(guest: Guest) -> bool:
    """Send QR code via email using SMTP. Returns True on success."""
    mail_server = _get_secret("MAIL_SERVER", "smtp.gmail.com")
    mail_port = int(_get_secret("MAIL_PORT", "587"))
    mail_username = _get_secret("MAIL_USERNAME", "")
    mail_password = _get_secret("MAIL_PASSWORD", "")
    mail_sender = _get_secret("MAIL_DEFAULT_SENDER", "party@example.com")

    if not mail_username or not mail_password:
        return False

    qr_image = generate_qr_image(guest.qr_code, guest.name)

    msg = MIMEMultipart()
    msg["Subject"] = "🎉 Your Dallas Boys Party 2026 QR Code!"
    msg["From"] = mail_sender
    msg["To"] = guest.email

    plus_one_line = f"👤 Plus One: {guest.plus_one_name}\n" if guest.plus_one_name else ""

    body = f"""Hi {guest.name}!

You're registered for Dallas Boys Party 2026 — 12th Year of Togetherness!

🎫 Tickets: {guest.ticket_count}
{plus_one_line}📅 Date: Friday, October 9th, 2026
🕕 Time: 5:30 PM onwards
📍 Venue: Elegance Ballroom & Event Center, 8740 Ohio Dr A1, Plano, TX 75024

Your QR code is attached. Please show this at the entrance for check-in.

See you there!
"""
    msg.attach(MIMEText(body, "plain"))

    img_attachment = MIMEImage(qr_image, _subtype="png")
    img_attachment.add_header("Content-Disposition", "attachment", filename="party_qr.png")
    msg.attach(img_attachment)

    try:
        with smtplib.SMTP(mail_server, mail_port) as server:
            server.starttls()
            server.login(mail_username, mail_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False


# ── Welcome Announcement ──────────────────────────────────────────────────────

def generate_welcome_announcement(name: str, ticket_count: int) -> str:
    """Generate welcome announcement text for speech synthesis."""
    if ticket_count == 1:
        return f"Welcome {name}! You have 1 ticket. Enjoy the party!"
    return f"Welcome {name}! You have {ticket_count} tickets. Enjoy the party!"


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
                g.checkin_time.strftime("%Y-%m-%d %H:%M:%S") if g.checkin_time else "",
                g.qr_code,
            ])
        return output.getvalue()
    finally:
        session.close()


# ── Admin Password ─────────────────────────────────────────────────────────────

def verify_admin_password(password: str) -> bool:
    """Verify admin password against secret using constant-time comparison."""
    expected = _get_secret("ADMIN_PASSWORD", "")
    if not expected:
        return True
    return compare_digest(password, expected)


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
    email = email.strip().lower()
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
