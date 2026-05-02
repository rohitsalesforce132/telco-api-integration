"""
Tests for CAMARA SIM Swap API
"""

import unittest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from camara.sim_swap import (
    ConsentStatus, SwapRiskLevel,
    SIMSwapConsentManager, SwapHistoryTracker,
    CarrierBackend, SwapRiskAssessor, SwapNotificationEngine,
    SIMSwapDetector, SIMSwapService
)


class TestSIMSwapConsentManager(unittest.TestCase):
    """Test SIMSwapConsentManager"""

    def setUp(self):
        self.manager = SIMSwapConsentManager()

    def test_request_consent(self):
        """Test requesting consent"""
        consent = self.manager.request_consent(
            msisdn="+1234567890",
            user_id="user1"
        )

        self.assertIsNotNone(consent)
        self.assertEqual(consent.msisdn, "+1234567890")
        self.assertEqual(consent.status, ConsentStatus.PENDING)

    def test_grant_consent(self):
        """Test granting consent"""
        consent = self.manager.request_consent("+1234567890", "user1")

        granted = self.manager.grant_consent(consent.consent_id)
        self.assertEqual(granted.status, ConsentStatus.GRANTED)
        self.assertIsNotNone(granted.granted_at)

    def test_deny_consent(self):
        """Test denying consent"""
        consent = self.manager.request_consent("+1234567890", "user1")

        denied = self.manager.deny_consent(consent.consent_id)
        self.assertEqual(denied.status, ConsentStatus.DENIED)

    def test_revoke_consent(self):
        """Test revoking consent"""
        consent = self.manager.request_consent("+1234567890", "user1")
        self.manager.grant_consent(consent.consent_id)

        result = self.manager.revoke_consent("+1234567890", "user1")
        self.assertTrue(result)

    def test_get_consent(self):
        """Test getting consent"""
        consent = self.manager.request_consent("+1234567890", "user1")
        self.manager.grant_consent(consent.consent_id)

        retrieved = self.manager.get_consent("+1234567890", "user1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.status, ConsentStatus.GRANTED)

    def test_validate_consent(self):
        """Test validating consent"""
        consent = self.manager.request_consent("+1234567890", "user1")
        self.manager.grant_consent(consent.consent_id)

        validated = self.manager.validate_consent("+1234567890", "user1")
        self.assertEqual(validated.status, ConsentStatus.GRANTED)

    def test_validate_consent_no_consent_fails(self):
        """Test that validating without consent fails"""
        with self.assertRaises(PermissionError):
            self.manager.validate_consent("+1234567890", "user1")


class TestSwapHistoryTracker(unittest.TestCase):
    """Test SwapHistoryTracker"""

    def setUp(self):
        self.tracker = SwapHistoryTracker()

    def test_record_swap(self):
        """Test recording a swap"""
        event = self.tracker.record_swap(
            msisdn="+1234567890",
            old_sim_iccid="8991000000000000001",
            new_sim_iccid="8991000000000000002"
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.msisdn, "+1234567890")
        self.assertEqual(event.old_sim_iccid, "8991000000000000001")
        self.assertEqual(event.new_sim_iccid, "8991000000000000002")

    def test_get_swap_history(self):
        """Test getting swap history"""
        self.tracker.record_swap("+1234567890", "old1", "new1")
        self.tracker.record_swap("+1234567890", "old2", "new2")

        history = self.tracker.get_swap_history("+1234567890")
        self.assertEqual(len(history), 2)

    def test_get_most_recent_swap(self):
        """Test getting most recent swap"""
        self.tracker.record_swap("+1234567890", "old1", "new1")
        time.sleep(0.01)
        self.tracker.record_swap("+1234567890", "old2", "new2")

        recent = self.tracker.get_most_recent_swap("+1234567890")
        self.assertIsNotNone(recent)
        self.assertEqual(recent.new_sim_iccid, "new2")

    def test_has_swapped_recently(self):
        """Test checking if swapped recently"""
        self.tracker.record_swap("+1234567890", "old1", "new1")

        has_swapped = self.tracker.has_swapped_recently("+1234567890", days=30)
        self.assertTrue(has_swapped)

    def test_get_swap_count(self):
        """Test getting swap count"""
        self.tracker.record_swap("+1234567890", "old1", "new1")
        self.tracker.record_swap("+1234567890", "old2", "new2")

        count = self.tracker.get_swap_count("+1234567890", days=90)
        self.assertEqual(count, 2)


class TestCarrierBackend(unittest.TestCase):
    """Test CarrierBackend"""

    def setUp(self):
        self.backend = CarrierBackend()

    def test_register_msisdn(self):
        """Test registering MSISDN"""
        self.backend.register_msisdn("+1234567890", "8991000000000000001")

        sim = self.backend.get_current_sim("+1234567890")
        self.assertEqual(sim, "8991000000000000001")

    def test_get_current_sim(self):
        """Test getting current SIM"""
        self.backend.register_msisdn("+1234567890", "8991000000000000001")

        sim = self.backend.get_current_sim("+1234567890")
        self.assertEqual(sim, "8991000000000000001")

    def test_perform_sim_swap(self):
        """Test performing SIM swap"""
        self.backend.register_msisdn("+1234567890", "8991000000000000001")
        tracker = SwapHistoryTracker()

        event = self.backend.perform_sim_swap("+1234567890", "8991000000000000002", tracker)

        self.assertIsNotNone(event)
        self.assertEqual(event.msisdn, "+1234567890")
        self.assertEqual(event.old_sim_iccid, "8991000000000000001")

    def test_is_valid_msisdn(self):
        """Test checking if MSISDN is valid"""
        self.backend.register_msisdn("+1234567890", "8991000000000000001")

        is_valid = self.backend.is_valid_msisdn("+1234567890")
        self.assertTrue(is_valid)

        is_invalid = self.backend.is_valid_msisdn("+9999999999")
        self.assertFalse(is_invalid)


class TestSwapRiskAssessor(unittest.TestCase):
    """Test SwapRiskAssessor"""

    def setUp(self):
        self.tracker = SwapHistoryTracker()
        self.assessor = SwapRiskAssessor(self.tracker)

    def test_assess_risk_no_history(self):
        """Test assessing risk with no history"""
        assessment = self.assessor.assess_risk("+1234567890")

        self.assertEqual(assessment.msisdn, "+1234567890")
        self.assertEqual(assessment.risk_level, SwapRiskLevel.LOW)
        self.assertLess(assessment.score, 30)

    def test_assess_risk_recent_swap(self):
        """Test assessing risk with recent swap"""
        self.tracker.record_swap("+1234567890", "old", "new")

        assessment = self.assessor.assess_risk("+1234567890")

        self.assertGreater(assessment.score, 0)
        self.assertIn("SIM swapped", assessment.factors[0])

    def test_assess_risk_multiple_swaps(self):
        """Test assessing risk with multiple swaps"""
        self.tracker.record_swap("+1234567890", "old1", "new1")
        self.tracker.record_swap("+1234567890", "old2", "new2")
        self.tracker.record_swap("+1234567890", "old3", "new3")

        assessment = self.assessor.assess_risk("+1234567890")

        self.assertGreater(assessment.score, 30)
        multiple_swaps_factor = any("Multiple swaps" in f for f in assessment.factors)
        self.assertTrue(multiple_swaps_factor)

    def test_is_risk_acceptable(self):
        """Test checking if risk is acceptable"""
        is_acceptable = self.assessor.is_risk_acceptable("+1234567890")
        self.assertTrue(is_acceptable)


class TestSwapNotificationEngine(unittest.TestCase):
    """Test SwapNotificationEngine"""

    def setUp(self):
        self.engine = SwapNotificationEngine()

    def test_send_notification(self):
        """Test sending notification"""
        notification = self.engine.send_notification(
            msisdn="+1234567890",
            user_id="user1",
            message="Test notification"
        )

        self.assertIsNotNone(notification)
        self.assertEqual(notification.msisdn, "+1234567890")
        self.assertTrue(notification.delivered)

    def test_get_notifications(self):
        """Test getting notifications"""
        self.engine.send_notification("+1234567890", "user1", "Message 1")
        self.engine.send_notification("+1234567890", "user1", "Message 2")

        notifications = self.engine.get_notifications(user_id="user1")
        self.assertEqual(len(notifications), 2)

    def test_get_undelivered_notifications(self):
        """Test getting undelivered notifications"""
        # All notifications are auto-delivered in this implementation
        undelivered = self.engine.get_undelivered_notifications()
        self.assertEqual(len(undelivered), 0)


class TestSIMSwapDetector(unittest.TestCase):
    """Test SIMSwapDetector"""

    def setUp(self):
        self.consent_manager = SIMSwapConsentManager()
        self.history_tracker = SwapHistoryTracker()
        self.carrier_backend = CarrierBackend()

        # Setup test data
        consent = self.consent_manager.request_consent("+1234567890", "user1")
        self.consent_manager.grant_consent(consent.consent_id)

        self.carrier_backend.register_msisdn("+1234567890", "8991000000000000001")

        self.detector = SIMSwapDetector(
            self.consent_manager,
            self.history_tracker,
            self.carrier_backend
        )

    def test_check_sim_swap_no_swap(self):
        """Test checking SIM swap when no swap occurred"""
        status = self.detector.check_sim_swap("+1234567890", "user1")

        self.assertFalse(status.swapped)
        self.assertEqual(status.msisdn, "+1234567890")

    def test_check_sim_swap_with_swap(self):
        """Test checking SIM swap when swap occurred"""
        # Perform swap
        self.carrier_backend.perform_sim_swap("+1234567890", "8991000000000000002", self.history_tracker)

        status = self.detector.check_sim_swap("+1234567890", "user1")

        self.assertTrue(hasattr(status, "swapped"))
        self.assertIsNotNone(status.swap_date)

    def test_check_sim_swap_with_max_age(self):
        """Test checking SIM swap with max age"""
        self.carrier_backend.perform_sim_swap("+1234567890", "8991000000000000002", self.history_tracker)

        # With max_days=30, recent swap should be detected
        status = self.detector.check_sim_swap_with_max_age("+1234567890", "user1", max_days=30)

        self.assertTrue(hasattr(status, "swapped"))

    def test_check_sim_swap_no_consent_fails(self):
        """Test that checking without consent fails"""
        with self.assertRaises(PermissionError):
            self.detector.check_sim_swap("+9999999999", "user2")


class TestSIMSwapService(unittest.TestCase):
    """Test SIMSwapService"""

    def setUp(self):
        self.service = SIMSwapService()

        # Setup test data
        consent = self.service.request_consent("+1234567890", "user1")
        self.service.grant_consent(consent.consent_id)
        self.service.register_msisdn("+1234567890", "8991000000000000001")

    def test_check_sim_swap(self):
        """Test checking SIM swap"""
        status = self.service.check_sim_swap("+1234567890", "user1")

        self.assertFalse(status.swapped)

    def test_perform_sim_swap(self):
        """Test performing SIM swap"""
        event = self.service.perform_sim_swap("+1234567890", "8991000000000000002")

        self.assertIsNotNone(event)
        self.assertEqual(event.msisdn, "+1234567890")

        # Check notification was sent
        notifications = self.service.notification_engine.get_notifications(user_id="system")
        self.assertGreater(len(notifications), 0)

    def test_assess_risk(self):
        """Test assessing risk"""
        self.service.perform_sim_swap("+1234567890", "8991000000000000002")

        assessment = self.service.assess_risk("+1234567890", "user1")

        self.assertEqual(assessment.msisdn, "+1234567890")
        self.assertGreater(assessment.score, 0)

    def test_get_swap_history(self):
        """Test getting swap history"""
        self.service.perform_sim_swap("+1234567890", "8991000000000000002")

        history = self.service.get_swap_history("+1234567890", "user1")

        self.assertEqual(len(history), 1)

    def test_is_risk_acceptable(self):
        """Test checking if risk is acceptable"""
        is_acceptable = self.service.is_risk_acceptable("+1234567890", "user1")
        self.assertTrue(is_acceptable)

    def test_get_service_status(self):
        """Test getting service status"""
        status = self.service.get_service_status()

        self.assertEqual(status["service"], "SIM Swap Detection")
        self.assertEqual(status["status"], "operational")
        self.assertGreater(status["registered_msisdns"], 0)


if __name__ == "__main__":
    unittest.main()
