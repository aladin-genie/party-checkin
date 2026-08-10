"""Flow 11: My QR lookup by email, deep link by guest_id (the link the QR
emails send), and the not-found case."""
from playwright.sync_api import expect

from .helpers import fill_and_blur, goto


def test_my_qr_lookup_by_email_renders_qr_image(page, base_url, reset_db, seed_guest):
    guest = seed_guest(name="Qr Lookup Guest", email="qrlookup@example.com",
                        zelle_ref="ZELLE-QRLOOK001")

    goto(page, base_url, "My QR")
    fill_and_blur(page, "Enter your email", guest["email"])
    page.get_by_role("button", name="🔍 Find My QR").click()

    expect(page.get_by_text("Qr Lookup Guest", exact=False).first).to_be_visible(timeout=10000)
    qr_image = page.locator('div[data-testid="stImage"] img')
    expect(qr_image.first).to_be_visible(timeout=10000)


def test_my_qr_deep_link_by_guest_id_renders_that_guests_qr(page, base_url, reset_db, seed_guest):
    """The QR email links to /?page=My%20QR&guest_id=<id> -- this must keep
    resolving straight to that guest's QR with no lookup step."""
    guest_a = seed_guest(name="Deep Link Alpha", email="deeplinka@example.com",
                          zelle_ref="ZELLE-DEEPA0001")
    guest_b = seed_guest(name="Deep Link Beta", email="deeplinkb@example.com",
                          zelle_ref="ZELLE-DEEPB0001")

    page.goto(f"{base_url}/?page=My%20QR&guest_id={guest_b['id']}", wait_until="networkidle")
    page.wait_for_timeout(1200)

    expect(page.get_by_text("Deep Link Beta", exact=False).first).to_be_visible(timeout=10000)
    expect(page.get_by_text("Deep Link Alpha", exact=False)).to_have_count(0)
    qr_image = page.locator('div[data-testid="stImage"] img')
    expect(qr_image.first).to_be_visible(timeout=10000)


def test_my_qr_unknown_email_shows_not_found_message(page, base_url, reset_db):
    goto(page, base_url, "My QR")
    fill_and_blur(page, "Enter your email", "nobody.registered@example.com")
    page.get_by_role("button", name="🔍 Find My QR").click()

    expect(page.get_by_text("No guest found", exact=False)).to_be_visible(timeout=10000)
