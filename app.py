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
import requests
import stripe
import flask

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32).hex()
# Support PostgreSQL (Railway) via DATABASE_URL, or SQLite (Render/local) via DATABASE_PATH
_database_url = os.getenv('DATABASE_URL')
if _database_url:
    # Railway/Heroku inject postgres:// but SQLAlchemy 1.4+ requires postgresql://
    if _database_url.startswith('postgres://'):
        _database_url = _database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = _database_url
else:
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

# Kimi API configuration
KIMI_API_KEY = os.getenv('KIMI_API_KEY', '')
KIMI_API_URL = "https://api.kimi.com/coding/chat/completions"

# Stripe configuration
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
# Price per ticket in cents (e.g., 2000 = $20.00)
TICKET_PRICE_CENTS = int(os.getenv('TICKET_PRICE_CENTS', '2000'))

# Admin password (optional, leave empty for no protection)
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

# Database Models
class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    ticket_count = db.Column(db.Integer, default=1)
    qr_code = db.Column(db.String(200), unique=True)
    checked_in = db.Column(db.Boolean, default=False)
    band_given = db.Column(db.Boolean, default=False)
    checkin_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'ticket_count': self.ticket_count,
            'qr_code': self.qr_code,
            'checked_in': self.checked_in,
            'band_given': self.band_given,
            'checkin_time': self.checkin_time.isoformat() if self.checkin_time else None
        }

class CheckInLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guest.id'))
    action = db.Column(db.String(50))  # 'checkin', 'band_given'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    device_info = db.Column(db.String(200))

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
    """Guest registration form - redirects to Stripe payment"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        ticket_count = int(request.form.get('ticket_count', 1))
        
        if not name or not email:
            flash('Name and email are required!', 'error')
            return redirect(url_for('register'))
        
        # Check if email already registered
        existing = Guest.query.filter_by(email=email).first()
        if existing:
            flash('Email already registered!', 'error')
            return redirect(url_for('register'))
        
        # Store registration data in session for after payment
        import flask
        flask.session['pending_registration'] = {
            'name': name,
            'email': email,
            'ticket_count': ticket_count
        }
        
        # If Stripe is not configured, create guest directly (dev mode)
        if not stripe.api_key:
            return create_guest_and_redirect(name, email, ticket_count)
        
        # Create Stripe Checkout Session
        try:
            checkout_session = stripe.checkout.Session.create(
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'Party 2026 Ticket{"s" if ticket_count > 1 else ""}',
                            'description': f'Admission for {name} - {ticket_count} ticket{"s" if ticket_count > 1 else ""}'
                        },
                        'unit_amount': TICKET_PRICE_CENTS,
                    },
                    'quantity': ticket_count,
                }],
                mode='payment',
                success_url=request.url_root + 'success?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.url_root + 'cancel',
                customer_email=email,
                metadata={
                    'name': name,
                    'email': email,
                    'ticket_count': str(ticket_count)
                }
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            flash(f'Payment setup failed: {str(e)}', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html', stripe_key=STRIPE_PUBLISHABLE_KEY, ticket_price=TICKET_PRICE_CENTS/100)

def create_guest_and_redirect(name, email, ticket_count):
    """Create guest after successful payment"""
    # Generate unique QR code
    qr_code = f"PARTY2026-{datetime.now().strftime('%Y%m%d')}-{base64.urlsafe_b64encode(os.urandom(6)).decode()[:8]}"
    
    guest = Guest(
        name=name,
        email=email,
        ticket_count=ticket_count,
        qr_code=qr_code
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

@app.route('/success')
def success():
    """Handle successful Stripe payment"""
    import flask
    session_id = request.args.get('session_id')
    
    if not session_id:
        flash('Invalid session', 'error')
        return redirect(url_for('index'))
    
    # Retrieve session to verify
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        if checkout_session.payment_status == 'paid':
            metadata = checkout_session.metadata
            name = metadata.get('name')
            email = metadata.get('email')
            ticket_count = int(metadata.get('ticket_count', 1))
            
            # Check if already created (webhook might have done it)
            guest = Guest.query.filter_by(email=email).first()
            if not guest:
                return create_guest_and_redirect(name, email, ticket_count)
            
            flash('Payment successful! Your QR code is ready.', 'success')
            return redirect(url_for('view_qr', guest_id=guest.id))
    except Exception as e:
        flash(f'Error verifying payment: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/cancel')
def cancel():
    """Handle cancelled payment"""
    flash('Payment cancelled. You can try again.', 'warning')
    return redirect(url_for('register'))

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhooks"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400
    
    # Handle successful payment
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        if session.payment_status == 'paid':
            metadata = session.metadata
            name = metadata.get('name')
            email = metadata.get('email')
            ticket_count = int(metadata.get('ticket_count', 1))
            
            # Check if already created
            existing = Guest.query.filter_by(email=email).first()
            if not existing:
                # Generate unique QR code
                qr_code = f"PARTY2026-{datetime.now().strftime('%Y%m%d')}-{base64.urlsafe_b64encode(os.urandom(6)).decode()[:8]}"
                
                guest = Guest(
                    name=name,
                    email=email,
                    ticket_count=ticket_count,
                    qr_code=qr_code
                )
                db.session.add(guest)
                db.session.commit()
                
                # Send email with QR code
                try:
                    send_qr_email(guest)
                except Exception as e:
                    print(f"Failed to send email: {e}")
    
    return '', 200

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

from functools import wraps

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

@app.route('/admin')
@admin_required
def admin():
    """Admin dashboard"""
    guests = Guest.query.order_by(Guest.created_at.desc()).all()
    recent_checkins = Guest.query.filter_by(checked_in=True).order_by(Guest.checkin_time.desc()).limit(10).all()
    
    stats = {
        'total': len(guests),
        'checked_in': sum(1 for g in guests if g.checked_in),
        'bands_given': sum(1 for g in guests if g.band_given),
        'pending': sum(1 for g in guests if not g.checked_in),
        'total_tickets': sum(g.ticket_count for g in guests),
        'tickets_admitted': sum(g.ticket_count for g in guests if g.checked_in)
    }
    
    return render_template('admin.html', guests=guests, recent_checkins=recent_checkins, stats=stats)

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

@app.route('/api/give-band', methods=['POST'])
def api_give_band():
    """Mark band as given"""
    data = request.get_json()
    guest_id = data.get('guest_id')
    
    guest = Guest.query.get(guest_id)
    if not guest:
        return jsonify({'success': False, 'error': 'Guest not found'}), 404
    
    guest.band_given = True
    
    log = CheckInLog(guest_id=guest.id, action='band_given', device_info=request.user_agent.string[:200])
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Band marked as given for {guest.name}'
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
    
    return jsonify({
        'total_guests': total,
        'checked_in': checked_in,
        'bands_distributed': bands,
        'pending': total - checked_in,
        'total_tickets': tickets,
        'admitted_tickets': admitted_tickets
    })

@app.route('/download/csv')
def download_csv():
    """Download guest list as CSV"""
    guests = Guest.query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Tickets', 'Checked In', 'Band Given', 'Check-in Time'])
    
    for g in guests:
        writer.writerow([
            g.name, g.email, g.ticket_count,
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
