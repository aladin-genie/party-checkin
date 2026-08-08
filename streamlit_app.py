"""
Party Check-In System — Streamlit App (Mobile-First, v2.1)
Entry point for Streamlit Community Cloud (free hosting).
"""

import base64
from datetime import datetime

import streamlit as st
import cv2
import numpy as np
from PIL import Image

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
)

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Party Check-In",
    page_icon="🎉",
    layout="centered",  # centered is better for mobile
    initial_sidebar_state="collapsed",  # collapsed by default for mobile
)

# ── Custom CSS for mobile-first UX ───────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Larger touch targets for mobile */
    button, .stButton>button {
        min-height: 48px !important;
        font-size: 1.1rem !important;
    }
    input, .stTextInput>div>div>input, .stNumberInput>div>div>input {
        font-size: 1.05rem !important;
        min-height: 44px !important;
    }
    /* Better spacing on mobile */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }
    /* Make QR code image larger on mobile */
    img[alt*="QR"] {
        max-width: 100% !important;
        width: 320px !important;
    }
    /* Hide default hamburger menu animation noise */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Initialize DB ────────────────────────────────────────────────────────────
init_db()

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

ZELLE_INFO = st.secrets.get("ZELLE_INFO", "")


# ═══════════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_home():
    st.title("🎉 Party 2026")
    st.caption("QR Code Check-In System")

    stats = get_stats()

    # Stats cards — 2x2 grid for mobile
    c1, c2 = st.columns(2)
    c1.metric("Registered", stats["total_guests"])
    c2.metric("Checked In", stats["checked_in"])
    c3, c4 = st.columns(2)
    c3.metric("Bands Given", stats["bands_distributed"])
    c4.metric("Total Tickets", stats["total_tickets"])

    st.divider()

    # Navigation cards — stacked for mobile, side-by-side for desktop
    st.subheader("Get Started")

    with st.container(border=True):
        st.markdown("### 📝 Register Guest")
        st.markdown("Pay via Zelle, get your QR code by email")
        if st.button("📝 Register →", key="nav_register", use_container_width=True):
            st.session_state["page"] = "Register"
            st.rerun()

    with st.container(border=True):
        st.markdown("### 📷 Self Check-In")
        st.markdown("Scan your QR code at the entrance")
        if st.button("📷 Scanner →", key="nav_scanner", use_container_width=True):
            st.session_state["page"] = "Scanner"
            st.rerun()

    with st.container(border=True):
        st.markdown("### 📊 Admin Dashboard")
        st.markdown("Manage guests and download reports")
        if st.button("📊 Admin →", key="nav_admin", use_container_width=True):
            st.session_state["page"] = "Admin"
            st.rerun()

    st.divider()
    st.markdown(
        "<p style='text-align:center; opacity:0.6; font-size:0.85em;'>Ready for 200+ guests • Auto-announcements • Wristband tracking</p>",
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

    # ── Zelle Payment Info Card (prominent, mobile-first) ────────────────────
    with st.container(border=True):
        st.markdown("### 💳 Step 1: Pay via Zelle")
        st.markdown(
            "Before registering, send your payment via Zelle in your banking app. "
            "You will need the **transaction confirmation number** on the next step."
        )
        if ZELLE_INFO:
            st.info(f"**Send Zelle to:** {ZELLE_INFO}")
        else:
            st.info(
                "**Send Zelle to:** [Your organizer will share their Zelle phone/email]"
            )
        st.markdown(f"**Price:** ${TICKET_PRICE:.2f} per ticket")

    # ── Registration Form ────────────────────────────────────────────────────
    with st.form("register_form", clear_on_submit=True):
        st.markdown("### 📝 Step 2: Fill Your Details")

        name = st.text_input("Full Name *", placeholder="Enter your full name", max_chars=100)
        email = st.text_input("Email Address *", placeholder="your@email.com", max_chars=120)
        phone = st.text_input("Phone Number (optional)", placeholder="+1 234 567 8900", max_chars=30)
        ticket_count = st.number_input(
            "Number of Tickets *", min_value=1, max_value=20, value=1, step=1
        )

        # Price display
        total = ticket_count * TICKET_PRICE
        st.markdown(
            f"""
            <div style='background: linear-gradient(135deg, #8B7E74 0%, #A0938B 100%); color: white; padding: 18px; border-radius: 12px; text-align: center; margin: 15px 0;'>
                <div style='font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; opacity: 0.9;'>Total to Pay</div>
                <div style='font-size: 2.2em; font-weight: bold;'>${total:.2f}</div>
                <div style='font-size: 0.85em; opacity: 0.8;'>{int(ticket_count)} ticket{'s' if ticket_count > 1 else ''} × ${TICKET_PRICE:.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        zelle_ref = st.text_input(
            "Zelle Transaction Reference *",
            placeholder="e.g. ABC-12345678 or confirmation #",
            help="Find this in your bank app after sending the Zelle payment",
            max_chars=100,
        )

        st.markdown(
            "<small style='opacity:0.7'>* Required fields. By registering, you agree to show your QR code at the entrance.</small>",
            unsafe_allow_html=True,
        )

        submitted = st.form_submit_button(
            "✅ Get My QR Code", use_container_width=True, type="primary"
        )

    if submitted:
        name_clean = sanitize_name(name)
        email_clean = sanitize_email(email)
        phone_clean = sanitize_phone(phone)
        zelle_clean = sanitize_zelle_ref(zelle_ref)

        if not name_clean or not email_clean:
            st.error("Name and email are required!")
            return
        if not zelle_clean:
            st.error("Zelle transaction reference is required to verify your payment.")
            return
        if not email_clean:
            st.error("Please enter a valid email address.")
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

    st.markdown("### 📱 Your QR Code")
    st.caption("Screenshot this page or download the image. Show it at the entrance.")

    qr_bytes = generate_qr_image(guest.qr_code, guest.name)

    # Center and enlarge QR for mobile screenshot
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.image(qr_bytes, use_container_width=True)

    st.markdown(
        f"""
        <div style='text-align: center; margin: 10px 0;'>
            <strong>{guest.name}</strong><br>
            {guest.ticket_count} Ticket{'s' if guest.ticket_count > 1 else ''}<br>
            <small style='opacity:0.6'>Zelle Ref: {guest.zelle_ref}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
