# Party Check-In System

A complete event registration and check-in system built with **Streamlit** (free hosting on Streamlit Community Cloud). Features QR codes, self check-in, audio announcements, and admin dashboard. Supports 200+ guests.

## Features

| Feature | Description |
|---------|-------------|
| **Zelle Payments** | Guests pay via Zelle then submit their transaction reference |
| **Auto QR Email** | QR codes sent automatically after registration |
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
              https://your-app.streamlit.app
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
                    Your Party App!
```

**What each part does:**

| Part | Role | Cost | URL |
|------|------|------|-----|
| **Streamlit Cloud** | Runs your app in the cloud | Free | `your-app.streamlit.app` |
| **Supabase** | Stores guest list & check-in data | Free | No URL — internal database only |
| **Custom Domain** | Custom web address (optional) | ~$12/yr | e.g. `myparty.com` — not needed |

> **Free tier note:** On Streamlit Cloud's free plan, apps sleep after ~7 days of inactivity and wake up on the next visit. Open the app a minute before guests arrive to pre-warm it.

---

## Your App URL

Once deployed, your app lives at:

```
https://<your-app-name>.streamlit.app
```

Share these links with your team:

| Page | Who uses it | URL |
|------|-------------|-----|
| **Register** | Guests — to register and pay | `https://your-app.streamlit.app?page=Register` |
| **Scanner** | Check-in staff — scan QR codes | `https://your-app.streamlit.app?page=Scanner` |
| **Admin** | Organiser — live dashboard | `https://your-app.streamlit.app?page=Admin` |

---

## Guest Flow

```
  Organiser shares Zelle details + registration link with guests
          |
          v
  Guest sends Zelle payment
          |
          v
  Guest opens the Register page
  Fills in: Name, Email, Tickets, Zelle Transaction ID
          |
          v
  QR code emailed to guest instantly
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
  Clicks "Mark Band Given"
          |
          v
  Guest enters the party!
```

---

## Deploy: Streamlit Cloud (Free) + Supabase (Free)

### Step 1 — Fork / Push to GitHub

1. Create a new GitHub repo (or fork this one)
2. Push all files: `streamlit_app.py`, `utils.py`, `requirements.txt`, `.streamlit/config.toml`
3. **Do NOT commit `.streamlit/secrets.toml`** — it contains passwords

---

### Step 2 — Set Up Supabase (database)

1. Go to [supabase.com](https://supabase.com) → **Start your project** (free)
2. Create a new project — pick any name and region
3. Wait ~2 minutes for it to provision
4. Go to **Settings → Database → Connection string → URI**
5. Copy the URI — it looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres
   ```
   Keep this — you'll paste it into Streamlit Cloud in Step 3.

> Supabase free tier: 500MB storage (enough for thousands of guests), 2 free projects. Project pauses after 7 days of inactivity — just log in and unpause before your next event.

---

### Step 3 — Deploy on Streamlit Community Cloud

1. Go to [streamlit.io/cloud](https://streamlit.io/cloud) → sign in with GitHub
2. Click **Create app → From existing repo**
3. Select your GitHub repo (`party-checkin`)
4. Set:
   - **Main file path**: `streamlit_app.py`
   - **Branch**: `main` (or whatever your default is)
5. Click **Advanced settings → Secrets** and paste the following (replace with your actual values):

```toml
[secrets]
SECRET_KEY = "your-long-random-secret-key-here"
DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@db.xxxx.supabase.co:5432/postgres"

# Email (Gmail SMTP example)
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = "587"
MAIL_USERNAME = "your-email@gmail.com"
MAIL_PASSWORD = "your-gmail-app-password"
MAIL_DEFAULT_SENDER = "your-email@gmail.com"

# Admin password (leave empty for no protection)
ADMIN_PASSWORD = "your-admin-password"

# Ticket price in cents (e.g., 2000 = $20.00)
TICKET_PRICE_CENTS = "2000"

# Zelle payment info (shown to guests on registration page)
ZELLE_INFO = "your-zelle-phone@email.com or +1-234-567-8900"
```

6. Click **Deploy** — done! Tables are created automatically on first boot.

Your app is live at `https://<your-app-name>.streamlit.app`

---

### Upgrade Path (when you need always-on)

No code changes needed — Streamlit Cloud doesn't have a paid "always-on" tier for personal apps, but apps stay awake while being used. For business needs, consider Streamlit in Snowflake or a VPS.

---

## Zelle Payment Setup

No third-party payment account needed. Zelle works directly through your bank app.

### How It Works
1. You share your Zelle details (phone number or email) with guests along with the registration link
2. Guest sends payment via Zelle in their banking app
3. Guest opens the registration form, fills in their details + Zelle transaction reference
4. You can cross-check the transaction reference in your bank app against the guest list in Admin

### Recommended Message to Share with Guests
```
Hi! Here's how to register for the party:

1. Send $20 per ticket via Zelle to: [your-zelle-phone-or-email]
2. Register here: https://your-app.streamlit.app?page=Register
   (Enter your Zelle transaction reference number in the form)
3. You'll receive your QR code by email — bring it on the night!
```

### Verifying Payments at the Door
- Open the **Admin** page on your phone
- Guest list shows the Zelle transaction reference each guest submitted
- Cross-check against your bank app if needed

---

## Gmail Setup

1. Google Account → Security → **2-Step Verification** (enable)
2. Google Account → Security → **App passwords**
3. Select App: Mail / Device: Other → name it "Party Check-In"
4. Copy the 16-character password → use as `MAIL_PASSWORD` in Streamlit Cloud secrets

---

## Party Day Checklist

**1 hour before:**
- [ ] Open `https://your-app.streamlit.app` to wake it from sleep (free tier cold start)
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

The price displayed on the registration form is controlled by `TICKET_PRICE_CENTS` in your Streamlit Cloud secrets. This is display only — it tells guests how much to send via Zelle.

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

## Troubleshooting

**App takes time to load**
Normal on Streamlit Cloud free tier — it was sleeping. Open it a minute before guests arrive.

**Supabase project is paused**
Log in to supabase.com → click your project → Restore. Takes ~30 seconds. Happens after 7 days of no activity.

**Guest says they registered but no QR code received**
- Check **Admin** to confirm their registration is there
- Ask them to check spam/junk folder
- Verify `MAIL_USERNAME` and `MAIL_PASSWORD` are set correctly in Streamlit Cloud secrets

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
