"""
Generic Event Check-In Platform
Multi-event support with QR codes, Zelle payment tracking, and 6 themes.
"""

import os
import io
import csv
import re
import base64
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, jsonify, send_file,
                   flash, redirect, url_for, session)
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32).hex()

# Database: PostgreSQL via DATABASE_URL, or SQLite locally
_database_url = os.getenv('DATABASE_URL')
if _database_url:
    if _database_url.startswith('postgres://'):
        _database_url = _database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = _database_url
else:
    db_path = os.getenv('DATABASE_PATH', 'checkin.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@example.com')

db = SQLAlchemy(app)
mail = Mail(app)

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

THEMES = {
    'party':     {'primary': '#667eea', 'secondary': '#764ba2', 'label': 'Party (Purple)'},
    'corporate': {'primary': '#1a73e8', 'secondary': '#0d47a1', 'label': 'Corporate (Blue)'},
    'casual':    {'primary': '#e91e8c', 'secondary': '#c2185b', 'label': 'Casual (Pink)'},
    'garden':    {'primary': '#2e7d32', 'secondary': '#1b5e20', 'label': 'Garden (Green)'},
    'gala':      {'primary': '#f9a825', 'secondary': '#e65100', 'label': 'Gala (Gold)'},
    'ocean':     {'primary': '#0288d1', 'secondary': '#006064', 'label': 'Ocean (Teal)'},
}


# ─── Models ───────────────────────────────────────────────────────────────────

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.DateTime)
    location = db.Column(db.String(200))
    theme = db.Column(db.String(50), default='party')
    ticket_price = db.Column(db.Numeric(10, 2), default=0)
    zelle_recipient = db.Column(db.String(200))
    zelle_instructions = db.Column(db.Text)
    admin_username = db.Column(db.String(100), nullable=False)
    admin_password_hash = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    max_tickets_per_person = db.Column(db.Integer, default=4)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    guests = db.relationship('Guest', backref='event', lazy=True,
                             cascade='all, delete-orphan')

    @property
    def theme_colors(self):
        return THEMES.get(self.theme, THEMES['party'])

    def guest_stats(self):
        guests = self.guests
        total = len(guests)
        checked_in = sum(1 for g in guests if g.checked_in)
        bands_given = sum(1 for g in guests if g.band_given)
        total_tickets = sum(g.ticket_count for g in guests)
        admitted_tickets = sum(g.ticket_count for g in guests if g.checked_in)
        return {
            'total': total,
            'checked_in': checked_in,
            'bands_given': bands_given,
            'pending': total - checked_in,
            'total_tickets': total_tickets,
            'admitted_tickets': admitted_tickets,
        }


class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'),
                         nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    ticket_count = db.Column(db.Integer, default=1)
    zelle_reference = db.Column(db.String(200))
    qr_code = db.Column(db.String(200), unique=True)
    checked_in = db.Column(db.Boolean, default=False)
    band_given = db.Column(db.Boolean, default=False)
    checkin_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('event_id', 'email', name='unique_event_email'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'name': self.name,
            'email': self.email,
            'ticket_count': self.ticket_count,
            'zelle_reference': self.zelle_reference,
            'qr_code': self.qr_code,
            'checked_in': self.checked_in,
            'band_given': self.band_given,
            'checkin_time': self.checkin_time.isoformat() if self.checkin_time else None,
        }


class CheckInLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guest.id'), nullable=False)
    action = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    device_info = db.Column(db.String(200))


# ─── Auth decorators ──────────────────────────────────────────────────────────

def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('super_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def event_admin_required(f):
    """Loads the event from slug and injects it as kwarg 'event'.
    Allows access for super admin OR the event's own admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        slug = kwargs.get('slug')
        event = Event.query.filter_by(slug=slug).first_or_404()
        if session.get('super_admin') or session.get('event_admin_for') == event.id:
            kwargs['event'] = event
            return f(*args, **kwargs)
        return redirect(url_for('event_admin_login', slug=slug))
    return decorated


# ─── Database init ────────────────────────────────────────────────────────────

@app.before_request
def create_tables():
    db.create_all()
    app.before_request_funcs[None].remove(create_tables)


# ─── Platform home ────────────────────────────────────────────────────────────

@app.route('/')
def home():
    events = Event.query.filter_by(is_active=True).order_by(Event.event_date).all()
    return render_template('home.html', events=events, themes=THEMES)


# ─── Public event routes ──────────────────────────────────────────────────────

@app.route('/e/<slug>/')
def event_landing(slug):
    event = Event.query.filter_by(slug=slug).first_or_404()
    return render_template('event/landing.html', event=event,
                           theme=event.theme_colors,
                           stats=event.guest_stats())


@app.route('/e/<slug>/register', methods=['GET', 'POST'])
def event_register(slug):
    event = Event.query.filter_by(slug=slug).first_or_404()
    theme = event.theme_colors

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        ticket_count = int(request.form.get('ticket_count', 1))
        zelle_reference = request.form.get('zelle_reference', '').strip()

        if not name or not email:
            flash('Name and email are required.', 'error')
            return render_template('event/register.html', event=event, theme=theme)

        if ticket_count < 1 or ticket_count > event.max_tickets_per_person:
            flash(f'Please select 1 to {event.max_tickets_per_person} tickets.', 'error')
            return render_template('event/register.html', event=event, theme=theme)

        if float(event.ticket_price or 0) > 0 and not zelle_reference:
            flash('Please enter your Zelle transaction reference number.', 'error')
            return render_template('event/register.html', event=event, theme=theme)

        existing = Guest.query.filter_by(event_id=event.id, email=email).first()
        if existing:
            flash('This email is already registered for this event.', 'error')
            return render_template('event/register.html', event=event, theme=theme)

        qr_token = (
            f"EVT{event.id}-{datetime.now().strftime('%Y%m%d')}"
            f"-{base64.urlsafe_b64encode(os.urandom(6)).decode()[:8]}"
        )
        guest = Guest(
            event_id=event.id,
            name=name,
            email=email,
            ticket_count=ticket_count,
            zelle_reference=zelle_reference or None,
            qr_code=qr_token,
        )
        db.session.add(guest)
        db.session.commit()

        try:
            send_qr_email(guest, event)
            flash(f'Registration successful! QR code sent to {email}', 'success')
        except Exception as e:
            flash(f'Registered! (Email delivery skipped: {e})', 'warning')

        return redirect(url_for('event_view_qr', slug=slug, guest_id=guest.id))

    return render_template('event/register.html', event=event, theme=theme)


@app.route('/e/<slug>/qr/<int:guest_id>')
def event_view_qr(slug, guest_id):
    event = Event.query.filter_by(slug=slug).first_or_404()
    guest = Guest.query.filter_by(id=guest_id, event_id=event.id).first_or_404()
    qr_image = generate_qr_image(guest.qr_code, guest.name, event.name)
    qr_base64 = base64.b64encode(qr_image).decode()
    return render_template('event/qr.html', event=event, guest=guest,
                           qr_image=qr_base64, theme=event.theme_colors)


@app.route('/e/<slug>/scanner')
def event_scanner(slug):
    event = Event.query.filter_by(slug=slug).first_or_404()
    return render_template('event/scanner.html', event=event, theme=event.theme_colors)


# ─── Scanner API ──────────────────────────────────────────────────────────────

@app.route('/api/e/<slug>/checkin', methods=['POST'])
def api_checkin(slug):
    event = Event.query.filter_by(slug=slug).first_or_404()
    data = request.get_json() or {}
    qr_code = data.get('qr_code', '').strip()

    if not qr_code:
        return jsonify({'success': False, 'error': 'QR code required'}), 400

    guest = Guest.query.filter_by(qr_code=qr_code, event_id=event.id).first()
    if not guest:
        return jsonify({'success': False, 'error': 'Invalid QR code for this event'}), 404

    if guest.checked_in:
        return jsonify({
            'success': True,
            'already_checked_in': True,
            'guest': guest.to_dict(),
            'message': f'{guest.name} already checked in at {guest.checkin_time.strftime("%H:%M")}',
        })

    guest.checked_in = True
    guest.checkin_time = datetime.utcnow()
    db.session.add(CheckInLog(guest_id=guest.id, action='checkin',
                              device_info=request.user_agent.string[:200]))
    db.session.commit()

    tickets = guest.ticket_count
    return jsonify({
        'success': True,
        'already_checked_in': False,
        'guest': guest.to_dict(),
        'message': f'Welcome {guest.name}! {tickets} ticket{"s" if tickets > 1 else ""}',
    })


@app.route('/api/e/<slug>/give-band', methods=['POST'])
def api_give_band(slug):
    event = Event.query.filter_by(slug=slug).first_or_404()
    data = request.get_json() or {}
    guest = Guest.query.filter_by(id=data.get('guest_id'), event_id=event.id).first()
    if not guest:
        return jsonify({'success': False, 'error': 'Guest not found'}), 404

    guest.band_given = True
    db.session.add(CheckInLog(guest_id=guest.id, action='band_given',
                              device_info=request.user_agent.string[:200]))
    db.session.commit()
    return jsonify({'success': True, 'message': f'Band given to {guest.name}'})


@app.route('/api/e/<slug>/stats')
def api_stats(slug):
    event = Event.query.filter_by(slug=slug).first_or_404()
    return jsonify(event.guest_stats())


# ─── Super admin ──────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if not ADMIN_PASSWORD:
            flash('Set the ADMIN_PASSWORD environment variable to enable super admin access.', 'warning')
        elif password == ADMIN_PASSWORD:
            session['super_admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Incorrect password.', 'error')
    return render_template('super_admin/login.html')


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('super_admin', None)
    return redirect(url_for('home'))


@app.route('/admin/')
@super_admin_required
def admin_dashboard():
    events = Event.query.order_by(Event.created_at.desc()).all()
    return render_template('super_admin/dashboard.html', events=events, themes=THEMES)


@app.route('/admin/events/new', methods=['GET', 'POST'])
@super_admin_required
def admin_event_new():
    if request.method == 'POST':
        return _save_event(None)
    return render_template('super_admin/event_form.html', event=None,
                           themes=THEMES, is_edit=False)


@app.route('/admin/events/<int:event_id>/edit', methods=['GET', 'POST'])
@super_admin_required
def admin_event_edit(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        return _save_event(event)
    return render_template('super_admin/event_form.html', event=event,
                           themes=THEMES, is_edit=True)


@app.route('/admin/events/<int:event_id>/delete', methods=['POST'])
@super_admin_required
def admin_event_delete(event_id):
    event = Event.query.get_or_404(event_id)
    name = event.name
    db.session.delete(event)
    db.session.commit()
    flash(f'Event "{name}" and all its guests have been deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/events/<int:event_id>/guests')
@super_admin_required
def admin_event_guests(event_id):
    event = Event.query.get_or_404(event_id)
    guests, q, status = _filter_guests(event.id)
    return render_template('super_admin/event_guests.html', event=event,
                           guests=guests, stats=event.guest_stats(),
                           q=q, status=status, themes=THEMES)


@app.route('/admin/events/<int:event_id>/export')
@super_admin_required
def admin_event_export(event_id):
    event = Event.query.get_or_404(event_id)
    return _export_csv(event)


# ─── Event admin ──────────────────────────────────────────────────────────────

@app.route('/e/<slug>/admin/login', methods=['GET', 'POST'])
def event_admin_login(slug):
    event = Event.query.filter_by(slug=slug).first_or_404()
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if (username == event.admin_username and
                check_password_hash(event.admin_password_hash, password)):
            session['event_admin_for'] = event.id
            return redirect(url_for('event_admin_dashboard', slug=slug))
        flash('Invalid username or password.', 'error')
    return render_template('event/admin/login.html', event=event,
                           theme=event.theme_colors)


@app.route('/e/<slug>/admin/logout', methods=['POST'])
def event_admin_logout(slug):
    session.pop('event_admin_for', None)
    return redirect(url_for('event_landing', slug=slug))


@app.route('/e/<slug>/admin/')
@event_admin_required
def event_admin_dashboard(slug, event=None):
    guests, q, status = _filter_guests(event.id)
    recent = (Guest.query.filter_by(event_id=event.id, checked_in=True)
              .order_by(Guest.checkin_time.desc()).limit(10).all())
    return render_template('event/admin/dashboard.html', event=event,
                           guests=guests, recent_checkins=recent,
                           stats=event.guest_stats(), q=q, status=status,
                           theme=event.theme_colors)


@app.route('/e/<slug>/admin/export')
@event_admin_required
def event_admin_export(slug, event=None):
    return _export_csv(event)


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _filter_guests(event_id):
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    query = Guest.query.filter_by(event_id=event_id)
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(
            Guest.name.ilike(like),
            Guest.email.ilike(like),
            Guest.zelle_reference.ilike(like),
        ))
    if status == 'checked_in':
        query = query.filter_by(checked_in=True)
    elif status == 'pending':
        query = query.filter_by(checked_in=False)
    elif status == 'band_given':
        query = query.filter_by(band_given=True)
    return query.order_by(Guest.created_at.desc()).all(), q, status


def _save_event(event):
    """Create or update an event from POST form data."""
    name = request.form.get('name', '').strip()
    slug = request.form.get('slug', '').strip().lower()
    description = request.form.get('description', '').strip()
    event_date_str = request.form.get('event_date', '').strip()
    location = request.form.get('location', '').strip()
    theme = request.form.get('theme', 'party')
    ticket_price = float(request.form.get('ticket_price', 0) or 0)
    zelle_recipient = request.form.get('zelle_recipient', '').strip()
    zelle_instructions = request.form.get('zelle_instructions', '').strip()
    admin_username = request.form.get('admin_username', '').strip()
    admin_password = request.form.get('admin_password', '').strip()
    max_tickets = int(request.form.get('max_tickets_per_person', 4) or 4)
    is_active = request.form.get('is_active') == 'on'
    is_edit = event is not None

    if not name or not slug or not admin_username:
        flash('Name, slug, and admin username are required.', 'error')
        return render_template('super_admin/event_form.html', event=event,
                               themes=THEMES, is_edit=is_edit)

    if not re.match(r'^[a-z0-9-]+$', slug):
        flash('Slug may only contain lowercase letters, numbers, and hyphens.', 'error')
        return render_template('super_admin/event_form.html', event=event,
                               themes=THEMES, is_edit=is_edit)

    conflict = Event.query.filter(
        Event.slug == slug,
        Event.id != (event.id if event else -1)
    ).first()
    if conflict:
        flash('That URL slug is already taken. Choose a different one.', 'error')
        return render_template('super_admin/event_form.html', event=event,
                               themes=THEMES, is_edit=is_edit)

    event_date = None
    if event_date_str:
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d'):
            try:
                event_date = datetime.strptime(event_date_str, fmt)
                break
            except ValueError:
                continue

    if not is_edit:
        if not admin_password:
            flash('Admin password is required when creating a new event.', 'error')
            return render_template('super_admin/event_form.html', event=None,
                                   themes=THEMES, is_edit=False)
        event = Event(
            name=name, slug=slug, description=description,
            event_date=event_date, location=location, theme=theme,
            ticket_price=ticket_price, zelle_recipient=zelle_recipient,
            zelle_instructions=zelle_instructions,
            admin_username=admin_username,
            admin_password_hash=generate_password_hash(admin_password),
            max_tickets_per_person=max_tickets, is_active=is_active,
        )
        db.session.add(event)
        db.session.commit()
        flash(f'Event "{name}" created successfully.', 'success')
    else:
        event.name = name
        event.slug = slug
        event.description = description
        event.event_date = event_date
        event.location = location
        event.theme = theme
        event.ticket_price = ticket_price
        event.zelle_recipient = zelle_recipient
        event.zelle_instructions = zelle_instructions
        event.admin_username = admin_username
        if admin_password:
            event.admin_password_hash = generate_password_hash(admin_password)
        event.max_tickets_per_person = max_tickets
        event.is_active = is_active
        db.session.commit()
        flash(f'Event "{name}" updated.', 'success')

    return redirect(url_for('admin_event_guests', event_id=event.id))


def _export_csv(event):
    guests = Guest.query.filter_by(event_id=event.id).order_by(Guest.created_at).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Tickets', 'Zelle Reference',
                     'Checked In', 'Band Given', 'Check-in Time', 'Registered At'])
    for g in guests:
        writer.writerow([
            g.name, g.email, g.ticket_count, g.zelle_reference or '',
            'Yes' if g.checked_in else 'No',
            'Yes' if g.band_given else 'No',
            g.checkin_time.strftime('%Y-%m-%d %H:%M') if g.checkin_time else '',
            g.created_at.strftime('%Y-%m-%d %H:%M') if g.created_at else '',
        ])
    output.seek(0)
    filename = f'{event.slug}_guests_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename,
    )


def generate_qr_image(qr_data, guest_name, event_name):
    """Generate a QR code PNG with event and guest name label."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white').convert('RGB')

    try:
        font = ImageFont.truetype(
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
    except Exception:
        font = ImageFont.load_default()

    width, height = img.size
    canvas = Image.new('RGB', (width, height + 60), 'white')
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    label = f'{event_name} — {guest_name}'
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    x = max(0, (width - text_w) // 2)
    draw.text((x, height + 15), label, fill='black', font=font)

    buf = io.BytesIO()
    canvas.save(buf, 'PNG')
    buf.seek(0)
    return buf.getvalue()


def send_qr_email(guest, event):
    """Send QR code ticket email for an event."""
    if not app.config['MAIL_USERNAME']:
        return
    qr_image = generate_qr_image(guest.qr_code, guest.name, event.name)
    date_str = (event.event_date.strftime('%B %d, %Y at %I:%M %p')
                if event.event_date else 'Date TBD')
    msg = Message(
        subject=f'Your ticket for {event.name}',
        recipients=[guest.email],
        body=f"""Hi {guest.name},

You're registered for {event.name}!

Date:     {date_str}
Location: {event.location or 'TBD'}
Tickets:  {guest.ticket_count}

Your QR code is attached. Show it at the entrance for check-in.

See you there!
""",
    )
    msg.attach('ticket_qr.png', 'image/png', qr_image)
    mail.send(msg)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
