"""
Party Check-In System — Utilities
Database, QR generation, email, and helper functions.
Works with Streamlit (no Flask dependencies).
"""

import html
import os
import io
import base64
import csv
import re
import smtplib
from datetime import datetime
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
    created_at = Column(DateTime, default=datetime.utcnow)

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
    timestamp = Column(DateTime, default=datetime.utcnow)
    device_info = Column(String(200))


# ── Database Engine & Session ─────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_engine():
    """Create a cached SQLAlchemy engine.

    Falls back to a local SQLite database if the configured DATABASE_URL
    cannot be reached (e.g., paused Supabase project or missing secret).
    """
    db_url = _get_secret("DATABASE_URL", "sqlite:///party_guests.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    try:
        engine = create_engine(db_url, pool_pre_ping=True, echo=False)
        # Validate the connection by listing table names
        inspector = inspect(engine)
        inspector.get_table_names()
        return engine
    except Exception as e:
        # Log the failure without exposing the full URL in the UI
        print(f"DATABASE_URL connection failed, falling back to SQLite: {e}")
        fallback_url = "sqlite:///party_guests.db"
        return create_engine(fallback_url, echo=False)


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
    if "guests" not in existing or "checkin_logs" not in existing:
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
        return {
            "total_guests": total,
            "checked_in": checked_in,
            "bands_distributed": bands,
            "pending": total - checked_in,
            "total_tickets": tickets,
            "admitted_tickets": admitted_tickets,
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
    """Sanitize and validate phone number; optional but validated if provided."""
    phone = phone.strip()
    if not phone:
        return ""
    phone = re.sub(r'[^0-9+\-\(\)\.\s]', '', phone)
    digits = re.sub(r'\D', '', phone)
    # Require 10-15 digits (covers US + international)
    if len(digits) < 10 or len(digits) > 15:
        return ""
    return phone[:30]


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
