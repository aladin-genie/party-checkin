"""Flows 2-5: registration happy path, per-field validation (incl. the
validation summary banner), duplicate email, the live-updating ticket
total, and bulk "Additional Guest Names" entry (PART 2)."""
import re

import pytest
from playwright.sync_api import expect

from .helpers import (
    fill_and_blur,
    fill_registration_form,
    goto,
    submit_registration,
    validation_banner_text,
)


# ── Flow 2: happy path ──────────────────────────────────────────────────

def test_registration_happy_path_creates_guest_and_submission_log(page, base_url, reset_db):
    goto(page, base_url, "Register")

    email = "happy.path.guest@example.com"
    fill_registration_form(
        page, name="Happy Path Guest", email=email, phone="(555) 246-8100",
        # 2 tickets is the booker plus exactly one named guest
        guest_names="Plus One Guest",
        zelle_ref="ZELLE-HAPPY0001", tickets=2,
    )
    submit_registration(page)

    expect(page.get_by_text("You're registered", exact=False)).to_be_visible(timeout=15000)
    expect(page.get_by_text("Happy Path Guest", exact=False).first).to_be_visible(timeout=10000)

    guest = reset_db.get_guest_by_email(email)
    assert guest is not None, "guest row was not created"
    assert guest["name"] == "Happy Path Guest"
    assert guest["email"] == email
    # However the guest types it, the number is stored normalized so that the
    # phone lookup finds them
    assert guest["phone"] == "+1-555-246-8100"
    assert reset_db.get_guest_by_phone("5552468100")["email"] == email
    assert guest["ticket_count"] == 2
    assert guest["plus_one_name"] == "Plus One Guest"
    assert guest["qr_code"], "qr_code was not generated"

    session = reset_db.get_db()
    try:
        log = (
            session.query(reset_db.SubmissionLog)
            .filter_by(email=email)
            .order_by(reset_db.SubmissionLog.id.desc())
            .first()
        )
        assert log is not None, "no submission_logs row was written"
        assert log.status == "registered"
        assert log.guest_id == guest["id"]
    finally:
        session.close()


# ── Flow 3: per-field validation ────────────────────────────────────────

@pytest.mark.parametrize(
    "field,bad_value,expected_error_substring",
    [
        # Substrings are chosen to be unique to the *error* message and not
        # also present in that field's `help=` tooltip text (e.g. both the
        # Zelle error and its help text mention "8-30 letters", so we match
        # a phrase only the error uses) -- a locator matching both would be
        # a Playwright strict-mode violation.
        ("name", "John123", "Please enter a valid full name"),
        ("email", "not-an-email", "valid email address"),
        ("zelle_ref", "short", "transaction reference is required"),
        # Phone is mandatory and US-only: blank, unparseable, and a valid
        # foreign number all have to be rejected here
        ("phone", "", "Phone number is required"),
        ("phone", "123", "valid 10-digit US phone number"),
        ("phone", "+44 20 7946 0958", "valid 10-digit US phone number"),
    ],
    ids=["invalid-name", "invalid-email", "short-zelle-ref",
         "blank-phone", "short-phone", "non-us-phone"],
)
def test_registration_validation_shows_visible_error_and_saves_nothing(
    page, base_url, reset_db, field, bad_value, expected_error_substring
):
    goto(page, base_url, "Register")

    values = dict(
        name="Valid Name",
        email=f"valid.{field}.case@example.com",
        phone="555-123-4567",
        zelle_ref="ZELLE12345678",
    )
    values[field] = bad_value

    fill_registration_form(
        page, name=values["name"], email=values["email"],
        phone=values["phone"], zelle_ref=values["zelle_ref"],
        tickets=1, agree=True,
    )
    submit_registration(page)

    # The at-a-glance summary banner above the form, plus the specific
    # per-field message under the offending field. Every case here
    # invalidates exactly one field, so the banner is always singular.
    expect(page.get_by_text(validation_banner_text(1), exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_text(expected_error_substring, exact=False)).to_be_visible(timeout=10000)
    assert reset_db.get_guest_by_email(values["email"]) is None


def test_registration_validation_terms_error_visible_without_opening_expander(page, base_url, reset_db):
    """The T&C expander only auto-expands (expanded=("terms" in reg_errors))
    on the rerun *after* a failed submit. This test deliberately never
    clicks the expander before submitting, to prove the error is visible
    without the user having to open it themselves."""
    goto(page, base_url, "Register")

    email = "terms.not.agreed@example.com"
    fill_registration_form(
        page, name="No Agree Guest", email=email,
        zelle_ref="ZELLE12345678", tickets=1,
        agree=False, open_expander=False,
    )
    submit_registration(page)

    expect(page.get_by_text(validation_banner_text(1), exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_text("Please check I/We Agree", exact=False)).to_be_visible(timeout=10000)
    assert reset_db.get_guest_by_email(email) is None


# ── Flow 4: duplicate email ─────────────────────────────────────────────

def test_registration_duplicate_email_rejected_without_creating_second_row(page, base_url, reset_db):
    email = "dupe.guest@example.com"
    first = reset_db.register_guest("First Dupe", email, "", 1, "", "ZELLE-DUPE0001")
    assert first["ok"]

    goto(page, base_url, "Register")
    fill_registration_form(
        page, name="Second Dupe", email=email,
        zelle_ref="ZELLE-DUPE0002", tickets=1,
    )
    submit_registration(page)

    expect(page.get_by_text("already registered", exact=False)).to_be_visible(timeout=10000)

    session = reset_db.get_db()
    try:
        count = session.query(reset_db.Guest).filter_by(email=email).count()
    finally:
        session.close()
    assert count == 1


# ── Flow 5: live ticket total ───────────────────────────────────────────

def test_ticket_total_updates_live_without_submitting(page, base_url, reset_db, app_config):
    goto(page, base_url, "Register")
    price = app_config.ticket_price_dollars()

    fill_and_blur(page, "Number of Tickets *", "3")
    expect(page.get_by_text(f"${3 * price:,.2f}", exact=True)).to_be_visible(timeout=8000)

    fill_and_blur(page, "Number of Tickets *", "5")
    expect(page.get_by_text(f"${5 * price:,.2f}", exact=True)).to_be_visible(timeout=8000)
    # The old total for 3 tickets must be gone, confirming a real re-render
    # rather than the new value simply being appended somewhere.
    expect(page.get_by_text(f"${3 * price:,.2f}", exact=True)).to_have_count(0)

    session = reset_db.get_db()
    try:
        assert session.query(reset_db.Guest).count() == 0, "changing the ticket count must not submit anything"
    finally:
        session.close()


# ── PART 2: bulk "Additional Guest Names" ───────────────────────────────

def test_registration_bulk_guest_names_persists_all_and_shows_on_success(page, base_url, reset_db):
    """5 names, mixing comma- and newline-separation, all persist to
    plus_one_name newline-joined and are listed on the success screen."""
    goto(page, base_url, "Register")

    email = "bulk.guest.names@example.com"
    names = ["Jane Doe", "John Doe", "Mary Smith", "Anna Lee", "Tom Brown"]
    # Mixes both accepted separators (comma and newline) in one input.
    guest_names_input = "Jane Doe, John Doe\nMary Smith, Anna Lee\nTom Brown"

    fill_registration_form(
        page, name="Bulk Names Guest", email=email,
        guest_names=guest_names_input,
        zelle_ref="ZELLE-BULK00001", tickets=6,
    )
    submit_registration(page)

    expect(page.get_by_text("You're registered", exact=False)).to_be_visible(timeout=15000)
    expect(page.get_by_text("Additional Guests (5)", exact=False)).to_be_visible(timeout=10000)
    for n in names:
        expect(page.get_by_text(n, exact=False).first).to_be_visible(timeout=10000)

    guest = reset_db.get_guest_by_email(email)
    assert guest is not None
    assert guest["plus_one_name"] == "\n".join(names)


def test_registration_guest_names_with_digits_shows_field_error(page, base_url, reset_db):
    goto(page, base_url, "Register")

    email = "invalid.guest.names@example.com"
    fill_registration_form(
        page, name="Valid Name", email=email,
        guest_names="Jane Doe\nJohn123",
        zelle_ref="ZELLE12345678", tickets=1,
    )
    submit_registration(page)

    expect(page.get_by_text(validation_banner_text(1), exact=False)).to_be_visible(timeout=10000)
    expect(
        page.get_by_text("Guest names must use letters and spaces only", exact=False)
    ).to_be_visible(timeout=10000)
    assert reset_db.get_guest_by_email(email) is None


def test_registration_over_the_guest_name_cap_rejected(page, base_url, reset_db):
    goto(page, base_url, "Register")

    email = "too.many.guest.names@example.com"
    # Individually-valid (letters-only) names, one past the cap -- rejected
    # purely on count.
    cap = reset_db.MAX_GUEST_NAMES
    names = "\n".join(f"Guest {chr(65 + i)}" for i in range(cap + 1))
    fill_registration_form(
        page, name="Valid Name", email=email,
        guest_names=names,
        zelle_ref="ZELLE12345678", tickets=1,
    )
    submit_registration(page)

    expect(page.get_by_text(validation_banner_text(1), exact=False)).to_be_visible(timeout=10000)
    expect(
        page.get_by_text(f"That's more than {cap} names", exact=False)
    ).to_be_visible(timeout=10000)
    assert reset_db.get_guest_by_email(email) is None


# ── Guest names must match the ticket count ─────────────────────────────
# N tickets is the booker plus N-1 named guests, enforced by
# utils.validate_registration. These cover the rule end-to-end.

def test_registration_multi_ticket_without_names_is_rejected(page, base_url, reset_db):
    goto(page, base_url, "Register")

    email = "missing.guest.names@example.com"
    fill_registration_form(
        page, name="No Names Guest", email=email,
        zelle_ref="ZELLE-NONAMES01", tickets=3,
    )
    submit_registration(page)

    expect(page.get_by_text(validation_banner_text(1), exact=False)).to_be_visible(timeout=10000)
    expect(
        page.get_by_text("2 other guests", exact=False).first
    ).to_be_visible(timeout=10000)
    assert reset_db.get_guest_by_email(email) is None, "a booking with no names must not be saved"


def test_registration_name_count_mismatch_states_both_numbers(page, base_url, reset_db):
    goto(page, base_url, "Register")

    email = "short.guest.names@example.com"
    fill_registration_form(
        page, name="Short List Guest", email=email,
        guest_names="Jane Doe\nJohn Doe",
        zelle_ref="ZELLE-SHORT0001", tickets=5,
    )
    submit_registration(page)

    expect(page.get_by_text(validation_banner_text(1), exact=False)).to_be_visible(timeout=10000)
    expect(
        page.get_by_text("but you listed 2", exact=False).first
    ).to_be_visible(timeout=10000)
    assert reset_db.get_guest_by_email(email) is None


def test_registration_names_on_a_single_ticket_is_rejected(page, base_url, reset_db):
    goto(page, base_url, "Register")

    email = "solo.with.names@example.com"
    fill_registration_form(
        page, name="Solo Guest", email=email,
        guest_names="Uninvited Person",
        zelle_ref="ZELLE-SOLO00001", tickets=1,
    )
    submit_registration(page)

    expect(page.get_by_text(validation_banner_text(1), exact=False)).to_be_visible(timeout=10000)
    expect(
        page.get_by_text("only booked 1 ticket", exact=False).first
    ).to_be_visible(timeout=10000)
    assert reset_db.get_guest_by_email(email) is None


def test_required_name_count_updates_live_with_the_ticket_selector(page, base_url, reset_db):
    """The required count is stated before the field and tracks the ticket
    selector, so a guest isn't told how many names to enter only after a
    rejected submit."""
    goto(page, base_url, "Register")

    fill_and_blur(page, "Number of Tickets *", "4")
    expect(page.get_by_text("you plus 3 other guests", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_label("Additional Guest Names")).to_be_visible(timeout=10000)

    fill_and_blur(page, "Number of Tickets *", "2")
    expect(page.get_by_text("you plus 1 other guest", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_text("you plus 3 other guests", exact=False)).to_have_count(0)

    # Back to a solo booking: no names wanted at all
    fill_and_blur(page, "Number of Tickets *", "1")
    expect(page.get_by_text("no other names needed", exact=False)).to_be_visible(timeout=10000)

    session = reset_db.get_db()
    try:
        assert session.query(reset_db.Guest).count() == 0, "changing the ticket count must not submit anything"
    finally:
        session.close()
