# Party Check-In System

A complete event registration and check-in system built with **Streamlit** (free hosting on Streamlit Community Cloud). Features QR codes, self check-in, audio announcements, and an admin dashboard. Supports 200+ guests.

## Current Status — Dallas Boys Party 2026

- **Event:** Friday, October 9, 2026 · 5:30 PM onwards
- **Venue:** Elegance Ballroom & Event Center, 8740 Ohio Dr A1, Plano, TX 75024
- **Theme:** 12th Year of Togetherness
- **Live app:** https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/
- **GitHub:** `aladin-genie/party-checkin` on `main`
- **Database:** Supabase PostgreSQL (connected)
- **Payment:** Zelle → `dallashudugaru@gmail.com`
- **Ticket price:** $20.00 per ticket
- **QR-code emails:** Configured and verified — Gmail SMTP sends QR codes automatically after registration.

### What works now
- Modern, mobile-first dark UI with the 2026 event details.
- Home page shows public **Site Activity** stats (visits, unique visitors, registrations).
- Registration page enforces field validations and shows red per-field errors.
- Ticket total updates automatically as guests change the number of tickets.
- Names accept letters and spaces only; plus-one is optional.
- Phone number accepts US digits and is normalized to `+1-XXX-XXX-XXXX` on submit.
- Zelle confirmation reference accepts 8–30 letters/digits/hyphens (e.g., `ZELLE12345678`, `TXN-ABCD1234`, `1234567890`).
- Terms & Conditions / Alcohol Disclaimer must be accepted before registering.
- QR code is hidden from the UI and is emailed automatically after registration.
- Admin dashboard with guest list, CSV export, manual check-in, and band tracking.

---

## Features

| Feature | Description |
|---------|-------------|
| **Zelle Payments** | Guests pay via Zelle then submit their transaction reference |
| **Auto QR Email** | QR code is emailed automatically after registration (when SMTP is configured) |
| **Self Check-In** | Guests scan their own QR codes at the door using camera or manual entry |
| **Audio Announcement** | Speaks name + ticket count for staff via browser TTS |
| **Wristband Tracking** | Prevents double distribution |
| **Admin Dashboard** | Real-time stats, guest management, CSV export |
| **CSV Export** | Download guest list anytime |

---

## How It Works (Architecture)

```
                        INTERNET
                            |
                    [ Your Guests ]
                            |
              https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app
                            |
                +-----------+----------+
                |                      |
         [ Streamlit Cloud ]     [ Supabase ]
         Runs the app             Stores data
         Streamlit + Python      PostgreSQL DB
         FREE tier               FREE tier
                |                      |
                +-----------+----------+
                            |
                    Dallas Boys Party App!
```

| Part | Role | Cost | URL |
|------|------|------|-----|
| **Streamlit Cloud** | Runs the app in the cloud | Free | https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/ |
| **Supabase** | Stores guest list & check-in data | Free | Internal database only |

> **Free tier note:** On Streamlit Cloud's free plan, apps sleep after ~7 days of inactivity and wake up on the next visit. Open the app a minute before guests arrive to pre-warm it.

---

## App URLs

Share these links with your team:

| Page | Who uses it | URL |
|------|-------------|-----|
| **Home** | Everyone | https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/ |
| **Register** | Guests — register and pay | https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/?page=Register |
| **Scanner** | Check-in staff — scan QR codes | https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/?page=Scanner |
| **Admin** | Organiser — live dashboard | https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/?page=Admin |

---

## Guest Flow

```
  Organiser shares Zelle details + registration link with guests
          |
          v
  Guest sends $20 per ticket via Zelle to dallashudugaru@gmail.com
          |
          v
  Guest opens the Register page
  Fills in: Name, Email, Phone (optional), Tickets,
            Plus One (optional), Zelle Transaction Reference
          |
          v
  Guest accepts Terms & Conditions (Alcohol Disclaimer)
          |
          v
  QR code is emailed to guest
          |
   Night of the party
          |
          v
  Guest shows QR code (phone or printout)
          |
          v
  Staff scans at Scanner page
          |
          v
  Audio: "Welcome Sarah! 2 tickets."
          |
          v
  Staff hands wristbands
          |
          v
  Clicks "Mark Band Given"
          |
          v
  Guest enters the party!
```

---

## Deploy / Re-Deploy on Streamlit Community Cloud

The app is already deployed. To push a new version:

1. Commit and push changes to `main` of `aladin-genie/party-checkin`.
2. Open the deploy page:  
   `https://share.streamlit.io/deploy?repository=aladin-genie/party-checkin&branch=main&mainModule=streamlit_app.py`
3. Make sure the workspace is `aladin-genie` (yvh1225@gmail.com account).
4. Click **Deploy**.

Tables are created automatically on first boot.

---

## Required Streamlit Cloud Secrets

Go to **Streamlit Cloud → App → ⋮ → Settings → Secrets** and paste:

```toml
SECRET_KEY = "your-long-random-secret-key-here"
# Use the Supabase Pooler connection string, not the direct db.*.supabase.co host.
DATABASE_URL = "postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres"

# Email (Gmail SMTP example) — REQUIRED for QR-code emails to send
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = "587"
MAIL_USERNAME = "your-sender@gmail.com"
MAIL_PASSWORD = "your-gmail-app-password"   # NOT your normal Gmail password
MAIL_DEFAULT_SENDER = "your-sender@gmail.com"

# Admin password for the dashboard
ADMIN_PASSWORD = "party2026"

# Ticket price in cents (e.g., 2000 = $20.00)
TICKET_PRICE_CENTS = "2000"

# Zelle payment info shown to guests
ZELLE_INFO = "dallashudugaru@gmail.com"
```

> **Do not commit `.streamlit/secrets.toml`.** It is already `.gitignore`d.

---

## Email Setup

QR-code emails are sent via SMTP. Without `MAIL_USERNAME` and `MAIL_PASSWORD`, the app still registers guests but cannot email the QR code.

### Gmail App Password (recommended)

1. Google Account → Security → **2-Step Verification** (enable)
2. Google Account → Security → **App passwords**
3. Select App: **Mail** / Device: **Other** → name it "Party Check-In"
4. Copy the 16-character password → use it as `MAIL_PASSWORD` in Streamlit Cloud secrets
5. Add `MAIL_USERNAME` and `MAIL_DEFAULT_SENDER` (usually the same Gmail address)
6. Reboot the Streamlit app from the cloud dashboard

---

## Zelle Payment Setup

No third-party payment account is needed. Zelle works directly through each guest's bank app.

### How It Works
1. You share the Zelle email `dallashudugaru@gmail.com` with guests
2. Guest sends $20 per ticket via Zelle in their banking app
3. Guest opens the registration form and enters the Zelle transaction reference
4. You can cross-check the transaction reference in your bank app against the guest list in Admin

### Recommended Message to Share with Guests
```
Hi! Here's how to register for the Dallas Boys Party — 12th Year of Togetherness:

Event: Friday, October 9th, 2026 | 5:30 PM onwards
Venue: Elegance Ballroom & Event Center, 8740 Ohio Dr A1, Plano, TX 75024

1. Send $20 per ticket via Zelle to: dallashudugaru@gmail.com
2. Register here: https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/?page=Register
   (Enter your Zelle transaction reference number in the form)
3. You'll receive your QR code by email — bring it on the night!
```

### Verifying Payments at the Door
- Open the **Admin** page on your phone
- The guest list shows the Zelle transaction reference each guest submitted
- Cross-check against your bank app if needed

---

## Input Validation Reference

| Field | Rules |
|-------|-------|
| **Full Name** | Letters and spaces only; minimum 2 characters |
| **Email** | Standard email format |
| **Phone** | Optional; placeholder shows `+1-XXX-XXX-XXXX`; digits are normalized on submit |
| **Plus One Name** | Optional; letters and spaces only |
| **Zelle Reference** | Required; 8–30 characters; letters, digits, hyphens |
| **Terms** | Must accept "I/We Agree" |

---

## Party Day Checklist

**1 hour before:**
- [ ] Open https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/ to wake it from sleep (free tier cold start)
- [ ] Log in to **Admin** and verify guest list and Zelle references look correct
- [ ] Open **Scanner** on the check-in tablet and test camera

**At the door:**
- [ ] **Scanner** page open on check-in tablet (camera facing guests)
- [ ] **Admin** page open on organiser phone for live view
- [ ] Volume up on scanner device for audio announcements

**After the party:**
- [ ] Download CSV from **Admin** for records
- [ ] Optionally pause/delete Supabase project and Streamlit app

---

## Ticket Price Configuration

The price displayed on the registration form is controlled by `TICKET_PRICE_CENTS` in your Streamlit Cloud secrets. This is display only — guests send the amount via Zelle manually.

| Ticket Price | Value to Set |
|-------|-------|
| $10 | `1000` |
| $20 | `2000` |
| $50 | `5000` |
| Free event | `0` |

---

## Local Development

```bash
cd party-checkin

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up local secrets (optional)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your values

# Run the app
streamlit run streamlit_app.py
```

Open `http://localhost:8501` — uses SQLite locally, no Supabase needed.

---

## Testing

Run the automated test suite to verify all backend features:

```bash
python test_party_checkin.py
```

Tests cover:
- Database CRUD (create guest, check-in, band marking)
- QR code generation and uniqueness
- Statistics calculation
- CSV export (including injection prevention)
- Email sending (with/without credentials)
- Input sanitization (email, name, phone, Zelle ref)
- Admin password verification (constant-time comparison)
- XSS prevention in audio announcements

---

## Project Structure

```
party-checkin/
├── streamlit_app.py          # Streamlit app (entry point — all pages)
├── utils.py                   # Database models, QR generation, email, helpers
├── test_party_checkin.py    # Automated test suite
├── requirements.txt           # Python dependencies
├── .streamlit/
│   ├── config.toml            # Streamlit theme and server config
│   └── secrets.toml.example   # Example secrets file (DO NOT commit secrets.toml)
├── README.md                  # This file
└── party_guests.db            # Local SQLite database (auto-created, .gitignored)
```

---

## Submission Tracking & Supabase Views

Every registration form submit (successful or failed) is written to the `submission_logs` table:

| Status | Meaning |
|--------|---------|
| `validation_error` | Form failed validation (name/email/phone/Zelle/terms) |
| `duplicate_email` | Email already registered |
| `registered` | New guest created successfully |

The following reporting views are created automatically in Supabase on app startup:

| View | Purpose |
|------|---------|
| `vw_registrations_summary` | Total guests, tickets, checked-in, bands, pending, admitted tickets |
| `vw_registrations_by_day` | Registrations grouped by date |
| `vw_checkins_by_hour` | Event-day check-ins grouped by hour |
| `vw_site_activity_summary` | Total/today visits and unique visitors |
| `vw_submissions_summary` | Submission counts grouped by status |
| `vw_submissions_recent` | Last 100 submission attempts |

You can query these directly in the Supabase SQL Editor for dashboards and reports.

---

## Troubleshooting

**App takes time to load**
Normal on Streamlit Cloud free tier — it was sleeping. Open it a minute before guests arrive.

**"Running on a temporary local database" warning**
The `DATABASE_URL` secret is missing or points to the wrong host. Use the **Pooler** connection string from Supabase (`aws-0-*.pooler.supabase.com:6543`), not the direct `db.*.supabase.co` host.

**Supabase project is paused**
Log in to supabase.com → click your project → Restore. Takes ~30 seconds. Happens after 7 days of no activity.

**Guest says they registered but no QR code received**
- Check **Admin** to confirm their registration is there
- Ask them to check spam/junk folder
- Verify `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_DEFAULT_SENDER` are set in Streamlit Cloud secrets

**Email not sending**
- Make sure you used the Gmail *app password* (not your normal login password)
- Check spam folder
- Verify `MAIL_USERNAME` and `MAIL_DEFAULT_SENDER` match

**QR code not scanning**
- Ensure good lighting at the check-in station
- Hold camera steady and fill the frame
- Use manual guest lookup as fallback
- Make sure the camera permission is allowed in your browser

**Camera not working on tablet/phone**
- Some mobile browsers block camera access in embedded frames. Use a desktop browser or Chrome on Android
- For iOS Safari, ensure camera permissions are granted in Settings → Safari → Camera

---

## License

MIT — use it for your parties!
