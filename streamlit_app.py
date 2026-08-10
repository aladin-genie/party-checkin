"""
Party Check-In System — Streamlit App (Mobile-First, v2.2)
Entry point for Streamlit Community Cloud (free hosting).
"""

import traceback

import streamlit as st

startup_error = None
try:
    import base64
    import os
    import re
    from datetime import datetime, timedelta, timezone

    from utils import (
        init_db,
        get_db,
        Guest,
        CheckInLog,
        get_stats,
        generate_qr_image,
        generate_qr_code_for_guest,
        send_qr_email,
        generate_welcome_announcement,
        generate_csv,
        verify_admin_password,
        audio_announcement_js,
        sanitize_email,
        sanitize_name,
        sanitize_phone,
        sanitize_zelle_ref,
        _using_fallback_db,
        record_visit,
        get_visit_stats,
        get_site_stats,
        record_submission,
    )

    # ── Initialize DB ────────────────────────────────────────────────────────────
    init_db()
except Exception as e:
    startup_error = traceback.format_exc()

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dallas Boys Party — 12th Year",
    page_icon="🎊",
    layout="centered",  # centered is better for mobile
    initial_sidebar_state="collapsed",  # collapsed by default for mobile
)

if startup_error:
    st.error("🚨 The app failed to start. Please share this error with the developer:")
    st.code(startup_error)
    st.stop()
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    /* Base typography */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }

    /* Main background gradient */
    .stApp {
        background: linear-gradient(135deg, #0a0a0a 0%, #141414 50%, #1a0a1a 100%) !important;
    }

    /* Headings: metallic gold look */
    h1, h2, h3 {
        color: #F5F5F5 !important;
        font-weight: 700 !important;
    }
    h1 {
        background: linear-gradient(90deg, #D4AF37 0%, #F4E4BC 50%, #D4AF37 100%);
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
    }

    /* Hide default header/footer noise */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}

    /* Block container spacing — fluid on mobile, wider on desktop */
    .block-container {
        padding: 1.5rem 0.8rem 2rem 0.8rem !important;
        max-width: 100% !important;
        width: 100% !important;
    }

    @media (min-width: 768px) {
        .block-container {
            max-width: 760px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
        }
    }

    @media (min-width: 1200px) {
        .block-container {
            max-width: 1080px !important;
        }
    }

    /* Buttons: gradient gold */
    button, .stButton>button {
        min-height: 52px !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        background: linear-gradient(90deg, #D4AF37 0%, #B8860B 100%) !important;
        color: #0a0a0a !important;
        border: none !important;
        box-shadow: 0 4px 14px rgba(212, 175, 55, 0.25) !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease !important;
    }
    button:hover, .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(212, 175, 55, 0.4) !important;
    }
    button[kind="secondary"], .stButton>button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.08) !important;
        color: #F5F5F5 !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        box-shadow: none !important;
    }

    /* Inputs: dark glass */
    input, .stTextInput>div>div>input, .stNumberInput>div>div>input,
    .stSelectbox>div>div, .stTextArea>div>div>textarea {
        font-size: 1.05rem !important;
        min-height: 48px !important;
        background: rgba(255, 255, 255, 0.06) !important;
        color: #F5F5F5 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 12px !important;
    }
    input::placeholder, .stTextInput>div>div>input::placeholder {
        color: rgba(245, 245, 245, 0.45) !important;
    }

    /* Cards/containers: glassmorphism */
    div[data-testid="stContainer"] {
        border-radius: 16px !important;
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35) !important;
    }

    /* Hero banner card */
    .hero-banner {
        background: linear-gradient(135deg, rgba(212, 175, 55, 0.15) 0%, rgba(138, 43, 226, 0.12) 100%) !important;
        border: 1px solid rgba(212, 175, 55, 0.35) !important;
        border-radius: 20px !important;
        padding: 24px 20px !important;
        text-align: center !important;
        box-shadow: 0 0 30px rgba(212, 175, 55, 0.15) !important;
        margin-bottom: 20px !important;
    }
    .hero-title {
        font-size: 2.4rem !important;
        font-weight: 800 !important;
        margin: 0 0 8px 0 !important;
        background: linear-gradient(90deg, #D4AF37 0%, #F4E4BC 50%, #D4AF37 100%);
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        letter-spacing: -0.5px !important;
    }
    .hero-subtitle {
        font-size: 1.15rem !important;
        color: #F4E4BC !important;
        font-weight: 600 !important;
        margin-bottom: 16px !important;
    }
    .hero-badge {
        display: inline-block !important;
        background: rgba(0, 0, 0, 0.4) !important;
        border: 1px solid rgba(212, 175, 55, 0.5) !important;
        border-radius: 50px !important;
        padding: 8px 16px !important;
        margin: 4px !important;
        color: #F5F5F5 !important;
        font-size: 0.9rem !important;
    }
    .hero-cta {
        display: inline-block !important;
        margin-top: 16px !important;
        background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%) !important;
        color: #0a0a0a !important;
        font-weight: 800 !important;
        padding: 10px 24px !important;
        border-radius: 50px !important;
        box-shadow: 0 0 20px rgba(0, 201, 255, 0.4) !important;
    }

    /* Payment card */
    .payment-card {
        background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%) !important;
        border: 1px solid rgba(212, 175, 55, 0.4) !important;
        border-radius: 20px !important;
        padding: 24px !important;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5) !important;
        position: relative !important;
        overflow: hidden !important;
    }
    .payment-card::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0; height: 4px;
        background: linear-gradient(90deg, #D4AF37, #8A2BE2, #00C9FF);
    }
    .zelle-email {
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        color: #F4E4BC !important;
        letter-spacing: 0.5px !important;
        word-break: break-all !important;
    }
    .price-tag {
        font-size: 2rem !important;
        font-weight: 800 !important;
        color: #D4AF37 !important;
    }

    /* Nav cards */
    .nav-card {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 20px !important;
        transition: all 0.2s ease !important;
    }
    .nav-card:hover {
        background: rgba(212, 175, 55, 0.08) !important;
        border-color: rgba(212, 175, 55, 0.3) !important;
        transform: translateY(-2px) !important;
    }
    .nav-card h3 {
        color: #F4E4BC !important;
        margin: 0 0 6px 0 !important;
    }
    .nav-card p {
        color: rgba(245, 245, 245, 0.65) !important;
        margin: 0 !important;
        font-size: 0.95rem !important;
    }

    /* QR code styling */
    img[alt*="QR"] {
        max-width: 100% !important;
        width: 320px !important;
        border-radius: 16px !important;
        box-shadow: 0 0 30px rgba(212, 175, 55, 0.2) !important;
    }

    /* Success/info messages */
    .stAlert {
        border-radius: 12px !important;
    }
    .stSuccess {
        background: rgba(34, 197, 94, 0.12) !important;
        border: 1px solid rgba(34, 197, 94, 0.3) !important;
    }
    .stInfo {
        background: rgba(59, 130, 246, 0.12) !important;
        border: 1px solid rgba(59, 130, 246, 0.3) !important;
    }

    /* Mobile tweaks */
    @media (max-width: 640px) {
        .hero-title { font-size: 1.9rem !important; }
        .hero-subtitle { font-size: 1rem !important; }
        .block-container { padding: 1rem 0.8rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session State Defaults ───────────────────────────────────────────────────
def _ensure_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

_ensure_state("registered_guest_id", None)
_ensure_state("scanner_result", None)
_ensure_state("admin_authenticated", False)
_ensure_state("confirm_delete", None)

# ── Constants ──────────────────────────────────────────────────────────────────
try:
    TICKET_PRICE = float(st.secrets.get("TICKET_PRICE_CENTS", 2000)) / 100
except Exception:
    TICKET_PRICE = 20.00

# Event date for check-in timeline charts
EVENT_DATE = datetime(2026, 10, 9)

_DEFAULT_ZELLE = "dallashudugaru@gmail.com"
_PLACEHOLDER_ZELLE = "your-zelle-phone@email.com or +1-234-567-8900"
ZELLE_INFO = st.secrets.get("ZELLE_INFO", _DEFAULT_ZELLE).strip()
if not ZELLE_INFO or ZELLE_INFO == _PLACEHOLDER_ZELLE or "organizer will share" in ZELLE_INFO.lower():
    ZELLE_INFO = _DEFAULT_ZELLE


# ═══════════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_home():
    site_stats = get_site_stats()

    # Hero banner
    st.markdown(
        """
        <div class="hero-banner">
            <div class="hero-title">🎉 Dallas Boys Party</div>
            <div class="hero-subtitle">12th Year of Togetherness</div>
            <div>
                <span class="hero-badge">📅 Friday, Oct 9, 2026</span>
                <span class="hero-badge">🕕 5:30 PM onwards</span>
            </div>
            <div style="margin-top: 8px;">
                <span class="hero-badge">📍 Elegance Ballroom & Event Center, 8740 Ohio Dr A1, Plano, TX 75024</span>
            </div>
            <div class="hero-cta">Registration Opens Soon</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Warn if running on fallback SQLite (e.g., Cloud secret missing or DB unreachable)
    try:
        if _using_fallback_db():
            st.warning(
                "⚠️ Running on a temporary local database. Guest data will not persist across restarts. "
                "Please set the DATABASE_URL secret in Streamlit Cloud to connect to Supabase.",
                icon="🗄️",
            )
    except Exception:
        pass

    # Site usage stats — public, popularity/engagement focus
    st.markdown("### 📊 Site Activity")
    c1, c2 = st.columns(2)
    c1.metric("Visits Today", site_stats["today_visits"])
    c2.metric("Total Visits", site_stats["total_visits"])
    c3, c4 = st.columns(2)
    c3.metric("Unique Visitors Today", site_stats["today_unique"])
    c4.metric("Total Unique Visitors", site_stats["unique_visitors"])
    c5, c6 = st.columns(2)
    c5.metric("Registrations Today", site_stats["today_regs"])
    c6.metric("Total Registered", site_stats["total_regs"])

    st.markdown("### ✨ Get Started")

    # Navigation cards
    nav_items = [
        ("📝", "Register Guest", "Pay via Zelle, get your QR code by email", "nav_register", "Register"),
        ("📷", "Self Check-In", "Scan your QR code at the entrance", "nav_scanner", "Scanner"),
        ("📊", "Admin Dashboard", "Manage guests and download reports", "nav_admin", "Admin"),
    ]
    for icon, title, desc, key, page in nav_items:
        with st.container(border=True):
            st.markdown(
                f"<div class='nav-card'><h3>{icon} {title}</h3><p>{desc}</p></div>",
                unsafe_allow_html=True,
            )
            if st.button(f"{icon} {title} →", key=key, use_container_width=True):
                st.session_state["page"] = page
                st.rerun()

    st.markdown(
        "<p style='text-align:center; opacity:0.5; font-size:0.8em; margin-top: 24px;'>"
        "Dallas Boys Party 2026 • 12th Year of Togetherness • Ready for 200+ guests</p>",
        unsafe_allow_html=True,
    )


def _home_button(key="home_button"):
    """Render a Home button that returns to the Home page."""
    if st.button("🏠 Home", key=key, use_container_width=True):
        st.session_state["page"] = "Home"
        st.rerun()


def _field_error(message: str):
    """Render a small red error message directly under a form field."""
    st.markdown(
        f"<p style='color:#ff4b4b; font-size:0.85em; margin-top:0.2rem; margin-bottom:0.8rem;'>"
        f"{message}</p>",
        unsafe_allow_html=True,
    )


def _format_phone_input():
    """Format the phone input as +1-XXX-XXX-XXXX once 10 digits are entered.

    Streamlit calls this callback on every change, before the main script runs,
    so we can safely mutate the widget's session-state value before it is drawn.
    """
    raw = st.session_state.get("reg_phone", "")
    digits = re.sub(r"\D", "", raw)
    # Accept either a bare 10-digit US number or an 11-digit number starting with 1
    if len(digits) == 10:
        st.session_state["reg_phone"] = f"+1-{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits.startswith("1"):
        d = digits[1:]
        st.session_state["reg_phone"] = f"+1-{d[:3]}-{d[3:6]}-{d[6:]}"


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_register():
    # Reset form fields at the very top, before any widgets are instantiated,
    # so stale values don't appear when re-entering the page or clicking "Register Another".
    if st.session_state.get("reset_register_form"):
        # Delete widget keys that also have a `value=` argument so Streamlit
        # doesn't warn about both a default value and session state.
        for _key in ("reg_name", "reg_email", "reg_phone", "reg_plus_one", "reg_zelle", "ticket_count"):
            st.session_state.pop(_key, None)
        st.session_state["reg_agree"] = False
        st.session_state["reset_register_form"] = False

    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.title("📝 Register Guest")
    with header_col2:
        _home_button(key="home_register")

    # If a guest was just registered, show their QR
    if st.session_state.get("registered_guest_id"):
        guest_id = st.session_state["registered_guest_id"]
        session = get_db()
        try:
            guest = session.query(Guest).filter_by(id=guest_id).first()
            if guest:
                _show_registration_success(guest)
                return
        finally:
            session.close()
        st.session_state["registered_guest_id"] = None

    # ── Zelle Payment Info Card (modern, prominent) ──────────────────────────
    st.markdown(
        f"""
        <div class="payment-card">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
                <span style="font-size: 1.8rem;">💳</span>
                <span style="font-size: 1.2rem; font-weight: 700; color: #F4E4BC;">Step 1: Pay via Zelle</span>
            </div>
            <p style="color: rgba(245,245,245,0.75); margin: 0 0 16px 0;">
                Before registering, send your payment via Zelle in your banking app.
                You'll need the <strong>transaction confirmation number</strong> on the next step.
            </p>
            <div style="background: rgba(0,0,0,0.35); border-radius: 12px; padding: 14px; margin-bottom: 14px; border: 1px solid rgba(212,175,55,0.25);">
                <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #D4AF37; margin-bottom: 4px;">Send Zelle To</div>
                <div class="zelle-email">{ZELLE_INFO}</div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: rgba(245,245,245,0.7);">Price per ticket</span>
                <span class="price-tag">${TICKET_PRICE:.2f}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Ticket count & dynamic total (outside form so it updates live) ───────
    st.markdown("### 🎫 Select Tickets")
    ticket_count = st.number_input(
        "Number of Tickets *",
        min_value=1,
        max_value=20,
        value=1,
        step=1,
        key="ticket_count",
        help="Select number of tickets. The total updates automatically as you change it.",
    )
    total = ticket_count * TICKET_PRICE
    st.markdown(
        f"""
        <div style='background: linear-gradient(135deg, rgba(212,175,55,0.25) 0%, rgba(138,43,226,0.15) 100%); border: 1px solid rgba(212,175,55,0.35); color: #F5F5F5; padding: 18px; border-radius: 16px; text-align: center; margin: 15px 0;'>
            <div style='font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; opacity: 0.9; color: #D4AF37;'>Total to Pay</div>
            <div style='font-size: 2.4em; font-weight: 800; color: #D4AF37;'>${total:.2f}</div>
            <div style='font-size: 0.9em; opacity: 0.8;'>{int(ticket_count)} ticket{'s' if ticket_count > 1 else ''} × ${TICKET_PRICE:.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Registration Details ───────────────────────────────────────────────────
    st.markdown("### 📝 Step 2: Fill Your Details")

    # Track submission across reruns so per-field errors can appear directly under
    # the relevant input. The flag is reset when navigating away from this page.
    submitted = st.session_state.get("reg_submit_clicked", False)

    with st.container(border=True):
        name = st.text_input(
            "Full Name *",
            key="reg_name",
            value="",
            placeholder="Enter your full name (letters only)",
            max_chars=100,
            help="Use letters and spaces only. Example: John Smith or Mary Jane",
        )
        if submitted and not sanitize_name(name):
            _field_error("Please enter a valid full name using letters and spaces only.")

        email = st.text_input(
            "Email Address *",
            key="reg_email",
            value="",
            placeholder="your@email.com",
            max_chars=120,
        )
        if submitted and not sanitize_email(email):
            _field_error("Please enter a valid email address.")

        # Default the phone widget to +1- via session state so the on_change
        # callback can overwrite it with the formatted number without fighting
        # the widget's `value=` argument.
        st.session_state.setdefault("reg_phone", "+1-")
        phone = st.text_input(
            "Phone Number (optional)",
            key="reg_phone",
            placeholder="+1-XXX-XXX-XXXX",
            max_chars=20,
            help="US numbers only. Enter 10 digits after +1-. The format will update automatically.",
            on_change=_format_phone_input,
        )
        _phone_touched = phone.strip() and phone.strip() not in ("+", "+1", "+1-")
        if submitted and _phone_touched and not sanitize_phone(phone):
            _field_error(
                "Please enter a valid 10-digit US phone number (only numbers after +1-)."
            )

        plus_one_name = st.text_input(
            "Plus One Name (optional)",
            key="reg_plus_one",
            value="",
            placeholder="Name of your guest",
            max_chars=100,
            help="Optional. Letters and spaces only.",
        )
        if submitted and plus_one_name.strip() and not sanitize_name(plus_one_name):
            _field_error("Plus one name must contain letters and spaces only.")

        zelle_ref = st.text_input(
            "Zelle Transaction Reference *",
            key="reg_zelle",
            value="",
            placeholder="e.g. ZELLE12345678",
            max_chars=30,
            help="8-30 letters, digits, or hyphens. Examples: ZELLE12345678, TXN-ABCD1234, 1234567890",
        )
        if submitted and not sanitize_zelle_ref(zelle_ref):
            _field_error(
                "Zelle transaction reference is required (8-30 letters, digits, hyphens)."
            )

        # ── Terms & Conditions ───────────────────────────────────────────────────
        with st.expander("📜 Terms & Conditions — Alcohol Disclaimer & Waiver"):
            st.markdown(
                """
                <div style='color: rgba(245,245,245,0.85); font-size: 0.88rem; line-height: 1.5;'>
                    <h4 style='color: #F4E4BC; margin-top: 0;'>Alcohol Disclaimer</h4>
                    <p>
                        I (Individual) or We (for all the listed attendees in this form and/or a person who is making group Zelle payment representing the group) the undersigned, hereby voluntarily assume all risks associated with participating in the activities related to the <strong>Dallas Boys Party on Oct 9, 2026</strong>.
                    </p>
                    <p>
                        I/We understand that the Dallas Boys Party organizers will not provide alcohol on-site, and that all alcohol at the event is BYOB (Bring Your Own Beverage). I/We acknowledge that consuming alcohol may impair judgment, motor skills, vision, and other abilities, and can lead to various health risks such as intoxication, nausea, vomiting, drowsiness, and other symptoms. I/We also understand that alcohol consumption can increase aggression and impair decision-making.
                    </p>
                    <p>
                        I/We acknowledge that it is my responsibility to ensure that no underage or prohibited individuals in my group consume alcohol, and I/We will comply with all local laws regarding alcohol consumption during the event.
                    </p>
                    <p>
                        I/We understand that the Dallas Boys Party organizers are not responsible for any property damage, injuries, or fatalities that may result from alcohol consumption or any activities during the event. By participating, I/We hereby release and discharge the Dallas Boys Party organizers, their owners, employees, volunteers, representatives, and agents from any and all liability for incidents occurring before, during, or after the event, including travel to and from the venue. This waiver includes, but is not limited to, liability arising from negligence.
                    </p>
                    <p>
                        In consideration of being allowed to participate, I/We further agree to indemnify and hold harmless the Dallas Boys Party organizers and their representatives from any claims or liabilities resulting from my participation in the event, including any consequences arising from alcohol consumption.
                    </p>
                    <p>
                        I/We consent to receiving medical treatment deemed necessary in case of injury, accident, or illness during the event. I/We also acknowledge that I/We may be photographed or filmed during the event, and I/We grant permission for my likeness to be used by the event organizers and sponsors for legitimate purposes without compensation.
                    </p>
                    <p>
                        By selecting <strong>"I/We Agree"</strong> below, I/We certify that I/We have read and understood this disclaimer and release of liability. I/We voluntarily agree to its terms and confirm that my participation is entirely voluntary.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            agree_terms = st.checkbox("I/We Agree", key="reg_agree", value=False)
        if submitted and not agree_terms:
            _field_error("Please check I/We Agree in the Terms & Conditions to continue.")

    st.markdown(
        "<small style='opacity:0.6'>* Required fields. By registering, you agree to the Terms & Conditions. Your QR code will be emailed to you.</small>",
        unsafe_allow_html=True,
    )

    # ── Client-side formatting & restrictions for a smoother mobile UX ───────
    st.components.v1.html(
        """
        <script>
        (function() {
            if (window.parent._partyInputHooked) return;
            window.parent._partyInputHooked = true;
            var parentDoc = window.parent.document;

            function formatPhone(input) {
                var digits = input.value.replace(/\D/g, "").replace(/^1/, "");
                if (digits.length > 10) digits = digits.slice(0, 10);
                var out = "+1";
                if (digits.length > 0) out += "-" + digits.slice(0, 3);
                if (digits.length > 3) out += "-" + digits.slice(3, 6);
                if (digits.length > 6) out += "-" + digits.slice(6, 10);
                input.value = out;
            }

            parentDoc.addEventListener("input", function(e) {
                var input = e.target;
                var label = input.getAttribute("aria-label") || "";
                if (label === "Phone Number (optional)") {
                    formatPhone(input);
                }
                if (label === "Full Name *" || label === "Plus One Name (optional)") {
                    input.value = input.value.replace(/[^A-Za-z\s]/g, "");
                }
                if (label === "Zelle Transaction Reference *") {
                    input.value = input.value.toUpperCase().replace(/[^A-Z0-9\-]/g, "");
                }
            }, true);
        })();
        </script>
        """,
        height=0,
    )

    submitted_btn = st.button("✅ Get My QR Code", type="primary", use_container_width=True)
    if submitted_btn:
        st.session_state["reg_submit_clicked"] = True
        st.rerun()

    if submitted:
        name_clean = sanitize_name(name)
        email_clean = sanitize_email(email)
        phone_clean = sanitize_phone(phone) if _phone_touched else ""
        plus_one_clean = sanitize_name(plus_one_name) if plus_one_name.strip() else ""
        zelle_clean = sanitize_zelle_ref(zelle_ref)

        error_msgs = []
        if not name_clean:
            error_msgs.append("invalid name")
        if not email_clean:
            error_msgs.append("invalid email")
        if not zelle_clean:
            error_msgs.append("invalid Zelle reference")
        if not agree_terms:
            error_msgs.append("terms not accepted")
        if _phone_touched and not phone_clean:
            error_msgs.append("invalid phone")
        if plus_one_name.strip() and not plus_one_clean:
            error_msgs.append("invalid plus-one name")

        if error_msgs:
            record_submission(
                name=name_clean or name,
                email=email_clean or email,
                phone=phone_clean or phone,
                ticket_count=ticket_count,
                plus_one_name=plus_one_clean or plus_one_name,
                zelle_ref=zelle_clean or zelle_ref,
                status="validation_error",
                errors="; ".join(error_msgs),
            )
            st.error("Please fix the highlighted fields and try again.")
            return

        session = get_db()
        try:
            existing = session.query(Guest).filter_by(email=email_clean).first()
            if existing:
                record_submission(
                    name=name_clean,
                    email=email_clean,
                    phone=phone_clean,
                    ticket_count=ticket_count,
                    plus_one_name=plus_one_clean,
                    zelle_ref=zelle_clean,
                    status="duplicate_email",
                    errors="Email already registered",
                )
                st.error("This email is already registered. Check your email or use the 'My QR' page.")
                return

            qr_code = generate_qr_code_for_guest(name_clean, email_clean)
            guest = Guest(
                name=name_clean,
                email=email_clean,
                phone=phone_clean,
                ticket_count=int(ticket_count),
                plus_one_name=plus_one_clean,
                zelle_ref=zelle_clean,
                qr_code=qr_code,
            )
            session.add(guest)
            session.commit()
            guest_id = guest.id

            email_sent = send_qr_email(guest)
            st.session_state["reg_email_sent"] = email_sent

            # Audit trail for every successful registration
            record_submission(
                name=name_clean,
                email=email_clean,
                phone=phone_clean,
                ticket_count=ticket_count,
                plus_one_name=plus_one_clean,
                zelle_ref=zelle_clean,
                status="registered",
                guest_id=guest_id,
            )

            # Show the success screen; form values are reset on the next visit
            # to this page via the reset_register_form flag.
            st.session_state["reg_submit_clicked"] = False
            st.session_state["registered_guest_id"] = guest_id
            st.rerun()
        finally:
            session.close()


def _show_registration_success(guest):
    """Display the post-registration confirmation. QR code is emailed; not shown here."""
    st.balloons()

    email_sent = st.session_state.get("reg_email_sent", False)

    if email_sent:
        st.success(
            f"🎉 You're registered, {guest.name}! Your QR code has been emailed to {guest.email}. "
            "Let's party! Check your inbox (and spam) shortly."
        )
    else:
        st.warning(
            f"🎉 You're registered, {guest.name}! However, we couldn't email your QR code automatically. "
            f"Please contact the organizer with your email ({guest.email}) to receive your QR code."
        )

    plus_one_line = (
        f"<div style='font-size: 0.9rem; color: #F4E4BC; margin-top: 6px;'>👤 Plus One: {guest.plus_one_name}</div>"
        if guest.plus_one_name
        else ""
    )

    st.markdown(
        f"""
        <div style='text-align: center; background: rgba(212,175,55,0.08); border: 1px solid rgba(212,175,55,0.3); border-radius: 20px; padding: 20px; margin: 16px 0;'>
            <div style='font-size: 1.4rem; font-weight: 800; color: #F4E4BC; margin-bottom: 4px;'>🎉 You're In!</div>
            <div style='font-size: 0.95rem; color: rgba(245,245,245,0.7);'>
                <strong>{guest.name}</strong> • {guest.ticket_count} Ticket{'s' if guest.ticket_count > 1 else ''}<br>
                {plus_one_line}
                <small>Zelle Ref: {guest.zelle_ref}</small>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info("📧 No need to screenshot — your QR code is on its way to your email.")

    if st.button("🔄 Register Another", use_container_width=True):
        st.session_state["registered_guest_id"] = None
        st.session_state["reg_email_sent"] = False
        st.session_state["reset_register_form"] = True
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MY QR PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_my_qr():
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.title("📱 My QR Code")
        st.caption("Look up your party QR code")
    with header_col2:
        _home_button(key="home_my_qr")

    # Try query params or session state
    guest_id = None
    try:
        qp = st.query_params
        if "guest_id" in qp:
            guest_id = int(qp["guest_id"])
    except Exception:
        pass
    if not guest_id and st.session_state.get("registered_guest_id"):
        guest_id = st.session_state["registered_guest_id"]

    if guest_id:
        session = get_db()
        try:
            guest = session.query(Guest).filter_by(id=guest_id).first()
            if guest:
                _display_guest_qr(guest)
                return
            else:
                st.error("Guest not found.")
        finally:
            session.close()

    # Email lookup
    lookup_email = st.text_input("Enter your email", placeholder="your@email.com")
    if st.button("🔍 Find My QR", type="primary", use_container_width=True):
        if lookup_email:
            email_clean = sanitize_email(lookup_email)
            if not email_clean:
                st.error("Please enter a valid email.")
                return
            session = get_db()
            try:
                guest = session.query(Guest).filter_by(email=email_clean).first()
                if guest:
                    _display_guest_qr(guest)
                else:
                    st.error("No guest found with that email. Please register first.")
            finally:
                session.close()


def _display_guest_qr(guest):
    """Render a guest's QR code card."""
    st.markdown(f"### {guest.name}")
    st.caption(f"{guest.ticket_count} Ticket{'s' if guest.ticket_count > 1 else ''}")

    qr_bytes = generate_qr_image(guest.qr_code, guest.name)

    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.image(qr_bytes, use_container_width=True)

    st.markdown(
        "<p style='text-align:center; opacity:0.7;'>Show this QR code at the entrance for check-in</p>",
        unsafe_allow_html=True,
    )

    st.download_button(
        label="💾 Download QR Code",
        data=qr_bytes,
        file_name=f"party_qr_{guest.name.replace(' ', '_')}.png",
        mime="image/png",
        use_container_width=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SCANNER PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_scanner():
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.title("📷 Self Check-In")
        st.caption("Scan your QR code at the entrance")
    with header_col2:
        _home_button(key="home_scanner")

    stats = get_stats()
    c1, c2 = st.columns(2)
    c1.metric("Checked In", stats["checked_in"])
    c2.metric("Total Guests", stats["total_guests"])

    st.divider()

    # ── Camera Scan ──────────────────────────────────────────────────────────
    st.subheader("📸 Camera Scan")
    st.write("Hold your QR code up to the camera and click 'Take Photo'")

    camera_image = st.camera_input("Capture QR code")

    if camera_image is not None:
        try:
            import cv2
            import numpy as np
            from PIL import Image

            pil_img = Image.open(camera_image)
            cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            detector = cv2.QRCodeDetector()
            data, bbox, _ = detector.detectAndDecode(cv_img)

            if data:
                st.success(f"QR Code detected: `{data[:50]}`")
                if st.button("✅ Confirm Check-In", type="primary", use_container_width=True):
                    _process_checkin(data)
            else:
                st.warning("No QR code detected in the photo. Try again or use manual entry below.")
        except Exception as e:
            st.error(f"Camera scan unavailable: {e}")
            st.info("Please use the manual entry option below.")

    st.divider()

    # ── Manual Entry ─────────────────────────────────────────────────────────
    st.subheader("⌨️ Manual Entry")
    st.write("Type your ticket ID or email if camera scan fails")
    manual_code = st.text_input(
        "Ticket ID / Email / QR Code", placeholder="Enter here", max_chars=200
    )
    if st.button("Check In Manually", type="primary", use_container_width=True):
        if manual_code.strip():
            _process_checkin(manual_code.strip())
        else:
            st.error("Please enter a ticket ID or email.")

    # ── Display Result ─────────────────────────────────────────────────────────
    if st.session_state.get("scanner_result"):
        result = st.session_state["scanner_result"]
        _show_scanner_result(result)


def _process_checkin(qr_code: str):
    """Process a check-in from a QR code string or email."""
    session = get_db()
    try:
        guest = session.query(Guest).filter_by(qr_code=qr_code).first()

        if not guest:
            # Try email lookup
            guest = session.query(Guest).filter_by(email=qr_code.lower()).first()
        if not guest:
            # Try by ID
            try:
                guest_id = int(qr_code)
                guest = session.query(Guest).filter_by(id=guest_id).first()
            except ValueError:
                pass

        if not guest:
            st.session_state["scanner_result"] = {
                "type": "error",
                "message": "Invalid ticket. Please try again or check your email.",
            }
            st.rerun()
            return

        if guest.checked_in:
            st.session_state["scanner_result"] = {
                "type": "warning",
                "guest": guest.to_dict(),
                "message": f"{guest.name} already checked in at {guest.checkin_time.strftime('%H:%M')}",
            }
            st.rerun()
            return

        guest.checked_in = True
        guest.checkin_time = datetime.now(timezone.utc).replace(tzinfo=None)
        log = CheckInLog(guest_id=guest.id, action="checkin", device_info="Streamlit Scanner")
        session.add(log)
        session.commit()

        announcement = generate_welcome_announcement(guest.name, guest.ticket_count)

        st.session_state["scanner_result"] = {
            "type": "success",
            "guest": guest.to_dict(),
            "message": f"Welcome {guest.name}!",
            "announcement": announcement,
            "guest_id": guest.id,
        }
        st.rerun()
    finally:
        session.close()


def _show_scanner_result(result):
    """Display the scanner result UI and play audio."""
    result_type = result.get("type")

    if result_type == "success":
        guest = result["guest"]
        st.balloons()
        st.success(f"🎉 {result['message']}")

        st.markdown(f"### {guest['name']}")
        st.markdown(f"**Tickets:** {guest['ticket_count']}")
        st.markdown(f"**Status:** ✅ Checked In")

        # Mark band given
        if st.button("✓ Mark Band Given", type="primary", use_container_width=True):
            _mark_band_given(result["guest_id"])

        # Audio announcement
        announcement = result.get("announcement", "")
        if announcement:
            st.components.v1.html(audio_announcement_js(announcement), height=0)
            st.info(f"🔊 {announcement}")

        if st.button("🔄 Scan Next Guest", use_container_width=True):
            st.session_state["scanner_result"] = None
            st.rerun()

    elif result_type == "warning":
        guest = result["guest"]
        st.warning(f"⚠️ {result['message']}")
        st.markdown(f"**Guest:** {guest['name']} — {guest['ticket_count']} ticket(s)")

        if st.button("🔄 Scan Next Guest", use_container_width=True):
            st.session_state["scanner_result"] = None
            st.rerun()

    elif result_type == "error":
        st.error(f"❌ {result['message']}")

        if st.button("🔄 Try Again", use_container_width=True):
            st.session_state["scanner_result"] = None
            st.rerun()


def _mark_band_given(guest_id: int):
    """Mark wristband as given for a guest."""
    session = get_db()
    try:
        guest = session.query(Guest).filter_by(id=guest_id).first()
        if guest and not guest.band_given:
            guest.band_given = True
            log = CheckInLog(guest_id=guest.id, action="band_given", device_info="Streamlit Scanner")
            session.add(log)
            session.commit()
            st.success(f"Band marked as given for {guest.name}")
            st.components.v1.html(audio_announcement_js("Band marked as given"), height=0)
            st.session_state["scanner_result"] = None
            st.rerun()
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_admin():
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.title("📊 Admin Dashboard")
        st.caption("Manage guests and monitor check-ins")
    with header_col2:
        _home_button(key="home_admin")

    # ── Auth ─────────────────────────────────────────────────────────────────
    if not st.session_state.get("admin_authenticated"):
        with st.form("admin_login"):
            st.info("Enter admin password to access the dashboard")
            password = st.text_input("Admin Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            if verify_admin_password(password):
                st.session_state["admin_authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        return

    if st.button("🔒 Logout", type="secondary"):
        st.session_state["admin_authenticated"] = False
        st.rerun()

    # ── Stats ────────────────────────────────────────────────────────────────
    stats = get_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Guests", stats["total_guests"])
    c2.metric("Checked In", stats["checked_in"])
    c3.metric("Pending", stats["pending"])
    c4, c5, c6 = st.columns(3)
    c4.metric("Bands Given", stats["bands_distributed"])
    c5.metric("Total Tickets", stats["total_tickets"])
    c6.metric("Admitted", stats["admitted_tickets"])
    c7, c8, c9 = st.columns(3)
    c7.metric("Revenue (est.)", f"${stats['revenue']:,.2f}")
    c8.metric("Plus Ones", stats["plus_one_count"])
    c9.metric("Avg Tickets", f"{stats['avg_tickets_per_guest']:.2f}")

    st.progress(
        stats["checkin_percentage"] / 100,
        text=f"Check-in rate: {stats['checkin_percentage']}%",
    )

    # ── Traffic Stats ────────────────────────────────────────────────────────────
    visit_stats = get_visit_stats()
    st.subheader("🌐 Traffic (just for fun)")
    v1, v2 = st.columns(2)
    v1.metric("Unique Visitors", visit_stats["unique_visitors"])
    v2.metric("Total Page Views", visit_stats["total_visits"])

    # ── Charts ───────────────────────────────────────────────────────────────────
    st.subheader("📈 Activity")
    session = get_db()
    try:
        from collections import defaultdict
        import pandas as pd

        # Registrations by day (registration happens over weeks, not hours)
        all_guests = session.query(Guest).order_by(Guest.created_at).all()
        if all_guests:
            daily_regs = defaultdict(int)
            for g in all_guests:
                day = g.created_at.date()
                daily_regs[day] += 1
            days = sorted(daily_regs.keys())
            reg_counts = [daily_regs[d] for d in days]
            reg_df = pd.DataFrame(
                {"Registrations": reg_counts},
                index=[d.strftime("%b %d") for d in days],
            )
            st.caption("Registrations by day")
            st.bar_chart(reg_df, use_container_width=True)
        else:
            st.info("No registrations yet.")

        # Check-ins on event day by hour
        event_start = EVENT_DATE.replace(hour=0, minute=0, second=0, microsecond=0)
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
        if event_checkins:
            hourly = defaultdict(int)
            for g in event_checkins:
                hourly[g.checkin_time.hour] += 1
            hours = list(range(24))
            checkin_counts = [hourly[h] for h in hours]
            checkin_df = pd.DataFrame(
                {"Check-ins": checkin_counts},
                index=[f"{h:02d}:00" for h in hours],
            )
            st.caption(f"Check-ins on event day ({EVENT_DATE.strftime('%b %d, %Y')})")
            st.bar_chart(checkin_df, use_container_width=True)
        else:
            st.info(f"No check-ins yet on event day ({EVENT_DATE.strftime('%b %d, %Y')}).")
    finally:
        session.close()

    st.divider()

    # ── Actions ──────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        if st.button("+ Add Guest", use_container_width=True):
            st.session_state["page"] = "Register"
            st.rerun()
    with col2:
        csv_data = generate_csv()
        st.download_button(
            label="⬇ Download CSV",
            data=csv_data,
            file_name=f"party_guests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.divider()

    # ── Guest List ───────────────────────────────────────────────────────────
    st.subheader("All Guests")

    session = get_db()
    try:
        guests = session.query(Guest).order_by(Guest.created_at.desc()).all()
        if not guests:
            st.info("No guests registered yet.")
        else:
            # Search
            search_term = st.text_input("🔍 Search by name or email", placeholder="Type to filter...")

            data = []
            for g in guests:
                data.append({
                    "ID": g.id,
                    "Name": g.name,
                    "Email": g.email,
                    "Phone": g.phone,
                    "Tickets": g.ticket_count,
                    "Plus One": g.plus_one_name or "—",
                    "Zelle Ref": g.zelle_ref,
                    "Checked In": "✅" if g.checked_in else "⏳",
                    "Check-in Time": g.checkin_time.strftime("%H:%M") if g.checkin_time else "—",
                    "Band": "✅" if g.band_given else "—",
                })

            if search_term:
                term = search_term.lower()
                data = [d for d in data if term in d["Name"].lower() or term in d["Email"].lower() or term in d["Zelle Ref"].lower()]

            st.dataframe(data, use_container_width=True, hide_index=True)

            # ── Guest Actions ────────────────────────────────────────────
            st.divider()
            st.subheader("Quick Actions")
            guest_options = {f"{g.id}: {g.name} ({g.email})": g for g in guests}
            selected = st.selectbox("Select a guest", list(guest_options.keys()))
            selected_guest = guest_options[selected] if selected else None

            if selected_guest:
                c1, c2, c3 = st.columns(3)
                with c1:
                    if not selected_guest.band_given:
                        if st.button("✓ Mark Band", use_container_width=True, type="primary"):
                            selected_guest.band_given = True
                            log = CheckInLog(
                                guest_id=selected_guest.id,
                                action="band_given",
                                device_info="Admin Dashboard",
                            )
                            session.add(log)
                            session.commit()
                            st.success("Band marked!")
                            st.rerun()
                    else:
                        st.success("Band given ✅")
                with c2:
                    if not selected_guest.checked_in:
                        if st.button("Check In", use_container_width=True):
                            selected_guest.checked_in = True
                            selected_guest.checkin_time = datetime.now(timezone.utc).replace(tzinfo=None)
                            log = CheckInLog(
                                guest_id=selected_guest.id,
                                action="checkin",
                                device_info="Admin Dashboard",
                            )
                            session.add(log)
                            session.commit()
                            st.success(f"Checked in {selected_guest.name}!")
                            st.rerun()
                    else:
                        st.info("Already in ✅")
                with c3:
                    if st.button("🗑 Delete", use_container_width=True, type="secondary"):
                        st.session_state["confirm_delete"] = selected_guest.id
                        st.rerun()

                if st.session_state.get("confirm_delete") == selected_guest.id:
                    st.warning(f"Delete **{selected_guest.name}**? This cannot be undone.")
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("Yes, Delete", type="primary", use_container_width=True):
                            session.delete(selected_guest)
                            session.commit()
                            st.session_state["confirm_delete"] = None
                            st.success("Guest deleted.")
                            st.rerun()
                    with cc2:
                        if st.button("Cancel", use_container_width=True):
                            st.session_state["confirm_delete"] = None
                            st.rerun()
    finally:
        session.close()

    st.divider()

    # ── Recent Check-ins ─────────────────────────────────────────────────────
    st.subheader("Recent Check-ins")
    session = get_db()
    try:
        recent = (
            session.query(Guest)
            .filter_by(checked_in=True)
            .order_by(Guest.checkin_time.desc())
            .limit(10)
            .all()
        )
        if not recent:
            st.info("No check-ins yet.")
        else:
            for g in recent:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{g.name}** — {g.ticket_count} ticket{'s' if g.ticket_count > 1 else ''}")
                        st.caption(f"Checked in at {g.checkin_time.strftime('%I:%M %p')}")
                    with c2:
                        st.markdown("✅ " + ("Band Given" if g.band_given else "No Band"))
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APP / NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    # Mobile-friendly sidebar (collapsed by default, opens as overlay on mobile)
    with st.sidebar:
        st.title("🎉 Party Check-In")
        st.markdown("---")

        if "page" not in st.session_state:
            try:
                qp = st.query_params
                if "page" in qp:
                    st.session_state["page"] = qp["page"]
                else:
                    st.session_state["page"] = "Home"
            except Exception:
                st.session_state["page"] = "Home"

        page = st.radio(
            "Navigate",
            ["Home", "Register", "My QR", "Scanner", "Admin"],
            index=["Home", "Register", "My QR", "Scanner", "Admin"].index(
                st.session_state["page"]
            ),
            label_visibility="collapsed",
        )

        if page != st.session_state.get("page"):
            st.session_state["page"] = page
            st.rerun()

        st.markdown("---")
        st.markdown("<small>v2.2 • Streamlit Edition</small>", unsafe_allow_html=True)

    # Record page visit once per navigation / refresh for traffic stats
    try:
        current_page = st.session_state.get("page", "Home")
        if st.session_state.get("last_recorded_page") != current_page:
            if "visitor_token" not in st.session_state:
                st.session_state["visitor_token"] = base64.urlsafe_b64encode(
                    os.urandom(12)
                ).decode()
            record_visit(st.session_state["visitor_token"], current_page)
            st.session_state["last_recorded_page"] = current_page
    except Exception:
        pass

    # Reset registration state when navigating to the Register page from elsewhere
    current_page = st.session_state.get("page", "Home")
    if st.session_state.get("_prev_page") != current_page:
        if current_page == "Register":
            st.session_state["reg_submit_clicked"] = False
            st.session_state["registered_guest_id"] = None
            st.session_state["reset_register_form"] = True
        st.session_state["_prev_page"] = current_page

    # Render selected page
    if page == "Home":
        page_home()
    elif page == "Register":
        page_register()
    elif page == "My QR":
        page_my_qr()
    elif page == "Scanner":
        page_scanner()
    elif page == "Admin":
        page_admin()


if __name__ == "__main__":
    main()
