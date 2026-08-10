"""
Party Check-In System — Streamlit App (Mobile-First, v2.1)
Entry point for Streamlit Community Cloud (free hosting).
"""

import traceback

import streamlit as st

startup_error = None
try:
    import base64
    from datetime import datetime

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

    /* Block container spacing */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 520px !important;
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

_DEFAULT_ZELLE = "dallashudugaru@gmail.com"
_PLACEHOLDER_ZELLE = "your-zelle-phone@email.com or +1-234-567-8900"
ZELLE_INFO = st.secrets.get("ZELLE_INFO", _DEFAULT_ZELLE).strip()
if not ZELLE_INFO or ZELLE_INFO == _PLACEHOLDER_ZELLE or "organizer will share" in ZELLE_INFO.lower():
    ZELLE_INFO = _DEFAULT_ZELLE


# ═══════════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_home():
    stats = get_stats()

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

    # Stats cards — 2x2 grid for mobile
    c1, c2 = st.columns(2)
    c1.metric("Registered", stats["total_guests"])
    c2.metric("Checked In", stats["checked_in"])
    c3, c4 = st.columns(2)
    c3.metric("Bands Given", stats["bands_distributed"])
    c4.metric("Total Tickets", stats["total_tickets"])

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


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_register():
    st.title("📝 Register Guest")

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

    # ── Registration Form ────────────────────────────────────────────────────
    with st.form("register_form", clear_on_submit=True):
        st.markdown("### 📝 Step 2: Fill Your Details")

        name = st.text_input(
            "Full Name *",
            placeholder="Enter your full name (letters only)",
            max_chars=100,
            help="Use letters and spaces only. Example: John Smith or Mary Jane",
        )
        email = st.text_input("Email Address *", placeholder="your@email.com", max_chars=120)
        phone = st.text_input(
            "Phone Number (optional)",
            placeholder="+1 234 567 8900",
            max_chars=30,
            help="Optional. If provided, enter a valid 10-15 digit number.",
        )
        plus_one_name = st.text_input(
            "Plus One Name (optional)",
            placeholder="Name of your guest",
            max_chars=100,
            help="Optional. If you're bringing a guest, enter their name.",
        )
        ticket_count = st.number_input(
            "Number of Tickets *", min_value=1, max_value=20, value=1, step=1
        )

        # Price display
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

        zelle_ref = st.text_input(
            "Zelle Transaction Reference *",
            placeholder="e.g. ZELLE12345678",
            help="Zelle confirmation numbers are typically 8-12 letters/digits from your bank. Accepted formats: 8-30 letters, digits, or hyphens. Examples: ZELLE12345678, 1234567890, TXN-ABCD1234, CONF-9876543210",
            max_chars=30,
        )

        # ── Terms & Conditions (placeholder; organizer will update text later) ───
        with st.expander("📜 Terms & Conditions"):
            st.markdown(
                """
                <div style='color: rgba(245,245,245,0.8); font-size: 0.9rem;'>
                    <p>Event terms and conditions will be updated here shortly by the organizer.</p>
                    <p>By registering, you agree to:</p>
                    <ul>
                        <li>Show your QR code at the entrance for check-in.</li>
                        <li>Follow all event guidelines and venue rules.</li>
                        <li>Understand that tickets are non-refundable.</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
            agree_terms = st.checkbox("I agree to the terms and conditions", value=True)

        st.markdown(
            "<small style='opacity:0.6'>* Required fields. By registering, you agree to show your QR code at the entrance and follow event guidelines.</small>",
            unsafe_allow_html=True,
        )

        submitted = st.form_submit_button(
            "✅ Get My QR Code", use_container_width=True, type="primary"
        )

    if submitted:
        name_clean = sanitize_name(name)
        email_clean = sanitize_email(email)
        phone_clean = sanitize_phone(phone)
        plus_one_clean = sanitize_name(plus_one_name) if plus_one_name.strip() else ""
        zelle_clean = sanitize_zelle_ref(zelle_ref)

        if not name_clean:
            st.error("Please enter a valid full name using letters and spaces only.")
            return
        if not email_clean:
            st.error("Please enter a valid email address.")
            return
        if phone and not phone_clean:
            st.error("Please enter a valid phone number with 10-15 digits, or leave it blank.")
            return
        if plus_one_name.strip() and not plus_one_clean:
            st.error("Plus one name must contain letters and spaces only.")
            return
        if not agree_terms:
            st.error("Please agree to the terms and conditions to continue.")
            return
        if not zelle_clean:
            st.error("Zelle transaction reference is required (8-30 characters: letters, digits, hyphens). Example: ZELLE12345678, TXN-ABCD1234, 1234567890")
            return

        session = get_db()
        try:
            existing = session.query(Guest).filter_by(email=email_clean).first()
            if existing:
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
            if not email_sent:
                st.warning("QR code generated but email could not be sent. Please download below.")
            else:
                st.success(f"QR code emailed to {email_clean}")

            st.session_state["registered_guest_id"] = guest_id
            st.rerun()
        finally:
            session.close()


def _show_registration_success(guest):
    """Display the post-registration success screen with QR code."""
    st.success(f"✅ Registration successful! Welcome, {guest.name}!")
    st.balloons()

    plus_one_line = f"<div style='font-size: 0.9rem; color: #F4E4BC; margin-top: 6px;'>👤 Plus One: {guest.plus_one_name}</div>" if guest.plus_one_name else ""

    st.markdown(
        f"""
        <div style='text-align: center; background: rgba(212,175,55,0.08); border: 1px solid rgba(212,175,55,0.3); border-radius: 20px; padding: 20px; margin: 16px 0;'>
            <div style='font-size: 1.4rem; font-weight: 800; color: #F4E4BC; margin-bottom: 4px;'>🎉 You're In!</div>
            <div style='font-size: 1rem; color: #F5F5F5; margin-bottom: 12px;'>Screenshot or download your QR code</div>
            <div style='font-size: 0.95rem; color: rgba(245,245,245,0.7);'>
                <strong>{guest.name}</strong> • {guest.ticket_count} Ticket{'s' if guest.ticket_count > 1 else ''}<br>
                {plus_one_line}
                <small>Zelle Ref: {guest.zelle_ref}</small>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    qr_bytes = generate_qr_image(guest.qr_code, guest.name)

    # Center and enlarge QR for mobile screenshot
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.image(qr_bytes, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            label="💾 Download QR",
            data=qr_bytes,
            file_name=f"party_qr_{guest.name.replace(' ', '_')}.png",
            mime="image/png",
            use_container_width=True,
        )
    with c2:
        if st.button("🔄 Register Another", use_container_width=True):
            st.session_state["registered_guest_id"] = None
            st.rerun()

    st.info("📧 A copy has also been sent to your email. Check spam/junk if not found.")


# ═══════════════════════════════════════════════════════════════════════════════
# MY QR PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_my_qr():
    st.title("📱 My QR Code")
    st.caption("Look up your party QR code")

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
    st.title("📷 Self Check-In")
    st.caption("Scan your QR code at the entrance")

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
        guest.checkin_time = datetime.utcnow()
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
    st.title("📊 Admin Dashboard")
    st.caption("Manage guests and monitor check-ins")

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
                            selected_guest.checkin_time = datetime.utcnow()
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
        st.markdown("<small>v2.1 • Streamlit Edition</small>", unsafe_allow_html=True)

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
