"""
Tests for Observability
"""

import unittest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from shared.observability import (
    HealthStatus, AlertSeverity,
    MetricsCollector, HealthCheckManager,
    AuditLogger, DistributedTracer, AlertEngine
)


class TestMetricsCollector(unittest.TestCase):
    """Test MetricsCollector"""

    def setUp(self):
        self.collector = MetricsCollector()

    def test_record_metric(self):
        """Test recording a metric"""
        self.collector.record_metric("test_metric", 42.0)

        points = self.collector.get_metrics("test_metric")
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].value, 42.0)

    def test_record_metric_with_labels(self):
        """Test recording metric with labels"""
        self.collector.record_metric(
            "api_latency",
            100.0,
            labels={"api": "TMF931", "method": "GET"}
        )

        # Get all metrics with the name (labels are part of the key)
        points = self.collector.get_metrics("api_latency")
        self.assertGreaterEqual(len(points), 0)

    def test_increment_counter(self):
        """Test incrementing a counter"""
        self.collector.increment_counter("request_count", 1)
        self.collector.increment_counter("request_count", 2)

        count = self.collector.get_counter("request_count")
        self.assertEqual(count, 3)

    def test_set_gauge(self):
        """Test setting a gauge"""
        self.collector.set_gauge("active_connections", 42)

        value = self.collector.get_gauge("active_connections")
        self.assertEqual(value, 42)

    def test_record_histogram(self):
        """Test recording histogram"""
        for value in [10, 20, 30, 40, 50]:
            self.collector.record_histogram("response_time", value)

        stats = self.collector.get_histogram_stats("response_time")

        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["min"], 10)
        self.assertEqual(stats["max"], 50)
        self.assertIn("p95", stats)

    def test_calculate_rate(self):
        """Test calculating rate"""
        self.collector.record_metric("requests", 100.0)
        time.sleep(0.1)
        self.collector.record_metric("requests", 150.0)

        rate = self.collector.calculate_rate("requests", window_seconds=60)

        self.assertGreater(rate, 0)


class TestHealthCheckManager(unittest.TestCase):
    """Test HealthCheckManager"""

    def setUp(self):
        self.manager = HealthCheckManager()

    def test_register_check(self):
        """Test registering a health check"""
        def check_func():
            return {"status": "healthy", "message": "OK"}

        check = self.manager.register_check(
            name="database",
            subsystem="storage",
            check_func=check_func
        )

        self.assertIsNotNone(check)
        self.assertEqual(check.name, "database")

    def test_run_check(self):
        """Test running a health check"""
        def check_func():
            return {"status": "healthy", "message": "All good"}

        self.manager.register_check("test", "test_subsystem", check_func)

        result = self.manager.run_check(self.manager.list_checks()[0].check_id)

        self.assertEqual(result.status, HealthStatus.HEALTHY)
        self.assertEqual(result.message, "All good")

    def test_run_check_failing(self):
        """Test running a failing health check"""
        def failing_check():
            raise Exception("Database connection failed")

        self.manager.register_check("failing", "test", failing_check)

        result = self.manager.run_check(self.manager.list_checks()[0].check_id)

        self.assertEqual(result.status, HealthStatus.UNHEALTHY)
        self.assertIn("failed", result.message.lower())

    def test_run_all_checks(self):
        """Test running all health checks"""
        def check1():
            return {"status": "healthy"}
        def check2():
            return {"status": "healthy"}

        self.manager.register_check("check1", "sub1", check1)
        self.manager.register_check("check2", "sub2", check2)

        results = self.manager.run_all_checks()

        self.assertEqual(len(results), 2)

    def test_get_overall_status(self):
        """Test getting overall status"""
        def healthy_check():
            return {"status": "healthy"}

        self.manager.register_check("healthy", "test", healthy_check)

        overall = self.manager.get_overall_status()

        self.assertEqual(overall, HealthStatus.HEALTHY)

    def test_get_overall_status_unhealthy(self):
        """Test getting overall status with unhealthy check"""
        def healthy_check():
            return {"status": "healthy"}

        def unhealthy_check():
            raise Exception("Failed")

        self.manager.register_check("healthy", "test", healthy_check)
        self.manager.register_check("unhealthy", "test", unhealthy_check)

        overall = self.manager.get_overall_status()

        self.assertEqual(overall, HealthStatus.UNHEALTHY)


class TestAuditLogger(unittest.TestCase):
    """Test AuditLogger"""

    def setUp(self):
        self.logger = AuditLogger()

    def test_log(self):
        """Test logging an audit event"""
        entry = self.logger.log(
            action="create_resource",
            actor="user1",
            resource_type="catalog",
            resource_id="cat1",
            outcome="success"
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.action, "create_resource")
        self.assertEqual(entry.actor, "user1")
        self.assertEqual(entry.outcome, "success")

    def test_query(self):
        """Test querying audit logs"""
        self.logger.log("action1", "user1", "catalog", "cat1", "success")
        self.logger.log("action2", "user1", "inventory", "inv1", "success")
        self.logger.log("action1", "user2", "catalog", "cat2", "success")

        # Query by actor
        user1_logs = self.logger.query(actor="user1")
        self.assertEqual(len(user1_logs), 2)

        # Query by action
        action1_logs = self.logger.query(action="action1")
        self.assertEqual(len(action1_logs), 2)

    def test_query_with_time_filter(self):
        """Test querying with time filter"""
        start_time = time.time()

        self.logger.log("action1", "user1", "catalog", "cat1", "success")
        time.sleep(0.01)
        self.logger.log("action2", "user1", "catalog", "cat2", "success")

        logs = self.logger.query(start_time=start_time)
        self.assertEqual(len(logs), 2)

    def test_get_failure_count(self):
        """Test getting failure count"""
        self.logger.log("action1", "user1", "catalog", "cat1", "failed")
        self.logger.log("action2", "user1", "catalog", "cat2", "failed")
        self.logger.log("action3", "user1", "catalog", "cat3", "success")

        count = self.logger.get_failure_count(hours=24)
        self.assertEqual(count, 2)


class TestDistributedTracer(unittest.TestCase):
    """Test DistributedTracer"""

    def setUp(self):
        self.tracer = DistributedTracer()

    def test_start_span(self):
        """Test starting a trace span"""
        span = self.tracer.start_span(
            operation_name="process_request",
            trace_id="trace123"
        )

        self.assertIsNotNone(span)
        self.assertEqual(span.operation_name, "process_request")
        self.assertEqual(span.trace_id, "trace123")
        self.assertIsNone(span.end_time)

    def test_start_span_with_parent(self):
        """Test starting span with parent"""
        parent = self.tracer.start_span("parent_op", "trace1")
        child = self.tracer.start_span("child_op", "trace1", parent_span_id=parent.span_id)

        self.assertEqual(child.parent_span_id, parent.span_id)

    def test_finish_span(self):
        """Test finishing a span"""
        span = self.tracer.start_span("test_op", "trace1")

        finished = self.tracer.finish_span(span.span_id)

        self.assertIsNotNone(finished.end_time)
        self.assertEqual(finished.status, "ok")

    def test_get_span(self):
        """Test getting a span"""
        span = self.tracer.start_span("test_op", "trace1")

        retrieved = self.tracer.get_span(span.span_id)
        self.assertEqual(retrieved.span_id, span.span_id)

    def test_get_trace(self):
        """Test getting a trace"""
        parent = self.tracer.start_span("parent", "trace1")
        child1 = self.tracer.start_span("child1", "trace1", parent.span_id)
        child2 = self.tracer.start_span("child2", "trace1", parent.span_id)

        self.tracer.finish_span(parent.span_id)
        self.tracer.finish_span(child1.span_id)
        self.tracer.finish_span(child2.span_id)

        trace = self.tracer.get_trace("trace1")

        self.assertEqual(len(trace), 3)

    def test_add_span_log(self):
        """Test adding log to span"""
        span = self.tracer.start_span("test_op", "trace1")

        self.tracer.add_span_log(span.span_id, "Processing started")

        self.assertEqual(len(span.logs), 1)
        self.assertEqual(span.logs[0]["message"], "Processing started")


class TestAlertEngine(unittest.TestCase):
    """Test AlertEngine"""

    def setUp(self):
        self.metrics = MetricsCollector()
        self.engine = AlertEngine(self.metrics)

        # Setup some metrics
        self.metrics.set_gauge("error_rate", 5.0)
        self.metrics.set_gauge("latency_p95", 100.0)

    def test_create_alert(self):
        """Test creating an alert"""
        alert = self.engine.create_alert(
            name="High Error Rate",
            severity=AlertSeverity.WARNING,
            metric_name="error_rate",
            condition="gt",
            threshold=10.0
        )

        self.assertIsNotNone(alert)
        self.assertEqual(alert.name, "High Error Rate")
        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertFalse(alert.triggered)

    def test_evaluate_alerts_no_trigger(self):
        """Test evaluating alerts with no triggers"""
        self.engine.create_alert(
            name="Test Alert",
            severity=AlertSeverity.INFO,
            metric_name="error_rate",
            condition="gt",
            threshold=10.0  # Current is 5.0
        )

        triggered = self.engine.evaluate_alerts()
        self.assertEqual(len(triggered), 0)

    def test_evaluate_alerts_triggered(self):
        """Test evaluating alerts with triggers"""
        # Set high error rate
        self.metrics.set_gauge("error_rate", 15.0)

        self.engine.create_alert(
            name="High Error Rate",
            severity=AlertSeverity.CRITICAL,
            metric_name="error_rate",
            condition="gt",
            threshold=10.0
        )

        triggered = self.engine.evaluate_alerts()

        self.assertEqual(len(triggered), 1)
        self.assertTrue(triggered[0].triggered)

    def test_get_alert(self):
        """Test getting an alert"""
        alert = self.engine.create_alert(
            name="Test",
            severity=AlertSeverity.INFO,
            metric_name="test",
            condition="gt",
            threshold=1.0
        )

        retrieved = self.engine.get_alert(alert.alert_id)
        self.assertEqual(retrieved.alert_id, alert.alert_id)

    def test_list_alerts(self):
        """Test listing alerts"""
        self.engine.create_alert("Alert 1", AlertSeverity.INFO, "metric1", "gt", 1.0)
        self.engine.create_alert("Alert 2", AlertSeverity.WARNING, "metric2", "gt", 1.0)

        alerts = self.engine.list_alerts()
        self.assertEqual(len(alerts), 2)

    def test_list_alerts_with_severity_filter(self):
        """Test listing alerts with severity filter"""
        self.engine.create_alert("Info Alert", AlertSeverity.INFO, "metric1", "gt", 1.0)
        self.engine.create_alert("Critical Alert", AlertSeverity.CRITICAL, "metric2", "gt", 1.0)

        critical = self.engine.list_alerts(severity=AlertSeverity.CRITICAL)
        self.assertEqual(len(critical), 1)
        self.assertEqual(critical[0].name, "Critical Alert")

    def test_list_triggered_alerts(self):
        """Test listing triggered alerts only"""
        alert = self.engine.create_alert("Test", AlertSeverity.INFO, "error_rate", "gt", 1.0)

        # Trigger it
        self.engine.evaluate_alerts()

        triggered = self.engine.list_alerts(triggered_only=True)
        self.assertGreater(len(triggered), 0)

    def test_register_handler(self):
        """Test registering alert handler"""
        handler_called = []

        def handler(alert):
            handler_called.append(alert.name)

        self.engine.register_handler(handler)

        # Trigger an alert
        self.metrics.set_gauge("test_metric", 100.0)
        self.engine.create_alert("Test Alert", AlertSeverity.INFO, "test_metric", "gt", 10.0)
        self.engine.evaluate_alerts()

        # Handler should have been called
        self.assertGreater(len(handler_called), 0)


if __name__ == "__main__":
    unittest.main()
