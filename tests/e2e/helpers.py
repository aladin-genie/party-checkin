"""
Shared Playwright helpers for the e2e suite.

Selector philosophy (per the test-design brief): only `get_by_role`,
`get_by_text`, label text, and Streamlit-emitted `data-testid` attributes.
Never CSS classes / colors / DOM structure, since a concurrent CSS redesign
must not break these tests.

Two Streamlit quirks these helpers work around (verified against the
running app before writing the suite):

1. A `st.text_input`/`st.number_input` that lives OUTSIDE an `st.form` only
   commits its value to session_state on blur/Enter, not on every
   keystroke. Filling it and immediately clicking a button elsewhere can
   race the blur, so `fill_and_blur()` always sends an explicit Tab.
   Fields INSIDE an `st.form` don't need this — the whole form's values are
   read together only when the submit button is clicked.

2. `st.dataframe` / `st.data_editor` both render through the same canvas-based
   grid (glide-data-grid) with a visually HIDDEN accessibility mirror
   `<table>` (`<td>` elements matched by `get_by_text`, but not
   `to_be_visible()` — Playwright correctly reports them as not visible).
   So assertions about guest-table content use `.count()` / `to_have_count()`,
   never `to_be_visible()`. Confirmed (2026-08-10 rewrite) that those mirror
   `<td>` cells are also not click-*able* — `st.data_editor`'s Checked
   In/Band Given/Delete checkboxes are drawn on the canvas itself with no
   corresponding interactable DOM element, so they cannot be toggled via any
   semantic Playwright selector. Coverage for that grid is therefore split:
   UI-level (renders, headers, Save button, search-filters-rows) here, and
   the actual mutation logic against `utils.apply_guest_changes()` directly
   at the service layer in test_admin.py.

3. Like the T&C checkbox above, `st.radio` options' underlying
   `<input type="radio">` are rendered zero-size (styling lives on a
   sibling element) — Playwright reports them not interactable via
   `get_by_role("radio", ...)`. Clicking the option's visible label text
   (`select_checkin_mode()` below) is what actually works.
"""
from __future__ import annotations

from playwright.sync_api import Page, expect

DEFAULT_SETTLE_MS = 700


def goto(page: Page, base_url: str, page_name: str | None = None, settle_ms: int = DEFAULT_SETTLE_MS) -> None:
    """Navigate to a page via query param (a fresh full navigation, which
    also means a fresh Streamlit session/session_state for this context)."""
    qs = f"?page={page_name.replace(' ', '%20')}" if page_name else ""
    page.goto(f"{base_url}/{qs}", wait_until="networkidle")
    page.wait_for_timeout(settle_ms)


def fill_and_blur(page: Page, label: str, value: str) -> None:
    """Fill a standalone (non-form) text/number input and blur it so
    Streamlit commits the value to session_state before any follow-up
    button click."""
    loc = page.get_by_label(label)
    loc.fill(value)
    loc.press("Tab")


def open_terms_expander(page: Page) -> None:
    page.get_by_text("Terms & Conditions", exact=False).first.click()


def check_terms_agree(page: Page) -> None:
    """Tick the 'I/We Agree' checkbox by clicking its visible label text.

    The underlying `<input type="checkbox">` is rendered zero-size (styling
    lives on a sibling element), so Playwright reports it as not
    interactable for `.check()`/`.click()`. Clicking the visible label text
    is what actually works and is a `get_by_text` selector, per the
    allowed-selector list.
    """
    page.get_by_text("I/We Agree", exact=True).click()


def fill_registration_form(
    page: Page,
    *,
    name: str = "",
    email: str = "",
    phone: str = "555-123-4567",
    guest_names: str = "",
    zelle_ref: str = "",
    tickets: int | None = None,
    agree: bool = True,
    open_expander: bool = True,
) -> None:
    """Fill the Register page form. `tickets` lives outside the form (it's
    the live-updating ticket count), everything else is inside it.

    `guest_names` fills the "Additional Guest Names (optional)" multi-line
    `st.text_area` (up to 20 names, one per line or comma-separated —
    formerly a single-line "Plus One Name" field).

    `phone` defaults to a valid US number because the field is mandatory —
    tests exercising one deliberately-invalid field would otherwise trip the
    phone error too. Pass phone="" to leave it blank on purpose.
    """
    if tickets is not None:
        fill_and_blur(page, "Number of Tickets *", str(tickets))

    page.get_by_label("Full Name *").fill(name)
    page.get_by_label("Email Address *").fill(email)
    if phone:
        page.get_by_label("Phone Number *").fill(phone)
    if guest_names:
        page.get_by_label("Additional Guest Names (optional)").fill(guest_names)
    page.get_by_label("Zelle Transaction Reference *").fill(zelle_ref)

    if open_expander:
        open_terms_expander(page)
    if agree:
        check_terms_agree(page)


def submit_registration(page: Page) -> None:
    page.get_by_role("button", name="🎟️ Get My QR Code").click()


def validation_banner_text(field_count: int) -> str:
    """The exact banner shown above the Register form when validation
    fails (theme.validation_banner), so tests can assert on it directly."""
    word = "field" if field_count == 1 else "fields"
    return f"Couldn’t submit — please fix the {field_count} highlighted {word} below."


def select_checkin_mode(page: Page, label: str) -> None:
    """Select a Check-in Window radio option (Admin > Overview) by clicking
    its visible label text — see the module docstring for why `.click()` on
    the `role=radio` locator itself doesn't work. `label` is one of "Auto
    (opens 2h before event)", "Open now", "Closed"."""
    page.get_by_text(label, exact=True).click()


SCANNER_LOOKUP_FIELD = "Phone / Email / Ticket ID / QR Code"


def scanner_find(page: Page, code: str) -> None:
    """Search the Scanner for a guest. Checks nobody in — the door flow puts
    the guest's details on screen first and waits for staff to confirm."""
    fill_and_blur(page, SCANNER_LOOKUP_FIELD, code)
    page.get_by_role("button", name="🔍 Find Guest").click()


def scanner_confirm_checkin(page: Page) -> None:
    """Press confirm on the guest card a search just produced, and wait for
    the check-in to actually land.

    The write happens server-side on that click, so a caller that asserts on
    the DB straight afterwards can beat the rerun that records it. The
    guest's name is on screen either side of the confirmation and the
    confirm button can unmount mid-rerun (i.e. before the write commits), so
    neither is a usable marker — the success card's status label only
    renders after the check-in is recorded, so wait on that."""
    confirm = page.get_by_role("button", name="✅ Confirm & Check In")
    confirm.wait_for(timeout=10000)
    confirm.click()
    page.get_by_text("✅ Checked In", exact=False).first.wait_for(timeout=15000)


def scanner_checkin(page: Page, code: str) -> None:
    """Both halves of the door flow: find the guest, then confirm them in."""
    scanner_find(page, code)
    scanner_confirm_checkin(page)


def login_admin(page: Page, password: str) -> None:
    """Fill + submit the admin login form (it's an `st.form`, so no blur
    needed between the two fields)."""
    page.get_by_label("Admin Password").fill(password)
    page.get_by_role("button", name="Login").click()


def assert_no_horizontal_overflow(page: Page) -> None:
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width + 2, (
        f"horizontal overflow detected: scrollWidth={scroll_width} "
        f"clientWidth={client_width}"
    )
