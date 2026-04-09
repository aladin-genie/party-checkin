# Dallas Boyz Party Check-In System 🏏🎉

**Event:** Dallas Boyz Party (RCB Theme)  
**Date:** September 19, 2025  
**Location:** Elegance Event Center, 8740 Ohio Dr A1, Plano, TX 75024  
**Time:** 6:00 PM - 11:00 PM

---

## Overview

A complete event registration and check-in system for 200+ guests with:
- ✅ Online registration with Zelle payment
- ✅ QR code generation and email delivery
- ✅ Self check-in with partial band collection
- ✅ Email lookup for lost QR codes
- ✅ Admin dashboard for payment tracking
- ✅ Real-time statistics and reporting

---

## Features

### For Guests

#### 1. Registration (`/register`)
- First Name + Last Name
- Number of attendees (1-10)
- Names of all attendees (for group registrations)
- Contact email and phone
- Zelle Transaction ID
- Food preferences (Veg/Non-Veg count)
- Volunteer option
- Alcohol disclaimer agreement with digital signature
- **Price:** $35 per person
- **Payment:** Zelle to dallashudugaru@gmail.com

#### 2. QR Code Delivery
- QR code generated immediately upon registration
- Email sent instantly with QR code attachment
- View QR code online at `/qr/<code>`
- Print or save option available

#### 3. Self Check-In (`/scanner`)
**Option 1 - QR Code:**
- Scan QR code at entrance
- Welcome message displayed on screen
- Select how many bands to collect now
- Collect bands from staff

**Option 2 - Email Lookup:**
- Enter email address if QR code lost
- System finds registration
- Same check-in flow as QR

**Partial Collection Support:**
- Bought 5 tickets but only 2 people arrived? Give 2 bands now, 3 later
- Counter shows: Total / Taking now / Can collect later
- Return later for remaining bands

---

### For Admin

#### Admin Dashboard (`/admin`)
Protected by password (set via `ADMIN_PASSWORD` env var)

**Stats Overview:**
- Total Guests
- Payment Verified ✅
- Payment Unverified ⏳
- Checked In
- Total Tickets
- Estimated Revenue

**Payment Verification Tab:**
- List of all registrations with Zelle Transaction IDs
- Checkbox to mark payment as verified
- Notes field for each payment
- "Open Zelle" button for quick access
- Shows registrant details and all attendee names

**Check-In Status Tab:**
- Who has checked in
- How many bands given
- "Resend QR Email" button (for undelivered emails)
- View QR code option

**All Guests Tab:**
- Complete guest list
- Search functionality
- Payment method and status

**Export:**
- Download CSV of all guests
- Includes: Name, Email, Tickets, Payment, Transaction ID, Check-in status

---

## Technical Stack

- **Backend:** Flask (Python)
- **Database:** SQLite (with Render disk persistence)
- **QR Codes:** qrcode library (PIL)
- **Email:** Flask-Mail (SMTP)
- **Frontend:** HTML5, CSS3, Vanilla JS
- **QR Scanning:** html5-qrcode library
- **Hosting:** Render.com (free tier)

---

## Database Schema

### Guest Model
```python
- id: Primary key
- first_name, last_name, name: Guest name
- email, phone: Contact info
- num_attendees, ticket_count: Number of tickets
- attendee_names: Comma-separated list of all attendees
- veg_count, nonveg_count: Food preferences
- volunteer: Yes/No
- payment_method: zelle (default)
- transaction_id: Zelle confirmation
- total_amount: Total paid
- qr_code: Unique QR code string
- checked_in: Boolean
- band_given: Boolean (all bands given)
- bands_given_count: Integer (partial tracking)
- checkin_time: Timestamp
- approved: Boolean (auto-true)
- disclaimer_agreed: Boolean
- signature_name: Digital signature
- payment_verified: Boolean (admin tracking)
- payment_verified_at: Timestamp
- payment_verified_by: Admin name
- payment_notes: Admin notes
- created_at: Timestamp
```

### CheckInLog Model
```python
- id: Primary key
- guest_id: Foreign key
- action: 'checkin', 'band_given_X'
- timestamp: When action occurred
- device_info: User agent string
```

---

## Deployment

### 1. Create Render Account
- Go to [dashboard.render.com](https://dashboard.render.com)
- Sign up with GitHub

### 2. Deploy Web Service
1. Click **New +** → **Web Service**
2. Connect GitHub → Select `aladin-genie/party-checkin`
3. Render auto-detects `render.yaml`
4. Set environment variables (see below)
5. Click **Create Web Service**

### 3. Environment Variables

```bash
# Required
SECRET_KEY=your-random-secret-key-here
DATABASE_PATH=/opt/render/project/src/data/party_guests.db
ADMIN_PASSWORD=your-admin-password

# Email Configuration (for QR code emails)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

**Note:** For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

### 4. Disk Setup (Render)
Render automatically creates a disk at `/opt/render/project/src/data/` for SQLite persistence.

---

## Local Development

### Setup
```bash
# Clone repository
git clone https://github.com/aladin-genie/party-checkin.git
cd party-checkin

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SECRET_KEY="dev-secret-key"
export DATABASE_PATH="party_guests.db"
export ADMIN_PASSWORD="admin123"
export MAIL_USERNAME="your-email@gmail.com"
export MAIL_PASSWORD="your-app-password"

# Run locally
python app.py
```

### Access Locally
- Home: http://localhost:5000
- Register: http://localhost:5000/register
- Scanner: http://localhost:5000/scanner
- Admin: http://localhost:5000/admin (password required)

---

## API Endpoints

### Public Endpoints
```
POST /register          # Submit registration
GET  /qr/<code>         # View QR code
GET  /scanner           # Self check-in page
```

### API Endpoints (JSON)
```
POST /api/checkin               # QR code check-in
POST /api/lookup-by-email       # Email lookup
POST /api/give-bands            # Give partial bands
GET  /api/stats                 # Get statistics
```

### Admin Endpoints (Password Protected)
```
GET  /admin                     # Admin dashboard
POST /admin/verify-payment/<id> # Mark payment verified
POST /admin/resend-qr/<id>      # Resend QR email
GET  /download/csv              # Export guest list
```

---

## Workflow

### Guest Journey
1. **Register** at `/register`
   - Fill form, enter Zelle transaction ID
   - Agree to alcohol disclaimer
   - Submit

2. **Receive QR Code**
   - QR code generated immediately
   - Email sent with QR code attachment
   - Can view/print at `/qr/<code>`

3. **Check-In at Event**
   - Go to `/scanner` on phone
   - Scan QR code (or enter email)
   - Select bands to collect now
   - Show confirmation to staff
   - Collect wristbands

### Admin Journey
1. **Track Payments**
   - Log in to `/admin`
   - Go to "Payment Verification" tab
   - Open Zelle, check each transaction
   - Mark verified ✅ or add notes

2. **Resend QR Codes** (if needed)
   - Find guest in "Check-In Status" tab
   - Click "📧 Resend Email" button
   - Only available if bands not collected yet

3. **Monitor Check-Ins**
   - Real-time stats on dashboard
   - See who checked in, bands given
   - Export CSV for records

---

## Important Notes

### Zelle Payments
- Guests send payment to: `dallashudugaru@gmail.com`
- Must include: Name, number of spots, food preference in memo
- Admin verifies manually in dashboard

### Partial Band Collection
- Groups can arrive at different times
- System tracks: total / given / remaining
- Can check in multiple times for remaining bands

### Lost QR Codes
- Guests can use email lookup at scanner
- Admin can resend QR code email
- No bands collected yet = can resend

### Privacy
- All data stored in SQLite database
- Email addresses used only for QR delivery
- No data shared with third parties

---

## Troubleshooting

### Email Not Sending
- Check MAIL_USERNAME and MAIL_PASSWORD
- For Gmail: Use App Password, not regular password
- Check spam/junk folders
- Use admin "Resend Email" feature

### Database Issues
- On Render: Check DATABASE_PATH is set correctly
- Ensure disk is mounted at `/opt/render/project/src/data/`
- Local: SQLite file created in project directory

### QR Code Not Scanning
- Ensure good lighting
- Hold phone steady
- Try manual email lookup as backup
- Check if QR code is blurred in email

### Payment Verification
- Transaction ID is required field
- Check Zelle app for exact transaction ID
- Admin can add notes if partial payment

---

## File Structure

```
party-checkin/
├── app.py                 # Flask application
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment config
├── gunicorn.conf.py      # Production server config
├── run.sh                # Local startup script
├── README.md             # This file
├── templates/            # HTML templates
│   ├── index.html        # Home page
│   ├── register.html     # Registration form
│   ├── scanner.html      # Self check-in
│   ├── admin.html        # Admin dashboard
│   ├── view_qr.html      # QR code display
│   └── pending.html      # Registration success
└── uploads/              # File uploads (if any)
```

---

## Support

For issues or questions:
1. Check this README
2. Review GitHub issues: https://github.com/aladin-genie/party-checkin/issues
3. Contact: [Your Contact Info]

---

## License

MIT License - Feel free to modify and reuse for your events!

---

**Built with ❤️ for Dallas Boyz Party 2025**  
🏏 RCB: Refreshment, Chill, Brotherhood 😊
