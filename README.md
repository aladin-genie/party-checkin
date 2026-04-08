# 🎉 Party Check-In System

A complete event registration and check-in system with Stripe payments, QR codes, and audio announcements. Supports 200+ guests with self check-in.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 💳 **Stripe Payments** | Secure payment processing per ticket |
| 📧 **Auto QR Email** | QR codes sent automatically after payment |
| 📷 **Self Check-In** | Guests scan their own QR codes |
| 🔊 **Audio Announcement** | Speaks name + ticket count for staff |
| 🎨 **Wristband Tracking** | Prevents double distribution |
| 📊 **Admin Dashboard** | Real-time stats and guest management |
| 📥 **CSV Export** | Download guest list anytime |

## 🚀 Quick Start (Local)

```bash
cd party-checkin
./run.sh
```

Open http://localhost:5000

The script will use Gunicorn if available, otherwise falls back to Flask dev server.

## 🌐 Deploy to Render.com

### 1. Create Render Account
- Go to [render.com](https://render.com)
- Sign up with GitHub

### 2. Create New Web Service
1. Click "New +" → "Web Service"
2. Connect your GitHub repo
3. Select the party-checkin folder

### 3. Configure Environment Variables

In Render dashboard → Your Service → Environment:

```
SECRET_KEY=(auto-generated or random string)
TICKET_PRICE_CENTS=2000

# Stripe (required for payments)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email (optional but recommended)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

### 4. Deploy
Click "Deploy" - Render will build and deploy automatically!

---

## 💳 Stripe Setup

### 1. Create Stripe Account
- Go to [stripe.com](https://stripe.com)
- Complete onboarding

### 2. Get API Keys
- Dashboard → Developers → API keys
- Copy **Publishable key** (starts with `pk_`)
- Copy **Secret key** (starts with `sk_`)

### 3. Set Up Webhook
1. Dashboard → Developers → Webhooks
2. Add endpoint: `https://your-app.onrender.com/webhook`
3. Select event: `checkout.session.completed`
4. Copy **Signing secret** (starts with `whsec_`)

### 4. Test Payment
Use Stripe test card:
- Card: `4242 4242 4242 4242`
- Date: Any future date
- CVC: Any 3 digits

---

## 📧 Email Setup (Gmail)

### 1. Enable 2FA
- Google Account → Security → 2-Step Verification

### 2. Create App Password
- Google Account → Security → App passwords
- Select "Mail" + "Other (Custom name)"
- Name: "Party Check-In"
- Copy the 16-character password

### 3. Configure in Render
```
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=xxxx xxxx xxxx xxxx (the app password)
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

---

## 🎨 Party Day Workflow

### Setup (Before Party)
```bash
# Deploy and verify
https://your-app.onrender.com/admin

# Test registration with Stripe test card
https://your-app.onrender.com/register
```

### At the Party
1. **Check-In Station**: Open `/scanner` on a tablet/laptop with camera
2. **Volume Up**: Ensure audio is audible for wristband staff
3. **Admin Access**: Keep `/admin` open on organizer's phone for monitoring

### Guest Flow
```
Guest arrives → Scans QR code
                ↓
Audio: "Welcome Sarah! You have 3 tickets."
                ↓
Staff hands 3 wristbands
                ↓
Staff clicks "Mark Band Given"
                ↓
Guest enters! 🎉
```

---

## 💰 Pricing Configuration

Change ticket price by setting `TICKET_PRICE_CENTS`:

| Price | Value |
|-------|-------|
| $10 | 1000 |
| $20 | 2000 |
| $50 | 5000 |
| Free | 0 (skips payment) |

---

## 🔒 Security Notes

- **Never commit `.env` files** with real keys
- **Stripe webhooks verify signatures** - tamper-proof
- **Admin page** is public - consider adding password protection for production
- **SQLite database** persists on Render's disk

---

## 🐛 Troubleshooting

### Payment not working
- Check Stripe keys are set in Render
- Verify webhook URL is correct
- Check Render logs: Dashboard → Logs

### Email not sending
- Verify app password (not regular Gmail password)
- Check spam folders
- Test with Mailtrap for development

### QR codes not scanning
- Ensure good lighting
- Hold phone steady
- Try manual entry as fallback

---

## 📁 Project Structure

```
party-checkin/
├── app.py                 # Flask backend
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment config
├── run.sh                # Local startup script
├── README.md             # This file
├── party_guests.db       # SQLite database
└── templates/
    ├── index.html        # Home page
    ├── register.html     # Registration + payment
    ├── scanner.html      # Self check-in
    ├── view_qr.html      # QR code display
    └── admin.html        # Dashboard
```

---

## 📝 License

MIT - Use for your parties! 🎊
