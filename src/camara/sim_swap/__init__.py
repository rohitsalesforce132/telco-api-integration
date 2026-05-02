"""
CAMARA SIM Swap API - SIM Swap Detection Service
Implements CAMARA SIM Swap Detection API standard
"""

import time
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum


class ConsentStatus(Enum):
    """Consent status for SIM swap checks"""
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


class SwapRiskLevel(Enum):
    """SIM swap fraud risk level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SwapConsentRecord:
    """User consent record for SIM swap checks"""
    consent_id: str
    msisdn: str
    user_id: str
    status: ConsentStatus = ConsentStatus.PENDING
    granted_at: Optional[float] = None
    expires_at: Optional[float] = None
    scope: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class SIMSwapEvent:
    """Recorded SIM swap event"""
    event_id: str
    msisdn: str
    old_sim_iccid: str
    new_sim_iccid: str
    swap_time: float
    location: Optional[Dict[str, Any]] = None
    verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SIMSwapStatus:
    """SIM swap status result"""
    msisdn: str
    swapped: bool
    swap_date: Optional[float] = None
    days_since_swap: Optional[int] = None
    verification_code: Optional[str] = None


@dataclass
class SwapRiskAssessment:
    """Risk assessment for SIM swap"""
    msisdn: str
    risk_level: SwapRiskLevel
    score: float
    factors: List[str]
    recommendation: str
    assessed_at: float = field(default_factory=time.time)


@dataclass
class SwapNotification:
    """SIM swap notification"""
    notification_id: str
    msisdn: str
    user_id: str
    message: str
    severity: str = "info"
    delivered: bool = False
    delivery_time: Optional[float] = None
    created_at: float = field(default_factory=time.time)


class SIMSwapConsentManager:
    """Manages user consent for SIM swap checks"""

    def __init__(self):
        self._consents: Dict[str, SwapConsentRecord] = {}
        self._counter = 0
        self._default_ttl = 86400  # 24 hours

    def request_consent(self, msisdn: str, user_id: str,
                       scope: Optional[List[str]] = None,
                       expires_in_seconds: Optional[int] = None) -> SwapConsentRecord:
        """Request consent from user"""
        consent_id = self._generate_id("consent")
        ttl = expires_in_seconds or self._default_ttl

        consent = SwapConsentRecord(
            consent_id=consent_id,
            msisdn=msisdn,
            user_id=user_id,
            status=ConsentStatus.PENDING,
            scope=scope or ["sim_swap_check"],
            expires_at=time.time() + ttl
        )
        self._consents[consent_id] = consent
        return consent

    def grant_consent(self, consent_id: str) -> SwapConsentRecord:
        """Grant consent"""
        if consent_id not in self._consents:
            raise ValueError(f"Consent not found: {consent_id}")

        consent = self._consents[consent_id]
        consent.status = ConsentStatus.GRANTED
        consent.granted_at = time.time()
        return consent

    def deny_consent(self, consent_id: str) -> SwapConsentRecord:
        """Deny consent"""
        if consent_id not in self._consents:
            raise ValueError(f"Consent not found: {consent_id}")

        consent = self._consents[consent_id]
        consent.status = ConsentStatus.DENIED
        return consent

    def revoke_consent(self, msisdn: str, user_id: str) -> bool:
        """Revoke consent for MSISDN"""
        for consent in self._consents.values():
            if consent.msisdn == msisdn and consent.user_id == user_id:
                if consent.status == ConsentStatus.GRANTED:
                    consent.status = ConsentStatus.REVOKED
                    return True
        return False

    def get_consent(self, msisdn: str, user_id: str) -> Optional[SwapConsentRecord]:
        """Get active consent for MSISDN and user"""
        # Find most recent granted consent
        for consent in reversed(list(self._consents.values())):
            if (consent.msisdn == msisdn and
                consent.user_id == user_id and
                consent.status == ConsentStatus.GRANTED):

                # Check if expired
                if consent.expires_at and time.time() > consent.expires_at:
                    consent.status = ConsentStatus.EXPIRED
                    continue

                return consent

        return None

    def validate_consent(self, msisdn: str, user_id: str) -> SwapConsentRecord:
        """Validate and return consent, raise if invalid"""
        consent = self.get_consent(msisdn, user_id)
        if not consent:
            raise PermissionError(f"No valid consent found for {msisdn}")
        return consent

    def list_consents(self, user_id: Optional[str] = None) -> List[SwapConsentRecord]:
        """List consents, optionally filtered by user"""
        consents = list(self._consents.values())

        if user_id:
            consents = [c for c in consents if c.user_id == user_id]

        return consents

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class SwapHistoryTracker:
    """Tracks SIM swap history per MSISDN"""

    def __init__(self):
        self._swap_events: Dict[str, List[SIMSwapEvent]] = {}
        self._counter = 0

    def record_swap(self, msisdn: str, old_sim_iccid: str, new_sim_iccid: str,
                   location: Optional[Dict[str, Any]] = None,
                   verified: bool = False) -> SIMSwapEvent:
        """Record a SIM swap event"""
        event_id = self._generate_id("swap")
        event = SIMSwapEvent(
            event_id=event_id,
            msisdn=msisdn,
            old_sim_iccid=old_sim_iccid,
            new_sim_iccid=new_sim_iccid,
            swap_time=time.time(),
            location=location or {},
            verified=verified
        )

        if msisdn not in self._swap_events:
            self._swap_events[msisdn] = []

        self._swap_events[msisdn].append(event)
        return event

    def get_swap_history(self, msisdn: str, limit: int = 10) -> List[SIMSwapEvent]:
        """Get swap history for MSISDN"""
        if msisdn not in self._swap_events:
            return []

        # Return most recent swaps first
        history = sorted(self._swap_events[msisdn], key=lambda x: x.swap_time, reverse=True)
        return history[:limit]

    def get_most_recent_swap(self, msisdn: str) -> Optional[SIMSwapEvent]:
        """Get the most recent swap event"""
        history = self.get_swap_history(msisdn, limit=1)
        return history[0] if history else None

    def has_swapped_recently(self, msisdn: str, days: int = 30) -> bool:
        """Check if MSISDN has swapped SIM within specified days"""
        most_recent = self.get_most_recent_swap(msisdn)
        if not most_recent:
            return False

        days_since = (time.time() - most_recent.swap_time) / 86400
        return days_since <= days

    def get_swap_count(self, msisdn: str, days: int = 90) -> int:
        """Get number of swaps within specified days"""
        if msisdn not in self._swap_events:
            return 0

        cutoff = time.time() - (days * 86400)
        return sum(1 for event in self._swap_events[msisdn] if event.swap_time >= cutoff)

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class CarrierBackend:
    """Simulates carrier backend for SIM swap status"""

    def __init__(self):
        # Simulated SIM mappings
        self._msisdn_to_sim: Dict[str, str] = {}
        self._sim_to_msisdn: Dict[str, str] = {}
        self._counter = 0

    def register_msisdn(self, msisdn: str, sim_iccid: str) -> None:
        """Register MSISDN to SIM ICCID"""
        # Remove old mapping if exists
        if msisdn in self._msisdn_to_sim:
            old_sim = self._msisdn_to_sim[msisdn]
            if old_sim in self._sim_to_msisdn:
                del self._sim_to_msisdn[old_sim]

        self._msisdn_to_sim[msisdn] = sim_iccid
        self._sim_to_msisdn[sim_iccid] = msisdn

    def get_current_sim(self, msisdn: str) -> Optional[str]:
        """Get current SIM ICCID for MSISDN"""
        return self._msisdn_to_sim.get(msisdn)

    def get_msisdn_for_sim(self, sim_iccid: str) -> Optional[str]:
        """Get MSISDN for SIM ICCID"""
        return self._sim_to_msisdn.get(sim_iccid)

    def perform_sim_swap(self, msisdn: str, new_sim_iccid: str,
                        history_tracker: SwapHistoryTracker) -> SIMSwapEvent:
        """Perform a SIM swap operation"""
        old_sim = self._msisdn_to_sim.get(msisdn)

        if old_sim == new_sim_iccid:
            raise ValueError("New SIM ICCID is the same as current SIM")

        if old_sim:
            event = history_tracker.record_swap(
                msisdn=msisdn,
                old_sim_iccid=old_sim,
                new_sim_iccid=new_sim_iccid,
                verified=True
            )

        self.register_msisdn(msisdn, new_sim_iccid)
        return event

    def is_valid_msisdn(self, msisdn: str) -> bool:
        """Check if MSISDN is valid and registered"""
        return msisdn in self._msisdn_to_sim

    def list_all_msisdns(self) -> List[str]:
        """List all registered MSISDNs"""
        return list(self._msisdn_to_sim.keys())


class SwapRiskAssessor:
    """Assesses fraud risk based on swap recency and patterns"""

    def __init__(self, history_tracker: SwapHistoryTracker):
        self.history_tracker = history_tracker

    def assess_risk(self, msisdn: str) -> SwapRiskAssessment:
        """Assess fraud risk for MSISDN"""
        factors = []
        score = 0.0

        # Factor 1: Recent swap (within 7 days)
        most_recent = self.history_tracker.get_most_recent_swap(msisdn)
        if most_recent:
            days_since = (time.time() - most_recent.swap_time) / 86400

            if days_since <= 1:
                score += 50.0
                factors.append("SIM swapped within 1 day")
            elif days_since <= 7:
                score += 30.0
                factors.append("SIM swapped within 7 days")
            elif days_since <= 30:
                score += 10.0
                factors.append("SIM swapped within 30 days")
        else:
            factors.append("No recent SIM swap history")

        # Factor 2: Multiple swaps
        swap_count_90 = self.history_tracker.get_swap_count(msisdn, days=90)
        if swap_count_90 > 3:
            score += 40.0
            factors.append(f"Multiple swaps in 90 days ({swap_count_90})")
        elif swap_count_90 > 1:
            score += 20.0
            factors.append(f"Multiple swaps in 90 days ({swap_count_90})")

        # Factor 3: Verification status
        if most_recent and not most_recent.verified:
            score += 15.0
            factors.append("Most recent swap not verified")

        # Determine risk level
        if score >= 80:
            risk_level = SwapRiskLevel.CRITICAL
            recommendation = "Block all transactions, require manual verification"
        elif score >= 60:
            risk_level = SwapRiskLevel.HIGH
            recommendation = "Require additional authentication steps"
        elif score >= 30:
            risk_level = SwapRiskLevel.MEDIUM
            recommendation = "Enhanced monitoring recommended"
        else:
            risk_level = SwapRiskLevel.LOW
            recommendation = "Normal processing"

        return SwapRiskAssessment(
            msisdn=msisdn,
            risk_level=risk_level,
            score=score,
            factors=factors,
            recommendation=recommendation
        )

    def get_risk_threshold(self, risk_level: SwapRiskLevel) -> float:
        """Get risk score threshold for level"""
        thresholds = {
            SwapRiskLevel.LOW: 0,
            SwapRiskLevel.MEDIUM: 30,
            SwapRiskLevel.HIGH: 60,
            SwapRiskLevel.CRITICAL: 80
        }
        return thresholds.get(risk_level, 0)

    def is_risk_acceptable(self, msisdn: str,
                          max_risk_level: SwapRiskLevel = SwapRiskLevel.MEDIUM) -> bool:
        """Check if risk is acceptable"""
        assessment = self.assess_risk(msisdn)
        threshold = self.get_risk_threshold(max_risk_level)
        return assessment.score < threshold


class SwapNotificationEngine:
    """Sends notifications on SIM swap events"""

    def __init__(self):
        self._notifications: Dict[str, SwapNotification] = {}
        self._counter = 0

    def send_notification(self, msisdn: str, user_id: str, message: str,
                         severity: str = "info") -> SwapNotification:
        """Send a SIM swap notification"""
        notification_id = self._generate_id("notif")
        notification = SwapNotification(
            notification_id=notification_id,
            msisdn=msisdn,
            user_id=user_id,
            message=message,
            severity=severity,
            delivered=False
        )
        self._notifications[notification_id] = notification

        # Simulate delivery
        notification.delivered = True
        notification.delivery_time = time.time()

        return notification

    def get_notifications(self, user_id: Optional[str] = None,
                         msisdn: Optional[str] = None) -> List[SwapNotification]:
        """Get notifications, optionally filtered"""
        notifications = list(self._notifications.values())

        if user_id:
            notifications = [n for n in notifications if n.user_id == user_id]

        if msisdn:
            notifications = [n for n in notifications if n.msisdn == msisdn]

        # Sort by creation time (newest first)
        notifications.sort(key=lambda n: n.created_at, reverse=True)

        return notifications

    def get_undelivered_notifications(self) -> List[SwapNotification]:
        """Get undelivered notifications"""
        return [n for n in self._notifications.values() if not n.delivered]

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class SIMSwapDetector:
    """Detects recent SIM swap events for a phone number"""

    def __init__(self, consent_manager: SIMSwapConsentManager,
                 history_tracker: SwapHistoryTracker,
                 carrier_backend: CarrierBackend):
        self.consent_manager = consent_manager
        self.history_tracker = history_tracker
        self.carrier_backend = carrier_backend

    def check_sim_swap(self, msisdn: str, user_id: str) -> SIMSwapStatus:
        """Check if SIM was recently swapped"""
        # Validate consent
        self.consent_manager.validate_consent(msisdn, user_id)

        # Get most recent swap
        most_recent = self.history_tracker.get_most_recent_swap(msisdn)

        if not most_recent:
            return SIMSwapStatus(
                msisdn=msisdn,
                swapped=False
            )

        # Calculate days since swap
        days_since = int((time.time() - most_recent.swap_time) / 86400)

        return SIMSwapStatus(
            msisdn=msisdn,
            swapped=True,
            swap_date=most_recent.swap_time,
            days_since_swap=days_since
        )

    def check_sim_swap_with_max_age(self, msisdn: str, user_id: str,
                                    max_days: int = 30) -> SIMSwapStatus:
        """Check if SIM was swapped within max days"""
        status = self.check_sim_swap(msisdn, user_id)

        if not status.swapped:
            return status

        if status.days_since_swap and status.days_since_swap <= max_days:
            return status

        # Swap occurred but outside max days
        return SIMSwapStatus(
            msisdn=msisdn,
            swapped=False
        )


class SIMSwapService:
    """Main SIM swap detection API service"""

    def __init__(self):
        self.consent_manager = SIMSwapConsentManager()
        self.history_tracker = SwapHistoryTracker()
        self.carrier_backend = CarrierBackend()
        self.risk_assessor = SwapRiskAssessor(self.history_tracker)
        self.notification_engine = SwapNotificationEngine()
        self.detector = SIMSwapDetector(
            self.consent_manager,
            self.history_tracker,
            self.carrier_backend
        )

    def check_sim_swap(self, msisdn: str, user_id: str) -> SIMSwapStatus:
        """Check SIM swap status for MSISDN"""
        return self.detector.check_sim_swap(msisdn, user_id)

    def check_sim_swap_with_max_age(self, msisdn: str, user_id: str,
                                    max_days: int = 30) -> SIMSwapStatus:
        """Check SIM swap status with maximum age filter"""
        return self.detector.check_sim_swap_with_max_age(msisdn, user_id, max_days)

    def request_consent(self, msisdn: str, user_id: str,
                       scope: Optional[List[str]] = None) -> SwapConsentRecord:
        """Request consent for SIM swap check"""
        return self.consent_manager.request_consent(msisdn, user_id, scope)

    def grant_consent(self, consent_id: str) -> SwapConsentRecord:
        """Grant consent"""
        return self.consent_manager.grant_consent(consent_id)

    def assess_risk(self, msisdn: str, user_id: str) -> SwapRiskAssessment:
        """Assess fraud risk"""
        # Validate consent
        self.consent_manager.validate_consent(msisdn, user_id)
        return self.risk_assessor.assess_risk(msisdn)

    def get_swap_history(self, msisdn: str, user_id: str,
                        limit: int = 10) -> List[SIMSwapEvent]:
        """Get swap history for MSISDN"""
        self.consent_manager.validate_consent(msisdn, user_id)
        return self.history_tracker.get_swap_history(msisdn, limit)

    def send_swap_notification(self, msisdn: str, user_id: str,
                              message: str) -> SwapNotification:
        """Send SIM swap notification"""
        return self.notification_engine.send_notification(msisdn, user_id, message)

    def register_msisdn(self, msisdn: str, sim_iccid: str) -> None:
        """Register MSISDN to SIM (carrier operation)"""
        self.carrier_backend.register_msisdn(msisdn, sim_iccid)

    def perform_sim_swap(self, msisdn: str, new_sim_iccid: str,
                        notify_user: bool = True) -> SIMSwapEvent:
        """Perform SIM swap operation"""
        # Perform swap
        event = self.carrier_backend.perform_sim_swap(msisdn, new_sim_iccid, self.history_tracker)

        # Send notification if requested
        if notify_user:
            self.notification_engine.send_notification(
                msisdn=msisdn,
                user_id="system",
                message=f"SIM swap detected for {msisdn}. If you did not initiate this, contact support immediately.",
                severity="high"
            )

        return event

    def is_risk_acceptable(self, msisdn: str, user_id: str,
                          max_risk_level: SwapRiskLevel = SwapRiskLevel.MEDIUM) -> bool:
        """Check if risk is acceptable"""
        self.consent_manager.validate_consent(msisdn, user_id)
        return self.risk_assessor.is_risk_acceptable(msisdn, max_risk_level)

    def get_service_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "service": "SIM Swap Detection",
            "status": "operational",
            "registered_msisdns": len(self.carrier_backend.list_all_msisdns()),
            "total_swap_events": sum(len(events) for events in self.history_tracker._swap_events.values()),
            "active_consents": len([c for c in self.consent_manager.list_consents() if c.status == ConsentStatus.GRANTED])
        }
