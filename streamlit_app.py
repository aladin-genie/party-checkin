"""
Party Check-In System — Streamlit App (Mobile-First, v3.0)
Entry point for Streamlit Community Cloud (free hosting).
"""

import time
import traceback
from types import SimpleNamespace

import streamlit as st

startup_error = None
try:
    import base64
    import html
    import os
    from datetime import datetime

    import pandas as pd

    import utils
    import config
    import theme
except Exception:
    startup_error = traceback.format_exc()

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{config.EVENT_NAME if not startup_error else 'Party Check-In'} — Check-In",
    page_icon="🎊",
    layout="centered",  # centered is better for mobile
    initial_sidebar_state="collapsed",  # collapsed by default for mobile
)

if startup_error:
    st.error("🚨 The app failed to start. Please share this error with the developer:")
    st.code(startup_error)
    st.stop()

# ── Initialize DB ─────────────────────────────────────────────────────────────
try:
    utils.ensure_db_ready()
except Exception:
    st.error("🚨 The app failed to start. Please share this error with the developer:")
    st.code(traceback.format_exc())
    st.stop()

theme.inject_css()

PAGES = ["Home", "Register", "My QR", "Scanner", "Admin"]

# ── Session State Defaults ───────────────────────────────────────────────────
def _ensure_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default


_ensure_state("registered_guest_id", None)
_ensure_state("scanner_result", None)
_ensure_state("admin_authenticated", False)
_ensure_state("admin_fail_count", 0)
_ensure_state("admin_lockout_until", 0.0)
_ensure_state("reg_errors", {})
_ensure_state("admin_pending_changes", None)
_ensure_state("flash", None)

# ── Constants ──────────────────────────────────────────────────────────────────
TICKET_PRICE = config.ticket_price_dollars()
ZELLE_INFO = config.zelle_info()


# ── Cached data reads ────────────────────────────────────────────────────────
# Streamlit reruns the whole script on every interaction; without this, every
# click would fire several queries against the remote Postgres DB. Mutations
# clear only the specific cache(s) their write affects (see PART 7) rather
# than st.cache_data.clear(), which would wipe every cached value for every
# user in the whole app.
@st.cache_data(ttl=10, show_spinner=False)
def _cached_stats():
    return utils.get_stats()


@st.cache_data(ttl=10, show_spinner=False)
def _cached_site_stats():
    return utils.get_site_stats()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_registration_daily_counts():
    return utils.get_registration_daily_counts()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_event_day_hourly_checkins():
    return utils.get_event_day_hourly_checkins()


def _fmt_checkin_iso(iso_str, fmt="%I:%M %p"):
    """Format an ISO-string checkin_time (as returned by Guest.to_dict()).

    utils.format_dt() expects a real datetime, not the ISO string that dict
    payloads carry, so this parses it back first. Tolerates None/garbage.
    """
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
    except Exception:
        return "—"
    return utils.format_dt(dt, fmt)


# ── Flash messages ────────────────────────────────────────────────────────────
# st.success/st.warning/st.error/st.info render into the CURRENT script frame.
# Several actions in this app do a mutation and then call st.rerun() right
# away so the page reflects the new state — but that discards the current
# frame before the browser ever paints it, so a message shown immediately
# before st.rerun() is never actually seen (see PART 6). Any such call site
# should stash its message with _set_flash() instead and let the top of the
# *next* run display it via _render_flash().
def _set_flash(kind: str, message: str) -> None:
    st.session_state["flash"] = {"kind": kind, "message": message}


def _render_flash() -> None:
    flash = st.session_state.pop("flash", None)
    if flash:
        renderer = {
            "success": st.success,
            "warning": st.warning,
            "error": st.error,
            "info": st.info,
        }.get(flash["kind"], st.info)
        renderer(flash["message"])


def _render_bar_chart(df):
    """st.bar_chart, falling back to a plain table if chart rendering fails.

    Some environments ship an altair build that's incompatible with the
    running Python's `typing.TypedDict` (unrelated to this app's code) and
    raise on any st.bar_chart call. Never let that take down the whole
    page — degrade to a table instead.

    Charts are drawn in the theme's gold rather than Streamlit's default blue,
    which clashes badly with the dark/gold palette, and are given a fixed
    height so a 24-bar check-in chart doesn't swallow the whole viewport.
    """
    try:
        st.bar_chart(df, color=theme.CHART_COLOR, height=260, use_container_width=True)
    except TypeError:
        # Older/newer Streamlit signatures may not accept color/height.
        try:
            st.bar_chart(df, use_container_width=True)
        except Exception:
            st.dataframe(df, use_container_width=True)
    except Exception:
        st.dataframe(df, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_home():
    st.markdown(theme.hero(), unsafe_allow_html=True)

    # Warn if running on fallback SQLite (e.g., Cloud secret missing or DB unreachable)
    try:
        if utils._using_fallback_db():
            st.warning(
                "Running on a temporary local database. Guest data will not persist across restarts. "
                "Please set the DATABASE_URL secret in Streamlit Cloud to connect to Supabase.",
                icon="🗄️",
            )
    except Exception:
        pass

    # ── Party Buzz ──────────────────────────────────────────────────────────
    # Public, aggregate-only site activity — no guest names/emails/phones/
    # Zelle refs ever appear here. Moved from the admin dashboard: the owner
    # doesn't consider it sensitive and would rather show it off than bury it.
    site_stats = _cached_site_stats()
    st.markdown(
        theme.section_header(
            "🎉 Party Buzz", "A live pulse of the site so far — nothing guest-specific, just the vibe."
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        theme.stat_tiles(
            [
                ("Unique Visitors", site_stats["unique_visitors"], "All time"),
                ("Page Views", site_stats["total_visits"], "All time"),
                ("Registered Guests", site_stats["total_regs"], f"+{site_stats['today_regs']} today"),
                ("Visitors Today", site_stats["today_unique"], f"{site_stats['today_visits']} views"),
            ]
        ),
        unsafe_allow_html=True,
    )

    daily_counts = _cached_registration_daily_counts()
    if daily_counts:
        reg_df = pd.DataFrame(
            {"Registrations": [c for _, c in daily_counts]},
            index=[d.strftime("%b %d") for d, _ in daily_counts],
        )
        st.caption("📈 Registrations by day — how quickly folks have been signing up.")
        _render_bar_chart(reg_df)
    else:
        st.info("No registrations yet — be the first to sign up!")

    hourly = _cached_event_day_hourly_checkins()
    if any(hourly):
        checkin_df = pd.DataFrame(
            {"Check-ins": hourly},
            index=[f"{h:02d}:00" for h in range(24)],
        )
        st.caption(f"🚪 Check-ins by hour on {config.EVENT_DATE_SHORT} — the flow through the door.")
        _render_bar_chart(checkin_df)
    else:
        st.info(f"Check-ins will show up here live once doors open on {config.EVENT_DATE_SHORT}.")

    st.markdown(theme.section_header("Get Started"), unsafe_allow_html=True)

    # Navigation cards
    nav_items = [
        ("📝", "Register Guest", "Pay via Zelle, get your QR code by email", "nav_register", "Register"),
        ("📱", "My QR Code", "Look up your ticket QR code by email", "nav_my_qr", "My QR"),
        ("📷", "Self Check-In", "Scan your QR code at the entrance", "nav_scanner", "Scanner"),
        ("📊", "Admin Dashboard", "Manage guests and download reports", "nav_admin", "Admin"),
    ]
    for icon, title, desc, key, page in nav_items:
        with st.container(border=True):
            st.markdown(theme.nav_card(icon, title, desc), unsafe_allow_html=True)
            if st.button(f"{icon} {title} →", key=key, use_container_width=True):
                st.session_state["page"] = page
                st.rerun()

    st.markdown(theme.footer(), unsafe_allow_html=True)


def _home_button(key="home_button"):
    """Render a Home button that returns to the Home page."""
    if st.button("🏠 Home", key=key, use_container_width=True):
        st.session_state["page"] = "Home"
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def page_register():
    # Reset form fields at the very top, before any widgets are instantiated,
    # so stale values don't appear when re-entering the page or clicking "Register Another".
    if st.session_state.get("reset_register_form"):
        for _key in ("reg_name", "reg_email", "reg_phone", "reg_plus_one", "reg_zelle", "ticket_count"):
            st.session_state.pop(_key, None)
        st.session_state["reg_agree"] = False
        st.session_state["reg_errors"] = {}
        st.session_state["reset_register_form"] = False

    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.title("📝 Register Guest")
    with header_col2:
        _home_button(key="home_register")

    # If a guest was just registered, show their QR
    if st.session_state.get("registered_guest_id"):
        guest_id = st.session_state["registered_guest_id"]
        guest = utils.get_guest(guest_id)
        if guest:
            _show_registration_success(guest)
            return
        st.session_state["registered_guest_id"] = None

    st.markdown(theme.stepper(2), unsafe_allow_html=True)

    # ── Zelle Payment Info Card ────────────────────────────────────────────
    st.markdown(theme.payment_card(ZELLE_INFO, TICKET_PRICE), unsafe_allow_html=True)

    # ── Ticket count & dynamic total (outside form so it updates live) ────
    st.markdown(theme.section_header("Select Tickets"), unsafe_allow_html=True)
    ticket_count = st.number_input(
        "Number of Tickets *",
        min_value=1,
        max_value=20,
        value=1,
        step=1,
        key="ticket_count",
        help="Select number of tickets. The total updates automatically as you change it.",
    )
    st.markdown(theme.total_card(ticket_count, TICKET_PRICE), unsafe_allow_html=True)

    # ── Registration Details ───────────────────────────────────────────────
    st.markdown(theme.section_header("Step 2: Fill Your Details"), unsafe_allow_html=True)

    reg_errors = st.session_state.get("reg_errors", {})
    if reg_errors:
        st.markdown(theme.validation_banner(len(reg_errors)), unsafe_allow_html=True)

    # Use a form for personal details so typing in these fields doesn't trigger a
    # Streamlit rerun on every keystroke. The ticket selector stays outside the
    # form so its total updates live.
    with st.form("registration_form"):
        name = st.text_input(
            "Full Name *",
            key="reg_name",
            placeholder="Enter your full name (letters only)",
            max_chars=100,
            help="Use letters and spaces only. Example: John Smith or Mary Jane",
        )
        if "name" in reg_errors:
            st.markdown(theme.field_error(reg_errors["name"]), unsafe_allow_html=True)

        email = st.text_input(
            "Email Address *",
            key="reg_email",
            placeholder="your@email.com",
            max_chars=120,
        )
        if "email" in reg_errors:
            st.markdown(theme.field_error(reg_errors["email"]), unsafe_allow_html=True)

        phone = st.text_input(
            "Phone Number (optional)",
            key="reg_phone",
            placeholder="+1-XXX-XXX-XXXX",
            max_chars=20,
            help="US numbers only. Enter 10 digits; the format +1-XXX-XXX-XXXX will be applied when you submit.",
        )
        if "phone" in reg_errors:
            st.markdown(theme.field_error(reg_errors["phone"]), unsafe_allow_html=True)

        plus_one_name = st.text_area(
            "Additional Guest Names (optional)",
            key="reg_plus_one",
            placeholder="Jane Doe\nJohn Doe\nMary Smith",
            help="One name per line (or comma-separated) — up to 20.",
            height=120,
            max_chars=1000,
        )
        if "plus_one_name" in reg_errors:
            st.markdown(theme.field_error(reg_errors["plus_one_name"]), unsafe_allow_html=True)

        zelle_ref = st.text_input(
            "Zelle Transaction Reference *",
            key="reg_zelle",
            placeholder="e.g. ZELLE12345678",
            max_chars=30,
            help="8-30 letters, digits, or hyphens. Examples: ZELLE12345678, TXN-ABCD1234, 1234567890",
        )
        if "zelle_ref" in reg_errors:
            st.markdown(theme.field_error(reg_errors["zelle_ref"]), unsafe_allow_html=True)

        # ── Terms & Conditions ──────────────────────────────────────────────
        # Auto-expand when the previous submit failed on this field — otherwise
        # a user who submits without ticking "I/We Agree" sees the form get
        # rejected with no visible reason, since the error renders inside this
        # (default-collapsed) expander.
        with st.expander(
            "📜 Terms & Conditions — Alcohol Disclaimer & Waiver",
            expanded=("terms" in reg_errors),
        ):
            event_title = f"{html.escape(config.EVENT_NAME)} on {html.escape(config.EVENT_DATE_TEXT)}"
            st.markdown(
                f"""
                <div style='color: rgba(245,245,245,0.85); font-size: 0.88rem; line-height: 1.5;'>
                    <h4 style='color: #F4E4BC; margin-top: 0;'>Alcohol Disclaimer</h4>
                    <p>
                        I (Individual) or We (for all the listed attendees in this form and/or a person who is making group Zelle payment representing the group) the undersigned, hereby voluntarily assume all risks associated with participating in the activities related to the <strong>{event_title}</strong>.
                    </p>
                    <p>
                        I/We understand that the {html.escape(config.EVENT_NAME)} organizers will not provide alcohol on-site, and that all alcohol at the event is BYOB (Bring Your Own Beverage). I/We acknowledge that consuming alcohol may impair judgment, motor skills, vision, and other abilities, and can lead to various health risks such as intoxication, nausea, vomiting, drowsiness, and other symptoms. I/We also understand that alcohol consumption can increase aggression and impair decision-making.
                    </p>
                    <p>
                        I/We acknowledge that it is my responsibility to ensure that no underage or prohibited individuals in my group consume alcohol, and I/We will comply with all local laws regarding alcohol consumption during the event.
                    </p>
                    <p>
                        I/We understand that the {html.escape(config.EVENT_NAME)} organizers are not responsible for any property damage, injuries, or fatalities that may result from alcohol consumption or any activities during the event. By participating, I/We hereby release and discharge the {html.escape(config.EVENT_NAME)} organizers, their owners, employees, volunteers, representatives, and agents from any and all liability for incidents occurring before, during, or after the event, including travel to and from the venue. This waiver includes, but is not limited to, liability arising from negligence.
                    </p>
                    <p>
                        In consideration of being allowed to participate, I/We further agree to indemnify and hold harmless the {html.escape(config.EVENT_NAME)} organizers and their representatives from any claims or liabilities resulting from my participation in the event, including any consequences arising from alcohol consumption.
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
            agree_terms = st.checkbox("I/We Agree", key="reg_agree")
            if "terms" in reg_errors:
                st.markdown(theme.field_error(reg_errors["terms"]), unsafe_allow_html=True)

        submitted = st.form_submit_button("🎟️ Get My QR Code", type="primary", use_container_width=True)

    st.markdown(
        "<small style='opacity:0.6'>* Required fields. By registering, you agree to the Terms & Conditions. "
        "Your QR code will be emailed to you.</small>",
        unsafe_allow_html=True,
    )

    if submitted:
        cleaned, errors = utils.validate_registration(
            name, email, phone, plus_one_name, zelle_ref, agree_terms
        )

        if errors:
            st.session_state["reg_errors"] = errors
            utils.record_submission(
                name=cleaned["name"] or name,
                email=cleaned["email"] or email,
                phone=cleaned["phone"] or phone,
                ticket_count=ticket_count,
                plus_one_name=cleaned["plus_one_name"] or plus_one_name,
                zelle_ref=cleaned["zelle_ref"] or zelle_ref,
                status="validation_error",
                errors="; ".join(errors.values()),
            )
            st.rerun()

        st.session_state["reg_errors"] = {}
        result = utils.register_guest(
            cleaned["name"],
            cleaned["email"],
            cleaned["phone"],
            int(ticket_count),
            cleaned["plus_one_name"],
            cleaned["zelle_ref"],
        )

        if result["ok"]:
            guest = result["guest"]
            # Fire-and-forget: a guest who just paid shouldn't stare at a
            # spinner for a full SMTP round-trip. The success screen below
            # reflects this honestly — it says the email is "on its way",
            # not that it was delivered (see PART 1).
            utils.send_qr_email_async(guest)
            utils.record_submission(
                name=cleaned["name"],
                email=cleaned["email"],
                phone=cleaned["phone"],
                ticket_count=ticket_count,
                plus_one_name=cleaned["plus_one_name"],
                zelle_ref=cleaned["zelle_ref"],
                status="registered",
                guest_id=guest["id"],
            )
            _cached_stats.clear()
            _cached_site_stats.clear()
            _cached_registration_daily_counts.clear()
            st.session_state["registered_guest_id"] = guest["id"]
            st.rerun()
        else:
            reason = result["reason"]
            utils.record_submission(
                name=cleaned["name"],
                email=cleaned["email"],
                phone=cleaned["phone"],
                ticket_count=ticket_count,
                plus_one_name=cleaned["plus_one_name"],
                zelle_ref=cleaned["zelle_ref"],
                status=reason,
                errors=result["message"],
            )
            if reason == "duplicate_email":
                st.session_state["reg_errors"] = {"email": result["message"]}
                st.rerun()
            else:
                st.error(
                    "⚠️ We couldn't save your registration due to a database problem. "
                    "Please try again in a moment, or contact the organizer if it keeps happening."
                )


def _show_registration_success(guest: dict):
    """Display the post-registration confirmation. QR code is emailed; not shown here."""
    st.balloons()
    st.markdown(theme.stepper(3), unsafe_allow_html=True)

    name = guest["name"]
    email = guest["email"]
    tickets = guest["ticket_count"]
    plus_one = guest.get("plus_one_name") or ""

    # The email send is fire-and-forget (utils.send_qr_email_async) — we have
    # no result to report here, so this must not claim delivery (see PART 1).
    st.success(
        f"🎉 You're registered, {name}! Your QR code is on its way to {email} — "
        "check your inbox (and spam folder) in a few minutes."
    )

    st.markdown(theme.section_header("You're In!"), unsafe_allow_html=True)
    st.markdown(f"**{name}** • {tickets} Ticket{'s' if tickets != 1 else ''}")
    if plus_one:
        names_list = [n for n in plus_one.split("\n") if n.strip()]
        st.markdown(f"**Additional Guests ({len(names_list)}):**")
        st.markdown("\n".join(f"- {n}" for n in names_list))
    st.markdown(f"📧 Sending your QR code to: `{email}`")
    st.divider()

    st.info("📧 No need to screenshot — your QR code is on its way to your email.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📧 Resend QR Email", use_container_width=True):
            with st.spinner("Emailing your QR code…"):
                sent = utils.send_qr_email(SimpleNamespace(**guest))
            if sent:
                st.success("QR code emailed again!")
            else:
                st.warning(
                    "We couldn't send the email right now (SMTP may be disabled in this environment). "
                    "Please try again later or contact the organizer."
                )
    with col2:
        if st.button("🔄 Register Another", use_container_width=True):
            st.session_state["registered_guest_id"] = None
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
        guest = utils.get_guest(guest_id)
        if guest:
            _display_guest_qr(guest)
            return
        else:
            st.error("Guest not found.")

    # Email lookup. This lives in a form so the typed value is committed
    # atomically with the button press — outside a form, Streamlit treats the
    # text edit and the click as two separate reruns, and a user who types and
    # immediately clicks can submit an empty value. A form also lets them just
    # press Enter.
    with st.form("qr_lookup_form"):
        lookup_email = st.text_input("Enter your email", placeholder="your@email.com")
        lookup_submitted = st.form_submit_button(
            "🔍 Find My QR", type="primary", use_container_width=True
        )

    found = False
    if lookup_submitted:
        if lookup_email:
            email_clean = utils.sanitize_email(lookup_email)
            if not email_clean:
                st.error("Please enter a valid email.")
                return
            guest = utils.get_guest_by_email(email_clean)
            if guest:
                _display_guest_qr(guest)
                found = True
            else:
                st.error("No guest found with that email. Please register first.")

    if not found:
        with st.container(border=True):
            st.markdown(
                theme.nav_card(
                    "💡",
                    "What is this page?",
                    "Enter the email address you registered with above to pull up your ticket "
                    "QR code. Your QR code was also emailed to you when you registered — check "
                    "your inbox (and spam folder) for it.",
                ),
                unsafe_allow_html=True,
            )
            if st.button(
                "📝 Haven't registered yet? Go to Register",
                key="my_qr_go_register",
                use_container_width=True,
            ):
                st.session_state["page"] = "Register"
                st.rerun()


def _display_guest_qr(guest: dict):
    """Render a guest's QR code card."""
    st.markdown(f"### {guest['name']}")
    tickets = guest["ticket_count"]
    st.caption(f"{tickets} Ticket{'s' if tickets != 1 else ''}")

    qr_bytes = utils.generate_qr_image(guest["qr_code"])

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
        file_name=f"party_qr_{guest['name'].replace(' ', '_')}.png",
        mime="image/png",
        use_container_width=True,
    )

    if st.button("📧 Resend QR Email", use_container_width=True):
        with st.spinner("Emailing your QR code…"):
            sent = utils.send_qr_email(SimpleNamespace(**guest))
        if sent:
            st.success("QR code emailed!")
        else:
            st.warning(
                "We couldn't send the email right now (SMTP may be disabled in this environment). "
                "Please try again later or contact the organizer."
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

    stats = _cached_stats()
    st.markdown(
        theme.stat_tiles(
            [
                ("Checked In", stats["checked_in"], ""),
                ("Total Guests", stats["total_guests"], ""),
            ]
        ),
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Check-in window gate (see PART 3) ──────────────────────────────────
    # The public Scanner must never render the camera/manual-entry inputs
    # while check-in is closed — there's nothing useful a guest could do with
    # them, and utils.check_in_by_code() would just reject the attempt
    # anyway. The server-side window check in utils.check_in_by_code() is
    # the real control; this is just so guests aren't shown dead inputs.
    status = utils.checkin_status()
    if not status["open"]:
        st.markdown(
            theme.closed_notice(status["message"] or f"Opens {status['opens_at_text']}."),
            unsafe_allow_html=True,
        )
        return

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
    # Wrapped in a form so the typed code is committed atomically with the
    # button press. Outside a form, Streamlit handles the text edit and the
    # click as two separate reruns, so someone who types a code and clicks
    # straight away can submit an empty value — a nasty failure mode on a
    # door queue. The form also lets staff just hit Enter after scanning.
    with st.form("manual_checkin_form"):
        manual_code = st.text_input(
            "Ticket ID / Email / QR Code", placeholder="Enter here", max_chars=200
        )
        manual_submitted = st.form_submit_button(
            "Check In Manually", type="primary", use_container_width=True
        )

    if manual_submitted:
        if manual_code.strip():
            _process_checkin(manual_code.strip())
        else:
            st.error("Please enter a ticket ID or email.")

    # ── Display Result ─────────────────────────────────────────────────────
    if st.session_state.get("scanner_result"):
        result = st.session_state["scanner_result"]
        _show_scanner_result(result)


def _process_checkin(code: str):
    """Thin wrapper over utils.check_in_by_code that updates UI state."""
    result = utils.check_in_by_code(code)

    if result["status"] == "not_open":
        # Defensive: the Scanner page already hides these inputs while
        # closed, but the window can close between page-load and button
        # click (e.g. an admin flips the mode mid-scan). check_in_by_code()
        # returns guest=None here, so this must be handled before the
        # "success" fallthrough below, which assumes a guest dict.
        st.session_state["scanner_result"] = {
            "type": "error",
            "message": result["message"] or "Check-in isn't open yet.",
        }
        st.rerun()
        return

    if result["status"] == "not_found":
        st.session_state["scanner_result"] = {
            "type": "error",
            "message": result["message"],
        }
        st.rerun()
        return

    if result["status"] == "already":
        st.session_state["scanner_result"] = {
            "type": "warning",
            "guest": result["guest"],
            "message": result["message"],
        }
        st.rerun()
        return

    # success
    guest = result["guest"]
    _cached_stats.clear()
    _cached_event_day_hourly_checkins.clear()
    announcement = utils.generate_welcome_announcement(guest["name"], guest["ticket_count"])
    st.session_state["scanner_result"] = {
        "type": "success",
        "guest": guest,
        "message": result["message"],
        "announcement": announcement,
        "guest_id": guest["id"],
    }
    st.rerun()


def _show_scanner_result(result):
    """Display the scanner result UI and play audio."""
    result_type = result.get("type")

    if result_type == "success":
        guest = result["guest"]
        st.balloons()
        st.markdown(
            theme.guest_result_card(guest["name"], guest["ticket_count"], "success", result["message"]),
            unsafe_allow_html=True,
        )

        if st.button("✓ Mark Band Given", type="primary", use_container_width=True):
            _mark_band_given(result["guest_id"])

        announcement = result.get("announcement", "")
        if announcement:
            st.components.v1.html(utils.audio_announcement_js(announcement), height=0)
            st.info(f"🔊 {announcement}")

        if st.button("🔄 Scan Next Guest", use_container_width=True):
            st.session_state["scanner_result"] = None
            st.rerun()

    elif result_type == "warning":
        guest = result["guest"]
        st.markdown(
            theme.guest_result_card(guest["name"], guest["ticket_count"], "already", result["message"]),
            unsafe_allow_html=True,
        )

        if st.button("🔄 Scan Next Guest", use_container_width=True):
            st.session_state["scanner_result"] = None
            st.rerun()

    elif result_type == "error":
        st.markdown(
            theme.guest_result_card("Unknown", None, "error", result["message"]),
            unsafe_allow_html=True,
        )

        if st.button("🔄 Try Again", use_container_width=True):
            st.session_state["scanner_result"] = None
            st.rerun()


def _mark_band_given(guest_id: int):
    """Thin wrapper over utils.mark_band_given that updates UI state.

    Stashes the result via _set_flash() instead of calling st.success()
    directly — a st.rerun() follows immediately below, which used to discard
    the message before staff ever saw it (see PART 6).
    """
    result = utils.mark_band_given(guest_id)
    _cached_stats.clear()
    if result["ok"]:
        _set_flash("success", result["message"])
        st.components.v1.html(utils.audio_announcement_js("Band marked as given"), height=0)
        st.session_state["scanner_result"] = None
        st.rerun()
    else:
        st.warning(result["message"])


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN PAGE
# ═══════════════════════════════════════════════════════════════════════════════
ADMIN_MAX_ATTEMPTS = 5
ADMIN_LOCKOUT_SECONDS = 60


def page_admin():
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.title("📊 Admin Dashboard")
        st.caption("Manage guests and monitor check-ins")
    with header_col2:
        _home_button(key="home_admin")

    if not utils.admin_password_is_configured():
        st.error(
            "🚫 Admin password is not set — configure the ADMIN_PASSWORD secret to enable the dashboard."
        )
        return

    # ── Auth ─────────────────────────────────────────────────────────────────
    if not st.session_state.get("admin_authenticated"):
        lockout_until = st.session_state.get("admin_lockout_until", 0.0)
        now = time.time()

        if lockout_until and now < lockout_until:
            remaining = int(lockout_until - now) + 1
            st.error(f"🔒 Too many attempts. Try again in {remaining}s.")
            return

        if lockout_until and now >= lockout_until:
            st.session_state["admin_lockout_until"] = 0.0
            st.session_state["admin_fail_count"] = 0

        with st.form("admin_login"):
            st.info("Enter admin password to access the dashboard")
            password = st.text_input("Admin Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            if utils.verify_admin_password(password):
                st.session_state["admin_authenticated"] = True
                st.session_state["admin_fail_count"] = 0
                st.session_state["admin_lockout_until"] = 0.0
                st.rerun()
            else:
                fail_count = st.session_state.get("admin_fail_count", 0) + 1
                st.session_state["admin_fail_count"] = fail_count
                if fail_count >= ADMIN_MAX_ATTEMPTS:
                    st.session_state["admin_lockout_until"] = time.time() + ADMIN_LOCKOUT_SECONDS
                    st.error(f"🔒 Too many attempts. Try again in {ADMIN_LOCKOUT_SECONDS}s.")
                else:
                    st.error(f"Incorrect password. ({fail_count}/{ADMIN_MAX_ATTEMPTS} attempts)")
        return

    if st.button("🔒 Logout", type="secondary"):
        st.session_state["admin_authenticated"] = False
        st.rerun()

    tab_overview, tab_guests, tab_checkins = st.tabs(["Overview", "Guests", "Check-ins"])

    with tab_overview:
        _admin_overview_tab()
    with tab_guests:
        _admin_guests_tab()
    with tab_checkins:
        _admin_checkins_tab()


def _admin_overview_tab():
    stats = _cached_stats()
    st.markdown(theme.section_header("At a Glance"), unsafe_allow_html=True)
    st.markdown(
        theme.stat_tiles(
            [
                ("Total Guests", stats["total_guests"], ""),
                ("Checked In", stats["checked_in"], ""),
                ("Pending", stats["pending"], ""),
                ("Bands Given", stats["bands_distributed"], ""),
                ("Total Tickets", stats["total_tickets"], ""),
                ("Admitted", stats["admitted_tickets"], ""),
                ("Revenue (est.)", f"${stats['revenue']:,.2f}", ""),
                ("Plus Ones", stats["plus_one_count"], ""),
            ]
        ),
        unsafe_allow_html=True,
    )

    st.progress(
        stats["checkin_percentage"] / 100,
        text=f"Check-in rate: {stats['checkin_percentage']}%",
    )

    # ── Check-in window control (see PART 3) ───────────────────────────────
    st.markdown(
        theme.section_header(
            "Check-in Window", "Control when guests can check themselves in on the Scanner page."
        ),
        unsafe_allow_html=True,
    )

    status = utils.checkin_status()
    if status["open"]:
        detail_text = "guests can check themselves in on the Scanner page right now"
    elif status["mode"] == utils.CHECKIN_MODE_CLOSED:
        detail_text = "closed by the organiser"
    else:
        detail_text = f"opens {status['opens_at_text']}"
    st.markdown(theme.checkin_window_banner(status["open"], detail_text), unsafe_allow_html=True)

    mode_options = {
        "Auto (opens 2h before event)": utils.CHECKIN_MODE_AUTO,
        "Open now": utils.CHECKIN_MODE_OPEN,
        "Closed": utils.CHECKIN_MODE_CLOSED,
    }
    labels = list(mode_options.keys())
    current_label = next(label for label, mode in mode_options.items() if mode == status["mode"])
    chosen_label = st.radio(
        "Check-in mode",
        labels,
        index=labels.index(current_label),
        horizontal=True,
        key="admin_checkin_mode_radio",
    )
    chosen_mode = mode_options[chosen_label]
    if chosen_mode != status["mode"]:
        utils.set_checkin_mode(chosen_mode)
        _set_flash("success", f"Check-in mode set to “{chosen_label}”.")
        st.rerun()


def _admin_guests_tab():
    st.markdown(
        theme.section_header("Guests", "Search, check people in, hand out bands, or remove a row — all in one pass."),
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("+ Add Guest", use_container_width=True):
            st.session_state["page"] = "Register"
            st.rerun()
    with col2:
        csv_data = utils.generate_csv()
        st.download_button(
            label="⬇ Download CSV",
            data=csv_data,
            file_name=f"party_guests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    guests = utils.list_guests()

    if not guests:
        st.info("No guests registered yet. Once someone registers, they'll show up here.")
        return

    search_term = st.text_input(
        "🔍 Search by name, email, or Zelle ref", placeholder="Type to filter...", key="admin_guest_search"
    )

    filtered = guests
    if search_term:
        term = search_term.lower()
        filtered = [
            g
            for g in guests
            if term in g["name"].lower()
            or term in g["email"].lower()
            or term in (g["zelle_ref"] or "").lower()
        ]

    if not filtered:
        st.warning(f"No guests match “{search_term}”.")
        return

    st.caption(
        f"{len(filtered)} of {len(guests)} guest{'s' if len(guests) != 1 else ''} shown. "
        "Tick boxes below, then Save changes."
    )

    df = pd.DataFrame(
        [
            {
                "id": g["id"],
                "Name": g["name"],
                "Email": g["email"],
                "Tickets": g["ticket_count"],
                "Additional Guests": (g["plus_one_name"] or "").replace("\n", ", ") or "—",
                "Checked In": bool(g["checked_in"]),
                "Band Given": bool(g["band_given"]),
                "Delete": False,
            }
            for g in filtered
        ]
    )

    edited = st.data_editor(
        df,
        key="admin_guest_editor",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "id": None,  # keep for row identity, hide from display
            "Name": st.column_config.TextColumn("Name"),
            "Email": st.column_config.TextColumn("Email"),
            "Tickets": st.column_config.NumberColumn("Tickets"),
            "Additional Guests": st.column_config.TextColumn("Additional Guests"),
            "Checked In": st.column_config.CheckboxColumn("Checked In", help="Tick to check this guest in."),
            "Band Given": st.column_config.CheckboxColumn("Band Given", help="Tick once their wristband is on."),
            "Delete": st.column_config.CheckboxColumn("Delete", help="Tick then Save changes — a confirmation step follows."),
        },
        disabled=["id", "Name", "Email", "Tickets", "Additional Guests"],
    )

    if st.button("💾 Save changes", type="primary", use_container_width=True, key="admin_save_changes"):
        original_by_id = {g["id"]: g for g in filtered}
        pending = []
        for _, row in edited.iterrows():
            gid = int(row["id"])
            orig = original_by_id.get(gid)
            if not orig:
                continue
            pending.append(
                {
                    "id": gid,
                    "name": orig["name"],
                    "checked_in": bool(row["Checked In"]),
                    "band_given": bool(row["Band Given"]),
                    "delete": bool(row["Delete"]),
                }
            )

        to_delete = [p for p in pending if p["delete"]]
        if to_delete:
            # Destructive changes need an explicit confirm step — don't
            # apply anything (not even the check-ins/bands in this same
            # batch) until the admin confirms below (see PART 5).
            st.session_state["admin_pending_changes"] = pending
        else:
            result = utils.apply_guest_changes(pending)
            st.session_state.pop("admin_guest_editor", None)
            _apply_guest_changes_cache_clear(result)
            _report_guest_changes(result)
            st.rerun()

    pending_changes = st.session_state.get("admin_pending_changes")
    if pending_changes:
        to_delete = [p for p in pending_changes if p["delete"]]
        names = ", ".join(f"**{p['name']}**" for p in to_delete)
        count = len(to_delete)
        st.warning(
            f"⚠️ This will permanently delete {count} guest{'s' if count != 1 else ''}: {names}. "
            "This cannot be undone."
        )
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button(
                "Yes, apply changes (incl. delete)",
                type="primary",
                use_container_width=True,
                key="admin_confirm_apply",
            ):
                result = utils.apply_guest_changes(st.session_state["admin_pending_changes"])
                st.session_state["admin_pending_changes"] = None
                st.session_state.pop("admin_guest_editor", None)
                _apply_guest_changes_cache_clear(result)
                _report_guest_changes(result)
                st.rerun()
        with cc2:
            if st.button("Cancel", use_container_width=True, key="admin_cancel_apply"):
                st.session_state["admin_pending_changes"] = None
                st.rerun()


def _apply_guest_changes_cache_clear(result: dict) -> None:
    """Targeted cache invalidation after utils.apply_guest_changes() (PART 7)."""
    _cached_stats.clear()
    if result.get("deleted"):
        _cached_site_stats.clear()
        _cached_registration_daily_counts.clear()
    if result.get("checked_in") or result.get("deleted"):
        _cached_event_day_hourly_checkins.clear()


def _report_guest_changes(result: dict) -> None:
    """Report what utils.apply_guest_changes() actually did, via toast + flash.

    st.toast() persists across the single st.rerun() that follows this call,
    but it's brief (~4s) and easy to miss, so we also stash a longer-lived
    summary via _set_flash() to show at the top of the next run.
    """
    parts = []
    if result.get("checked_in"):
        parts.append(f"Checked in {result['checked_in']}")
    if result.get("band_given"):
        parts.append(f"Bands given {result['band_given']}")
    if result.get("deleted"):
        parts.append(f"Deleted {result['deleted']}")
    summary = " · ".join(parts) if parts else "No changes to apply."
    st.toast(summary, icon="✅" if parts else "ℹ️")
    _set_flash("success" if parts else "info", summary)


def _admin_checkins_tab():
    st.markdown(
        theme.section_header("Recent Check-ins", "The last 10 guests through the door."),
        unsafe_allow_html=True,
    )
    recent = utils.get_recent_checkins(10)
    if not recent:
        st.info("No check-ins yet. They'll appear here as guests arrive.")
        return

    for g in recent:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                tickets = g["ticket_count"]
                st.markdown(f"**{g['name']}** — {tickets} ticket{'s' if tickets != 1 else ''}")
                st.caption(f"Checked in at {_fmt_checkin_iso(g['checkin_time'], '%I:%M %p')}")
            with c2:
                st.markdown("✅ " + ("Band Given" if g["band_given"] else "No Band"))


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
                requested = qp["page"] if "page" in qp else None
                st.session_state["page"] = requested if requested in PAGES else "Home"
            except Exception:
                st.session_state["page"] = "Home"

        page = st.radio(
            "Navigate",
            PAGES,
            index=PAGES.index(st.session_state["page"]),
            label_visibility="collapsed",
        )

        if page != st.session_state.get("page"):
            st.session_state["page"] = page
            try:
                st.query_params["page"] = page
            except Exception:
                pass
            st.rerun()

        st.markdown("---")
        st.markdown(f"<small>v{config.APP_VERSION} • Streamlit Edition</small>", unsafe_allow_html=True)

    # Sticky brand bar on every page
    st.markdown(theme.brand_bar(), unsafe_allow_html=True)

    # Show (and clear) any flash message stashed by the previous run — see
    # the "Flash messages" section above / PART 6.
    _render_flash()

    # Record page visit once per navigation / refresh for traffic stats
    try:
        current_page = st.session_state.get("page", "Home")
        if st.session_state.get("last_recorded_page") != current_page:
            if "visitor_token" not in st.session_state:
                st.session_state["visitor_token"] = base64.urlsafe_b64encode(
                    os.urandom(12)
                ).decode()
            utils.record_visit(st.session_state["visitor_token"], current_page)
            st.session_state["last_recorded_page"] = current_page
    except Exception:
        pass

    # Reset registration state when navigating to the Register page from elsewhere
    current_page = st.session_state.get("page", "Home")
    if st.session_state.get("_prev_page") != current_page:
        if current_page == "Register":
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
