"""
Shared - API Gateway and Observability
"""

from .gateway import (
    HTTPMethod,
    AuthType,
    ErrorType,
    APIRoute,
    APIKey,
    OAuth2Token,
    RateLimitBucket,
    RequestLog,
    ErrorMapping,
    APIGateway,
    OAuth2Server,
    APIKeyManager,
    RateLimiter,
    RequestValidator,
    ResponseFormatter,
    ErrorMapper
)

from .observability import (
    HealthStatus,
    AlertSeverity,
    MetricDataPoint,
    HealthCheck,
    AuditLogEntry,
    TraceSpan,
    Alert,
    MetricsCollector,
    HealthCheckManager,
    AuditLogger,
    DistributedTracer,
    AlertEngine
)

__all__ = [
    # Gateway
    "HTTPMethod",
    "AuthType",
    "ErrorType",
    "APIRoute",
    "APIKey",
    "OAuth2Token",
    "RateLimitBucket",
    "RequestLog",
    "ErrorMapping",
    "APIGateway",
    "OAuth2Server",
    "APIKeyManager",
    "RateLimiter",
    "RequestValidator",
    "ResponseFormatter",
    "ErrorMapper",
    # Observability
    "HealthStatus",
    "AlertSeverity",
    "MetricDataPoint",
    "HealthCheck",
    "AuditLogEntry",
    "TraceSpan",
    "Alert",
    "MetricsCollector",
    "HealthCheckManager",
    "AuditLogger",
    "DistributedTracer",
    "AlertEngine"
]
