"""Flow 1: Home loads; hero shows the event name; the "Party Buzz" section
(PART 4 admin redesign: traffic tiles + both bar charts, moved here from
the old admin Overview tab) renders; each nav card navigates to the right
page."""
import re

from playwright.sync_api import expect

from .helpers import goto

NAV_CARDS = [
    (re.compile(r"Register Guest"), re.compile(r"Register Guest")),
    (re.compile(r"My QR Code"), re.compile(r"My QR Code")),
    (re.compile(r"Self Check-In"), re.compile(r"Self Check-In")),
    (re.compile(r"Admin Dashboard"), re.compile(r"Admin Dashboard")),
]

PARTY_BUZZ_STAT_LABELS = [
    "Unique Visitors",
    "Page Views",
    "Registered Guests",
    "Visitors Today",
]


def test_home_hero_and_party_buzz_tiles_render(page, base_url, reset_db, app_config):
    goto(page, base_url)

    expect(page.get_by_text(app_config.EVENT_NAME, exact=False).first).to_be_visible(timeout=10000)
    expect(page.get_by_text(app_config.EVENT_TAGLINE, exact=False).first).to_be_visible(timeout=10000)

    expect(page.get_by_text("Party Buzz", exact=False).first).to_be_visible(timeout=10000)
    for label in PARTY_BUZZ_STAT_LABELS:
        expect(page.get_by_text(label, exact=True)).to_be_visible(timeout=10000)


def test_home_party_buzz_registrations_chart_renders_once_there_are_registrations(
    page, base_url, reset_db, app_config
):
    """The registrations-by-day bar chart (also moved here from the old
    admin Overview tab) only renders once there's at least one guest --
    before that it shows an info fallback ("No registrations yet").

    The check-ins-by-hour chart is deliberately NOT asserted in its
    real-bar-rendered state: it only has data for check-ins whose
    checkin_time falls on the actual `config.EVENT_DATE`, which a test
    can't manufacture without changing the app's clock (the event date is
    always far in the future relative to whenever this suite runs). So
    it's covered via its own equally-real empty-state message instead.
    """
    reset_db.register_guest("Buzz Guest", "buzzguest@example.com", "", 1, "", "ZELLE-BUZZ00001")

    # Party Buzz reads through @st.cache_data(ttl=30). Seeding straight into
    # the DB (rather than registering through the form, which clears that
    # cache) leaves the app holding a pre-seed value, so wait the TTL out
    # before asserting. This is a real, bounded synchronisation point, not a
    # hopeful sleep.
    page.wait_for_timeout(31000)

    goto(page, base_url)

    expect(page.get_by_text("Registrations by day", exact=False)).to_be_visible(timeout=10000)
    expect(page.get_by_text("No registrations yet", exact=False)).to_have_count(0)
    expect(page.locator("[data-testid='stVegaLiteChart']").first).to_be_visible(timeout=10000)

    expect(
        page.get_by_text(
            f"Check-ins will show up here live once doors open on {app_config.EVENT_DATE_SHORT}.",
            exact=False,
        )
    ).to_be_visible(timeout=10000)


def test_home_nav_cards_navigate_to_correct_pages(page, base_url, reset_db):
    for button_pattern, heading_pattern in NAV_CARDS:
        goto(page, base_url)  # start fresh from Home each time
        page.get_by_role("button", name=button_pattern).click()
        expect(page.get_by_role("heading", name=heading_pattern, level=1)).to_be_visible(timeout=10000)
