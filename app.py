"""
Party Check-In System with QR Codes and Audio Announcements
Supports 200+ guests, self check-in, wristband tracking
"""

from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import qrcode
import io
import os
import csv
import json
from datetime import datetime, timedelta
from functools import wraps
from PIL import Image, ImageDraw, ImageFont
import base64
import flask

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32).hex()
# Use DATABASE_PATH env var for Render disk, fallback to local
db_path = os.getenv('DATABASE_PATH', 'party_guests.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

# Email configuration (update with your SMTP settings)
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'party@example.com')

db = SQLAlchemy(app)
mail = Mail(app)

# Admin password (optional, leave empty for no protection)
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

# Database Models
class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Name fields
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # Combined first + last
    
    # Contact
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    
    # Attendance
    num_attendees = db.Column(db.Integer, default=1)
    attendee_names = db.Column(db.Text)  # JSON array of names
    ticket_count = db.Column(db.Integer, default=1)  # Alias for num_attendees
    
    # Food preferences
    veg_count = db.Column(db.Integer, default=0)
    nonveg_count = db.Column(db.Integer, default=0)
    
    # Volunteer
    volunteer = db.Column(db.String(10))  # 'yes' or 'no'
    
    # Payment
    payment_method = db.Column(db.String(20), default='zelle')  # zelle only for this event
    transaction_id = db.Column(db.String(100), nullable=False)
    total_amount = db.Column(db.String(20))
    
    # QR Code & Check-in
    qr_code = db.Column(db.String(200), unique=True)
    checked_in = db.Column(db.Boolean, default=False)
    band_given = db.Column(db.Boolean, default=False)
    bands_given_count = db.Column(db.Integer, default=0)  # For partial band collection
    checkin_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Approval workflow
    approved = db.Column(db.Boolean, default=False)
    approved_at = db.Column(db.DateTime)
    disclaimer_agreed = db.Column(db.Boolean, default=False)
    signature_name = db.Column(db.String(100))
    
    # Payment verification (for admin manual tracking)
    payment_verified = db.Column(db.Boolean, default=False)
    payment_verified_at = db.Column(db.DateTime)
    payment_verified_by = db.Column(db.String(100))
    payment_notes = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'num_attendees': self.num_attendees,
            'attendee_names': self.attendee_names,
            'veg_count': self.veg_count,
            'nonveg_count': self.nonveg_count,
            'volunteer': self.volunteer,
            'payment_method': self.payment_method,
            'transaction_id': self.transaction_id,
            'total_amount': self.total_amount,
            'qr_code': self.qr_code,
            'checked_in': self.checked_in,
            'band_given': self.band_given,
            'bands_given_count': self.bands_given_count or 0,
            'checkin_time': self.checkin_time.isoformat() if self.checkin_time else None,
            'approved': self.approved,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'payment_verified': self.payment_verified,
            'payment_verified_at': self.payment_verified_at.isoformat() if self.payment_verified_at else None,
            'payment_verified_by': self.payment_verified_by,
            'payment_notes': self.payment_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CheckInLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guest.id'))
    action = db.Column(db.String(50))  # 'checkin', 'band_given'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    device_info = db.Column(db.String(200))

def admin_required(f):
    """Decorator for admin password protection"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if ADMIN_PASSWORD:
            auth = request.authorization
            if not auth or auth.password != ADMIN_PASSWORD:
                return ('Admin Access Required', 401, {
                    'WWW-Authenticate': 'Basic realm="Admin"'
                })
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    """Home page with navigation"""
    stats = {
        'total_guests': Guest.query.count(),
        'checked_in': Guest.query.filter_by(checked_in=True).count(),
        'bands_distributed': Guest.query.filter_by(band_given=True).count(),
        'total_tickets': db.session.query(db.func.sum(Guest.ticket_count)).scalar() or 0
    }
    return render_template('index.html', stats=stats)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Guest registration with manual payment verification"""
    if request.method == 'POST':
        # Get form data
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        num_attendees = int(request.form.get('num_attendees', 1))
        attendee_names = request.form.get('attendee_names', '').strip()
        transaction_id = request.form.get('transaction_id', '').strip()
        veg_count = int(request.form.get('veg_count', 0))
        nonveg_count = int(request.form.get('nonveg_count', 0))
        volunteer = request.form.get('volunteer', 'no')
        signature_name = request.form.get('signature_name', '').strip()
        total_amount = request.form.get('total_amount', '$35.00')
        
        # Validation
        if not first_name or not last_name or not email or not phone:
            flash('First name, last name, email, and phone are required!', 'error')
            return redirect(url_for('register'))
        
        if not transaction_id:
            flash('Zelle Transaction ID is required!', 'error')
            return redirect(url_for('register'))
        
        # Check food counts
        if veg_count + nonveg_count != num_attendees:
            flash('Vegetarian + Non-vegetarian count must equal number of attendees!', 'error')
            return redirect(url_for('register'))
        
        # Check if email already registered
        existing = Guest.query.filter_by(email=email).first()
        if existing:
            flash('Email already registered!', 'error')
            return redirect(url_for('register'))
        
        name = f"{first_name} {last_name}"
        
        # Generate QR code immediately
        qr_code = f"DBZ2025-{datetime.now().strftime('%m%d')}-{base64.urlsafe_b64encode(os.urandom(6)).decode()[:8].upper()}"
        
        # Create guest with immediate approval (QR sent now)
        guest = Guest(
            first_name=first_name,
            last_name=last_name,
            name=name,
            email=email,
            phone=phone,
            num_attendees=num_attendees,
            ticket_count=num_attendees,
            attendee_names=attendee_names,
            veg_count=veg_count,
            nonveg_count=nonveg_count,
            volunteer=volunteer,
            payment_method='zelle',
            transaction_id=transaction_id,
            total_amount=total_amount,
            qr_code=qr_code,
            approved=True,  # Auto-approved, QR sent immediately
            approved_at=datetime.utcnow(),
            disclaimer_agreed=True,
            signature_name=signature_name,
            payment_verified=False,  # Admin will verify later
            payment_notes=f"Transaction ID: {transaction_id}"
        )
        db.session.add(guest)
        db.session.commit()
        
        # Send QR code email immediately
        try:
            send_qr_email(guest)
            flash(f'✅ Registration successful! QR code sent to {email}. Please check your inbox and bring the QR code to the event.', 'success')
        except Exception as e:
            flash(f'⚠️ Registration saved but email failed. Please contact support. Error: {str(e)}', 'warning')
        
        return redirect(url_for('view_qr', code=qr_code))
    
    return render_template('register.html')

@app.route('/pending')
def pending():
    """Show pending approval message"""
    return render_template('pending.html')

@app.route('/admin/approve/<int:guest_id>', methods=['POST'])
@admin_required
def approve_guest(guest_id):
    """Approve a pending guest and send QR code"""
    guest = Guest.query.get_or_404(guest_id)
    
    if guest.approved:
        return jsonify({'success': False, 'error': 'Already approved'}), 400
    
    # Generate QR code
    guest.qr_code = f"PARTY2026-{datetime.now().strftime('%Y%m%d')}-{base64.urlsafe_b64encode(os.urandom(6)).decode()[:8]}"
    guest.approved = True
    guest.approved_at = datetime.utcnow()
    db.session.commit()
    
    # Send email with QR code
    try:
        send_qr_email(guest)
        return jsonify({
            'success': True,
            'message': f'Approved {guest.name}! QR code sent to {guest.email}'
        })
    except Exception as e:
        return jsonify({
            'success': True,
            'warning': f'Approved but email failed: {str(e)}'
        })

def create_guest_and_redirect(name, email, ticket_count):
    """Create guest directly (for dev/testing)"""
    # Generate unique QR code
    qr_code = f"PARTY2026-{datetime.now().strftime('%Y%m%d')}-{base64.urlsafe_b64encode(os.urandom(6)).decode()[:8]}"
    
    guest = Guest(
        name=name,
        email=email,
        ticket_count=ticket_count,
        qr_code=qr_code,
        approved=True,
        approved_at=datetime.utcnow()
    )
    db.session.add(guest)
    db.session.commit()
    
    # Generate and send QR code via email
    try:
        send_qr_email(guest)
        flash(f'Registration successful! QR code sent to {email}', 'success')
    except Exception as e:
        flash(f'Registered but email failed: {str(e)}', 'warning')
    
    return redirect(url_for('view_qr', guest_id=guest.id))

@app.route('/qr/<int:guest_id>')
def view_qr(guest_id):
    """View QR code on screen"""
    guest = Guest.query.get_or_404(guest_id)
    qr_image = generate_qr_image(guest.qr_code, guest.name)
    qr_base64 = base64.b64encode(qr_image).decode()
    return render_template('view_qr.html', guest=guest, qr_image=qr_base64)

@app.route('/scanner')
def scanner():
    """Self check-in scanner page"""
    return render_template('scanner.html')

@app.route('/admin')
@admin_required
def admin():
    """Admin dashboard"""
    all_guests = Guest.query.order_by(Guest.created_at.desc()).all()
    pending_guests = Guest.query.filter_by(approved=False).order_by(Guest.created_at.desc()).all()
    approved_guests = Guest.query.filter_by(approved=True).order_by(Guest.created_at.desc()).all()
    recent_checkins = Guest.query.filter_by(checked_in=True).order_by(Guest.checkin_time.desc()).limit(10).all()
    
    stats = {
        'total': len(all_guests),
        'checked_in': sum(1 for g in all_guests if g.checked_in),
        'bands_given': sum(1 for g in all_guests if g.band_given),
        'pending': sum(1 for g in all_guests if not g.checked_in),
        'pending_approval': len(pending_guests),
        'total_tickets': sum(g.ticket_count for g in all_guests),
        'tickets_admitted': sum(g.ticket_count for g in all_guests if g.checked_in),
        'total_revenue': sum(g.ticket_count * 35 for g in all_guests if g.approved),
        'payment_verified': sum(1 for g in all_guests if g.payment_verified),
        'payment_unverified': sum(1 for g in all_guests if not g.payment_verified)
    }
    
    return render_template('admin.html', 
                         all_guests=all_guests,
                         pending_guests=pending_guests,
                         approved_guests=approved_guests,
                         recent_checkins=recent_checkins,
                         stats=stats)

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    """API endpoint for check-in"""
    data = request.get_json()
    qr_code = data.get('qr_code', '').strip()
    
    if not qr_code:
        return jsonify({'success': False, 'error': 'QR code required'}), 400
    
    guest = Guest.query.filter_by(qr_code=qr_code).first()
    
    if not guest:
        return jsonify({'success': False, 'error': 'Invalid QR code'}), 404
    
    if guest.checked_in:
        return jsonify({
            'success': True,
            'already_checked_in': True,
            'guest': guest.to_dict(),
            'message': f'{guest.name} already checked in at {guest.checkin_time.strftime("%H:%M")}'
        })
    
    # Perform check-in
    guest.checked_in = True
    guest.checkin_time = datetime.utcnow()
    
    # Log the action
    log = CheckInLog(guest_id=guest.id, action='checkin', device_info=request.user_agent.string[:200])
    db.session.add(log)
    db.session.commit()
    
    # Generate welcome announcement text
    announcement = generate_welcome_announcement(guest.name, guest.ticket_count)
    
    return jsonify({
        'success': True,
        'already_checked_in': False,
        'guest': guest.to_dict(),
        'announcement': announcement,
        'message': f'Welcome {guest.name}!'
    })

@app.route('/api/lookup-by-email', methods=['POST'])
def api_lookup_by_email():
    """Look up guest by email for manual check-in"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'success': False, 'error': 'Email required'}), 400
    
    guest = Guest.query.filter_by(email=email).first()
    
    if not guest:
        return jsonify({'success': False, 'error': 'Email not found'}), 404
    
    if not guest.approved:
        return jsonify({'success': False, 'error': 'Registration not approved yet'}), 403
    
    # Return guest info for check-in
    return jsonify({
        'success': True,
        'guest': guest.to_dict(),
        'already_checked_in': guest.checked_in,
        'message': f'Found {guest.name}'
    })

@app.route('/api/give-bands', methods=['POST'])
def api_give_bands():
    """Give partial or full bands to guest"""
    data = request.get_json()
    guest_id = data.get('guest_id')
    bands_count = data.get('bands_count', 1)
    
    guest = Guest.query.get(guest_id)
    if not guest:
        return jsonify({'success': False, 'error': 'Guest not found'}), 404
    
    # Calculate how many bands they already have
    current_bands = getattr(guest, 'bands_given_count', 0) or 0
    total_tickets = guest.ticket_count or guest.num_attendees or 1
    
    # Validate
    if current_bands + bands_count > total_tickets:
        return jsonify({
            'success': False, 
            'error': f'Cannot give {bands_count} more bands. Total tickets: {total_tickets}, already given: {current_bands}'
        }), 400
    
    # Update band count
    guest.bands_given_count = current_bands + bands_count
    
    # Mark as checked in if not already
    if not guest.checked_in:
        guest.checked_in = True
        guest.checkin_time = datetime.utcnow()
    
    # Mark band_given if all bands are given
    if guest.bands_given_count >= total_tickets:
        guest.band_given = True
    else:
        guest.band_given = False  # Partial
    
    log = CheckInLog(
        guest_id=guest.id, 
        action=f'band_given_{bands_count}', 
        device_info=request.user_agent.string[:200]
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Gave {bands_count} band{"s" if bands_count > 1 else ""} to {guest.name}',
        'bands_given': guest.bands_given_count,
        'total_bands': total_tickets,
        'remaining': total_tickets - guest.bands_given_count
    })

@app.route('/api/guests')
def api_guests():
    """Get all guests (for admin)"""
    guests = Guest.query.all()
    return jsonify([g.to_dict() for g in guests])

@app.route('/api/stats')
def api_stats():
    """Get current statistics"""
    total = Guest.query.count()
    checked_in = Guest.query.filter_by(checked_in=True).count()
    bands = Guest.query.filter_by(band_given=True).count()
    tickets = db.session.query(db.func.sum(Guest.ticket_count)).scalar() or 0
    admitted_tickets = db.session.query(db.func.sum(Guest.ticket_count)).filter(Guest.checked_in==True).scalar() or 0
    
    pending_approval = Guest.query.filter_by(approved=False).count()
    total_revenue = sum(g.ticket_count * 30 for g in Guest.query.filter_by(approved=True).all())
    
    return jsonify({
        'total_guests': total,
        'checked_in': checked_in,
        'bands_distributed': bands,
        'pending': total - checked_in,
        'pending_approval': pending_approval,
        'total_tickets': tickets,
        'admitted_tickets': admitted_tickets,
        'total_revenue': total_revenue
    })

@app.route('/download/csv')
def download_csv():
    """Download guest list as CSV"""
    guests = Guest.query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Tickets', 'Payment', 'Transaction ID', 'Approved', 'Checked In', 'Band Given', 'Check-in Time'])
    
    for g in guests:
        writer.writerow([
            g.name, g.email, g.ticket_count,
            g.payment_method or '',
            g.transaction_id or '',
            'Yes' if g.approved else 'No',
            'Yes' if g.checked_in else 'No',
            'Yes' if g.band_given else 'No',
            g.checkin_time.strftime('%Y-%m-%d %H:%M:%S') if g.checkin_time else ''
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'party_guests_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@app.route('/admin/resend-qr/<int:guest_id>', methods=['POST'])
@admin_required
def resend_qr(guest_id):
    """Resend QR code email to guest"""
    guest = Guest.query.get_or_404(guest_id)
    
    if not guest.qr_code:
        return jsonify({'success': False, 'error': 'No QR code exists for this guest'}), 400
    
    if guest.band_given:
        return jsonify({'success': False, 'error': 'Bands already collected - cannot resend'}), 400
    
    try:
        send_qr_email(guest)
        return jsonify({
            'success': True,
            'message': f'QR code resent to {guest.email}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to send email: {str(e)}'
        }), 500

@app.route('/admin/verify-payment/<int:guest_id>', methods=['POST'])
@admin_required
def verify_payment(guest_id):
    """Manually verify a payment (for admin tracking)"""
    guest = Guest.query.get_or_404(guest_id)
    
    data = request.get_json()
    verified = data.get('verified', True)
    notes = data.get('notes', '')
    
    if verified:
        guest.payment_verified = True
        guest.payment_verified_at = datetime.utcnow()
        guest.payment_verified_by = request.authorization.username if request.authorization else 'admin'
        if notes:
            guest.payment_notes = f"{guest.payment_notes or ''}\nVerified: {notes}".strip()
    else:
        guest.payment_verified = False
        guest.payment_verified_at = None
        guest.payment_verified_by = None
        if notes:
            guest.payment_notes = f"{guest.payment_notes or ''}\nUnverified: {notes}".strip()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'guest_id': guest_id,
        'payment_verified': guest.payment_verified,
        'message': f'Payment for {guest.name} marked as {"verified" if verified else "unverified"}'
    })

# Helper Functions
def generate_qr_image(qr_data, guest_name):
    """Generate QR code image"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to RGB mode for compatibility
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Add text below QR code
    # Try to use a nice font, fallback to default
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except:
        font = ImageFont.load_default()
    
    # Create new image with space for text
    width, height = img.size
    new_img = Image.new('RGB', (width, height + 60), 'white')
    new_img.paste(img, (0, 0))
    
    draw = ImageDraw.Draw(new_img)
    text = f"Party 2026 - {guest_name}"
    
    # Center text
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (width - text_width) // 2
    
    draw.text((x, height + 15), text, fill='black', font=font)
    
    # Save to bytes
    img_io = io.BytesIO()
    new_img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return img_io.getvalue()

def send_qr_email(guest):
    """Send QR code via email"""
    if not app.config['MAIL_USERNAME']:
        print("Email not configured, skipping send")
        return
    
    qr_image = generate_qr_image(guest.qr_code, guest.name)
    
    msg = Message(
        subject='🎉 Your Party 2026 QR Code!',
        recipients=[guest.email],
        body=f"""Hi {guest.name}!

You're registered for Party 2026!

📅 Date: [Add your party date]
📍 Location: [Add your party location]
🎫 Tickets: {guest.ticket_count}

Your QR code is attached. Please show this at the entrance for check-in.

See you there!
"""
    )
    
    # Attach QR code
    msg.attach('party_qr.png', 'image/png', qr_image)
    
    mail.send(msg)

def generate_welcome_announcement(name, ticket_count):
    """Generate welcome announcement text using Kimi or fallback"""
    
    # Simple fallback without API call
    if ticket_count == 1:
        return f"Welcome {name}! You have 1 ticket. Enjoy the party!"
    else:
        return f"Welcome {name}! You have {ticket_count} tickets. Enjoy the party!"

@app.route('/reports/registration')
def registration_report():
    """Show daily registration counts leading up to the event"""
    from sqlalchemy import func
    
    # Event date: September 19, 2025
    event_date = datetime(2025, 9, 19)
    
    # Get all guests ordered by creation date
    guests = Guest.query.order_by(Guest.created_at).all()
    
    if not guests:
        return render_template('registration_report.html', 
                             daily_stats=[],
                             total_guests=0,
                             total_tickets=0,
                             event_date=event_date,
                             days_until_event=(event_date - datetime.utcnow()).days)
    
    # Build daily registration stats
    from collections import defaultdict
    daily_registrations = defaultdict(lambda: {'count': 0, 'tickets': 0, 'attendees': []})
    
    for guest in guests:
        date_key = guest.created_at.date()
        daily_registrations[date_key]['count'] += 1
        daily_registrations[date_key]['tickets'] += guest.ticket_count or guest.num_attendees or 1
        daily_registrations[date_key]['attendees'].append({
            'name': guest.name,
            'tickets': guest.ticket_count or guest.num_attendees or 1
        })
    
    # Build complete timeline from first registration to event date
    first_date = min(daily_registrations.keys())
    current_date = first_date
    end_date = event_date.date()
    
    daily_stats = []
    running_total_guests = 0
    running_total_tickets = 0
    
    while current_date <= end_date:
        day_data = daily_registrations.get(current_date, {'count': 0, 'tickets': 0, 'attendees': []})
        running_total_guests += day_data['count']
        running_total_tickets += day_data['tickets']
        
        daily_stats.append({
            'date': current_date,
            'date_str': current_date.strftime('%A, %B %d, %Y'),
            'new_registrations': day_data['count'],
            'new_tickets': day_data['tickets'],
            'cumulative_guests': running_total_guests,
            'cumulative_tickets': running_total_tickets,
            'attendees': day_data['attendees'],
            'is_event_day': current_date == end_date
        })
        
        current_date += timedelta(days=1)
    
    return render_template('registration_report.html',
                         daily_stats=daily_stats,
                         total_guests=running_total_guests,
                         total_tickets=running_total_tickets,
                         event_date=event_date,
                         days_until_event=(event_date - datetime.utcnow()).days)

@app.route('/api/reports/daily')
def api_daily_registrations():
    """API endpoint for daily registration data"""
    from sqlalchemy import func
    
    # Get date range from query params or default to all
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    query = db.session.query(
        func.date(Guest.created_at).label('date'),
        func.count(Guest.id).label('registrations'),
        func.sum(Guest.ticket_count).label('tickets')
    ).group_by(func.date(Guest.created_at))
    
    if start_date:
        query = query.filter(func.date(Guest.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(Guest.created_at) <= end_date)
    
    results = query.order_by(func.date(Guest.created_at)).all()
    
    data = [{
        'date': r.date.isoformat(),
        'registrations': r.registrations,
        'tickets': int(r.tickets) if r.tickets else 0
    } for r in results]
    
    return jsonify(data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
