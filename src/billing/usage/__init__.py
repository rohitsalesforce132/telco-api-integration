"""
Billing Usage Metering - Usage Event Collection and Aggregation
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
from collections import defaultdict


class MeteringMode(Enum):
    """Metering modes"""
    PER_CALL = "per_call"
    PER_TRANSACTION = "per_transaction"
    TIERED = "tiered"
    VOLUME_BASED = "volume_based"


@dataclass
class UsageEvent:
    """Single API usage event"""
    event_id: str
    partner_id: str
    api_name: str
    resource_type: str
    timestamp: float = field(default_factory=time.time)
    request_size: int = 0
    response_size: int = 0
    duration_ms: int = 0
    status_code: int = 200
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageAggregate:
    """Aggregated usage for a period"""
    aggregate_id: str
    partner_id: str
    api_name: str
    period_start: float
    period_end: float
    total_calls: int = 0
    total_duration_ms: int = 0
    total_size_bytes: int = 0
    success_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateCard:
    """Pricing rate card for API/tier"""
    rate_card_id: str
    api_name: str
    tier: str
    mode: MeteringMode
    base_rate: float
    unit: str
    currency: str = "USD"
    tiers: List[Dict[str, Any]] = field(default_factory=list)
    effective_from: float = field(default_factory=time.time)
    effective_until: Optional[float] = None


@dataclass
class UsageLedgerEntry:
    """Dual-entry usage ledger record"""
    entry_id: str
    event_id: str
    partner_id: str
    api_name: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    currency: str = "USD"
    balance: float = 0.0
    timestamp: float = field(default_factory=time.time)
    description: str = ""


@dataclass
class UsageReport:
    """Generated usage report for partners"""
    report_id: str
    partner_id: str
    period_start: float
    period_end: float
    api_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    total_cost: float = 0.0
    currency: str = "USD"
    generated_at: float = field(default_factory=time.time)


class UsageEventCollector:
    """Collects API usage events"""

    def __init__(self):
        self._events: List[UsageEvent] = []
        self._counter = 0

    def collect(self, partner_id: str, api_name: str, resource_type: str,
               request_size: int = 0, response_size: int = 0,
               duration_ms: int = 0, status_code: int = 200,
               metadata: Optional[Dict[str, Any]] = None) -> UsageEvent:
        """Collect a usage event"""
        event_id = self._generate_id("event")
        event = UsageEvent(
            event_id=event_id,
            partner_id=partner_id,
            api_name=api_name,
            resource_type=resource_type,
            request_size=request_size,
            response_size=response_size,
            duration_ms=duration_ms,
            status_code=status_code,
            metadata=metadata or {}
        )
        self._events.append(event)
        return event

    def get_event(self, event_id: str) -> Optional[UsageEvent]:
        """Get event by ID"""
        for event in self._events:
            if event.event_id == event_id:
                return event
        return None

    def get_events(self, partner_id: Optional[str] = None,
                  api_name: Optional[str] = None,
                  start_time: Optional[float] = None,
                  end_time: Optional[float] = None) -> List[UsageEvent]:
        """Get events with filters"""
        events = self._events.copy()

        if partner_id:
            events = [e for e in events if e.partner_id == partner_id]

        if api_name:
            events = [e for e in events if e.api_name == api_name]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        return events

    def clear_events(self) -> None:
        """Clear all events"""
        self._events.clear()

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class UsageAggregator:
    """Aggregates usage by partner, API, time period"""

    def __init__(self, event_collector: UsageEventCollector):
        self.event_collector = event_collector
        self._aggregates: Dict[str, UsageAggregate] = {}
        self._counter = 0

    def aggregate_by_partner(self, partner_id: str,
                           period_start: float,
                           period_end: float) -> Dict[str, UsageAggregate]:
        """Aggregate usage by API for a partner in a period"""
        events = self.event_collector.get_events(
            partner_id=partner_id,
            start_time=period_start,
            end_time=period_end
        )

        # Group by API
        api_events: Dict[str, List[UsageEvent]] = defaultdict(list)
        for event in events:
            api_events[event.api_name].append(event)

        # Create aggregates
        aggregates = {}
        for api_name, api_event_list in api_events.items():
            aggregate = self._create_aggregate(
                partner_id, api_name, period_start, period_end, api_event_list
            )
            aggregates[api_name] = aggregate

        return aggregates

    def aggregate_by_api(self, api_name: str,
                        period_start: float,
                        period_end: float) -> Dict[str, UsageAggregate]:
        """Aggregate usage by partner for an API in a period"""
        events = self.event_collector.get_events(
            api_name=api_name,
            start_time=period_start,
            end_time=period_end
        )

        # Group by partner
        partner_events: Dict[str, List[UsageEvent]] = defaultdict(list)
        for event in events:
            partner_events[event.partner_id].append(event)

        # Create aggregates
        aggregates = {}
        for partner_id, partner_event_list in partner_events.items():
            aggregate = self._create_aggregate(
                partner_id, api_name, period_start, period_end, partner_event_list
            )
            aggregates[partner_id] = aggregate

        return aggregates

    def get_aggregate(self, aggregate_id: str) -> Optional[UsageAggregate]:
        """Get aggregate by ID"""
        return self._aggregates.get(aggregate_id)

    def _create_aggregate(self, partner_id: str, api_name: str,
                         period_start: float, period_end: float,
                         events: List[UsageEvent]) -> UsageAggregate:
        """Create aggregate from events"""
        aggregate_id = self._generate_id("aggregate")

        total_calls = len(events)
        total_duration = sum(e.duration_ms for e in events)
        total_size = sum(e.request_size + e.response_size for e in events)
        success_count = sum(1 for e in events if 200 <= e.status_code < 300)
        error_count = total_calls - success_count

        aggregate = UsageAggregate(
            aggregate_id=aggregate_id,
            partner_id=partner_id,
            api_name=api_name,
            period_start=period_start,
            period_end=period_end,
            total_calls=total_calls,
            total_duration_ms=total_duration,
            total_size_bytes=total_size,
            success_count=success_count,
            error_count=error_count
        )

        self._aggregates[aggregate_id] = aggregate
        return aggregate

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class MeteringEngine:
    """Meters API calls (per-call, per-transaction, tiered)"""

    def __init__(self, rate_card_manager: 'RateCardManager'):
        self.rate_card_manager = rate_card_manager

    def meter_call(self, partner_id: str, api_name: str,
                  tier: str = "standard") -> float:
        """Meter a single API call (per-call mode)"""
        rate_card = self.rate_card_manager.get_active_rate_card(api_name, tier)
        if not rate_card:
            raise ValueError(f"No active rate card found for {api_name} tier {tier}")

        if rate_card.mode != MeteringMode.PER_CALL:
            raise ValueError(f"Rate card mode is {rate_card.mode.value}, expected per_call")

        return rate_card.base_rate

    def meter_transaction(self, partner_id: str, api_name: str,
                         transaction_value: float,
                         tier: str = "standard") -> float:
        """Meter a transaction (per-transaction mode)"""
        rate_card = self.rate_card_manager.get_active_rate_card(api_name, tier)
        if not rate_card:
            raise ValueError(f"No active rate card found for {api_name} tier {tier}")

        if rate_card.mode != MeteringMode.PER_TRANSACTION:
            raise ValueError(f"Rate card mode is {rate_card.mode.value}, expected per_transaction")

        return rate_card.base_rate * transaction_value

    def meter_tiered(self, partner_id: str, api_name: str,
                    usage_quantity: float,
                    tier: str = "standard") -> float:
        """Meter usage with tiered pricing"""
        rate_card = self.rate_card_manager.get_active_rate_card(api_name, tier)
        if not rate_card:
            raise ValueError(f"No active rate card found for {api_name} tier {tier}")

        if rate_card.mode != MeteringMode.TIERED:
            raise ValueError(f"Rate card mode is {rate_card.mode.value}, expected tiered")

        # Calculate tiered cost
        total_cost = 0.0
        remaining_quantity = usage_quantity

        # Sort tiers by upper bound
        sorted_tiers = sorted(rate_card.tiers, key=lambda t: t.get("upper_bound", float('inf')))

        for tier_def in sorted_tiers:
            if remaining_quantity <= 0:
                break

            lower_bound = tier_def.get("lower_bound", 0)
            upper_bound = tier_def.get("upper_bound", float('inf'))
            rate = tier_def.get("rate", 0.0)

            # Calculate quantity in this tier
            tier_quantity = min(remaining_quantity, upper_bound - lower_bound)
            if tier_quantity > 0:
                total_cost += tier_quantity * rate
                remaining_quantity -= tier_quantity

        return total_cost

    def meter_volume(self, partner_id: str, api_name: str,
                    volume_bytes: int,
                    tier: str = "standard") -> float:
        """Meter volume-based usage"""
        rate_card = self.rate_card_manager.get_active_rate_card(api_name, tier)
        if not rate_card:
            raise ValueError(f"No active rate card found for {api_name} tier {tier}")

        if rate_card.mode != MeteringMode.VOLUME_BASED:
            raise ValueError(f"Rate card mode is {rate_card.mode.value}, expected volume_based")

        # Calculate volume in specified units (e.g., GB)
        unit_multiplier = self._get_unit_multiplier(rate_card.unit)
        volume_units = volume_bytes / unit_multiplier

        return volume_units * rate_card.base_rate

    def _get_unit_multiplier(self, unit: str) -> int:
        """Get byte multiplier for unit"""
        multipliers = {
            "B": 1,
            "KB": 1024,
            "MB": 1024 ** 2,
            "GB": 1024 ** 3,
            "TB": 1024 ** 4
        }
        return multipliers.get(unit.upper(), 1)


class UsageLedger:
    """Persistent usage ledger with dual-entry"""

    def __init__(self):
        self._entries: List[UsageLedgerEntry] = []
        self._balances: Dict[str, float] = {}
        self._counter = 0

    def record_debit(self, event_id: str, partner_id: str, api_name: str,
                    amount: float, currency: str = "USD",
                    description: str = "") -> UsageLedgerEntry:
        """Record a debit entry"""
        entry_id = self._generate_id("entry")

        # Update balance
        current_balance = self._balances.get(partner_id, 0.0)
        new_balance = current_balance - amount
        self._balances[partner_id] = new_balance

        entry = UsageLedgerEntry(
            entry_id=entry_id,
            event_id=event_id,
            partner_id=partner_id,
            api_name=api_name,
            debit_amount=amount,
            credit_amount=0.0,
            currency=currency,
            balance=new_balance,
            description=description or f"Debit for {api_name}"
        )

        self._entries.append(entry)
        return entry

    def record_credit(self, event_id: str, partner_id: str, api_name: str,
                     amount: float, currency: str = "USD",
                     description: str = "") -> UsageLedgerEntry:
        """Record a credit entry"""
        entry_id = self._generate_id("entry")

        # Update balance
        current_balance = self._balances.get(partner_id, 0.0)
        new_balance = current_balance + amount
        self._balances[partner_id] = new_balance

        entry = UsageLedgerEntry(
            entry_id=entry_id,
            event_id=event_id,
            partner_id=partner_id,
            api_name=api_name,
            debit_amount=0.0,
            credit_amount=amount,
            currency=currency,
            balance=new_balance,
            description=description or f"Credit for {api_name}"
        )

        self._entries.append(entry)
        return entry

    def get_balance(self, partner_id: str) -> float:
        """Get balance for partner"""
        return self._balances.get(partner_id, 0.0)

    def get_entries(self, partner_id: Optional[str] = None,
                   start_time: Optional[float] = None,
                   end_time: Optional[float] = None) -> List[UsageLedgerEntry]:
        """Get ledger entries with filters"""
        entries = self._entries.copy()

        if partner_id:
            entries = [e for e in entries if e.partner_id == partner_id]

        if start_time:
            entries = [e for e in entries if e.timestamp >= start_time]

        if end_time:
            entries = [e for e in entries if e.timestamp <= end_time]

        return entries

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class RateCardManager:
    """Manages pricing rate cards per API/tier"""

    def __init__(self):
        self._rate_cards: Dict[str, RateCard] = {}
        self._counter = 0

    def create_rate_card(self, api_name: str, tier: str, mode: MeteringMode,
                        base_rate: float, unit: str,
                        currency: str = "USD",
                        tiers: Optional[List[Dict[str, Any]]] = None,
                        effective_from: Optional[float] = None,
                        effective_until: Optional[float] = None) -> RateCard:
        """Create a rate card"""
        rate_card_id = self._generate_id("ratecard")

        rate_card = RateCard(
            rate_card_id=rate_card_id,
            api_name=api_name,
            tier=tier,
            mode=mode,
            base_rate=base_rate,
            unit=unit,
            currency=currency,
            tiers=tiers or [],
            effective_from=effective_from or time.time(),
            effective_until=effective_until
        )

        self._rate_cards[rate_card_id] = rate_card
        return rate_card

    def get_rate_card(self, rate_card_id: str) -> Optional[RateCard]:
        """Get rate card by ID"""
        return self._rate_cards.get(rate_card_id)

    def get_active_rate_card(self, api_name: str, tier: str) -> Optional[RateCard]:
        """Get active rate card for API and tier"""
        current_time = time.time()

        for rate_card in self._rate_cards.values():
            if (rate_card.api_name == api_name and
                rate_card.tier == tier and
                rate_card.effective_from <= current_time and
                (rate_card.effective_until is None or rate_card.effective_until > current_time)):
                return rate_card

        return None

    def list_rate_cards(self, api_name: Optional[str] = None,
                       tier: Optional[str] = None) -> List[RateCard]:
        """List rate cards with filters"""
        rate_cards = list(self._rate_cards.values())

        if api_name:
            rate_cards = [rc for rc in rate_cards if rc.api_name == api_name]

        if tier:
            rate_cards = [rc for rc in rate_cards if rc.tier == tier]

        return rate_cards

    def update_rate_card(self, rate_card_id: str, **kwargs) -> RateCard:
        """Update rate card"""
        if rate_card_id not in self._rate_cards:
            raise ValueError(f"Rate card not found: {rate_card_id}")

        rate_card = self._rate_cards[rate_card_id]
        for key, value in kwargs.items():
            if hasattr(rate_card, key) and key not in ('rate_card_id', 'created_at'):
                setattr(rate_card, key, value)

        return rate_card

    def delete_rate_card(self, rate_card_id: str) -> bool:
        """Delete rate card"""
        if rate_card_id in self._rate_cards:
            del self._rate_cards[rate_card_id]
            return True
        return False

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class UsageReportGenerator:
    """Generates usage reports for partners"""

    def __init__(self, aggregator: UsageAggregator,
                 metering_engine: MeteringEngine,
                 ledger: UsageLedger):
        self.aggregator = aggregator
        self.metering_engine = metering_engine
        self.ledger = ledger
        self._counter = 0

    def generate_report(self, partner_id: str, period_start: float,
                       period_end: float) -> UsageReport:
        """Generate usage report for partner"""
        # Get aggregates
        aggregates = self.aggregator.aggregate_by_partner(partner_id, period_start, period_end)

        # Calculate costs
        api_breakdown = {}
        total_cost = 0.0

        for api_name, aggregate in aggregates.items():
            # Get active rate card
            rate_card = self.metering_engine.rate_card_manager.get_active_rate_card(api_name, "standard")
            if rate_card:
                if rate_card.mode == MeteringMode.PER_CALL:
                    cost = aggregate.total_calls * rate_card.base_rate
                elif rate_card.mode == MeteringMode.TIERED:
                    cost = self.metering_engine.meter_tiered(partner_id, api_name, aggregate.total_calls, "standard")
                elif rate_card.mode == MeteringMode.VOLUME_BASED:
                    cost = self.metering_engine.meter_volume(partner_id, api_name, aggregate.total_size_bytes, "standard")
                else:
                    cost = 0.0
            else:
                cost = 0.0

            api_breakdown[api_name] = {
                "total_calls": aggregate.total_calls,
                "total_duration_ms": aggregate.total_duration_ms,
                "total_size_bytes": aggregate.total_size_bytes,
                "success_count": aggregate.success_count,
                "error_count": aggregate.error_count,
                "cost": cost
            }

            total_cost += cost

        report_id = self._generate_id("report")
        report = UsageReport(
            report_id=report_id,
            partner_id=partner_id,
            period_start=period_start,
            period_end=period_end,
            api_breakdown=api_breakdown,
            total_cost=total_cost
        )

        return report

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"
