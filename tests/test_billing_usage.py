"""
Tests for Billing Usage Metering
"""

import unittest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from billing.usage import (
    MeteringMode, UsageEvent, UsageAggregate, RateCard, UsageLedgerEntry,
    UsageEventCollector, UsageAggregator, MeteringEngine,
    UsageLedger, RateCardManager, UsageReportGenerator
)


class TestUsageEventCollector(unittest.TestCase):
    """Test UsageEventCollector"""

    def setUp(self):
        self.collector = UsageEventCollector()

    def test_collect(self):
        """Test collecting a usage event"""
        event = self.collector.collect(
            partner_id="partner1",
            api_name="TMF931",
            resource_type="catalog",
            request_size=100,
            response_size=200,
            duration_ms=50
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.partner_id, "partner1")
        self.assertEqual(event.api_name, "TMF931")

    def test_get_event(self):
        """Test getting an event"""
        event = self.collector.collect("partner1", "TMF931", "catalog")

        retrieved = self.collector.get_event(event.event_id)
        self.assertEqual(retrieved.event_id, event.event_id)

    def test_get_events(self):
        """Test getting events with filters"""
        self.collector.collect("partner1", "TMF931", "catalog")
        self.collector.collect("partner1", "CAMARA", "sim_swap")
        self.collector.collect("partner2", "TMF931", "catalog")

        events = self.collector.get_events(partner_id="partner1")
        self.assertEqual(len(events), 2)

        events = self.collector.get_events(api_name="TMF931")
        self.assertEqual(len(events), 2)

    def test_get_events_with_time_filter(self):
        """Test getting events with time filter"""
        start_time = time.time()

        event1 = self.collector.collect("partner1", "TMF931", "catalog")
        time.sleep(0.01)
        event2 = self.collector.collect("partner1", "TMF931", "catalog")

        events = self.collector.get_events(start_time=start_time)
        self.assertEqual(len(events), 2)


class TestUsageAggregator(unittest.TestCase):
    """Test UsageAggregator"""

    def setUp(self):
        self.collector = UsageEventCollector()
        self.aggregator = UsageAggregator(self.collector)

        # Add test events
        self.collector.collect("partner1", "TMF931", "catalog", duration_ms=100, status_code=200)
        self.collector.collect("partner1", "TMF931", "catalog", duration_ms=150, status_code=200)
        self.collector.collect("partner1", "CAMARA", "sim_swap", duration_ms=200, status_code=200)
        self.collector.collect("partner1", "TMF931", "catalog", duration_ms=50, status_code=500)

    def test_aggregate_by_partner(self):
        """Test aggregating by partner"""
        start_time = time.time() - 3600
        end_time = time.time()

        aggregates = self.aggregator.aggregate_by_partner("partner1", start_time, end_time)

        self.assertIn("TMF931", aggregates)
        self.assertIn("CAMARA", aggregates)

        tmf_agg = aggregates["TMF931"]
        self.assertEqual(tmf_agg.total_calls, 3)
        self.assertEqual(tmf_agg.success_count, 2)
        self.assertEqual(tmf_agg.error_count, 1)

    def test_aggregate_by_api(self):
        """Test aggregating by API"""
        start_time = time.time() - 3600
        end_time = time.time()

        aggregates = self.aggregator.aggregate_by_api("TMF931", start_time, end_time)

        self.assertIn("partner1", aggregates)

        partner_agg = aggregates["partner1"]
        self.assertEqual(partner_agg.total_calls, 3)


class TestRateCardManager(unittest.TestCase):
    """Test RateCardManager"""

    def setUp(self):
        self.manager = RateCardManager()

    def test_create_rate_card(self):
        """Test creating a rate card"""
        rate_card = self.manager.create_rate_card(
            api_name="TMF931",
            tier="standard",
            mode=MeteringMode.PER_CALL,
            base_rate=0.01,
            unit="call"
        )

        self.assertIsNotNone(rate_card)
        self.assertEqual(rate_card.api_name, "TMF931")
        self.assertEqual(rate_card.mode, MeteringMode.PER_CALL)
        self.assertEqual(rate_card.base_rate, 0.01)

    def test_create_tiered_rate_card(self):
        """Test creating a tiered rate card"""
        tiers = [
            {"lower_bound": 0, "upper_bound": 1000, "rate": 0.01},
            {"lower_bound": 1000, "upper_bound": 10000, "rate": 0.005},
            {"lower_bound": 10000, "upper_bound": float('inf'), "rate": 0.001}
        ]

        rate_card = self.manager.create_rate_card(
            api_name="TMF931",
            tier="standard",
            mode=MeteringMode.TIERED,
            base_rate=0.01,
            unit="call",
            tiers=tiers
        )

        self.assertEqual(len(rate_card.tiers), 3)

    def test_get_active_rate_card(self):
        """Test getting active rate card"""
        self.manager.create_rate_card(
            api_name="TMF931",
            tier="standard",
            mode=MeteringMode.PER_CALL,
            base_rate=0.01,
            unit="call"
        )

        rate_card = self.manager.get_active_rate_card("TMF931", "standard")

        self.assertIsNotNone(rate_card)
        self.assertEqual(rate_card.api_name, "TMF931")

    def test_list_rate_cards(self):
        """Test listing rate cards"""
        self.manager.create_rate_card("TMF931", "standard", MeteringMode.PER_CALL, 0.01, "call")
        self.manager.create_rate_card("CAMARA", "standard", MeteringMode.PER_CALL, 0.02, "call")

        rate_cards = self.manager.list_rate_cards()
        self.assertEqual(len(rate_cards), 2)

    def test_update_rate_card(self):
        """Test updating rate card"""
        rate_card = self.manager.create_rate_card("TMF931", "standard", MeteringMode.PER_CALL, 0.01, "call")

        updated = self.manager.update_rate_card(rate_card.rate_card_id, base_rate=0.02)

        self.assertEqual(updated.base_rate, 0.02)

    def test_delete_rate_card(self):
        """Test deleting rate card"""
        rate_card = self.manager.create_rate_card("TMF931", "standard", MeteringMode.PER_CALL, 0.01, "call")

        result = self.manager.delete_rate_card(rate_card.rate_card_id)
        self.assertTrue(result)


class TestMeteringEngine(unittest.TestCase):
    """Test MeteringEngine"""

    def setUp(self):
        self.rate_card_manager = RateCardManager()
        self.engine = MeteringEngine(self.rate_card_manager)

        # Create test rate cards
        self.rate_card_manager.create_rate_card(
            api_name="per_call_api",
            tier="standard",
            mode=MeteringMode.PER_CALL,
            base_rate=0.01,
            unit="call"
        )

        tiers = [
            {"lower_bound": 0, "upper_bound": 100, "rate": 0.01},
            {"lower_bound": 100, "upper_bound": 1000, "rate": 0.005},
            {"lower_bound": 1000, "upper_bound": float('inf'), "rate": 0.001}
        ]

        self.rate_card_manager.create_rate_card(
            api_name="tiered_api",
            tier="standard",
            mode=MeteringMode.TIERED,
            base_rate=0.01,
            unit="call",
            tiers=tiers
        )

        self.rate_card_manager.create_rate_card(
            api_name="volume_api",
            tier="standard",
            mode=MeteringMode.VOLUME_BASED,
            base_rate=0.000001,
            unit="GB"
        )

    def test_meter_per_call(self):
        """Test metering per call"""
        cost = self.engine.meter_call("partner1", "per_call_api", "standard")

        self.assertEqual(cost, 0.01)

    def test_meter_tiered(self):
        """Test metering with tiered pricing"""
        # First tier (0-100 calls)
        cost_50 = self.engine.meter_tiered("partner1", "tiered_api", 50, "standard")
        self.assertEqual(cost_50, 0.5)

        # Second tier (100-1000 calls)
        cost_500 = self.engine.meter_tiered("partner1", "tiered_api", 500, "standard")
        expected = (100 * 0.01) + ((500 - 100) * 0.005)
        self.assertEqual(cost_500, expected)

    def test_meter_volume(self):
        """Test metering volume-based"""
        # 1 GB = 1024^3 bytes
        one_gb = 1024 ** 3
        cost = self.engine.meter_volume("partner1", "volume_api", one_gb, "standard")

        self.assertEqual(cost, 0.000001)


class TestUsageLedger(unittest.TestCase):
    """Test UsageLedger"""

    def setUp(self):
        self.ledger = UsageLedger()

    def test_record_debit(self):
        """Test recording a debit"""
        entry = self.ledger.record_debit(
            event_id="event1",
            partner_id="partner1",
            api_name="TMF931",
            amount=10.0
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.debit_amount, 10.0)
        self.assertEqual(entry.credit_amount, 0.0)
        self.assertEqual(entry.balance, -10.0)

    def test_record_credit(self):
        """Test recording a credit"""
        entry = self.ledger.record_credit(
            event_id="event1",
            partner_id="partner1",
            api_name="TMF931",
            amount=10.0
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.credit_amount, 10.0)
        self.assertEqual(entry.debit_amount, 0.0)
        self.assertEqual(entry.balance, 10.0)

    def test_get_balance(self):
        """Test getting balance"""
        self.ledger.record_debit("event1", "partner1", "TMF931", 10.0)
        self.ledger.record_credit("event2", "partner1", "TMF931", 5.0)

        balance = self.ledger.get_balance("partner1")
        self.assertEqual(balance, -5.0)

    def test_get_entries(self):
        """Test getting ledger entries"""
        self.ledger.record_debit("event1", "partner1", "TMF931", 10.0)
        self.ledger.record_debit("event2", "partner2", "TMF931", 20.0)

        entries = self.ledger.get_entries(partner_id="partner1")
        self.assertEqual(len(entries), 1)

        all_entries = self.ledger.get_entries()
        self.assertEqual(len(all_entries), 2)


class TestUsageReportGenerator(unittest.TestCase):
    """Test UsageReportGenerator"""

    def setUp(self):
        self.collector = UsageEventCollector()
        self.aggregator = UsageAggregator(self.collector)
        self.rate_card_manager = RateCardManager()
        self.engine = MeteringEngine(self.rate_card_manager)
        self.ledger = UsageLedger()

        # Setup rate card
        self.rate_card_manager.create_rate_card(
            api_name="TMF931",
            tier="standard",
            mode=MeteringMode.PER_CALL,
            base_rate=0.01,
            unit="call"
        )

        self.report_generator = UsageReportGenerator(self.aggregator, self.engine, self.ledger)

        # Add test events
        start_time = time.time() - 3600
        for i in range(10):
            self.collector.collect("partner1", "TMF931", "catalog", status_code=200)

    def test_generate_report(self):
        """Test generating usage report"""
        period_start = time.time() - 3600
        period_end = time.time()

        report = self.report_generator.generate_report("partner1", period_start, period_end)

        self.assertIsNotNone(report)
        self.assertEqual(report.partner_id, "partner1")
        self.assertIn("TMF931", report.api_breakdown)
        self.assertGreater(report.total_cost, 0)


if __name__ == "__main__":
    unittest.main()
