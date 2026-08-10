"""
Party Check-In System — Comprehensive Test Suite
Tests all backend features: DB, QR, email, security, CSV, check-in flow.
Run with: python test_party_checkin.py
"""

import os
import sys
import tempfile
import io

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import (
    init_db,
    get_db,
    Guest,
    CheckInLog,
    PageVisit,
    SubmissionLog,
    get_stats,
    generate_qr_image,
    generate_qr_code_for_guest,
    send_qr_email,
    generate_welcome_announcement,
    generate_csv,
    verify_admin_password,
    audio_announcement_js,
    sanitize_email,
    sanitize_name,
    sanitize_phone,
    sanitize_zelle_ref,
    _sanitize_csv_field,
    record_visit,
    get_visit_stats,
    record_submission,
)
from datetime import datetime, timezone

# We need to mock Streamlit for testing outside the app
import unittest
from unittest.mock import patch, MagicMock

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
    
    # ── Database Tests ──────────────────────────────────────────────────────
    
    def test_create_guest(self):
        session = get_db()
        guest = Guest(
            name="Test User",
            email="test@example.com",
            phone="+1-555-0100",
            ticket_count=2,
            zelle_ref="ZELLE-ABC123",
            qr_code=generate_qr_code_for_guest("Test User", "test@example.com"),
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
            qr_code=generate_qr_code_for_guest("Alice", "alice@example.com"),
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
            qr_code=generate_qr_code_for_guest("Bob", "bob@example.com"),
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
        qr_bytes = generate_qr_image("TEST-QR-123", "QR Test")
        self.assertGreater(len(qr_bytes), 1000)  # PNG should be at least 1KB
        # Verify it's a valid PNG by checking magic bytes
        self.assertEqual(qr_bytes[:4], b'\x89PNG')
    
    def test_qr_code_uniqueness(self):
        codes = set()
        for _ in range(100):
            code = generate_qr_code_for_guest("Name", "email@test.com")
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
                qr_code=generate_qr_code_for_guest(f"Guest{i}", f"guest{i}@test.com"),
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
                qr_code=generate_qr_code_for_guest(name, f"{name.lower()}@test.com"),
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
            qr_code=generate_qr_code_for_guest("CSV Test", "csv@test.com"),
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
