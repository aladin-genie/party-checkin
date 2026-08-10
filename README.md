# Party Check-In System

Event registration and check-in for **Dallas Boys Party 2026**, built with **Streamlit** and hosted free on Streamlit Community Cloud. Zelle payments, emailed QR codes, self check-in with audio announcements, and an admin dashboard. Sized for 200+ guests.

- **Event:** Friday, October 9, 2026 · 5:30 PM onwards
- **Venue:** Elegance Ballroom & Event Center, 8740 Ohio Dr A1, Plano, TX 75024
- **Theme:** 12th Year of Togetherness
- **Live app:** https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/
- **Repo:** `aladin-genie/party-checkin` (branch `main`)
- **Database:** Supabase PostgreSQL
- **Payment:** Zelle → `dallashudugaru@gmail.com` · $20.00 per ticket

---

## Architecture

```
                        INTERNET
                            |
                    [ Your Guests ]
                            |
              party-checkin-…streamlit.app
                            |
                +-----------+----------+
                |                      |
         [ Streamlit Cloud ]     [ Supabase ]
         Runs the app             Stores data
         FREE tier                FREE tier
```

The code is layered so that business logic is testable without a browser:

| File | Responsibility |
|------|----------------|
| `config.py` | Single source of truth for event details (name, date, venue) and secret access. Nothing else reads `st.secrets` for config. |
| `utils.py` | Database models, the service layer (register / check-in / band / delete / lookups / reporting), QR generation, email, validation. No Streamlit UI. |
| `theme.py` | The design system: CSS custom-property tokens plus HTML component builders (hero, stat tiles, payment card, stepper, …). |
| `streamlit_app.py` | Pages and navigation only. Renders `theme` components and calls `utils` service functions — it never touches the ORM or opens a DB session. |
| `test_party_checkin.py` | Unit tests for the service layer, validation, and security behavior. |
| `tests/e2e/` | Playwright end-to-end tests that drive the real UI. |

**Why it is layered this way:** Streamlit re-executes the entire script on every user interaction. Anything expensive left at module scope or inline in a page runs on every single click. Keeping DB work behind cached service calls is what keeps the app responsive against a remote Postgres.

---

## Features

| Feature | Description |
|---------|-------------|
| **Zelle Payments** | Guests pay via Zelle, then submit their transaction reference |
| **Auto QR Email** | QR code is emailed after registration, on a background thread so the guest isn't held up by the SMTP round-trip |
| **Bulk registration** | One person can buy up to 20 tickets and list every guest's name |
| **My QR lookup** | Guests re-find their QR code by email, or via the link in their email |
| **Self Check-In** | Camera scan or manual entry at the door |
| **Check-in window** | Check-in stays locked until 2 hours before the party, with an admin override |
| **Audio Announcement** | Speaks name + ticket count for staff via browser TTS |
| **Wristband Tracking** | Prevents double distribution |
| **Admin Dashboard** | Live stats, a spreadsheet for fast check-in/band/delete, and recent check-ins |
| **Party Buzz** | Public, aggregate-only activity stats and charts on the Home page |
| **CSV Export** | Download the guest list anytime (formula-injection safe) |
| **Submission audit log** | Every form submit — successful or not — is recorded |

### Check-in window

Guests should not be able to check themselves in weeks ahead of the party, so check-in is
**closed by default** and opens automatically **2 hours before the event** (3:30 PM CDT on
Oct 9, 2026). Until then the Scanner page shows when it opens instead of an input box.

Admin → Overview → **Check-in Window** overrides this:

| Mode | Behavior |
|------|----------|
| **Auto** (default) | Opens automatically 2 hours before the event |
| **Open now** | Forces it open — use for a rehearsal or an early start |
| **Closed** | Forces it shut |

The setting lives in the database, so it applies to everyone and survives restarts. The rule is
enforced in the service layer, not just hidden in the UI. Admin check-ins made from the Guests
spreadsheet always bypass the window, so an organiser can admit someone by hand at any time.

### Admin Guests spreadsheet

The Guests tab is an editable grid: tick **Checked In**, **Band Given**, and/or **Delete**
across as many rows as you like, then press **Save changes** once. Deletions require an explicit
confirmation step. Identity columns are read-only so they can't be edited by accident.

---

## App URLs

| Page | Who uses it | URL |
|------|-------------|-----|
| **Home** | Everyone | https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/ |
| **Register** | Guests | …/?page=Register |
| **My QR** | Guests | …/?page=My%20QR |
| **Scanner** | Check-in staff | …/?page=Scanner |
| **Admin** | Organiser | …/?page=Admin |

---

## Guest Flow

```
  Organiser shares Zelle details + registration link
          |
  Guest sends $20 per ticket via Zelle
          |
  Guest registers (name, email, tickets, Zelle reference, accepts T&Cs)
          |
  QR code is emailed to the guest
          |
   ── Night of the party ──
          |
  Guest shows QR  →  staff scans at Scanner
          |
  Audio: "Welcome Sarah! 2 tickets."
          |
  Staff hands wristband → clicks "Mark Band Given"
```

---

## Required Streamlit Cloud Secrets

**Streamlit Cloud → App → ⋮ → Settings → Secrets:**

```toml
SECRET_KEY = "your-long-random-secret-key-here"
# Use the Supabase Pooler connection string, NOT the direct db.*.supabase.co host.
DATABASE_URL = "postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres"

# Email (Gmail SMTP) — required for QR-code emails
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = "587"
MAIL_USERNAME = "your-sender@gmail.com"
MAIL_PASSWORD = "your-gmail-app-password"   # NOT your normal Gmail password
MAIL_DEFAULT_SENDER = "your-sender@gmail.com"

ADMIN_PASSWORD = "choose-a-strong-password"
TICKET_PRICE_CENTS = "2000"                  # 2000 = $20.00
ZELLE_INFO = "dallashudugaru@gmail.com"
APP_URL = "https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app"
```

> ⚠️ **`ADMIN_PASSWORD` is mandatory.** The admin dashboard exposes guest PII and can delete
> records, so password verification **fails closed**: if the secret is missing, nobody can log
> in and the page says so explicitly. (It used to do the opposite — an unset password let
> *anyone* straight in.)

> **Never commit `.streamlit/secrets.toml`** — it is `.gitignore`d. The copy in a local
> checkout may hold production database and SMTP credentials.

Set **Python 3.12** under Streamlit Cloud → Advanced settings. `requirements.txt` is pinned
against that version.

---

## Local Development

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then edit it
streamlit run streamlit_app.py
```

Open `http://localhost:8501`. With the example secrets it uses local SQLite — no Supabase needed.

> **Careful:** if your local `.streamlit/secrets.toml` contains the *production* `DATABASE_URL`
> and real SMTP credentials, running the app locally writes to the live guest list and sends
> real email. Point `DATABASE_URL` at `sqlite:///party_guests.db` and blank out `MAIL_USERNAME`
> before doing local UI work.

---

## Testing

**Unit tests** — service layer, validation, security, CSV/email escaping:

```bash
python -m unittest test_party_checkin -v
```

**End-to-end tests** — drive the real UI in a headless browser:

```bash
pip install pytest playwright && playwright install chromium
python -m pytest tests/e2e -v
```

The E2E suite launches its own Streamlit instance against a throwaway SQLite database with
SMTP disabled, so it never touches production data or sends mail.

Coverage includes: registration (valid, per-field validation errors, duplicate email),
check-in by QR / email / ID, double check-in, wristband tracking, admin auth (including
lockout after repeated failures), CSV export, QR generation and uniqueness, input
sanitization, CSV-injection and XSS escaping, and Postgres URL normalization.

---

## Input Validation Reference

| Field | Rules |
|-------|-------|
| **Full Name** | Letters and spaces only; 2–100 characters |
| **Email** | Standard email format; must be unique |
| **Phone** | Optional; US only; normalized to `+1-XXX-XXX-XXXX` on submit |
| **Additional Guest Names** | Optional; up to 20 names, one per line or comma-separated; letters and spaces only |
| **Zelle Reference** | Required; 8–30 characters; letters, digits, hyphens |
| **Terms** | Must accept "I/We Agree" |

---

## Party Day Checklist

**1 hour before:**
- [ ] Open the app to wake it from free-tier sleep
- [ ] Log in to **Admin**; verify the guest list and Zelle references
- [ ] Open **Scanner** on the check-in tablet and test the camera

**At the door:**
- [ ] **Scanner** open on the check-in tablet, camera facing guests
- [ ] **Admin** open on the organiser's phone for a live view
- [ ] Volume up for audio announcements

**After:**
- [ ] Download the CSV from **Admin**

---

## Submission Tracking & Supabase Views

Every registration submit is written to `submission_logs` with a status of `validation_error`,
`duplicate_email`, `db_error`, or `registered`.

These reporting views are created automatically on Postgres at startup:

| View | Purpose |
|------|---------|
| `vw_registrations_summary` | Totals: guests, tickets, checked-in, bands, pending, admitted |
| `vw_registrations_by_day` | Registrations grouped by date |
| `vw_checkins_by_hour` | Event-day check-ins grouped by hour |
| `vw_site_activity_summary` | Total/today visits and unique visitors |
| `vw_submissions_summary` | Submission counts grouped by status |
| `vw_submissions_recent` | Last 100 submission attempts |

---

## Troubleshooting

**App is slow to load**
Normal on the free tier — it was asleep. Open it a few minutes before guests arrive.

**"Running on a temporary local database" warning**
`DATABASE_URL` is missing or unreachable, and the app fell back to SQLite. Use the Supabase
**Pooler** string (`aws-0-*.pooler.supabase.com:6543`), not the direct `db.*.supabase.co` host.

**Nobody can log in to Admin**
`ADMIN_PASSWORD` is not set in secrets. Verification fails closed by design — set the secret
and reboot the app.

**Supabase project paused**
supabase.com → your project → Restore (~30 seconds). Happens after 7 days idle.

**Guest registered but got no QR email**
Confirm the registration in **Admin**, ask them to check spam, then use the **Resend QR Email**
button. Verify `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_DEFAULT_SENDER` are set and that
`MAIL_PASSWORD` is a Gmail *app password*.

**QR code not scanning**
Good lighting, steady camera, fill the frame. Fall back to manual entry — the Scanner accepts
the QR string, the guest's email, or their numeric ID.

**Camera not working on tablet/phone**
Some mobile browsers block camera access in embedded frames. Use Chrome on Android or grant
permission in iOS Settings → Safari → Camera.

**Charts fail to render locally**
`altair` (which `st.bar_chart` renders through) does not import on Python 3.14. Use Python 3.12.

---

## License

MIT — use it for your parties!
