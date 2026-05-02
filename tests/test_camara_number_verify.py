"""
Tests for CAMARA Number Verification API
"""

import unittest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from camara.number_verify import (
    VerificationStatus, ConsentStatus,
    VerifyConsentRecord, VerificationSession, VerificationResult,
    PhoneNumberValidator, DeviceAssociationChecker, OTPGenerator,
    VerificationSessionManager, VerificationAuditLog,
    FraudScoreCalculator, NumberVerificationService
)


class TestPhoneNumberValidator(unittest.TestCase):
    """Test PhoneNumberValidator"""

    def setUp(self):
        self.validator = PhoneNumberValidator()

    def test_valid_e164_numbers(self):
        """Test validating valid E.164 numbers"""
        self.assertTrue(self.validator.validate("+1234567890"))
        self.assertTrue(self.validator.validate("+441234567890"))
        self.assertTrue(self.validator.validate("+911234567890"))

    def test_invalid_numbers(self):
        """Test validating invalid numbers"""
        self.assertFalse(self.validator.validate("1234567890"))  # Missing +
        self.assertFalse(self.validator.validate("+abc"))  # Non-digits
        self.assertFalse(self.validator.validate("+1"))  # Too short
        self.assertFalse(self.validator.validate(""))  # Empty

    def test_normalize(self):
        """Test normalizing phone numbers"""
        normalized = self.validator.normalize("1234567890")
        self.assertEqual(normalized, "+1234567890")

        normalized = self.validator.normalize("+1234567890")
        self.assertEqual(normalized, "+1234567890")

    def test_get_country_code(self):
        """Test getting country code"""
        code = self.validator.get_country_code("+1234567890")
        self.assertEqual(code, "1")

        code = self.validator.get_country_code("+441234567890")
        self.assertEqual(code, "44")


class TestDeviceAssociationChecker(unittest.TestCase):
    """Test DeviceAssociationChecker"""

    def setUp(self):
        self.checker = DeviceAssociationChecker()

    def test_associate_device(self):
        """Test associating device with MSISDN"""
        self.checker.associate_device("+1234567890", "device1", "192.168.1.1")

        device = self.checker.get_device_for_msisdn("+1234567890")
        self.assertEqual(device, "device1")

    def test_verify_association(self):
        """Test verifying device association"""
        self.checker.associate_device("+1234567890", "device1", "192.168.1.1")

        is_valid = self.checker.verify_association("+1234567890", "192.168.1.1")
        self.assertTrue(is_valid)

        is_invalid = self.checker.verify_association("+9999999999", "192.168.1.1")
        self.assertFalse(is_invalid)

    def test_verify_association_with_device_id(self):
        """Test verifying association with device ID"""
        self.checker.associate_device("+1234567890", "device1", "192.168.1.1")

        is_valid = self.checker.verify_association("+1234567890", "192.168.1.1", "device1")
        self.assertTrue(is_valid)

        is_invalid = self.checker.verify_association("+1234567890", "192.168.1.1", "device2")
        self.assertFalse(is_invalid)

    def test_is_valid_ip(self):
        """Test validating IP addresses"""
        self.assertTrue(self.checker.is_valid_ip("192.168.1.1"))
        self.assertTrue(self.checker.is_valid_ip("10.0.0.1"))
        self.assertFalse(self.checker.is_valid_ip("999.999.999.999"))
        self.assertFalse(self.checker.is_valid_ip("not-an-ip"))


class TestOTPGenerator(unittest.TestCase):
    """Test OTPGenerator"""

    def setUp(self):
        self.generator = OTPGenerator()

    def test_generate_code(self):
        """Test generating OTP code"""
        code = self.generator.generate_code()

        self.assertIsNotNone(code)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_validate_code(self):
        """Test validating OTP code"""
        code = self.generator.generate_code()

        is_valid = self.generator.validate_code(code, code)
        self.assertTrue(is_valid)

        is_invalid = self.generator.validate_code(code, "000000")
        self.assertFalse(is_invalid)

    def test_is_expired(self):
        """Test checking if session is expired"""
        session = VerificationSession(
            session_id="test",
            msisdn="+1234567890",
            device_ip="192.168.1.1",
            device_id="device1",
            otp_code="123456",
            expires_at=time.time() - 10  # Expired
        )

        is_expired = self.generator.is_expired(session)
        self.assertTrue(is_expired)


class TestVerificationSessionManager(unittest.TestCase):
    """Test VerificationSessionManager"""

    def setUp(self):
        self.otp_generator = OTPGenerator()
        self.session_manager = VerificationSessionManager(self.otp_generator)

    def test_create_session(self):
        """Test creating a verification session"""
        session = self.session_manager.create_session(
            msisdn="+1234567890",
            device_ip="192.168.1.1",
            device_id="device1"
        )

        self.assertIsNotNone(session)
        self.assertEqual(session.msisdn, "+1234567890")
        self.assertEqual(session.status, VerificationStatus.PENDING)
        self.assertEqual(len(session.otp_code), 6)

    def test_validate_otp(self):
        """Test validating OTP"""
        session = self.session_manager.create_session(
            msisdn="+1234567890",
            device_ip="192.168.1.1",
            device_id="device1"
        )

        validated = self.session_manager.validate_otp(session.session_id, session.otp_code)

        self.assertEqual(validated.status, VerificationStatus.VERIFIED)
        self.assertIsNotNone(validated.verified_at)

    def test_validate_otp_invalid(self):
        """Test validating invalid OTP"""
        session = self.session_manager.create_session(
            msisdn="+1234567890",
            device_ip="192.168.1.1",
            device_id="device1"
        )

        validated = self.session_manager.validate_otp(session.session_id, "000000")

        self.assertEqual(validated.status, VerificationStatus.FAILED)
        self.assertEqual(validated.attempts, 1)

    def test_validate_otp_max_attempts(self):
        """Test that max attempts is enforced"""
        session = self.session_manager.create_session(
            msisdn="+1234567890",
            device_ip="192.168.1.1",
            device_id="device1"
        )

        # Fail max attempts
        for _ in range(3):
            self.session_manager.validate_otp(session.session_id, "000000")

        # Fourth attempt should fail
        with self.assertRaises(ValueError):
            self.session_manager.validate_otp(session.session_id, "000000")

    def test_cancel_session(self):
        """Test cancelling a session"""
        session = self.session_manager.create_session(
            msisdn="+1234567890",
            device_ip="192.168.1.1",
            device_id="device1"
        )

        result = self.session_manager.cancel_session(session.session_id)
        self.assertTrue(result)

    def test_list_sessions(self):
        """Test listing sessions"""
        self.session_manager.create_session("+1234567890", "192.168.1.1", "device1")
        self.session_manager.create_session("+1234567890", "192.168.1.1", "device1")

        sessions = self.session_manager.list_sessions(msisdn="+1234567890")
        self.assertEqual(len(sessions), 2)

    def test_list_sessions_with_status_filter(self):
        """Test listing sessions with status filter"""
        session = self.session_manager.create_session("+1234567890", "192.168.1.1", "device1")
        self.session_manager.validate_otp(session.session_id, session.otp_code)

        verified = self.session_manager.list_sessions(status=VerificationStatus.VERIFIED)
        self.assertEqual(len(verified), 1)


class TestVerificationAuditLog(unittest.TestCase):
    """Test VerificationAuditLog"""

    def setUp(self):
        self.audit_log = VerificationAuditLog()

    def test_log(self):
        """Test logging an audit entry"""
        entry = self.audit_log.log(
            session_id="session1",
            msisdn="+1234567890",
            device_ip="192.168.1.1",
            device_id="device1",
            action="create_session",
            result="success"
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.action, "create_session")
        self.assertEqual(entry.result, "success")

    def test_get_logs(self):
        """Test getting audit logs"""
        self.audit_log.log("s1", "+1234567890", "192.168.1.1", "d1", "action1", "success")
        self.audit_log.log("s2", "+1234567890", "192.168.1.1", "d1", "action2", "success")

        logs = self.audit_log.get_logs(msisdn="+1234567890")
        self.assertEqual(len(logs), 2)

    def test_get_failed_attempts(self):
        """Test getting failed attempts"""
        self.audit_log.log("s1", "+1234567890", "192.168.1.1", "d1", "validate_otp", "failed")
        self.audit_log.log("s2", "+1234567890", "192.168.1.1", "d1", "validate_otp", "failed")
        self.audit_log.log("s3", "+1234567890", "192.168.1.1", "d1", "validate_otp", "success")

        failed = self.audit_log.get_failed_attempts("+1234567890", hours=24)
        self.assertEqual(failed, 2)


class TestFraudScoreCalculator(unittest.TestCase):
    """Test FraudScoreCalculator"""

    def setUp(self):
        self.audit_log = VerificationAuditLog()
        self.calculator = FraudScoreCalculator(self.audit_log)

    def test_calculate_no_attempts(self):
        """Test calculating fraud score with no attempts"""
        score = self.calculator.calculate("+1234567890")

        self.assertEqual(score.msisdn, "+1234567890")
        self.assertEqual(score.risk_level, "low")
        self.assertEqual(score.score, 0.0)

    def test_calculate_with_failed_attempts(self):
        """Test calculating with failed attempts"""
        for i in range(10):
            self.audit_log.log(f"s{i}", "+1234567890", "192.168.1.1", "d1", "validate_otp", "failed")

        score = self.calculator.calculate("+1234567890")

        self.assertGreater(score.score, 0)
        self.assertGreater(score.score, 30)


class TestNumberVerificationService(unittest.TestCase):
    """Test NumberVerificationService"""

    def setUp(self):
        self.service = NumberVerificationService()

        # Setup test data
        consent = self.service.request_consent("+1234567890", "user1")
        self.service.grant_consent(consent.consent_id)

        self.service.register_device("+1234567890", "device1", "192.168.1.1")

    def test_verify_number(self):
        """Test verifying number"""
        result = self.service.verify_number("+1234567890", "192.168.1.1", "device1", "user1")

        self.assertTrue(result.verified)
        self.assertEqual(result.msisdn, "+1234567890")
        self.assertEqual(result.status, VerificationStatus.VERIFIED)

    def test_verify_number_not_associated(self):
        """Test verifying number not associated with device"""
        result = self.service.verify_number("+1234567890", "192.168.1.2", "device2", "user1")

        self.assertFalse(result.verified)
        self.assertEqual(result.status, VerificationStatus.FAILED)

    def test_verify_number_invalid_format_fails(self):
        """Test that verifying invalid number format fails"""
        with self.assertRaises(ValueError):
            self.service.verify_number("1234567890", "192.168.1.1", "device1", "user1")

    def test_initiate_verification(self):
        """Test initiating verification"""
        session = self.service.initiate_verification(
            msisdn="+1234567890",
            device_ip="192.168.1.1",
            device_id="device1",
            user_id="user1"
        )

        self.assertIsNotNone(session)
        self.assertEqual(session.status, VerificationStatus.PENDING)
        self.assertEqual(len(session.otp_code), 6)

    def test_complete_verification(self):
        """Test completing verification"""
        session = self.service.initiate_verification(
            msisdn="+1234567890",
            device_ip="192.168.1.1",
            device_id="device1",
            user_id="user1"
        )

        result = self.service.complete_verification(
            session_id=session.session_id,
            otp_code=session.otp_code,
            user_id="user1"
        )

        self.assertTrue(result.verified)
        self.assertEqual(result.status, VerificationStatus.VERIFIED)

    def test_complete_verification_invalid_otp(self):
        """Test completing verification with invalid OTP"""
        session = self.service.initiate_verification(
            msisdn="+1234567890",
            device_ip="192.168.1.1",
            device_id="device1",
            user_id="user1"
        )

        result = self.service.complete_verification(
            session_id=session.session_id,
            otp_code="000000",
            user_id="user1"
        )

        self.assertFalse(result.verified)
        self.assertEqual(result.status, VerificationStatus.FAILED)

    def test_calculate_fraud_score(self):
        """Test calculating fraud score"""
        # Add some failed attempts
        for i in range(5):
            self.service.audit_log.log(f"s{i}", "+1234567890", "192.168.1.1", "d1", "validate_otp", "failed")

        score = self.service.calculate_fraud_score("+1234567890", "user1")

        self.assertEqual(score.msisdn, "+1234567890")

    def test_get_audit_logs(self):
        """Test getting audit logs"""
        self.service.initiate_verification("+1234567890", "192.168.1.1", "device1", "user1")

        logs = self.service.get_audit_logs("+1234567890", "user1")
        self.assertGreater(len(logs), 0)

    def test_get_service_status(self):
        """Test getting service status"""
        status = self.service.get_service_status()

        self.assertEqual(status["service"], "Number Verification")
        self.assertEqual(status["status"], "operational")


if __name__ == "__main__":
    unittest.main()
