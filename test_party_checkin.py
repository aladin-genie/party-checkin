"""
Party Check-In System — Comprehensive Test Suite
Tests all backend features: DB, QR, email, security, CSV, check-in flow.
Run with: python test_party_checkin.py
"""

import os
import sys
import io
import csv
import threading

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import utils
from utils import (
    init_db,
    get_db,
    Guest,
    CheckInLog,
    PageVisit,
    SubmissionLog,
    AppSetting,
    get_stats,
    generate_qr_image,
    generate_qr_code,
    send_qr_email,
    send_qr_email_async,
    generate_welcome_announcement,
    generate_csv,
    verify_admin_password,
    admin_password_is_configured,
    audio_announcement_js,
    sanitize_email,
    sanitize_name,
    sanitize_phone,
    sanitize_zelle_ref,
    sanitize_guest_names,
    _sanitize_csv_field,
    _normalize_postgres_url,
    record_visit,
    get_visit_stats,
    record_submission,
    get_table_counts,
    get_engine,
    reset_all_data,
    validate_registration,
    register_guest,
    check_in_by_code,
    mark_band_given,
    delete_guest,
    list_guests,
    get_recent_checkins,
    get_registration_daily_counts,
    get_event_day_hourly_checkins,
    format_dt,
    get_setting,
    set_setting,
    get_checkin_mode,
    set_checkin_mode,
    checkin_status,
    CHECKIN_MODE_AUTO,
    CHECKIN_MODE_OPEN,
    CHECKIN_MODE_CLOSED,
)
from datetime import datetime, timezone, timedelta

# We need to mock Streamlit for testing outside the app
import unittest
from unittest.mock import patch, MagicMock

import config

# Mock st.secrets before importing utils
mock_secrets = {
    "SECRET_KEY": "test-secret",
    "DATABASE_URL": "sqlite:///test_party.db",
    "ADMIN_PASSWORD": "testadmin123",
    "TICKET_PRICE_CENTS": "2000",
    "ZELLE_INFO": "test@zelle.com",
    "MAIL_USERNAME": "",
    "MAIL_PASSWORD": "",
}

class TestPartyCheckIn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Patch st.secrets
        cls.secrets_patcher = patch('utils.st')
        cls.mock_st = cls.secrets_patcher.start()
        cls.mock_st.secrets = mock_secrets
        
        # Remove test DB if exists
        if os.path.exists("test_party.db"):
            os.remove("test_party.db")
        
        init_db()
    
    @classmethod
    def tearDownClass(cls):
        cls.secrets_patcher.stop()
        if os.path.exists("test_party.db"):
            os.remove("test_party.db")
    
    def setUp(self):
        # Clean up guests between tests
        session = get_db()
        session.query(CheckInLog).delete()
        session.query(Guest).delete()
        session.commit()
        session.close()
        # Force the check-in window open by default so existing check-in
        # tests don't depend on the real wall-clock date relative to the
        # (2026) event date. Tests that specifically exercise auto/closed
        # modes override this within their own body; tearDown() always
        # resets the persisted setting so tests stay order-independent.
        set_checkin_mode(CHECKIN_MODE_OPEN)

    def tearDown(self):
        # Remove any app_settings rows written during the test (checkin
        # mode override, etc.) so later tests aren't affected by leftover
        # state and the suite stays order-independent.
        session = get_db()
        session.query(AppSetting).delete()
        session.commit()
        session.close()

    def _register(self, name="Reg Guest", email="reg@test.com", phone="",
                   ticket_count=1, plus_one_name="", zelle_ref="ZELLE-DEFAULT01"):
        """Helper: create a guest via the service layer (returns the result dict)."""
        return register_guest(name, email, phone, ticket_count, plus_one_name, zelle_ref)

    # ── Database Tests ──────────────────────────────────────────────────────
    
    def test_create_guest(self):
        session = get_db()
        guest = Guest(
            name="Test User",
            email="test@example.com",
            phone="+1-555-0100",
            ticket_count=2,
            zelle_ref="ZELLE-ABC123",
            qr_code=generate_qr_code(),
        )
        session.add(guest)
        session.commit()
        
        self.assertIsNotNone(guest.id)
        self.assertTrue(guest.qr_code.startswith("PARTY2026-"))
        self.assertFalse(guest.checked_in)
        session.close()
    
    def test_checkin_flow(self):
        session = get_db()
        guest = Guest(
            name="Alice",
            email="alice@example.com",
            ticket_count=1,
            zelle_ref="ZELLE-XYZ789",
            qr_code=generate_qr_code(),
        )
        session.add(guest)
        session.commit()
        
        # Check in
        guest.checked_in = True
        guest.checkin_time = datetime.now(timezone.utc).replace(tzinfo=None)
        log = CheckInLog(guest_id=guest.id, action="checkin", device_info="Test")
        session.add(log)
        session.commit()
        
        stats = get_stats()
        self.assertEqual(stats["total_guests"], 1)
        self.assertEqual(stats["checked_in"], 1)
        self.assertEqual(stats["pending"], 0)
        self.assertEqual(stats["total_tickets"], 1)
        session.close()
    
    def test_band_given_flow(self):
        session = get_db()
        guest = Guest(
            name="Bob",
            email="bob@example.com",
            ticket_count=3,
            zelle_ref="ZELLE-999",
            qr_code=generate_qr_code(),
            checked_in=True,
            checkin_time=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(guest)
        session.commit()
        
        guest.band_given = True
        log = CheckInLog(guest_id=guest.id, action="band_given", device_info="Test")
        session.add(log)
        session.commit()
        
        stats = get_stats()
        self.assertEqual(stats["bands_distributed"], 1)
        session.close()
    
    # ── QR Code Tests ───────────────────────────────────────────────────────
    
    def test_qr_generation(self):
        guest = Guest(name="QR Test", email="qr@test.com", ticket_count=1, qr_code="TEST-QR-123")
        qr_bytes = generate_qr_image("TEST-QR-123")
        self.assertGreater(len(qr_bytes), 1000)  # PNG should be at least 1KB
        # Verify it's a valid PNG by checking magic bytes
        self.assertEqual(qr_bytes[:4], b'\x89PNG')
    
    def test_qr_code_uniqueness(self):
        codes = set()
        for _ in range(100):
            code = generate_qr_code()
            self.assertNotIn(code, codes)
            codes.add(code)
    
    # ── Stats Tests ─────────────────────────────────────────────────────────
    
    def test_stats_with_multiple_guests(self):
        session = get_db()
        for i in range(5):
            g = Guest(
                name=f"Guest{i}",
                email=f"guest{i}@test.com",
                ticket_count=i+1,
                zelle_ref=f"ZELLE-{i}",
                qr_code=generate_qr_code(),
            )
            session.add(g)
        session.commit()
        
        # Check in 2 guests
        guests = session.query(Guest).all()
        for g in guests[:2]:
            g.checked_in = True
            g.checkin_time = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()
        
        stats = get_stats()
        self.assertEqual(stats["total_guests"], 5)
        self.assertEqual(stats["checked_in"], 2)
        self.assertEqual(stats["pending"], 3)
        self.assertEqual(stats["total_tickets"], 15)  # 1+2+3+4+5
        self.assertEqual(stats["admitted_tickets"], 3)  # 1+2
        session.close()
    
    def test_stats_extended(self):
        session = get_db()
        guests_data = [
            ("Alice", 2, True, "Bob"),
            ("Charlie", 1, False, ""),
            ("Dave", 3, True, "Eve"),
        ]
        for name, tickets, checked, plus in guests_data:
            g = Guest(
                name=name,
                email=f"{name.lower()}@test.com",
                ticket_count=tickets,
                plus_one_name=plus,
                zelle_ref=f"ZELLE-{name}",
                qr_code=generate_qr_code(),
                checked_in=checked,
                checkin_time=datetime.now(timezone.utc).replace(tzinfo=None) if checked else None,
            )
            session.add(g)
        session.commit()
        
        stats = get_stats()
        self.assertEqual(stats["total_guests"], 3)
        self.assertEqual(stats["total_tickets"], 6)
        self.assertEqual(stats["checked_in"], 2)
        self.assertEqual(stats["plus_one_count"], 2)
        self.assertEqual(stats["avg_tickets_per_guest"], 2.0)
        self.assertAlmostEqual(stats["checkin_percentage"], 66.7, places=1)
        self.assertEqual(stats["revenue"], 120.0)  # 6 tickets * $20
        session.close()
    
    def test_visit_stats(self):
        # Record a few visits from different tokens
        record_visit("token-abc", "Home")
        record_visit("token-abc", "Register")
        record_visit("token-xyz", "Home")
        record_visit("token-xyz", "Admin")
        
        stats = get_visit_stats()
        self.assertEqual(stats["total_visits"], 4)
        self.assertEqual(stats["unique_visitors"], 2)
    
    # ── Security Tests ──────────────────────────────────────────────────────
    
    def test_csv_injection_prevention(self):
        malicious = "=cmd|' /C calc'!A0"
        sanitized = _sanitize_csv_field(malicious)
        self.assertTrue(sanitized.startswith("'"))
        self.assertIn("=cmd", sanitized)
    
    def test_csv_injection_safe_value(self):
        safe = "John Doe"
        sanitized = _sanitize_csv_field(safe)
        self.assertEqual(sanitized, "John Doe")
    
    def test_email_sanitization(self):
        self.assertEqual(sanitize_email("  Test@Example.COM  "), "test@example.com")
        self.assertEqual(sanitize_email("not-an-email"), "")
        self.assertEqual(sanitize_email(""), "")
    
    def test_name_sanitization(self):
        self.assertEqual(sanitize_name("  John   Doe  "), "John Doe")
        self.assertEqual(sanitize_name(""), "")
        # Control characters removed
        self.assertEqual(sanitize_name("John\x00Doe"), "JohnDoe")
        # Letters and spaces only
        self.assertEqual(sanitize_name("Mary Jane OConnor"), "Mary Jane OConnor")
        # Invalid: digits, symbols, hyphens, apostrophes
        self.assertEqual(sanitize_name("John123"), "")
        self.assertEqual(sanitize_name("John@Doe"), "")
        self.assertEqual(sanitize_name("Mary-Jane O'Connor"), "")
    
    def test_phone_sanitization(self):
        # Default +1 prefix only is treated as empty (optional field)
        self.assertEqual(sanitize_phone("+1-"), "")
        # Formatted US number
        self.assertEqual(sanitize_phone("+1 (555) 123-4567"), "+1-555-123-4567")
        # Bare 10 digits
        self.assertEqual(sanitize_phone("5551234567"), "+1-555-123-4567")
        # Empty is fine (optional)
        self.assertEqual(sanitize_phone(""), "")
        # Too few digits rejected
        self.assertEqual(sanitize_phone("123"), "")
        # Letters rejected
        self.assertEqual(sanitize_phone("+1-555-123-abc"), "")
        # Non-US length rejected
        self.assertEqual(sanitize_phone("+44 20 7946 0958"), "")
    
    def test_zelle_ref_sanitization(self):
        # Valid 8-30 character refs (uppercased, cleaned)
        self.assertEqual(sanitize_zelle_ref("ABC-12345678"), "ABC-12345678")
        self.assertEqual(sanitize_zelle_ref("  zelle-9876543210  "), "ZELLE-9876543210")
        # Invalid: too short
        self.assertEqual(sanitize_zelle_ref("ABC-123"), "")
        # Symbols removed, remaining valid
        self.assertEqual(sanitize_zelle_ref("ABC-123!@#45678"), "ABC-12345678")
    
    def test_plus_one_name_optional(self):
        # Optional plus-one name follows same rules as name
        self.assertEqual(sanitize_name("Alice Smith"), "Alice Smith")
        self.assertEqual(sanitize_name(""), "")
        self.assertEqual(sanitize_name("Bob123"), "")
    
    def test_admin_password_constant_time(self):
        self.assertTrue(verify_admin_password("testadmin123"))
        self.assertFalse(verify_admin_password("wrongpassword"))
        self.assertFalse(verify_admin_password(""))
    
    def test_audio_announcement_xss_prevention(self):
        malicious_name = '<script>alert("xss")</script>'
        text = generate_welcome_announcement(malicious_name, 1)
        js = audio_announcement_js(text)
        # The malicious script tag should be HTML-escaped in the JS string
        self.assertIn('&lt;script&gt;', js)
        self.assertIn('&lt;/script&gt;', js)
        # Raw unescaped script tag should NOT appear in the JSON string content
        # (the outer HTML <script> tags are legitimate)
        self.assertNotIn('<script>alert', js)
        self.assertNotIn('</script>!', js)
    
    # ── CSV Export Tests ────────────────────────────────────────────────────
    
    def test_csv_export(self):
        session = get_db()
        guest = Guest(
            name="CSV Test",
            email="csv@test.com",
            phone="+1-555-0000",
            ticket_count=2,
            zelle_ref="ZELLE-CSV123",
            qr_code=generate_qr_code(),
            checked_in=True,
            checkin_time=datetime.now(timezone.utc).replace(tzinfo=None),
            band_given=True,
        )
        session.add(guest)
        session.commit()
        session.close()
        
        csv_data = generate_csv()
        self.assertIn("CSV Test", csv_data)
        self.assertIn("csv@test.com", csv_data)
        self.assertIn("ZELLE-CSV123", csv_data)
        self.assertIn("Yes", csv_data)
    
    # ── Email Tests ─────────────────────────────────────────────────────────
    
    def test_email_without_credentials(self):
        # With empty MAIL_USERNAME, should return False
        guest = Guest(name="Email Test", email="email@test.com", ticket_count=1, qr_code="TEST")
        result = send_qr_email(guest)
        self.assertFalse(result)  # No SMTP credentials configured
    
    # ── Announcement Tests ────────────────────────────────────────────────
    
    def test_welcome_announcement_singular(self):
        text = generate_welcome_announcement("Alice", 1)
        self.assertIn("Alice", text)
        self.assertIn("1 ticket", text)
    
    def test_welcome_announcement_plural(self):
        text = generate_welcome_announcement("Bob", 3)
        self.assertIn("Bob", text)
        self.assertIn("3 tickets", text)

    # ── Submission Log Tests ──────────────────────────────────────────────

    def test_record_submission_validation_error(self):
        record_submission(
            name="Bad Name 123",
            email="not-an-email",
            phone="abc",
            ticket_count=2,
            plus_one_name="",
            zelle_ref="short",
            status="validation_error",
            errors="invalid name; invalid email; invalid Zelle reference",
        )
        session = get_db()
        try:
            log = session.query(SubmissionLog).order_by(SubmissionLog.id.desc()).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.status, "validation_error")
            self.assertIn("invalid name", log.errors)
            self.assertEqual(log.ticket_count, 2)
        finally:
            session.close()

    def test_record_submission_registered(self):
        record_submission(
            name="Alice Smith",
            email="alice@example.com",
            phone="+1-555-123-4567",
            ticket_count=1,
            plus_one_name="Bob Smith",
            zelle_ref="ZELLE12345678",
            status="registered",
            guest_id=42,
        )
        session = get_db()
        try:
            log = session.query(SubmissionLog).order_by(SubmissionLog.id.desc()).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.status, "registered")
            self.assertEqual(log.email, "alice@example.com")
            self.assertEqual(log.guest_id, 42)
        finally:
            session.close()

    # ── Service Layer: register_guest ───────────────────────────────────────

    def test_register_guest_success(self):
        result = self._register(
            name="Reg Success",
            email="regsuccess@test.com",
            phone="+1-555-000-1111",
            ticket_count=2,
            plus_one_name="Plus One",
            zelle_ref="ZELLE-REGSUCC1",
        )
        self.assertTrue(result["ok"])
        guest = result["guest"]
        self.assertIsInstance(guest, dict)
        self.assertIsNotNone(guest["id"])
        self.assertEqual(guest["email"], "regsuccess@test.com")
        self.assertEqual(guest["ticket_count"], 2)
        self.assertTrue(guest["qr_code"].startswith(config.qr_prefix() + "-"))

    def test_register_guest_duplicate_email(self):
        first = self._register(name="First", email="dupe@test.com", zelle_ref="ZELLE-DUPE1111")
        self.assertTrue(first["ok"])
        second = self._register(name="Second", email="dupe@test.com", zelle_ref="ZELLE-DUPE2222")
        self.assertFalse(second["ok"])
        self.assertEqual(second["reason"], "duplicate_email")

    def test_register_guest_ticket_count_coercion_falsy(self):
        # ticket_count=0 is falsy -> coerced to the default of 1
        result = self._register(name="Zero Tix", email="zerotix@test.com",
                                 ticket_count=0, zelle_ref="ZELLE-ZEROTIX1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["guest"]["ticket_count"], 1)

    def test_register_guest_ticket_count_coercion_numeric_string(self):
        result = self._register(name="Str Tix", email="strtix@test.com",
                                 ticket_count="4", zelle_ref="ZELLE-STRTIX01")
        self.assertTrue(result["ok"])
        self.assertEqual(result["guest"]["ticket_count"], 4)

    # ── Service Layer: check_in_by_code ─────────────────────────────────────

    def test_check_in_by_code_by_qr_code_success_then_already(self):
        reg = self._register(name="QR Flow", email="qrflow@test.com", zelle_ref="ZELLE-QRFLOW01")
        code = reg["guest"]["qr_code"]

        first = check_in_by_code(code)
        self.assertEqual(first["status"], "success")
        self.assertTrue(first["guest"]["checked_in"])

        second = check_in_by_code(code)
        self.assertEqual(second["status"], "already")
        self.assertIn("QR Flow", second["message"])

    def test_check_in_by_code_by_email(self):
        self._register(name="Email Flow", email="emailflow@test.com", zelle_ref="ZELLE-EMLFLOW1")
        result = check_in_by_code("emailflow@test.com")
        self.assertEqual(result["status"], "success")

    def test_check_in_by_code_by_numeric_id(self):
        reg = self._register(name="Id Flow", email="idflow@test.com", zelle_ref="ZELLE-IDFLOW01")
        gid = reg["guest"]["id"]
        result = check_in_by_code(str(gid))
        self.assertEqual(result["status"], "success")

    def test_check_in_by_code_not_found(self):
        result = check_in_by_code("totally-garbage-code-does-not-exist")
        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["guest"])

    def test_check_in_by_code_already_with_null_checkin_time_does_not_raise(self):
        # A guest can end up checked_in=True with checkin_time=None (e.g. rows
        # edited outside the app). Resolving it a second time must return the
        # "already" status without raising AttributeError.
        session = get_db()
        code = generate_qr_code()
        guest = Guest(
            name="NullTime Guest",
            email="nulltime@test.com",
            ticket_count=1,
            qr_code=code,
            checked_in=True,
            checkin_time=None,
        )
        session.add(guest)
        session.commit()
        session.close()

        result = check_in_by_code(code)
        self.assertEqual(result["status"], "already")
        self.assertIn("NullTime Guest", result["message"])

    # ── Service Layer: mark_band_given ──────────────────────────────────────

    def test_mark_band_given_flow(self):
        reg = self._register(name="Band Flow", email="bandflow@test.com", zelle_ref="ZELLE-BANDFLW1")
        gid = reg["guest"]["id"]

        first = mark_band_given(gid)
        self.assertTrue(first["ok"])

        second = mark_band_given(gid)
        self.assertFalse(second["ok"])
        self.assertIn("already", second["message"].lower())

    def test_mark_band_given_nonexistent(self):
        result = mark_band_given(999999)
        self.assertFalse(result["ok"])

    # ── Service Layer: delete_guest ─────────────────────────────────────────

    def test_delete_guest_flow(self):
        reg = self._register(name="Delete Me", email="deleteme@test.com", zelle_ref="ZELLE-DELETEM1")
        gid = reg["guest"]["id"]

        self.assertTrue(delete_guest(gid))

        session = get_db()
        remaining = session.query(Guest).filter_by(id=gid).first()
        session.close()
        self.assertIsNone(remaining)

    def test_delete_guest_nonexistent(self):
        self.assertFalse(delete_guest(999999))

    # ── Service Layer: list_guests / get_recent_checkins ───────────────────

    def test_list_guests_returns_dicts_newest_first(self):
        r1 = self._register(name="Alice LG", email="alice.lg@test.com", zelle_ref="ZELLE-ALICELG1")
        r2 = self._register(name="Bob LG", email="bob.lg@test.com", zelle_ref="ZELLE-BOBLG0001")
        r3 = self._register(name="Carol LG", email="carol.lg@test.com", zelle_ref="ZELLE-CAROLLG1")

        # Pin distinct created_at values so ordering is deterministic
        # regardless of clock resolution.
        session = get_db()
        base = datetime(2026, 1, 1, 12, 0, 0)
        for i, gid in enumerate([r1["guest"]["id"], r2["guest"]["id"], r3["guest"]["id"]]):
            g = session.query(Guest).filter_by(id=gid).first()
            g.created_at = base + timedelta(minutes=i)
        session.commit()
        session.close()

        guests = list_guests()
        self.assertTrue(all(isinstance(g, dict) for g in guests))
        ids_in_order = [g["id"] for g in guests]
        expected_order = [r3["guest"]["id"], r2["guest"]["id"], r1["guest"]["id"]]
        self.assertEqual(ids_in_order, expected_order)

    def test_get_recent_checkins_limit_and_checked_in_only(self):
        ids = []
        for i in range(5):
            r = self._register(name=f"Recent{i}", email=f"recent{i}@test.com",
                                zelle_ref=f"ZELLE-RECENT0{i}")
            ids.append(r["guest"]["id"])

        # Only check in the first 3 of 5 guests.
        for gid in ids[:3]:
            check_in_by_code(str(gid))

        limited = get_recent_checkins(limit=2)
        self.assertEqual(len(limited), 2)
        for g in limited:
            self.assertTrue(g["checked_in"])

        all_checked_in = get_recent_checkins(limit=10)
        self.assertEqual(len(all_checked_in), 3)  # never includes the 2 not checked in

    # ── Service Layer: analytics bucketing ──────────────────────────────────

    def test_get_registration_daily_counts_buckets_by_day(self):
        r1 = self._register(name="Day1a", email="day1a@test.com", zelle_ref="ZELLE-DAY1A0001")
        r2 = self._register(name="Day1b", email="day1b@test.com", zelle_ref="ZELLE-DAY1B0001")
        r3 = self._register(name="Day2a", email="day2a@test.com", zelle_ref="ZELLE-DAY2A0001")

        day1 = datetime(2026, 3, 1, 9, 0, 0)
        day1_later = datetime(2026, 3, 1, 15, 0, 0)
        day2 = datetime(2026, 3, 2, 10, 0, 0)

        session = get_db()
        for gid, dt in [
            (r1["guest"]["id"], day1),
            (r2["guest"]["id"], day1_later),
            (r3["guest"]["id"], day2),
        ]:
            g = session.query(Guest).filter_by(id=gid).first()
            g.created_at = dt
        session.commit()
        session.close()

        counts = get_registration_daily_counts()
        counts_dict = dict(counts)
        self.assertEqual(counts_dict[day1.date()], 2)
        self.assertEqual(counts_dict[day2.date()], 1)
        # Oldest first
        self.assertEqual(counts[0][0], day1.date())

    def test_get_event_day_hourly_checkins_24_entries_and_bucketing(self):
        r1 = self._register(name="Hourly1", email="hourly1@test.com", zelle_ref="ZELLE-HOURLY001")
        r2 = self._register(name="Hourly2", email="hourly2@test.com", zelle_ref="ZELLE-HOURLY002")
        r3 = self._register(name="OffDay", email="offday@test.com", zelle_ref="ZELLE-OFFDAY001")

        event_hour_a = config.EVENT_DATE.replace(hour=9, minute=15)
        event_hour_b = config.EVENT_DATE.replace(hour=9, minute=45)
        other_day = config.EVENT_DATE - timedelta(days=1)
        other_day = other_day.replace(hour=9, minute=0)

        session = get_db()
        for gid, dt in [
            (r1["guest"]["id"], event_hour_a),
            (r2["guest"]["id"], event_hour_b),
            (r3["guest"]["id"], other_day),
        ]:
            g = session.query(Guest).filter_by(id=gid).first()
            g.checked_in = True
            g.checkin_time = dt
        session.commit()
        session.close()

        hourly = get_event_day_hourly_checkins()
        self.assertEqual(len(hourly), 24)
        self.assertEqual(hourly[9], 2)
        self.assertEqual(sum(hourly), 2)  # the off-day checkin must not be counted

    # ── Service Layer: validate_registration ────────────────────────────────

    def test_validate_registration_all_valid(self):
        cleaned, errors = validate_registration(
            name="Jane Doe",
            email="janevalid@example.com",
            phone="555-123-4567",
            plus_one_name="John Doe",
            zelle_ref="ZELLE12345678",
            agree_terms=True,
        )
        self.assertEqual(errors, {})
        self.assertEqual(cleaned["name"], "Jane Doe")
        self.assertEqual(cleaned["email"], "janevalid@example.com")
        self.assertEqual(cleaned["phone"], "+1-555-123-4567")
        self.assertEqual(cleaned["plus_one_name"], "John Doe")
        self.assertEqual(cleaned["zelle_ref"], "ZELLE12345678")
        self.assertTrue(cleaned["terms"])

    def test_validate_registration_invalid_name(self):
        cleaned, errors = validate_registration(
            "John123", "a@b.com", "", "", "ZELLE12345678", True
        )
        self.assertIn("name", errors)
        self.assertEqual(cleaned["name"], "")

    def test_validate_registration_invalid_email(self):
        cleaned, errors = validate_registration(
            "Jane Doe", "not-an-email", "", "", "ZELLE12345678", True
        )
        self.assertIn("email", errors)
        self.assertEqual(cleaned["email"], "")

    def test_validate_registration_blank_phone_optional_no_error(self):
        cleaned, errors = validate_registration(
            "Jane Doe", "jane2@example.com", "", "", "ZELLE12345678", True
        )
        self.assertNotIn("phone", errors)
        self.assertEqual(cleaned["phone"], "")

    def test_validate_registration_invalid_phone_non_blank(self):
        cleaned, errors = validate_registration(
            "Jane Doe", "jane3@example.com", "123", "", "ZELLE12345678", True
        )
        self.assertIn("phone", errors)

    def test_validate_registration_blank_plus_one_optional_no_error(self):
        cleaned, errors = validate_registration(
            "Jane Doe", "jane4@example.com", "", "", "ZELLE12345678", True
        )
        self.assertNotIn("plus_one_name", errors)
        self.assertEqual(cleaned["plus_one_name"], "")

    def test_validate_registration_invalid_plus_one_non_blank(self):
        cleaned, errors = validate_registration(
            "Jane Doe", "jane5@example.com", "", "Bob123", "ZELLE12345678", True
        )
        self.assertIn("plus_one_name", errors)

    def test_validate_registration_invalid_zelle_ref(self):
        cleaned, errors = validate_registration(
            "Jane Doe", "jane6@example.com", "", "", "short", True
        )
        self.assertIn("zelle_ref", errors)
        self.assertEqual(cleaned["zelle_ref"], "")

    def test_validate_registration_terms_not_agreed(self):
        cleaned, errors = validate_registration(
            "Jane Doe", "jane7@example.com", "", "", "ZELLE12345678", False
        )
        self.assertIn("terms", errors)
        self.assertFalse(cleaned["terms"])

    # ── format_dt ────────────────────────────────────────────────────────────

    def test_format_dt_formats_datetime(self):
        dt = datetime(2026, 10, 9, 14, 30, 0)
        self.assertEqual(format_dt(dt, "%H:%M"), "14:30")

    def test_format_dt_fallback_for_none(self):
        self.assertEqual(format_dt(None), "—")
        self.assertEqual(format_dt(None, fallback="N/A"), "N/A")

    # ── Security: admin password fail-closed ────────────────────────────────

    def test_verify_admin_password_fails_closed_when_unconfigured(self):
        with patch.dict(mock_secrets, {"ADMIN_PASSWORD": ""}):
            self.assertFalse(verify_admin_password(""))
            self.assertFalse(verify_admin_password("anything"))
            self.assertFalse(verify_admin_password("testadmin123"))

    def test_verify_admin_password_non_ascii_does_not_raise(self):
        try:
            result = verify_admin_password("pässwörd™😀")
        except TypeError:
            self.fail("verify_admin_password raised TypeError on non-ASCII input")
        self.assertFalse(result)

    def test_admin_password_is_configured_true(self):
        self.assertTrue(admin_password_is_configured())

    def test_admin_password_is_configured_false(self):
        with patch.dict(mock_secrets, {"ADMIN_PASSWORD": ""}):
            self.assertFalse(admin_password_is_configured())

    # ── CSV export edge cases ───────────────────────────────────────────────

    def test_generate_csv_escapes_formula_name_and_handles_null_checkin_time(self):
        session = get_db()
        guest = Guest(
            name='=HYPERLINK("http://evil.com","click")',
            email="csvformula@test.com",
            ticket_count=1,
            zelle_ref="ZELLE-CSVFORM1",
            qr_code=generate_qr_code(),
            checked_in=True,
            checkin_time=None,  # must not crash the export
        )
        session.add(guest)
        session.commit()
        session.close()

        csv_data = generate_csv()  # must not raise

        reader = csv.reader(io.StringIO(csv_data))
        rows = list(reader)
        header = rows[0]
        name_idx = header.index("Name")
        checkin_idx = header.index("Check-in Time")
        row = next(r for r in rows[1:] if "HYPERLINK" in r[name_idx])
        self.assertTrue(row[name_idx].startswith("'"))
        self.assertEqual(row[checkin_idx], "")

    # ── Email: HTML-escaping of guest-controlled values ─────────────────────

    def test_send_qr_email_escapes_html_and_never_hits_the_network(self):
        guest = Guest(
            id=99999,
            name="<script>alert(1)</script>",
            email="xss@test.com",
            ticket_count=1,
            plus_one_name="",
            qr_code="XSS-QR-CODE",
        )
        with patch.dict(mock_secrets, {"MAIL_USERNAME": "sender@test.com", "MAIL_PASSWORD": "testpass"}):
            with patch("smtplib.SMTP") as mock_smtp_cls:
                mock_server = MagicMock()
                mock_smtp_cls.return_value.__enter__.return_value = mock_server
                result = send_qr_email(guest)

        self.assertTrue(result)
        mock_smtp_cls.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("sender@test.com", "testpass")
        mock_server.send_message.assert_called_once()

        sent_msg = mock_server.send_message.call_args[0][0]
        # The body is transfer-encoded (base64, since it contains emoji), so
        # decode the actual HTML part rather than grepping the raw message.
        html_part = next(
            part for part in sent_msg.walk() if part.get_content_type() == "text/html"
        )
        html_content = html_part.get_payload(decode=True).decode("utf-8")
        self.assertNotIn("<script>alert", html_content)
        self.assertIn("&lt;script&gt;", html_content)

    # ── Pure helpers: _normalize_postgres_url ───────────────────────────────

    def test_normalize_postgres_url_variants(self):
        expected = "postgresql+psycopg2://user:pass@host:5432/db"
        self.assertEqual(_normalize_postgres_url("postgres://user:pass@host:5432/db"), expected)
        self.assertEqual(_normalize_postgres_url("postgresql://user:pass@host:5432/db"), expected)
        self.assertEqual(_normalize_postgres_url("postgresql+psycopg://user:pass@host:5432/db"), expected)
        self.assertEqual(_normalize_postgres_url("postgresql+psycopg2://user:pass@host:5432/db"), expected)

    def test_normalize_postgres_url_sqlite_passthrough(self):
        self.assertEqual(_normalize_postgres_url("sqlite:///test.db"), "sqlite:///test.db")

    # ── Pure helpers: generate_qr_code ──────────────────────────────────────

    def test_generate_qr_code_prefix(self):
        code = generate_qr_code()
        self.assertTrue(code.startswith(config.qr_prefix() + "-"))

    # ── Pure helpers: sanitize_* edge cases ─────────────────────────────────

    def test_sanitize_name_edge_cases(self):
        # Very long input: exceeds the 100-char cap -> rejected outright
        self.assertEqual(sanitize_name("A" * 150), "")
        # Unicode letters are outside the ASCII-only [A-Za-z] allow-list
        self.assertEqual(sanitize_name("Émile Zola"), "")
        # Tabs/newlines are collapsed to single spaces, not rejected
        self.assertEqual(sanitize_name("John\tDoe"), "John Doe")
        self.assertEqual(sanitize_name("  \n Jane  Doe \t "), "Jane Doe")

    def test_sanitize_email_edge_cases(self):
        # Long but well-formed email passes (no explicit length cap)
        long_email = "a" * 100 + "@example.com"
        self.assertEqual(sanitize_email(long_email), long_email)
        # Unicode local part rejected by the ASCII-only regex
        self.assertEqual(sanitize_email("josé@example.com"), "")
        # Leading/trailing whitespace and mixed case normalized
        self.assertEqual(sanitize_email("\t  Foo.Bar+tag@Example.COM \n"), "foo.bar+tag@example.com")

    def test_sanitize_phone_edge_cases(self):
        # Very long garbage input rejected
        self.assertEqual(sanitize_phone("1" * 50), "")
        # Unicode (full-width) digits are not ASCII digits -> rejected
        self.assertEqual(sanitize_phone("５５５１２３４５６７"), "")
        # Leading/trailing whitespace tolerated around a valid number
        self.assertEqual(sanitize_phone("   555-123-4567   "), "+1-555-123-4567")

    def test_sanitize_zelle_ref_edge_cases(self):
        # Very long ref exceeds 30 chars after cleaning -> rejected
        self.assertEqual(sanitize_zelle_ref("A" * 40), "")
        # Unicode characters are stripped out entirely; remaining digits still valid
        self.assertEqual(sanitize_zelle_ref("ÉÉÉÉÉÉÉÉ12345678"), "12345678")
        # Leading/trailing junk (symbols) cleaned, remainder valid
        self.assertEqual(sanitize_zelle_ref("***ABC-12345678***"), "ABC-12345678")

    # ── App Settings: get_setting / set_setting ─────────────────────────────

    def test_get_setting_set_setting_round_trip_and_default(self):
        # Default when unset
        self.assertEqual(get_setting("no_such_setting_key", "fallback"), "fallback")
        self.assertEqual(get_setting("no_such_setting_key"), "")

        set_setting("my_setting", "value1")
        self.assertEqual(get_setting("my_setting"), "value1")

        # set_setting overwrites rather than duplicating the row
        set_setting("my_setting", "value2")
        self.assertEqual(get_setting("my_setting"), "value2")

        session = get_db()
        try:
            count = session.query(AppSetting).filter_by(key="my_setting").count()
        finally:
            session.close()
        self.assertEqual(count, 1)

    # ── Check-in window: get_checkin_mode / set_checkin_mode ────────────────

    def test_get_checkin_mode_defaults_to_auto_when_unset(self):
        session = get_db()
        session.query(AppSetting).delete()
        session.commit()
        session.close()
        self.assertEqual(get_checkin_mode(), CHECKIN_MODE_AUTO)

    def test_get_checkin_mode_defaults_to_auto_when_stored_value_is_garbage(self):
        # Bypass set_checkin_mode's validation to simulate a corrupted/old
        # value already sitting in the table.
        set_setting("checkin_mode", "not-a-real-mode")
        self.assertEqual(get_checkin_mode(), CHECKIN_MODE_AUTO)

    def test_set_checkin_mode_rejects_invalid_mode(self):
        with self.assertRaises(ValueError):
            set_checkin_mode("definitely-not-valid")
        # And the invalid value must not have been persisted.
        self.assertEqual(get_checkin_mode(), CHECKIN_MODE_OPEN)  # set by setUp()

    # ── Check-in window: checkin_status() ───────────────────────────────────

    def test_checkin_status_open_mode(self):
        set_checkin_mode(CHECKIN_MODE_OPEN)
        status = checkin_status()
        self.assertTrue(status["open"])
        self.assertEqual(status["message"], "")

    def test_checkin_status_closed_mode(self):
        set_checkin_mode(CHECKIN_MODE_CLOSED)
        status = checkin_status()
        self.assertFalse(status["open"])
        self.assertGreater(len(status["message"]), 0)

    def test_checkin_status_auto_mode_before_window_is_closed(self):
        set_checkin_mode(CHECKIN_MODE_AUTO)
        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        with patch.object(config, "checkin_opens_at_utc", return_value=future):
            status = checkin_status()
        self.assertFalse(status["open"])
        self.assertGreater(len(status["message"]), 0)

    def test_checkin_status_auto_mode_after_window_is_open(self):
        set_checkin_mode(CHECKIN_MODE_AUTO)
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        with patch.object(config, "checkin_opens_at_utc", return_value=past):
            status = checkin_status()
        self.assertTrue(status["open"])
        self.assertEqual(status["message"], "")

    # ── Check-in window: check_in_by_code gating ────────────────────────────

    def test_check_in_by_code_auto_mode_before_window_leaves_guest_unmodified(self):
        set_checkin_mode(CHECKIN_MODE_AUTO)
        reg = self._register(name="Early Bird", email="earlybird@test.com", zelle_ref="ZELLE-EARLYBRD")
        code = reg["guest"]["qr_code"]
        gid = reg["guest"]["id"]

        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        with patch.object(config, "checkin_opens_at_utc", return_value=future):
            result = check_in_by_code(code)

        self.assertEqual(result["status"], "not_open")
        self.assertIsNone(result["guest"])

        # Assert against the DB, not just the return value: the row must be
        # genuinely untouched -- no lookup/write happened at all.
        session = get_db()
        try:
            guest = session.query(Guest).filter_by(id=gid).first()
            self.assertFalse(guest.checked_in)
            self.assertIsNone(guest.checkin_time)
        finally:
            session.close()

    def test_check_in_by_code_bypass_window_succeeds_when_closed(self):
        set_checkin_mode(CHECKIN_MODE_CLOSED)
        reg = self._register(name="Admin Admit", email="adminadmit@test.com", zelle_ref="ZELLE-ADMADMIT")
        code = reg["guest"]["qr_code"]

        result = check_in_by_code(code, bypass_window=True)
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["guest"]["checked_in"])

    def test_check_in_by_code_mode_open_allows_checkin(self):
        set_checkin_mode(CHECKIN_MODE_OPEN)
        reg = self._register(name="Open Mode Guest", email="openmodeguest@test.com", zelle_ref="ZELLE-OPENMODE1")
        result = check_in_by_code(reg["guest"]["qr_code"])
        self.assertEqual(result["status"], "success")

    def test_check_in_by_code_mode_closed_blocks_checkin(self):
        set_checkin_mode(CHECKIN_MODE_CLOSED)
        reg = self._register(name="Closed Mode Guest", email="closedmodeguest@test.com", zelle_ref="ZELLE-CLSDMODE1")
        result = check_in_by_code(reg["guest"]["qr_code"])
        self.assertEqual(result["status"], "not_open")
        self.assertIsNone(result["guest"])

    # ── Bulk guest names: sanitize_guest_names ──────────────────────────────

    def test_sanitize_guest_names_newline_separated(self):
        result = sanitize_guest_names("Alice Smith\nBob Jones\nCarol White")
        self.assertEqual(result, "Alice Smith\nBob Jones\nCarol White")

    def test_sanitize_guest_names_comma_separated(self):
        result = sanitize_guest_names("Alice Smith, Bob Jones, Carol White")
        self.assertEqual(result, "Alice Smith\nBob Jones\nCarol White")

    def test_sanitize_guest_names_mixed_separators(self):
        result = sanitize_guest_names("Alice Smith, Bob Jones\nCarol White")
        self.assertEqual(result, "Alice Smith\nBob Jones\nCarol White")

    def test_sanitize_guest_names_blank_input_returns_empty(self):
        self.assertEqual(sanitize_guest_names(""), "")
        self.assertEqual(sanitize_guest_names("   "), "")
        self.assertEqual(sanitize_guest_names("\n\n  \n"), "")

    def test_sanitize_guest_names_any_invalid_entry_rejects_all(self):
        # "Bob123" contains digits -> entire list is rejected, not just that entry
        result = sanitize_guest_names("Alice Smith\nBob123\nCarol White")
        self.assertEqual(result, "")

    def test_sanitize_guest_names_over_max_returns_empty(self):
        names_21 = [f"Guest {chr(65 + i)}" for i in range(21)]  # 21 valid names
        self.assertEqual(sanitize_guest_names("\n".join(names_21)), "")

    def test_sanitize_guest_names_exactly_max_accepted(self):
        names_20 = [f"Guest {chr(65 + i)}" for i in range(20)]  # exactly 20
        expected = "\n".join(names_20)
        self.assertEqual(sanitize_guest_names("\n".join(names_20)), expected)

    def test_sanitize_guest_names_collapses_blank_lines_and_whitespace(self):
        result = sanitize_guest_names("Alice Smith\n\n\n   Bob Jones   \n\n,,,")
        self.assertEqual(result, "Alice Smith\nBob Jones")

    # ── Bulk guest names: validate_registration integration ─────────────────

    def test_validate_registration_plus_one_bulk_names_valid_20_no_error(self):
        names_20 = [f"Guest {chr(65 + i)}" for i in range(20)]
        text = "\n".join(names_20)
        cleaned, errors = validate_registration(
            "Jane Doe", "janebulk20@example.com", "", text, "ZELLE12345678", True
        )
        self.assertNotIn("plus_one_name", errors)
        self.assertEqual(cleaned["plus_one_name"], text)

    def test_validate_registration_plus_one_over_max_names_error(self):
        names_21 = [f"Guest {chr(65 + i)}" for i in range(21)]
        text = "\n".join(names_21)
        cleaned, errors = validate_registration(
            "Jane Doe", "janebulk21@example.com", "", text, "ZELLE12345678", True
        )
        self.assertIn("plus_one_name", errors)
        self.assertEqual(cleaned["plus_one_name"], "")

    # ── Async email: send_qr_email_async ────────────────────────────────────

    def test_send_qr_email_async_blank_credentials_returns_without_smtp(self):
        # Class-level mock_secrets already has blank MAIL_USERNAME/MAIL_PASSWORD.
        guest = {
            "id": 1,
            "name": "No Creds",
            "email": "nocreds@test.com",
            "ticket_count": 1,
            "plus_one_name": "",
            "qr_code": "NOCREDS-QR",
            "phone": "",
            "zelle_ref": "",
        }
        with patch("smtplib.SMTP") as mock_smtp_cls, patch("smtplib.SMTP_SSL") as mock_smtp_ssl_cls:
            send_qr_email_async(guest)  # must return promptly, no thread spawned

        mock_smtp_cls.assert_not_called()
        mock_smtp_ssl_cls.assert_not_called()

    def test_send_qr_email_async_missing_optional_keys_does_not_raise(self):
        # Blank credentials -> returns immediately without touching the
        # (missing) optional keys at all, but must not raise regardless.
        guest = {"id": 2, "name": "Minimal", "email": "minimal@test.com"}
        try:
            send_qr_email_async(guest)
        except Exception as e:
            self.fail(f"send_qr_email_async raised with a minimal guest dict: {e}")

    def test_send_qr_email_async_with_credentials_sends_and_worker_touches_no_st(self):
        guest = {"id": 3, "name": "Async Guest", "email": "asyncguest@test.com"}  # missing optional keys too

        local_secrets = dict(mock_secrets)
        local_secrets.update({"MAIL_USERNAME": "sender@test.com", "MAIL_PASSWORD": "testpass"})

        # A Mock (not a plain dict) so we can assert on call_count: every
        # st.secrets.get() must happen on the calling thread, synchronously,
        # before send_qr_email_async() returns -- never from the worker.
        secrets_mock = MagicMock()
        secrets_mock.get.side_effect = local_secrets.get
        mock_st_local = MagicMock()
        mock_st_local.secrets = secrets_mock

        done = threading.Event()

        with patch.object(utils, "st", mock_st_local):
            with patch("smtplib.SMTP") as mock_smtp_cls:
                mock_server = MagicMock()
                mock_smtp_cls.return_value.__enter__.return_value = mock_server
                mock_server.send_message.side_effect = lambda *a, **k: done.set()

                send_qr_email_async(guest)

                # _read_mail_secrets() runs synchronously on the calling
                # thread before the worker thread is even started.
                calls_after_dispatch = secrets_mock.get.call_count
                self.assertGreater(calls_after_dispatch, 0)

                # Join deterministically on the worker's own completion
                # signal rather than sleeping and hoping.
                self.assertTrue(done.wait(timeout=5), "background email send did not complete in time")

            mock_server.send_message.assert_called_once()

        # No additional st.secrets reads must have happened after dispatch
        # -- proves the worker thread itself never touched st.*.
        self.assertEqual(secrets_mock.get.call_count, calls_after_dispatch)

    def test_send_qr_email_sync_paths_still_pass(self):
        # Guards against the async addition above accidentally sharing
        # mutable state with the synchronous sender.
        guest = Guest(name="Sync Check", email="synccheck@test.com", ticket_count=1, qr_code="SYNC-QR")
        self.assertFalse(send_qr_email(guest))  # blank creds -> False, unchanged behavior

    # ── Postgres pool config: _get_engine_cached ────────────────────────────

    def test_get_engine_cached_passes_pool_kwargs_for_postgres_url(self):
        with patch.dict(mock_secrets, {"DATABASE_URL": "postgresql://user:pass@host:5432/db"}):
            with patch("utils.create_engine") as mock_create_engine, \
                 patch("utils.inspect") as mock_inspect:
                mock_inspect.return_value.get_table_names.return_value = []
                db_url_hash = utils._get_engine_url_hash()
                # Bypass st.cache_resource's memoization via the underlying
                # function so each call actually re-invokes create_engine().
                utils._get_engine_cached.__wrapped__(db_url_hash)

        mock_create_engine.assert_called_once()
        args, kwargs = mock_create_engine.call_args
        self.assertTrue(args[0].startswith("postgresql+psycopg2://"))
        self.assertEqual(kwargs.get("pool_size"), 5)
        self.assertEqual(kwargs.get("max_overflow"), 10)
        self.assertEqual(kwargs.get("pool_recycle"), 1800)

    def test_get_engine_cached_omits_pool_kwargs_for_sqlite_url(self):
        with patch.dict(mock_secrets, {"DATABASE_URL": "sqlite:///somefile.db"}):
            with patch("utils.create_engine") as mock_create_engine, \
                 patch("utils.inspect") as mock_inspect:
                mock_inspect.return_value.get_table_names.return_value = []
                db_url_hash = utils._get_engine_url_hash()
                utils._get_engine_cached.__wrapped__(db_url_hash)

        mock_create_engine.assert_called_once()
        args, kwargs = mock_create_engine.call_args
        self.assertTrue(args[0].startswith("sqlite://"))
        self.assertNotIn("pool_size", kwargs)
        self.assertNotIn("max_overflow", kwargs)
        self.assertNotIn("pool_recycle", kwargs)


    # ── Reset / wipe-all (destructive admin action) ────────────────────────

    def _seed_for_reset(self):
        """Populate every table reset_all_data() is supposed to empty."""
        session = get_db()
        try:
            g = Guest(name="Reset Me", email="reset.me@test.com", ticket_count=2,
                      zelle_ref="ZELLE-RESET1", qr_code=generate_qr_code())
            session.add(g)
            session.commit()
            gid = g.id
            session.add(CheckInLog(guest_id=gid, action="checkin", device_info="Test"))
            session.commit()
        finally:
            session.close()
        record_visit("reset-token", "Home")
        record_submission("Reset Me", "reset.me@test.com", "", 2, "", "ZELLE-RESET1",
                          status="registered", guest_id=gid)
        return gid

    def test_get_table_counts_matches_reality(self):
        self._seed_for_reset()
        counts = get_table_counts()
        self.assertEqual(set(counts), {"guests", "checkin_logs", "page_visits", "submission_logs"})
        self.assertEqual(counts["guests"], 1)
        self.assertEqual(counts["checkin_logs"], 1)
        self.assertGreaterEqual(counts["page_visits"], 1)
        self.assertGreaterEqual(counts["submission_logs"], 1)

    def test_reset_all_data_empties_every_table(self):
        self._seed_for_reset()
        result = reset_all_data()

        self.assertEqual(result["guests"], 1)
        self.assertEqual(result["checkin_logs"], 1)
        self.assertGreaterEqual(result["page_visits"], 1)
        self.assertGreaterEqual(result["submission_logs"], 1)

        after = get_table_counts()
        self.assertEqual(after["guests"], 0)
        self.assertEqual(after["checkin_logs"], 0)
        self.assertEqual(after["page_visits"], 0)
        self.assertEqual(after["submission_logs"], 0)

    def test_reset_all_data_preserves_schema(self):
        """It must empty tables, never drop them — the app has to keep working."""
        self._seed_for_reset()
        reset_all_data()
        from sqlalchemy import inspect as sa_inspect
        tables = set(sa_inspect(get_engine()).get_table_names())
        for expected in ("guests", "checkin_logs", "page_visits", "submission_logs", "app_settings"):
            self.assertIn(expected, tables)
        # and the app can still write afterwards
        res = register_guest("After Reset", "after.reset@test.com", "", 1, "", "ZELLE-AFTER01")
        self.assertTrue(res["ok"])

    def test_reset_all_data_restores_auto_checkin_mode(self):
        """A wipe must not leave check-in forced open from testing."""
        set_checkin_mode(CHECKIN_MODE_OPEN)
        self.assertEqual(get_checkin_mode(), CHECKIN_MODE_OPEN)
        reset_all_data()
        self.assertEqual(get_checkin_mode(), CHECKIN_MODE_AUTO)

    def test_reset_all_data_keep_settings_false_clears_settings(self):
        set_checkin_mode(CHECKIN_MODE_CLOSED)
        reset_all_data(keep_settings=False)
        # With no rows left, get_checkin_mode() falls back to its own default.
        self.assertEqual(get_checkin_mode(), CHECKIN_MODE_AUTO)

    def test_reset_all_data_on_empty_db_is_a_harmless_noop(self):
        result = reset_all_data()
        self.assertEqual(result["guests"], 0)
        self.assertEqual(get_table_counts()["guests"], 0)


def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPartyCheckIn)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
