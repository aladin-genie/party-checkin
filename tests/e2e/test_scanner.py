"""Flows 6-8: scanner manual entry (by QR / email / numeric id), double
check-in, invalid code, wristband tracking, and the check-in time-window
gate (PART 1: `utils.check_in_by_code` / `utils.checkin_status`).

Every test that actually performs a check-in through the Scanner UI uses
the `force_checkin_open` fixture, since the default 'auto' mode is closed
until 2h before the real event date (always far in the future relative to
whenever this suite runs)."""
from playwright.sync_api import expect

from .helpers import goto, scanner_checkin


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

    # Scan the same guest again -> "already checked in" path, no state change.
    page.get_by_role("button", name="🔄 Scan Next Guest").click()
    expect(page.get_by_label("Ticket ID / Email / QR Code")).to_be_visible(timeout=8000)
    scanner_checkin(page, guest["qr_code"])

    # "...already checked in at <time>" (the message div) only -- the
    # status div's "⚠ Already Checked In" label is a separate element that
    # a shorter, case-insensitive "already checked in" substring also
    # matches, tripping Playwright's strict mode.
    expect(page.get_by_text("already checked in at", exact=False)).to_be_visible(timeout=10000)
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


def test_scanner_invalid_code_shows_error(page, base_url, reset_db, force_checkin_open):
    goto(page, base_url, "Scanner")
    scanner_checkin(page, "totally-bogus-code-does-not-exist")
    expect(page.get_by_text("Invalid ticket", exact=False)).to_be_visible(timeout=10000)


def test_wristband_mark_band_given_after_checkin(page, base_url, reset_db, seed_guest, force_checkin_open):
    guest = seed_guest(name="Band Guest", email="bandguest@example.com",
                        zelle_ref="ZELLE-BANDG0001")

    goto(page, base_url, "Scanner")
    scanner_checkin(page, guest["qr_code"])
    expect(page.get_by_role("button", name="✓ Mark Band Given")).to_be_visible(timeout=10000)

    assert reset_db.get_guest(guest["id"])["band_given"] is False

    # NOTE: not asserting the "Band marked as given" success text here.
    # `_mark_band_given()` in streamlit_app.py calls st.success(message)
    # immediately followed by st.rerun() in the same function -- the rerun
    # appears to supersede the frame before the success message is ever
    # flushed to the browser, so it never becomes visible (confirmed: DB
    # state below still updates correctly). Filed as a real bug in the
    # test-suite report; the task's acceptance criterion for this flow is
    # the DB assertion, which we do check.
    page.get_by_role("button", name="✓ Mark Band Given").click()
    page.wait_for_timeout(2000)

    assert reset_db.get_guest(guest["id"])["band_given"] is True


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
    expect(page.get_by_label("Ticket ID / Email / QR Code")).to_have_count(0)
    expect(page.get_by_role("button", name="Check In Manually")).to_have_count(0)

    result = reset_db.check_in_by_code(guest["qr_code"])
    assert result["status"] == "not_open"
    assert result["guest"] is None

    untouched = reset_db.get_guest(guest["id"])
    assert untouched["checked_in"] is False
    assert untouched["checkin_time"] is None
