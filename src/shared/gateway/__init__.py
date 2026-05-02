"""
API Gateway & Security - Request routing, authentication, rate limiting
"""

import time
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Callable
from enum import Enum
from collections import defaultdict, deque


class HTTPMethod(Enum):
    """HTTP methods"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class AuthType(Enum):
    """Authentication types"""
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT = "jwt"


class ErrorType(Enum):
    """Error types for mapping"""
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


@dataclass
class APIRoute:
    """API route definition"""
    route_id: str
    path: str
    method: HTTPMethod
    handler: str
    auth_required: bool = True
    auth_type: AuthType = AuthType.API_KEY
    rate_limit_per_minute: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIKey:
    """API key for authentication"""
    key_id: str
    key_value: str
    partner_id: str
    scopes: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    last_used_at: Optional[float] = None


@dataclass
class OAuth2Token:
    """OAuth2 token"""
    token_id: str
    access_token: str
    refresh_token: Optional[str]
    client_id: str
    user_id: str
    scopes: List[str] = field(default_factory=list)
    expires_at: float = 0
    created_at: float = field(default_factory=time.time)


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting"""
    bucket_id: str
    identifier: str
    capacity: int
    tokens: int
    last_refill: float
    refill_rate: float  # tokens per second


@dataclass
class RequestLog:
    """Request log entry"""
    log_id: str
    request_id: str
    path: str
    method: str
    partner_id: str
    status_code: int
    duration_ms: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class ErrorMapping:
    """Error mapping configuration"""
    error_type: ErrorType
    http_status: int
    tmf_code: Optional[str] = None
    camara_code: Optional[str] = None
    message_template: str = ""


class APIGateway:
    """Routes requests, handles authentication"""

    def __init__(self):
        self._routes: Dict[str, APIRoute] = {}
        self._request_log: List[RequestLog] = []
        self._counter = 0
        self._handlers: Dict[str, Callable] = {}

    def add_route(self, path: str, method: HTTPMethod, handler: str,
                  auth_required: bool = True,
                  auth_type: AuthType = AuthType.API_KEY,
                  rate_limit_per_minute: int = 60) -> APIRoute:
        """Add an API route"""
        route_id = self._generate_id("route")

        route = APIRoute(
            route_id=route_id,
            path=path,
            method=method,
            handler=handler,
            auth_required=auth_required,
            auth_type=auth_type,
            rate_limit_per_minute=rate_limit_per_minute
        )

        self._routes[route_id] = route
        return route

    def get_route(self, path: str, method: HTTPMethod) -> Optional[APIRoute]:
        """Get route for path and method"""
        for route in self._routes.values():
            if route.path == path and route.method == method:
                return route
        return None

    def list_routes(self) -> List[APIRoute]:
        """List all routes"""
        return list(self._routes.values())

    def register_handler(self, name: str, handler: Callable) -> None:
        """Register a request handler"""
        self._handlers[name] = handler

    def handle_request(self, path: str, method: str, headers: Dict[str, str],
                      body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle an incoming request"""
        request_id = self._generate_id("req")
        start_time = time.time()

        try:
            http_method = HTTPMethod(method)
            route = self.get_route(path, http_method)

            if not route:
                return self._error_response(ErrorType.NOT_FOUND, f"Route not found: {method} {path}")

            # Get handler
            handler = self._handlers.get(route.handler)
            if not handler:
                return self._error_response(ErrorType.INTERNAL_ERROR, f"Handler not found: {route.handler}")

            # Execute handler (simplified)
            result = handler(request_id, path, method, headers, body or {})

            # Log request
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_request(request_id, path, method, "unknown", result.get("status", 200), duration_ms)

            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_request(request_id, path, method, "unknown", 500, duration_ms)
            return self._error_response(ErrorType.INTERNAL_ERROR, str(e))

    def _error_response(self, error_type: ErrorType, message: str) -> Dict[str, Any]:
        """Generate error response"""
        mapper = ErrorMapper()
        mapping = mapper.get_mapping(error_type)

        return {
            "status": mapping.http_status,
            "error": {
                "type": error_type.value,
                "code": mapping.tmf_code or mapping.camara_code or error_type.value,
                "message": message or mapping.message_template,
                "timestamp": time.time()
            }
        }

    def _log_request(self, request_id: str, path: str, method: str,
                    partner_id: str, status_code: int, duration_ms: int) -> None:
        """Log a request"""
        log_id = self._generate_id("log")
        log = RequestLog(
            log_id=log_id,
            request_id=request_id,
            path=path,
            method=method,
            partner_id=partner_id,
            status_code=status_code,
            duration_ms=duration_ms
        )
        self._request_log.append(log)

    def get_request_logs(self, limit: int = 100) -> List[RequestLog]:
        """Get request logs"""
        return self._request_log[-limit:]

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class OAuth2Server:
    """OAuth2 token issuance and validation"""

    def __init__(self):
        self._tokens: Dict[str, OAuth2Token] = {}
        self._clients: Dict[str, Dict[str, Any]] = {}
        self._users: Dict[str, Dict[str, Any]] = {}
        self._counter = 0

    def register_client(self, client_id: str, client_secret: str,
                       redirect_uris: List[str], scopes: List[str]) -> None:
        """Register OAuth2 client"""
        self._clients[client_id] = {
            "client_secret": client_secret,
            "redirect_uris": redirect_uris,
            "scopes": scopes
        }

    def register_user(self, user_id: str, username: str, password: str) -> None:
        """Register user (simplified - in production use proper hashing)"""
        self._users[user_id] = {
            "username": username,
            "password": password
        }

    def issue_token(self, client_id: str, client_secret: str,
                   user_id: str, scopes: Optional[List[str]] = None,
                   expires_in_seconds: int = 3600) -> OAuth2Token:
        """Issue OAuth2 access token"""
        # Validate client
        client = self._clients.get(client_id)
        if not client or client["client_secret"] != client_secret:
            raise ValueError("Invalid client credentials")

        # Validate user
        if user_id not in self._users:
            raise ValueError("Invalid user")

        # Validate scopes
        valid_scopes = client["scopes"]
        if scopes:
            scopes = [s for s in scopes if s in valid_scopes]
        else:
            scopes = valid_scopes

        # Generate token
        token_id = self._generate_id("token")
        access_token = self._generate_token()
        refresh_token = self._generate_token()

        token = OAuth2Token(
            token_id=token_id,
            access_token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            user_id=user_id,
            scopes=scopes,
            expires_at=time.time() + expires_in_seconds
        )

        self._tokens[access_token] = token
        return token

    def validate_token(self, access_token: str) -> Optional[OAuth2Token]:
        """Validate OAuth2 access token"""
        token = self._tokens.get(access_token)
        if not token:
            return None

        # Check expiration
        if time.time() > token.expires_at:
            return None

        return token

    def refresh_token(self, refresh_token: str, client_id: str) -> OAuth2Token:
        """Refresh access token"""
        # Find token with refresh token
        token = None
        for t in self._tokens.values():
            if t.refresh_token == refresh_token and t.client_id == client_id:
                token = t
                break

        if not token:
            raise ValueError("Invalid refresh token")

        # Get client secret for re-issuance
        client = self._clients.get(client_id)
        if not client:
            raise ValueError("Client not found")

        # Issue new token
        return self.issue_token(
            client_id=client_id,
            client_secret=client["client_secret"],
            user_id=token.user_id,
            scopes=token.scopes
        )

    def revoke_token(self, access_token: str) -> bool:
        """Revoke access token"""
        if access_token in self._tokens:
            del self._tokens[access_token]
            return True
        return False

    def _generate_token(self) -> str:
        """Generate random token"""
        import random
        import string
        return "".join(random.choices(string.ascii_letters + string.digits, k=32))

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class APIKeyManager:
    """API key lifecycle management"""

    def __init__(self):
        self._api_keys: Dict[str, APIKey] = {}
        self._counter = 0

    def create_key(self, partner_id: str, scopes: Optional[List[str]] = None,
                  expires_in_seconds: Optional[int] = None) -> APIKey:
        """Create an API key"""
        key_id = self._generate_id("key")
        key_value = self._generate_key_value()

        key = APIKey(
            key_id=key_id,
            key_value=key_value,
            partner_id=partner_id,
            scopes=scopes or [],
            expires_at=time.time() + expires_in_seconds if expires_in_seconds else None
        )

        self._api_keys[key_value] = key
        return key

    def validate_key(self, key_value: str) -> Optional[APIKey]:
        """Validate API key"""
        key = self._api_keys.get(key_value)
        if not key:
            return None

        # Check if active
        if not key.is_active:
            return None

        # Check expiration
        if key.expires_at and time.time() > key.expires_at:
            return None

        # Update last used
        key.last_used_at = time.time()

        return key

    def revoke_key(self, key_value: str) -> bool:
        """Revoke API key"""
        key = self._api_keys.get(key_value)
        if key:
            key.is_active = False
            return True
        return False

    def list_keys(self, partner_id: str) -> List[APIKey]:
        """List keys for partner"""
        return [k for k in self._api_keys.values() if k.partner_id == partner_id]

    def _generate_key_value(self) -> str:
        """Generate random API key"""
        import random
        import string
        return "".join(random.choices(string.ascii_letters + string.digits, k=32))

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class RateLimiter:
    """Token bucket rate limiting per API/partner"""

    def __init__(self):
        self._buckets: Dict[str, RateLimitBucket] = {}

    def check_rate_limit(self, identifier: str, limit_per_minute: int) -> bool:
        """Check if request is within rate limit"""
        bucket_id = identifier

        # Get or create bucket
        if bucket_id not in self._buckets:
            self._buckets[bucket_id] = RateLimitBucket(
                bucket_id=bucket_id,
                identifier=identifier,
                capacity=limit_per_minute,
                tokens=limit_per_minute - 1,
                last_refill=time.time(),
                refill_rate=limit_per_minute / 60.0
            )
            return True

        bucket = self._buckets[bucket_id]

        # Refill tokens
        self._refill_bucket(bucket)

        # Check if tokens available
        if bucket.tokens > 0:
            bucket.tokens -= 1
            return True

        return False

    def _refill_bucket(self, bucket: RateLimitBucket) -> None:
        """Refill bucket based on elapsed time"""
        current_time = time.time()
        elapsed = current_time - bucket.last_refill

        tokens_to_add = int(elapsed * bucket.refill_rate)
        bucket.tokens = min(bucket.capacity, bucket.tokens + tokens_to_add)
        bucket.last_refill = current_time

    def reset_bucket(self, identifier: str) -> None:
        """Reset rate limit bucket"""
        if identifier in self._buckets:
            bucket = self._buckets[identifier]
            bucket.tokens = bucket.capacity
            bucket.last_refill = time.time()

    def get_bucket_status(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get bucket status"""
        if identifier not in self._buckets:
            return None

        bucket = self._buckets[identifier]
        self._refill_bucket(bucket)

        return {
            "identifier": identifier,
            "tokens_remaining": bucket.tokens,
            "capacity": bucket.capacity,
            "reset_in_seconds": max(0, int((bucket.capacity - bucket.tokens) / bucket.refill_rate))
        }


class RequestValidator:
    """Validates request schemas"""

    def __init__(self):
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def register_schema(self, name: str, schema: Dict[str, Any]) -> None:
        """Register a validation schema"""
        self._schemas[name] = schema

    def validate(self, data: Dict[str, Any], schema_name: str) -> tuple[bool, List[str]]:
        """Validate data against schema"""
        schema = self._schemas.get(schema_name)
        if not schema:
            return False, ["Schema not found"]

        errors = []

        # Required fields
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        # Field types
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field in data:
                expected_type = field_schema.get("type")
                if expected_type:
                    if not self._check_type(data[field], expected_type):
                        errors.append(f"Field '{field}' must be of type {expected_type}")

                # Enum validation
                if "enum" in field_schema:
                    if data[field] not in field_schema["enum"]:
                        errors.append(f"Field '{field}' must be one of {field_schema['enum']}")

        return len(errors) == 0, errors

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type"""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }

        expected_python_type = type_map.get(expected_type)
        if not expected_python_type:
            return True

        return isinstance(value, expected_python_type)


class ResponseFormatter:
    """Formats TMF/CAMARA standard responses"""

    def format_success(self, data: Any, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Format successful response"""
        response = {
            "status": "success",
            "data": data,
            "timestamp": time.time()
        }

        if request_id:
            response["request_id"] = request_id

        return response

    def format_error(self, error_type: str, message: str,
                    request_id: Optional[str] = None,
                    details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Format error response"""
        response = {
            "status": "error",
            "error": {
                "type": error_type,
                "message": message
            },
            "timestamp": time.time()
        }

        if request_id:
            response["request_id"] = request_id

        if details:
            response["error"]["details"] = details

        return response

    def format_paginated(self, items: List[Any], total: int,
                        offset: int, limit: int) -> Dict[str, Any]:
        """Format paginated response"""
        return {
            "items": items,
            "pagination": {
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": offset + limit < total
            },
            "timestamp": time.time()
        }


class ErrorMapper:
    """Maps internal errors to TMF645/CAMARA error codes"""

    def __init__(self):
        self._mappings: Dict[ErrorType, ErrorMapping] = {
            ErrorType.INVALID_REQUEST: ErrorMapping(
                error_type=ErrorType.INVALID_REQUEST,
                http_status=400,
                tmf_code="ERR_400",
                camara_code="INVALID_REQUEST",
                message_template="Invalid request"
            ),
            ErrorType.UNAUTHORIZED: ErrorMapping(
                error_type=ErrorType.UNAUTHORIZED,
                http_status=401,
                tmf_code="ERR_401",
                camara_code="UNAUTHORIZED",
                message_template="Unauthorized"
            ),
            ErrorType.FORBIDDEN: ErrorMapping(
                error_type=ErrorType.FORBIDDEN,
                http_status=403,
                tmf_code="ERR_403",
                camara_code="FORBIDDEN",
                message_template="Forbidden"
            ),
            ErrorType.NOT_FOUND: ErrorMapping(
                error_type=ErrorType.NOT_FOUND,
                http_status=404,
                tmf_code="ERR_404",
                camara_code="NOT_FOUND",
                message_template="Resource not found"
            ),
            ErrorType.RATE_LIMIT_EXCEEDED: ErrorMapping(
                error_type=ErrorType.RATE_LIMIT_EXCEEDED,
                http_status=429,
                tmf_code="ERR_429",
                camara_code="RATE_LIMIT_EXCEEDED",
                message_template="Rate limit exceeded"
            ),
            ErrorType.INTERNAL_ERROR: ErrorMapping(
                error_type=ErrorType.INTERNAL_ERROR,
                http_status=500,
                tmf_code="ERR_500",
                camara_code="INTERNAL_ERROR",
                message_template="Internal server error"
            ),
            ErrorType.SERVICE_UNAVAILABLE: ErrorMapping(
                error_type=ErrorType.SERVICE_UNAVAILABLE,
                http_status=503,
                tmf_code="ERR_503",
                camara_code="SERVICE_UNAVAILABLE",
                message_template="Service unavailable"
            )
        }

    def get_mapping(self, error_type: ErrorType) -> ErrorMapping:
        """Get error mapping"""
        return self._mappings.get(error_type, self._mappings[ErrorType.INTERNAL_ERROR])

    def map_exception(self, exception: Exception) -> ErrorMapping:
        """Map exception to error type"""
        error_str = str(exception).lower()

        if "not found" in error_str or "does not exist" in error_str:
            return self.get_mapping(ErrorType.NOT_FOUND)
        elif "unauthorized" in error_str or "permission" in error_str:
            return self.get_mapping(ErrorType.UNAUTHORIZED)
        elif "forbidden" in error_str:
            return self.get_mapping(ErrorType.FORBIDDEN)
        elif "rate limit" in error_str:
            return self.get_mapping(ErrorType.RATE_LIMIT_EXCEEDED)
        elif "invalid" in error_str or "validation" in error_str:
            return self.get_mapping(ErrorType.INVALID_REQUEST)
        else:
            return self.get_mapping(ErrorType.INTERNAL_ERROR)
