"""
Observability - Metrics, health checks, audit logging, tracing, alerting
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Callable
from enum import Enum
from collections import defaultdict, deque


class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricDataPoint:
    """Single metric data point"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class HealthCheck:
    """Health check definition"""
    check_id: str
    name: str
    subsystem: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check: float = 0.0
    response_time_ms: float = 0.0
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditLogEntry:
    """Comprehensive audit log entry"""
    log_id: str
    action: str
    actor: str
    resource_type: str
    resource_id: Optional[str]
    outcome: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class TraceSpan:
    """Distributed tracing span"""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "ok"
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Alert:
    """Alert definition"""
    alert_id: str
    name: str
    severity: AlertSeverity
    metric_name: str
    condition: str
    threshold: float
    triggered: bool = False
    triggered_at: Optional[float] = None
    resolved_at: Optional[float] = None
    message: str = ""


class MetricsCollector:
    """Collects API latency, throughput, error rates"""

    def __init__(self, max_points: int = 10000):
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points))
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def record_metric(self, name: str, value: float,
                     labels: Optional[Dict[str, str]] = None) -> None:
        """Record a metric data point"""
        metric_key = self._make_key(name, labels)

        with self._lock:
            self._metrics[metric_key].append(
                MetricDataPoint(
                    timestamp=time.time(),
                    value=value,
                    labels=labels or {}
                )
            )

    def increment_counter(self, name: str, value: int = 1,
                         labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter"""
        metric_key = self._make_key(name, labels)

        with self._lock:
            self._counters[metric_key] += value

    def set_gauge(self, name: str, value: float,
                 labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge value"""
        metric_key = self._make_key(name, labels)

        with self._lock:
            self._gauges[metric_key] = value

    def record_histogram(self, name: str, value: float,
                        labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram value"""
        metric_key = self._make_key(name, labels)

        with self._lock:
            self._histograms[metric_key].append(value)
            # Keep last 1000 values
            if len(self._histograms[metric_key]) > 1000:
                self._histograms[metric_key] = self._histograms[metric_key][-1000:]

    def get_metrics(self, name: str,
                   labels: Optional[Dict[str, str]] = None,
                   start_time: Optional[float] = None,
                   end_time: Optional[float] = None) -> List[MetricDataPoint]:
        """Get metric data points"""
        metric_key = self._make_key(name, labels)

        with self._lock:
            points = list(self._metrics.get(metric_key, []))

        if start_time:
            points = [p for p in points if p.timestamp >= start_time]

        if end_time:
            points = [p for p in points if p.timestamp <= end_time]

        return points

    def get_counter(self, name: str,
                   labels: Optional[Dict[str, str]] = None) -> int:
        """Get counter value"""
        metric_key = self._make_key(name, labels)

        with self._lock:
            return self._counters.get(metric_key, 0)

    def get_gauge(self, name: str,
                 labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value"""
        metric_key = self._make_key(name, labels)

        with self._lock:
            return self._gauges.get(metric_key)

    def get_histogram_stats(self, name: str,
                           labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics"""
        metric_key = self._make_key(name, labels)

        with self._lock:
            values = self._histograms.get(metric_key, [])

        if not values:
            return {}

        sorted_values = sorted(values)
        n = len(values)

        return {
            "count": n,
            "sum": sum(values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": sum(values) / n,
            "p50": sorted_values[int(n * 0.5)],
            "p95": sorted_values[int(n * 0.95)],
            "p99": sorted_values[int(n * 0.99)]
        }

    def calculate_rate(self, name: str, window_seconds: int = 60,
                      labels: Optional[Dict[str, str]] = None) -> float:
        """Calculate rate per second for a counter"""
        points = self.get_metrics(name, labels,
                                  start_time=time.time() - window_seconds)

        if not points:
            return 0.0

        first_value = points[0].value
        last_value = points[-1].value
        time_diff = points[-1].timestamp - points[0].timestamp

        if time_diff == 0:
            return 0.0

        return (last_value - first_value) / time_diff

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create metric key from name and labels"""
        if not labels:
            return name

        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


class HealthCheckManager:
    """Health checks for all subsystems"""

    def __init__(self):
        self._health_checks: Dict[str, HealthCheck] = {}
        self._check_functions: Dict[str, Callable[[], Dict[str, Any]]] = {}
        self._counter = 0

    def register_check(self, name: str, subsystem: str,
                      check_func: Callable[[], Dict[str, Any]]) -> HealthCheck:
        """Register a health check"""
        check_id = self._generate_id("check")

        health_check = HealthCheck(
            check_id=check_id,
            name=name,
            subsystem=subsystem
        )

        self._health_checks[check_id] = health_check
        self._check_functions[check_id] = check_func

        return health_check

    def run_check(self, check_id: str) -> HealthCheck:
        """Run a single health check"""
        health_check = self._health_checks.get(check_id)
        if not health_check:
            raise ValueError(f"Health check not found: {check_id}")

        check_func = self._check_functions.get(check_id)
        if not check_func:
            raise ValueError(f"Check function not found: {check_id}")

        # Run check
        start_time = time.time()
        try:
            result = check_func()
            response_time_ms = (time.time() - start_time) * 1000

            health_check.status = HealthStatus(result.get("status", "unknown"))
            health_check.message = result.get("message", "")
            health_check.metadata = result.get("metadata", {})

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            health_check.status = HealthStatus.UNHEALTHY
            health_check.message = str(e)

        health_check.response_time_ms = response_time_ms
        health_check.last_check = time.time()

        return health_check

    def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all health checks"""
        results = {}

        for check_id in self._health_checks:
            try:
                results[check_id] = self.run_check(check_id)
            except Exception as e:
                # Mark as unhealthy if check fails
                health_check = self._health_checks[check_id]
                health_check.status = HealthStatus.UNHEALTHY
                health_check.message = str(e)
                health_check.last_check = time.time()
                results[check_id] = health_check

        return results

    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status"""
        results = self.run_all_checks()

        statuses = [hc.status for hc in results.values()]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        else:
            return HealthStatus.DEGRADED

    def get_check(self, check_id: str) -> Optional[HealthCheck]:
        """Get health check by ID"""
        return self._health_checks.get(check_id)

    def list_checks(self, subsystem: Optional[str] = None) -> List[HealthCheck]:
        """List health checks, optionally by subsystem"""
        checks = list(self._health_checks.values())

        if subsystem:
            checks = [c for c in checks if c.subsystem == subsystem]

        return checks

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class AuditLogger:
    """Comprehensive audit logging"""

    def __init__(self, max_entries: int = 10000):
        self._logs: deque = deque(maxlen=max_entries)
        self._counter = 0
        self._lock = threading.Lock()

    def log(self, action: str, actor: str, resource_type: str,
           resource_id: Optional[str], outcome: str,
           details: Optional[Dict[str, Any]] = None,
           ip_address: Optional[str] = None,
           user_agent: Optional[str] = None) -> AuditLogEntry:
        """Log an audit event"""
        log_id = self._generate_id("audit")

        entry = AuditLogEntry(
            log_id=log_id,
            action=action,
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )

        with self._lock:
            self._logs.append(entry)

        return entry

    def query(self, action: Optional[str] = None,
             actor: Optional[str] = None,
             resource_type: Optional[str] = None,
             resource_id: Optional[str] = None,
             start_time: Optional[float] = None,
             end_time: Optional[float] = None,
             limit: int = 100) -> List[AuditLogEntry]:
        """Query audit logs"""
        with self._lock:
            logs = list(self._logs)

        # Apply filters
        if action:
            logs = [log for log in logs if log.action == action]

        if actor:
            logs = [log for log in logs if log.actor == actor]

        if resource_type:
            logs = [log for log in logs if log.resource_type == resource_type]

        if resource_id:
            logs = [log for log in logs if log.resource_id == resource_id]

        if start_time:
            logs = [log for log in logs if log.timestamp >= start_time]

        if end_time:
            logs = [log for log in logs if log.timestamp <= end_time]

        # Sort by timestamp (newest first) and limit
        logs.sort(key=lambda log: log.timestamp, reverse=True)

        return logs[:limit]

    def get_failure_count(self, action: Optional[str] = None,
                         hours: int = 24) -> int:
        """Count failed audit events"""
        cutoff = time.time() - (hours * 3600)

        with self._lock:
            logs = [log for log in self._logs
                   if log.outcome in ("failed", "error") and log.timestamp >= cutoff]

        if action:
            logs = [log for log in logs if log.action == action]

        return len(logs)

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class DistributedTracer:
    """Request tracing across subsystems"""

    def __init__(self):
        self._spans: Dict[str, TraceSpan] = {}
        self._active_traces: Dict[str, List[str]] = defaultdict(list)
        self._counter = 0
        self._lock = threading.Lock()

    def start_span(self, operation_name: str, trace_id: Optional[str] = None,
                  parent_span_id: Optional[str] = None,
                  tags: Optional[Dict[str, str]] = None) -> TraceSpan:
        """Start a new trace span"""
        span_id = self._generate_id("span")
        trace_id = trace_id or self._generate_id("trace")

        span = TraceSpan(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=time.time(),
            tags=tags or {}
        )

        with self._lock:
            self._spans[span_id] = span
            self._active_traces[trace_id].append(span_id)

        return span

    def finish_span(self, span_id: str, status: str = "ok") -> TraceSpan:
        """Finish a trace span"""
        with self._lock:
            span = self._spans.get(span_id)
            if not span:
                raise ValueError(f"Span not found: {span_id}")

            span.end_time = time.time()
            span.status = status

        return span

    def get_span(self, span_id: str) -> Optional[TraceSpan]:
        """Get span by ID"""
        return self._spans.get(span_id)

    def get_trace(self, trace_id: str) -> List[TraceSpan]:
        """Get all spans for a trace"""
        with self._lock:
            span_ids = self._active_traces.get(trace_id, [])

        return [self._spans[sid] for sid in span_ids if sid in self._spans]

    def add_span_log(self, span_id: str, message: str,
                     fields: Optional[Dict[str, Any]] = None) -> None:
        """Add a log entry to a span"""
        with self._lock:
            span = self._spans.get(span_id)
            if span:
                span.logs.append({
                    "timestamp": time.time(),
                    "message": message,
                    "fields": fields or {}
                })

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class AlertEngine:
    """Threshold-based alerting"""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self._alerts: Dict[str, Alert] = {}
        self._alert_handlers: List[Callable[[Alert], None]] = []
        self._counter = 0
        self._evaluation_interval = 60  # seconds

    def create_alert(self, name: str, severity: AlertSeverity,
                    metric_name: str, condition: str, threshold: float,
                    message: str = "") -> Alert:
        """Create an alert"""
        alert_id = self._generate_id("alert")

        alert = Alert(
            alert_id=alert_id,
            name=name,
            severity=severity,
            metric_name=metric_name,
            condition=condition,
            threshold=threshold,
            message=message
        )

        self._alerts[alert_id] = alert
        return alert

    def evaluate_alerts(self) -> List[Alert]:
        """Evaluate all alerts and trigger if needed"""
        triggered = []

        for alert in self._alerts.values():
            # Get current metric value
            value = self._get_metric_value(alert.metric_name)
            if value is None:
                continue

            # Check condition
            should_trigger = self._check_condition(value, alert.condition, alert.threshold)

            if should_trigger and not alert.triggered:
                # Trigger alert
                alert.triggered = True
                alert.triggered_at = time.time()
                triggered.append(alert)

                # Notify handlers
                for handler in self._alert_handlers:
                    try:
                        handler(alert)
                    except Exception:
                        pass

            elif not should_trigger and alert.triggered:
                # Resolve alert
                alert.triggered = False
                alert.resolved_at = time.time()

        return triggered

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        return self._alerts.get(alert_id)

    def list_alerts(self, severity: Optional[AlertSeverity] = None,
                    triggered_only: bool = False) -> List[Alert]:
        """List alerts"""
        alerts = list(self._alerts.values())

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if triggered_only:
            alerts = [a for a in alerts if a.triggered]

        return alerts

    def register_handler(self, handler: Callable[[Alert], None]) -> None:
        """Register an alert handler"""
        self._alert_handlers.append(handler)

    def _get_metric_value(self, metric_name: str) -> Optional[float]:
        """Get current metric value"""
        # Try gauge first
        value = self.metrics_collector.get_gauge(metric_name)
        if value is not None:
            return value

        # Try counter
        counter = self.metrics_collector.get_counter(metric_name)
        return float(counter)

    def _check_condition(self, value: float, condition: str,
                        threshold: float) -> bool:
        """Check if condition is met"""
        if condition == "gt":
            return value > threshold
        elif condition == "gte":
            return value >= threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "lte":
            return value <= threshold
        elif condition == "eq":
            return value == threshold
        elif condition == "ne":
            return value != threshold
        else:
            return False

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"
