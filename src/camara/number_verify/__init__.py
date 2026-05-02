"""
CAMARA Number Verification API - Number Verification Service
Implements CAMARA Number Verification API standard
"""

import time
import random
import string
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum


class VerificationStatus(Enum):
    """Verification status"""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ConsentStatus(Enum):
    """Consent status"""
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass
class VerifyConsentRecord:
    """User consent record for number verification"""
    consent_id: str
    msisdn: str
    user_id: str
    status: ConsentStatus = ConsentStatus.PENDING
    granted_at: Optional[float] = None
    expires_at: Optional[float] = None
    scope: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class VerificationSession:
    """Verification session with TTL"""
    session_id: str
    msisdn: str
    device_ip: str
    device_id: str
    otp_code: str
    status: VerificationStatus = VerificationStatus.PENDING
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    verified_at: Optional[float] = None
    attempts: int = 0
    max_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Number verification result"""
    session_id: str
    msisdn: str
    verified: bool
    device_ip: str
    device_id: str
    timestamp: float
    status: VerificationStatus
    failure_reason: Optional[str] = None


@dataclass
class AuditLogEntry:
    """Audit trail entry for verification attempts"""
    log_id: str
    session_id: str
    msisdn: str
    device_ip: str
    device_id: str
    action: str
    result: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FraudScore:
    """Fraud score calculation result"""
    msisdn: str
    score: float
    risk_level: str
    factors: List[str]
    assessed_at: float = field(default_factory=time.time)


class PhoneNumberValidator:
    """Validates phone number format (E.164)"""

    def __init__(self):
        self._valid_country_codes = {
            "1", "7", "20", "27", "30", "31", "32", "33", "34", "36",
            "39", "40", "41", "43", "44", "45", "46", "47", "48", "49",
            "51", "52", "53", "54", "55", "56", "57", "58", "60", "61",
            "62", "63", "64", "65", "66", "81", "82", "84", "86", "90",
            "91", "92", "93", "94", "95", "98", "212", "213", "216", "218"
        }

    def validate(self, phone_number: str) -> bool:
        """Validate phone number in E.164 format"""
        if not phone_number:
            return False

        # Must start with +
        if not phone_number.startswith("+"):
            return False

        # Remove + and validate
        number = phone_number[1:]

        # Must be digits only
        if not number.isdigit():
            return False

        # Must be between 8 and 15 digits
        if len(number) < 8 or len(number) > 15:
            return False

        # Validate country code (optional)
        country_code = self._extract_country_code(number)
        if country_code and country_code not in self._valid_country_codes:
            return False

        return True

    def normalize(self, phone_number: str) -> str:
        """Normalize phone number to E.164 format"""
        number = phone_number.strip()

        # Add + if missing
        if not number.startswith("+"):
            number = "+" + number

        # Remove non-digit characters
        digits = "".join(c for c in number if c.isdigit())

        return "+" + digits

    def _extract_country_code(self, number: str) -> Optional[str]:
        """Extract country code from number"""
        # Try 1-digit country codes
        for code in ["1", "7"]:
            if number.startswith(code):
                return code

        # Try 2-digit country codes
        for code in ["20", "27", "30", "31", "32", "33", "34", "36",
                     "39", "40", "41", "43", "44", "45", "46", "47",
                     "48", "49", "51", "52", "53", "54", "55", "56",
                     "57", "58", "60", "61", "62", "63", "64", "65",
                     "66", "81", "82", "84", "86", "90", "91", "92",
                     "93", "94", "95", "98"]:
            if number.startswith(code):
                return code

        # Try 3-digit country codes
        for code in ["212", "213", "216", "218"]:
            if number.startswith(code):
                return code

        return None

    def get_country_code(self, phone_number: str) -> Optional[str]:
        """Get country code from phone number"""
        if not phone_number.startswith("+"):
            phone_number = self.normalize(phone_number)

        number = phone_number[1:]
        return self._extract_country_code(number)


class DeviceAssociationChecker:
    """Verifies device is associated with phone number"""

    def __init__(self):
        # Simulated device mappings
        self._msisdn_to_device: Dict[str, str] = {}
        self._device_to_msisdn: Dict[str, str] = {}
        self._ip_to_device: Dict[str, str] = {}

    def associate_device(self, msisdn: str, device_id: str, device_ip: str) -> None:
        """Associate device with MSISDN"""
        # Remove old associations
        if msisdn in self._msisdn_to_device:
            old_device = self._msisdn_to_device[msisdn]
            if old_device in self._device_to_msisdn:
                del self._device_to_msisdn[old_device]

        if device_id in self._device_to_msisdn:
            del self._msisdn_to_device[self._device_to_msisdn[device_id]]

        # Create new associations
        self._msisdn_to_device[msisdn] = device_id
        self._device_to_msisdn[device_id] = msisdn
        self._ip_to_device[device_ip] = device_id

    def get_device_for_msisdn(self, msisdn: str) -> Optional[str]:
        """Get device ID associated with MSISDN"""
        return self._msisdn_to_device.get(msisdn)

    def get_msisdn_for_device(self, device_id: str) -> Optional[str]:
        """Get MSISDN associated with device"""
        return self._device_to_msisdn.get(device_id)

    def get_device_for_ip(self, device_ip: str) -> Optional[str]:
        """Get device ID for IP address"""
        return self._ip_to_device.get(device_ip)

    def verify_association(self, msisdn: str, device_ip: str,
                          device_id: Optional[str] = None) -> bool:
        """Verify device is associated with MSISDN"""
        # Get device from IP
        ip_device = self.get_device_for_ip(device_ip)
        if not ip_device:
            return False

        # Check if device matches (if provided)
        if device_id and ip_device != device_id:
            return False

        # Check MSISDN association
        associated_msisdn = self.get_msisdn_for_device(ip_device)
        return associated_msisdn == msisdn

    def is_valid_ip(self, device_ip: str) -> bool:
        """Validate IP address format"""
        try:
            parts = device_ip.split(".")
            if len(parts) != 4:
                return False

            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False

            return True
        except (ValueError, AttributeError):
            return False


class OTPGenerator:
    """Generates and validates OTP codes for verification"""

    def __init__(self, code_length: int = 6, expiry_seconds: int = 300):
        self.code_length = code_length
        self.expiry_seconds = expiry_seconds

    def generate_code(self) -> str:
        """Generate random OTP code"""
        return "".join(random.choices(string.digits, k=self.code_length))

    def validate_code(self, provided_code: str, expected_code: str) -> bool:
        """Validate OTP code"""
        return provided_code == expected_code

    def is_expired(self, session: VerificationSession) -> bool:
        """Check if session is expired"""
        return time.time() > session.expires_at

    def get_remaining_time(self, session: VerificationSession) -> int:
        """Get remaining time in seconds"""
        remaining = int(session.expires_at - time.time())
        return max(0, remaining)


class VerificationSessionManager:
    """Manages verification sessions with TTL"""

    def __init__(self, otp_generator: OTPGenerator):
        self.otp_generator = otp_generator
        self._sessions: Dict[str, VerificationSession] = {}
        self._counter = 0

    def create_session(self, msisdn: str, device_ip: str,
                      device_id: str, ttl_seconds: int = 300) -> VerificationSession:
        """Create a new verification session"""
        session_id = self._generate_id("session")
        otp_code = self.otp_generator.generate_code()

        session = VerificationSession(
            session_id=session_id,
            msisdn=msisdn,
            device_ip=device_ip,
            device_id=device_id,
            otp_code=otp_code,
            expires_at=time.time() + ttl_seconds
        )

        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[VerificationSession]:
        """Get session by ID"""
        return self._sessions.get(session_id)

    def validate_otp(self, session_id: str, otp_code: str) -> VerificationSession:
        """Validate OTP code for session"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Check if expired
        if self.otp_generator.is_expired(session):
            session.status = VerificationStatus.EXPIRED
            raise ValueError(f"Session expired: {session_id}")

        # Check max attempts
        if session.attempts >= session.max_attempts:
            session.status = VerificationStatus.FAILED
            raise ValueError(f"Max attempts exceeded for session: {session_id}")

        # Validate OTP
        session.attempts += 1
        if self.otp_generator.validate_code(otp_code, session.otp_code):
            session.status = VerificationStatus.VERIFIED
            session.verified_at = time.time()
        else:
            session.status = VerificationStatus.FAILED

        return session

    def cancel_session(self, session_id: str) -> bool:
        """Cancel a verification session"""
        session = self.get_session(session_id)
        if session:
            session.status = VerificationStatus.CANCELLED
            return True
        return False

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        current_time = time.time()
        expired_ids = [
            sid for sid, session in self._sessions.items()
            if session.expires_at < current_time
        ]

        for sid in expired_ids:
            del self._sessions[sid]

        return len(expired_ids)

    def list_sessions(self, msisdn: Optional[str] = None,
                     status: Optional[VerificationStatus] = None) -> List[VerificationSession]:
        """List sessions, optionally filtered"""
        sessions = list(self._sessions.values())

        if msisdn:
            sessions = [s for s in sessions if s.msisdn == msisdn]

        if status:
            sessions = [s for s in sessions if s.status == status]

        # Sort by creation time (newest first)
        sessions.sort(key=lambda s: s.created_at, reverse=True)

        return sessions

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class VerificationAuditLog:
    """Audit trail for all verification attempts"""

    def __init__(self):
        self._logs: List[AuditLogEntry] = []
        self._counter = 0

    def log(self, session_id: str, msisdn: str, device_ip: str,
           device_id: str, action: str, result: str,
           metadata: Optional[Dict[str, Any]] = None) -> AuditLogEntry:
        """Log a verification attempt"""
        log_id = self._generate_id("log")
        entry = AuditLogEntry(
            log_id=log_id,
            session_id=session_id,
            msisdn=msisdn,
            device_ip=device_ip,
            device_id=device_id,
            action=action,
            result=result,
            metadata=metadata or {}
        )
        self._logs.append(entry)
        return entry

    def get_logs(self, msisdn: Optional[str] = None,
                session_id: Optional[str] = None,
                limit: int = 100) -> List[AuditLogEntry]:
        """Get audit logs, optionally filtered"""
        logs = self._logs.copy()

        if msisdn:
            logs = [l for l in logs if l.msisdn == msisdn]

        if session_id:
            logs = [l for l in logs if l.session_id == session_id]

        # Sort by timestamp (newest first)
        logs.sort(key=lambda l: l.timestamp, reverse=True)

        return logs[:limit]

    def get_failed_attempts(self, msisdn: str, hours: int = 24) -> int:
        """Count failed verification attempts"""
        cutoff = time.time() - (hours * 3600)
        return sum(
            1 for log in self._logs
            if log.msisdn == msisdn and log.result == "failed" and log.timestamp >= cutoff
        )

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class FraudScoreCalculator:
    """Calculates fraud score based on verification patterns"""

    def __init__(self, audit_log: VerificationAuditLog):
        self.audit_log = audit_log

    def calculate(self, msisdn: str) -> FraudScore:
        """Calculate fraud score for MSISDN"""
        score = 0.0
        factors = []

        # Factor 1: Failed attempts in last 24h
        failed_24h = self.audit_log.get_failed_attempts(msisdn, hours=24)
        if failed_24h > 10:
            score += 50.0
            factors.append(f"High number of failed attempts in 24h ({failed_24h})")
        elif failed_24h > 5:
            score += 30.0
            factors.append(f"Multiple failed attempts in 24h ({failed_24h})")
        elif failed_24h > 2:
            score += 10.0
            factors.append(f"Some failed attempts in 24h ({failed_24h})")

        # Factor 2: Failed attempts in last 1h
        failed_1h = self.audit_log.get_failed_attempts(msisdn, hours=1)
        if failed_1h > 5:
            score += 40.0
            factors.append(f"Rapid failed attempts in 1h ({failed_1h})")

        # Determine risk level
        if score >= 80:
            risk_level = "critical"
        elif score >= 60:
            risk_level = "high"
        elif score >= 30:
            risk_level = "medium"
        else:
            risk_level = "low"

        if not factors:
            factors.append("No suspicious patterns detected")

        return FraudScore(
            msisdn=msisdn,
            score=score,
            risk_level=risk_level,
            factors=factors
        )


class NumberVerificationService:
    """Main number verification API service"""

    def __init__(self):
        self.validator = PhoneNumberValidator()
        self.device_checker = DeviceAssociationChecker()
        self.otp_generator = OTPGenerator()
        self.session_manager = VerificationSessionManager(self.otp_generator)
        self.audit_log = VerificationAuditLog()
        self.fraud_calculator = FraudScoreCalculator(self.audit_log)
        self._consent_manager: Dict[str, VerifyConsentRecord] = {}
        self._consent_counter = 0

    def verify_number(self, msisdn: str, device_ip: str, device_id: str,
                     user_id: str) -> VerificationResult:
        """Verify phone number ownership"""
        # Validate MSISDN format
        if not self.validator.validate(msisdn):
            raise ValueError(f"Invalid MSISDN format: {msisdn}")

        # Normalize MSISDN
        msisdn = self.validator.normalize(msisdn)

        # Validate IP
        if not self.device_checker.is_valid_ip(device_ip):
            raise ValueError(f"Invalid IP address: {device_ip}")

        # Check consent
        self._validate_consent(msisdn, user_id)

        # Verify device association
        is_associated = self.device_checker.verify_association(msisdn, device_ip, device_id)

        # Log verification attempt
        result_str = "verified" if is_associated else "failed"
        self.audit_log.log(
            session_id="direct",
            msisdn=msisdn,
            device_ip=device_ip,
            device_id=device_id,
            action="verify_number",
            result=result_str
        )

        return VerificationResult(
            session_id="direct",
            msisdn=msisdn,
            verified=is_associated,
            device_ip=device_ip,
            device_id=device_id,
            timestamp=time.time(),
            status=VerificationStatus.VERIFIED if is_associated else VerificationStatus.FAILED,
            failure_reason=None if is_associated else "Device not associated with MSISDN"
        )

    def initiate_verification(self, msisdn: str, device_ip: str,
                             device_id: str, user_id: str,
                             ttl_seconds: int = 300) -> VerificationSession:
        """Initiate OTP-based verification"""
        # Validate MSISDN format
        if not self.validator.validate(msisdn):
            raise ValueError(f"Invalid MSISDN format: {msisdn}")

        # Normalize MSISDN
        msisdn = self.validator.normalize(msisdn)

        # Check consent
        self._validate_consent(msisdn, user_id)

        # Create session
        session = self.session_manager.create_session(msisdn, device_ip, device_id, ttl_seconds)

        # Log session creation
        self.audit_log.log(
            session_id=session.session_id,
            msisdn=msisdn,
            device_ip=device_ip,
            device_id=device_id,
            action="create_session",
            result="success"
        )

        return session

    def complete_verification(self, session_id: str, otp_code: str,
                             user_id: str) -> VerificationResult:
        """Complete verification with OTP code"""
        # Get session
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Validate OTP
        session = self.session_manager.validate_otp(session_id, otp_code)

        # Log verification attempt
        result_str = "verified" if session.status == VerificationStatus.VERIFIED else "failed"
        self.audit_log.log(
            session_id=session_id,
            msisdn=session.msisdn,
            device_ip=session.device_ip,
            device_id=session.device_id,
            action="validate_otp",
            result=result_str
        )

        return VerificationResult(
            session_id=session_id,
            msisdn=session.msisdn,
            verified=session.status == VerificationStatus.VERIFIED,
            device_ip=session.device_ip,
            device_id=session.device_id,
            timestamp=time.time(),
            status=session.status,
            failure_reason=None if session.status == VerificationStatus.VERIFIED else "Invalid OTP"
        )

    def register_device(self, msisdn: str, device_id: str, device_ip: str) -> None:
        """Register device to MSISDN"""
        # Validate MSISDN
        if not self.validator.validate(msisdn):
            raise ValueError(f"Invalid MSISDN format: {msisdn}")

        msisdn = self.validator.normalize(msisdn)
        self.device_checker.associate_device(msisdn, device_id, device_ip)

    def calculate_fraud_score(self, msisdn: str, user_id: str) -> FraudScore:
        """Calculate fraud score for MSISDN"""
        self._validate_consent(msisdn, user_id)
        return self.fraud_calculator.calculate(msisdn)

    def request_consent(self, msisdn: str, user_id: str,
                       scope: Optional[List[str]] = None,
                       expires_in_seconds: int = 86400) -> VerifyConsentRecord:
        """Request consent for verification"""
        consent_id = self._generate_consent_id()
        consent = VerifyConsentRecord(
            consent_id=consent_id,
            msisdn=msisdn,
            user_id=user_id,
            status=ConsentStatus.PENDING,
            scope=scope or ["number_verify"],
            expires_at=time.time() + expires_in_seconds
        )
        self._consent_manager[consent_id] = consent
        return consent

    def grant_consent(self, consent_id: str) -> VerifyConsentRecord:
        """Grant consent"""
        if consent_id not in self._consent_manager:
            raise ValueError(f"Consent not found: {consent_id}")

        consent = self._consent_manager[consent_id]
        consent.status = ConsentStatus.GRANTED
        consent.granted_at = time.time()
        return consent

    def get_audit_logs(self, msisdn: str, user_id: str,
                      limit: int = 100) -> List[AuditLogEntry]:
        """Get audit logs for MSISDN"""
        self._validate_consent(msisdn, user_id)
        return self.audit_log.get_logs(msisdn=msisdn, limit=limit)

    def _validate_consent(self, msisdn: str, user_id: str) -> None:
        """Validate consent exists"""
        # Find active consent
        for consent in reversed(list(self._consent_manager.values())):
            if (consent.msisdn == msisdn and
                consent.user_id == user_id and
                consent.status == ConsentStatus.GRANTED):

                # Check if expired
                if consent.expires_at and time.time() > consent.expires_at:
                    consent.status = ConsentStatus.EXPIRED
                    continue

                return

        raise PermissionError(f"No valid consent found for {msisdn}")

    def _generate_consent_id(self) -> str:
        """Generate unique consent ID"""
        self._consent_counter += 1
        return f"consent_{int(time.time() * 1000)}_{self._consent_counter}"

    def get_service_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "service": "Number Verification",
            "status": "operational",
            "active_sessions": len(self.session_manager.list_sessions()),
            "total_audit_logs": len(self.audit_log._logs),
            "registered_devices": len(self.device_checker._device_to_msisdn)
        }
