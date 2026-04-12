# Party Check-In System

A complete event registration and check-in system with Stripe payments, QR codes, and audio announcements. Supports 200+ guests with self check-in.

## Features

| Feature | Description |
|---------|-------------|
| **Stripe Payments** | Secure payment processing per ticket |
| **Auto QR Email** | QR codes sent automatically after payment |
| **Self Check-In** | Guests scan their own QR codes |
| **Audio Announcement** | Speaks name + ticket count for staff |
| **Wristband Tracking** | Prevents double distribution |
| **Admin Dashboard** | Real-time stats and guest management |
| **CSV Export** | Download guest list anytime |

---

## How It Works (Architecture)

```
                        INTERNET
                            |
                    [ Your Guests ]
                            |
              https://party-checkin.onrender.com
                            |
                +-----------+----------+
                |                      |
         [ Render.com ]         [ Supabase ]
         Runs the app            Stores data
         Flask + Python          PostgreSQL DB
         FREE tier               FREE tier
         (sleeps when idle)      (500MB storage)
                |                      |
                +-----------+----------+
                            |
                    Your Party App!
```

**What each part does:**

| Part | Role | Cost | URL |
|------|------|------|-----|
| **Render** | Runs your Flask app in the cloud | Free | `party-checkin.onrender.com` |
| **Supabase** | Stores guest list & check-in data | Free | No URL — internal database only |
| **Domain** | Custom web address (optional) | ~$12/yr | e.g. `myparty.com` — not needed |

> **Free tier note:** On Render's free plan the app sleeps after 15 min of inactivity and takes ~30 seconds to wake up on the next visit. This is fine — just open the app a minute before guests arrive to pre-warm it. Upgrade to Render Starter ($7/mo) anytime for always-on.

---

## Your App URL

Once deployed, your app lives at:

```
https://<your-service-name>.onrender.com
```

Share these links with your team:

| Link | Who uses it |
|------|-------------|
| `https://your-app.onrender.com/register` | Guests — to register and pay |
| `https://your-app.onrender.com/scanner` | Check-in staff — scan QR codes |
| `https://your-app.onrender.com/admin` | Organiser — live dashboard |

---

## Guest Flow

```
  Guest registers online
          |
          v
  Stripe payment page
          |
    Payment success
          |
          v
  QR code emailed to guest
          |
   Night of the party
          |
          v
  Guest shows QR code
          |
          v
  Staff scans at /scanner
          |
          v
  Audio: "Welcome Sarah! 2 tickets."
          |
          v
  Staff hands wristbands
          |
  Click "Mark Band Given"
          |
          v
  Guest enters the party!
```

---

## Deploy: Render Free + Supabase Free

### Step 1 — Set Up Supabase (database)

1. Go to [supabase.com](https://supabase.com) → **Start your project** (free)
2. Create a new project — pick any name and region
3. Wait ~2 minutes for it to provision
4. Go to **Settings → Database → Connection string → URI**
5. Copy the URI — it looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres
   ```
   Keep this — you'll paste it into Render in Step 2.

> Supabase free tier: 500MB storage (enough for thousands of guests), 2 free projects. Project pauses after 7 days of inactivity — just log in and unpause before your next event.

---

### Step 2 — Deploy on Render (app host)

1. Go to [render.com](https://render.com) → sign up with GitHub
2. Click **New + → Web Service**
3. Connect your GitHub repo (`party-checkin`)
4. Render auto-detects `render.yaml` — confirm the settings:
   - **Runtime**: Python
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
   - **Plan**: Free
5. Set these environment variables in the dashboard:

```
DATABASE_URL        = postgresql://postgres:...@db.xxxx.supabase.co:5432/postgres
                      (paste your Supabase URI from Step 1)

SECRET_KEY          = (any long random string, e.g. mysupersecretkey123)

STRIPE_SECRET_KEY   = sk_test_...
STRIPE_PUBLISHABLE_KEY = pk_test_...
STRIPE_WEBHOOK_SECRET  = whsec_...

MAIL_USERNAME       = your-gmail@gmail.com
MAIL_PASSWORD       = xxxx xxxx xxxx xxxx  (Gmail app password)
MAIL_DEFAULT_SENDER = your-gmail@gmail.com

TICKET_PRICE_CENTS  = 2000   (= $20 per ticket)
ADMIN_PASSWORD      = (optional, protects /admin)
```

6. Click **Deploy** — done. Tables are created automatically on first boot.

Your app is live at `https://<service-name>.onrender.com`

---

### Upgrade Path (when you need always-on)

No code changes needed — just change the Render plan:

```
Render Free ($0)  →  Render Starter ($7/mo)
  sleeps when idle      always on, no cold start
```

Supabase stays free either way.

---

## Stripe Setup

### Get API Keys
1. [stripe.com](https://stripe.com) → Developers → API keys
2. Copy **Publishable key** (`pk_...`) and **Secret key** (`sk_...`)

### Set Up Webhook
1. Stripe Dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://your-app.onrender.com/webhook`
3. Event: `checkout.session.completed`
4. Copy **Signing secret** (`whsec_...`)

### Test Payment
```
Card:  4242 4242 4242 4242
Date:  Any future date
CVC:   Any 3 digits
```

---

## Gmail Setup

1. Google Account → Security → **2-Step Verification** (enable)
2. Google Account → Security → **App passwords**
3. Select App: Mail / Device: Other → name it "Party Check-In"
4. Copy the 16-character password → use as `MAIL_PASSWORD`

---

## Party Day Checklist

**1 hour before:**
- [ ] Open `https://your-app.onrender.com` to wake it from sleep
- [ ] Log in to `/admin` and verify guest list looks correct
- [ ] Open `/scanner` on the check-in tablet and test camera

**At the door:**
- [ ] `/scanner` open on check-in tablet (camera facing guests)
- [ ] `/admin` open on organiser phone for live view
- [ ] Volume up on scanner device for audio announcements

**After the party:**
- [ ] Download CSV from `/admin` for records
- [ ] Optionally pause/delete Supabase project and Render service

---

## Pricing Configuration

Change ticket price by setting `TICKET_PRICE_CENTS` in Render dashboard:

| Price | Value |
|-------|-------|
| $10 | `1000` |
| $20 | `2000` |
| $50 | `5000` |
| Free | `0` (skips payment) |

---

## Local Development

```bash
cd party-checkin
./run.sh
```

Open `http://localhost:5000` — uses SQLite locally, no Supabase needed.

---

## Project Structure

```
party-checkin/
├── app.py              # Flask app (routes, models, logic)
├── requirements.txt    # Python dependencies
├── render.yaml         # Render deployment config (free tier + Supabase)
├── railway.toml        # Railway deployment config (alternative)
├── gunicorn.conf.py    # Production server config
├── run.sh              # Local dev startup script
├── README.md           # This file
└── templates/
    ├── index.html      # Home / stats page
    ├── register.html   # Registration + Stripe payment
    ├── scanner.html    # Self check-in QR scanner
    ├── view_qr.html    # QR code display
    └── admin.html      # Live admin dashboard
```

---

## Troubleshooting

**App takes 30 seconds to load**
Normal on Render free tier — it was sleeping. Open it a minute before guests arrive.

**Supabase project is paused**
Log in to supabase.com → click your project → Restore. Takes ~30 seconds. Happens after 7 days of no activity.

**Payment not working**
- Check Stripe keys are set in Render environment variables
- Verify webhook URL matches your Render URL exactly
- Check Render logs: Dashboard → your service → Logs

**Email not sending**
- Make sure you used the Gmail *app password* (not your normal login password)
- Check spam folder
- Verify `MAIL_USERNAME` and `MAIL_DEFAULT_SENDER` match

**QR code not scanning**
- Ensure good lighting at the check-in station
- Hold camera steady and wait 1-2 seconds
- Use manual guest lookup as fallback

---

## License

MIT — use it for your parties!
