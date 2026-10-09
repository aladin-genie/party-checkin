"""Flows 6-8: scanner lookup (by QR / email / phone / numeric id), the
confirm-before-check-in step, double check-in, invalid code, wristband
tracking, and the check-in time-window gate (PART 1:
`utils.check_in_by_code` / `utils.checkin_status`).

The door flow is two steps by design: a search only ever *finds* someone,
and a second deliberate press checks them in. Staff search by phone far more
often than anything else (guests don't remember which email address their QR
code went to), and a phone number identifies a booking, not a person — so
the details have to be confirmed against whoever is standing there.

Every test that actually performs a check-in through the Scanner UI uses
the `force_checkin_open` fixture, since the default 'auto' mode is closed
until 2h before the real event date (always far in the future relative to
whenever this suite runs)."""
from playwright.sync_api import expect

from .helpers import (
    SCANNER_LOOKUP_FIELD,
    WAIVER_ACCEPT_AND_CHECKIN,
    WAIVER_AGREE_TEXT,
    goto,
    scanner_checkin,
    scanner_find,
    scanner_sign_waiver,
)


def test_scanner_checkin_by_qr_code_then_already_checked_in(page, base_url, reset_db, seed_guest, force_checkin_open):
    guest = seed_guest(name="Scan Qr Guest", email="scanqr@example.com",
                        ticket_count=2, zelle_ref="ZELLE-SCANQR01")

    goto(page, base_url, "Scanner")
    scanner_checkin(page, guest["qr_code"])

    # exact=True: the guest name also appears (non-exact) inside the
    # welcome message and the audio-announcement caption on the same card,
    # which would otherwise be a Playwright strict-mode multi-match.
    expect(page.get_by_text("Scan Qr Guest", exact=True)).to_be_visible(timeout=10000)
    # The literal "✅ Checked In" status label, not the "Checked In" stat
    # tile that's also on this page -- the emoji prefix disambiguates them.
    expect(page.get_by_text("✅ Checked In", exact=False)).to_be_visible(timeout=10000)

    updated = reset_db.get_guest(guest["id"])
    assert updated["checked_in"] is True
    assert updated["checkin_time"] is not None

    # Scan the same guest again -> "already checked in" path, no state
    # change, and no confirm button to press a second time.
    page.get_by_role("button", name="🔄 Scan Next Guest").click()
    expect(page.get_by_label(SCANNER_LOOKUP_FIELD)).to_be_visible(timeout=8000)
    scanner_find(page, guest["qr_code"])

    expect(page.get_by_text("Already checked in at", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_role("button", name="✅ Confirm & Check In")).to_have_count(0)
    # Signed on the way in, so the waiver isn't asked for a second time.
    expect(page.get_by_text("✅ Signed by Scan Qr Guest", exact=True)).to_be_visible(timeout=10000)
    expect(page.get_by_role("button", name=WAIVER_ACCEPT_AND_CHECKIN)).to_have_count(0)
    still = reset_db.get_guest(guest["id"])
    assert still["checked_in"] is True


def test_scanner_checkin_by_email(page, base_url, reset_db, seed_guest, force_checkin_open):
    guest = seed_guest(name="Scan Email Guest", email="scanemail@example.com",
                        zelle_ref="ZELLE-SCANEML1")

    goto(page, base_url, "Scanner")
    scanner_checkin(page, guest["email"])

    expect(page.get_by_text("Scan Email Guest", exact=True)).to_be_visible(timeout=10000)
    assert reset_db.get_guest(guest["id"])["checked_in"] is True


def test_scanner_checkin_by_numeric_id(page, base_url, reset_db, seed_guest, force_checkin_open):
    guest = seed_guest(name="Scan Id Guest", email="scanid@example.com",
                        zelle_ref="ZELLE-SCANID001")

    goto(page, base_url, "Scanner")
    scanner_checkin(page, str(guest["id"]))

    expect(page.get_by_text("Scan Id Guest", exact=True)).to_be_visible(timeout=10000)
    assert reset_db.get_guest(guest["id"])["checked_in"] is True


def test_scanner_lookup_by_phone_shows_details_and_checks_nobody_in(
    page, base_url, reset_db, seed_guest, force_checkin_open
):
    """The reason the flow is two steps: staff search by phone, and the
    search alone must not admit anyone. Every identifying detail is on
    screen to confirm against, including how many wristbands are owed."""
    guest = seed_guest(name="Phone Door Guest", email="phonedoor@example.com",
                        phone="+1-555-707-1234", ticket_count=3,
                        zelle_ref="ZELLE-PHDOOR001")

    goto(page, base_url, "Scanner")
    scanner_find(page, "(555) 707-1234")

    # .first: the identity card's heading — the name is also in the waiver's party list.
    expect(page.get_by_text("Phone Door Guest", exact=True).first).to_be_visible(timeout=10000)
    expect(page.get_by_text("phonedoor@example.com", exact=True)).to_be_visible(timeout=10000)
    expect(page.get_by_text("+1-555-707-1234", exact=True)).to_be_visible(timeout=10000)
    expect(page.get_by_text("Not checked in yet", exact=False)).to_be_visible(timeout=10000)
    # 3 tickets => 3 wristbands, stated rather than left for staff to infer
    expect(page.get_by_text("Wristbands", exact=True)).to_be_visible(timeout=10000)
    # ...and the waiver says it covers all 3 of them.
    expect(page.get_by_text("The purchaser accepts for everyone in this booking — 3 people", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_text("I, Phone Door Guest, have read this waiver and accept it for myself and my group (3 people).", exact=True)).to_be_visible(timeout=10000)
    expect(page.get_by_label("Type your full name to sign")).to_have_count(0)

    # The whole point: found, but untouched until someone confirms.
    pending = reset_db.get_guest(guest["id"])
    assert pending["checked_in"] is False
    assert pending["checkin_time"] is None

    scanner_sign_waiver(page)
    expect(page.get_by_text("✅ Checked In", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_text("Hand over 3 wristbands", exact=False)).to_be_visible(timeout=10000)
    assert reset_db.get_guest(guest["id"])["checked_in"] is True


def test_scanner_search_for_someone_else_discards_the_match(
    page, base_url, reset_db, seed_guest, force_checkin_open
):
    """Wrong person on screen -> staff back out, and nothing was recorded."""
    guest = seed_guest(name="Wrong Match Guest", email="wrongmatch@example.com",
                        phone="+1-555-808-4321", zelle_ref="ZELLE-WRONGM001")

    goto(page, base_url, "Scanner")
    scanner_find(page, "555-808-4321")
    expect(page.get_by_text("Wrong Match Guest", exact=True).first).to_be_visible(timeout=10000)

    page.get_by_role("button", name="🔍 Search for Someone Else").click()

    expect(page.get_by_text("Wrong Match Guest", exact=True)).to_have_count(0, timeout=10000)
    expect(page.get_by_label(SCANNER_LOOKUP_FIELD)).to_be_visible(timeout=8000)
    assert reset_db.get_guest(guest["id"])["checked_in"] is False


def test_scanner_invalid_code_shows_error(page, base_url, reset_db, force_checkin_open):
    goto(page, base_url, "Scanner")
    scanner_find(page, "totally-bogus-code-does-not-exist")
    expect(page.get_by_text("No guest found", exact=False)).to_be_visible(timeout=10000)


def test_wristband_mark_band_given_after_checkin(page, base_url, reset_db, seed_guest, force_checkin_open):
    guest = seed_guest(name="Band Guest", email="bandguest@example.com",
                        zelle_ref="ZELLE-BANDG0001")

    goto(page, base_url, "Scanner")
    scanner_checkin(page, guest["qr_code"])
    band_button = page.get_by_role("button", name="✓ Mark 1 Wristband Given")
    expect(band_button).to_be_visible(timeout=10000)

    assert reset_db.get_guest(guest["id"])["band_given"] is False

    # NOTE: not asserting the "Band marked as given" success text here.
    # `_mark_band_given()` in streamlit_app.py calls st.success(message)
    # immediately followed by st.rerun() in the same function -- the rerun
    # appears to supersede the frame before the success message is ever
    # flushed to the browser, so it never becomes visible (confirmed: DB
    # state below still updates correctly). Filed as a real bug in the
    # test-suite report; the task's acceptance criterion for this flow is
    # the DB assertion, which we do check.
    band_button.click()
    page.wait_for_timeout(2000)

    assert reset_db.get_guest(guest["id"])["band_given"] is True


# ── Door waiver ─────────────────────────────────────────────────────────

def test_waiver_lists_the_party_and_records_the_signature(
    page, base_url, reset_db, seed_guest, force_checkin_open
):
    """Whoever signs sees exactly who they're signing for, and the record
    keeps the party and the typed name alongside the wording version."""
    guest = seed_guest(name="Party Booker", email="partybooker@example.com",
                        ticket_count=3, plus_one_name="Ann Lee\nBob Ray",
                        zelle_ref="ZELLE-PARTY001")

    goto(page, base_url, "Scanner")
    scanner_find(page, guest["qr_code"])
    expect(page.get_by_text("1. ASSUMPTION OF RISK", exact=True)).to_be_visible(timeout=10000)
    for name in ("Ann Lee", "Bob Ray"):
        expect(page.get_by_text(name, exact=True)).to_be_visible(timeout=10000)
    # Nobody gets the old one-tap check-in while the waiver is unsigned.
    expect(page.get_by_role("button", name="✅ Confirm & Check In")).to_have_count(0)

    scanner_sign_waiver(page)
    expect(page.get_by_text("✅ Checked In", exact=False)).to_be_visible(timeout=15000)

    waiver = reset_db.get_waiver(guest["id"])
    assert waiver["decision"] == reset_db.WAIVER_ACCEPTED
    assert waiver["signed_name"] == "Party Booker"  # the purchaser, for the group
    assert waiver["party_names"].split("\n") == ["Party Booker", "Ann Lee", "Bob Ray"]
    assert reset_db.get_guest(guest["id"])["checked_in"] is True


def test_waiver_accept_needs_the_tick(page, base_url, reset_db, seed_guest, force_checkin_open):
    guest = seed_guest(name="Half Signed", email="halfsigned@example.com",
                        zelle_ref="ZELLE-HALFSG01")

    goto(page, base_url, "Scanner")
    scanner_find(page, guest["qr_code"])

    # No tick -> refused, nothing written.
    page.get_by_role("button", name=WAIVER_ACCEPT_AND_CHECKIN).click()
    expect(page.get_by_text("Please tick the box", exact=False)).to_be_visible(timeout=10000)
    assert reset_db.get_waiver(guest["id"]) is None
    assert reset_db.get_guest(guest["id"])["checked_in"] is False

    # Tick -> accepted in the purchaser's name, and checked in.
    page.get_by_text(WAIVER_AGREE_TEXT, exact=False).click()
    page.get_by_role("button", name=WAIVER_ACCEPT_AND_CHECKIN).click()
    expect(page.get_by_text("✅ Checked In", exact=False).first).to_be_visible(timeout=15000)
    assert reset_db.get_waiver(guest["id"])["signed_name"] == "Half Signed"


def test_waiver_decline_blocks_checkin_and_can_be_reversed(
    page, base_url, reset_db, seed_guest, force_checkin_open
):
    guest = seed_guest(name="Decline Guest", email="decline@example.com",
                        ticket_count=2, plus_one_name="Cara Diaz",
                        zelle_ref="ZELLE-DECLN001")

    goto(page, base_url, "Scanner")
    scanner_find(page, guest["qr_code"])
    page.get_by_role("button", name="✖ I Decline").click()

    expect(page.get_by_text("✖ Waiver Declined", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_text("Do not hand over the 2 wristbands", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_role("button", name="✓ Mark 2 Wristbands Given")).to_have_count(0)
    assert reset_db.get_waiver(guest["id"])["decision"] == reset_db.WAIVER_DECLINED
    assert reset_db.get_guest(guest["id"])["checked_in"] is False

    # Changed their mind: scan again, the card says so, and accepting works.
    page.get_by_role("button", name="🔄 Scan Next Guest").click()
    scanner_find(page, guest["qr_code"])
    expect(page.get_by_text("Declined earlier", exact=False)).to_be_visible(timeout=10000)
    scanner_sign_waiver(page)
    expect(page.get_by_text("✅ Checked In", exact=False)).to_be_visible(timeout=15000)
    assert reset_db.get_waiver(guest["id"])["decision"] == reset_db.WAIVER_ACCEPTED
    assert reset_db.get_guest(guest["id"])["checked_in"] is True


def test_admitted_without_waiver_must_sign_before_wristbands(
    page, base_url, reset_db, seed_guest, force_checkin_open
):
    """Someone already let in from the admin grid (or before the waiver was
    switched on) still signs before wristbands go out at the door."""
    guest = seed_guest(name="Early Bird", email="earlybird@example.com",
                        zelle_ref="ZELLE-EARLY001")
    assert reset_db.check_in_guest(guest["id"], bypass_window=True)["status"] == "success"

    goto(page, base_url, "Scanner")
    scanner_find(page, guest["qr_code"])
    expect(page.get_by_text("Already checked in at", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_role("button", name="✓ Mark 1 Wristband Given")).to_have_count(0)

    scanner_sign_waiver(page, button="✅ I Accept")
    band_button = page.get_by_role("button", name="✓ Mark 1 Wristband Given")
    expect(band_button).to_be_visible(timeout=10000)
    band_button.click()
    expect(band_button).to_have_count(0, timeout=10000)
    assert reset_db.get_guest(guest["id"])["band_given"] is True


def test_waiver_switched_off_restores_the_plain_confirm(
    page, base_url, reset_db, seed_guest, force_checkin_open
):
    """The organiser's off switch: no waiver, the one-tap confirm is back."""
    reset_db.set_waiver_required(False)
    guest = seed_guest(name="No Waiver Guest", email="nowaiver@example.com",
                        zelle_ref="ZELLE-NOWAIV01")

    goto(page, base_url, "Scanner")
    scanner_find(page, guest["qr_code"])
    expect(page.get_by_text(WAIVER_AGREE_TEXT, exact=False)).to_have_count(0)
    page.get_by_role("button", name="✅ Confirm & Check In").click()
    expect(page.get_by_text("✅ Checked In", exact=False)).to_be_visible(timeout=10000)
    assert reset_db.get_guest(guest["id"])["checked_in"] is True
    assert reset_db.get_waiver(guest["id"]) is None


# ── Check-in window gate (PART 1) ───────────────────────────────────────

def test_scanner_gate_closed_shows_notice_hides_manual_entry_and_leaves_guest_untouched(
    page, base_url, reset_db, seed_guest
):
    """Positive coverage of the gate itself (no `force_checkin_open` here):
    default mode is 'auto' and the real event date is always far in the
    future relative to whenever this suite runs, so the window is closed.
    The Scanner page must show the "opens at ..." notice, must NOT render
    the manual-entry input at all, and an attempted check-in against the
    closed window must leave the guest row completely untouched.

    The UI intentionally gives a guest nothing to click while closed, so
    the "attempted check-in" half of this test calls
    `utils.check_in_by_code()` directly (service-level) -- this is exactly
    the server-side control the UI gate is a convenience wrapper around."""
    guest = seed_guest(name="Gate Closed Guest", email="gateclosed@example.com",
                        zelle_ref="ZELLE-GATECL01")

    assert reset_db.get_checkin_mode() == reset_db.CHECKIN_MODE_AUTO
    assert reset_db.checkin_status()["open"] is False

    goto(page, base_url, "Scanner")
    expect(page.get_by_text("Check-in isn't open yet", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_text("opens", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_label(SCANNER_LOOKUP_FIELD)).to_have_count(0)
    expect(page.get_by_role("button", name="🔍 Find Guest")).to_have_count(0)

    result = reset_db.check_in_by_code(guest["qr_code"])
    assert result["status"] == "not_open"
    assert result["guest"] is None

    untouched = reset_db.get_guest(guest["id"])
    assert untouched["checked_in"] is False
    assert untouched["checkin_time"] is None
