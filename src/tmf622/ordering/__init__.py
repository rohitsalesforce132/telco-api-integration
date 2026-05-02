"""
TMF622 Product Ordering Module
Implements product ordering, lifecycle management, fulfillment, and compensation.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field, asdict
from copy import deepcopy
import uuid


class OrderState(Enum):
    """Order states per TMF622 standard."""
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "inProgress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class OrderItemState(Enum):
    """Order item states."""
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "inProgress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QuoteState(Enum):
    """Quote states."""
    DRAFT = "draft"
    VALID = "valid"
    EXPIRED = "expired"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass
class QuoteItem:
    """Individual item within a quote."""
    id: str
    product_offering_id: str
    product_offering_name: str
    quantity: int
    unit_price: float
    total_price: float
    recurring_price: Optional[float] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class Quote:
    """Quote for a product order."""
    id: str
    items: List[QuoteItem] = field(default_factory=list)
    total_one_time_price: float = 0.0
    total_recurring_price: float = 0.0
    valid_until: Optional[datetime] = None
    state: QuoteState = QuoteState.DRAFT
    customer_id: Optional[str] = None
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_item(self, offering_id: str, offering_name: str, quantity: int,
                 unit_price: float, recurring_price: Optional[float] = None,
                 description: str = "") -> None:
        """Add an item to the quote."""
        item = QuoteItem(
            id=str(uuid.uuid4()),
            product_offering_id=offering_id,
            product_offering_name=offering_name,
            quantity=quantity,
            unit_price=unit_price,
            total_price=unit_price * quantity,
            recurring_price=recurring_price,
            description=description
        )
        self.items.append(item)
        self.total_one_time_price += item.total_price
        if recurring_price:
            self.total_recurring_price += recurring_price * quantity
        self.updated_at = datetime.now()

    def remove_item(self, item_id: str) -> bool:
        """Remove an item from the quote."""
        for i, item in enumerate(self.items):
            if item.id == item_id:
                self.total_one_time_price -= item.total_price
                if item.recurring_price:
                    self.total_recurring_price -= item.recurring_price * item.quantity
                self.items.pop(i)
                self.updated_at = datetime.now()
                return True
        return False

    def validate(self, valid_for_hours: int = 24) -> bool:
        """Validate the quote."""
        now = datetime.now()
        if self.state == QuoteState.EXPIRED:
            return False
        if self.valid_until and now > self.valid_until:
            self.state = QuoteState.EXPIRED
            self.updated_at = datetime.now()
            return False
        return True

    def set_validity(self, hours: int = 24) -> None:
        """Set quote validity period."""
        self.valid_until = datetime.now() + timedelta(hours=hours)
        self.state = QuoteState.VALID
        self.updated_at = datetime.now()

    def accept(self) -> None:
        """Mark quote as accepted."""
        if not self.validate():
            raise ValueError("Cannot accept expired or invalid quote")
        self.state = QuoteState.ACCEPTED
        self.updated_at = datetime.now()

    def reject(self) -> None:
        """Mark quote as rejected."""
        self.state = QuoteState.REJECTED
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['state'] = self.state.value
        data['valid_until'] = self.valid_until.isoformat() if self.valid_until else None
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


@dataclass
class OrderItem:
    """Individual item within a product order."""
    id: str
    product_offering_id: str
    product_offering_name: str
    quantity: int
    state: OrderItemState = OrderItemState.ACKNOWLEDGED
    unit_price: float = 0.0
    total_price: float = 0.0
    recurring_price: Optional[float] = None
    action: str = "add"  # add, modify, delete
    service_id: Optional[str] = None
    resource_id: Optional[str] = None
    error_message: Optional[str] = None
    description: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def transition_state(self, new_state: OrderItemState) -> bool:
        """Transition to a new state."""
        valid_transitions = {
            OrderItemState.ACKNOWLEDGED: [OrderItemState.IN_PROGRESS, OrderItemState.CANCELLED],
            OrderItemState.IN_PROGRESS: [OrderItemState.COMPLETED, OrderItemState.FAILED, OrderItemState.CANCELLED],
            OrderItemState.COMPLETED: [],
            OrderItemState.FAILED: [OrderItemState.IN_PROGRESS],  # Retry
            OrderItemState.CANCELLED: []
        }

        if new_state in valid_transitions.get(self.state, []):
            self.state = new_state
            if new_state == OrderItemState.IN_PROGRESS and self.started_at is None:
                self.started_at = datetime.now()
            if new_state == OrderItemState.COMPLETED:
                self.completed_at = datetime.now()
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['state'] = self.state.value
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data


@dataclass
class ProductOrder:
    """Product order with items, lifecycle, and fulfillment tracking."""
    id: str
    customer_id: str
    items: List[OrderItem] = field(default_factory=list)
    state: OrderState = OrderState.ACKNOWLEDGED
    total_amount: float = 0.0
    currency: str = "USD"
    priority: str = "normal"  # low, normal, high, urgent
    channel: str = "web"
    notes: str = ""
    requested_completion_date: Optional[datetime] = None
    expected_completion_date: Optional[datetime] = None
    actual_completion_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Calculate total_amount from items after initialization."""
        self.total_amount = sum(item.total_price for item in self.items)

    def add_item(self, item: OrderItem) -> None:
        """Add an item to the order."""
        if self.state != OrderState.ACKNOWLEDGED:
            raise ValueError("Cannot add items to order that is not in ACKNOWLEDGED state")
        self.items.append(item)
        self.total_amount += item.total_price
        self.updated_at = datetime.now()

    def remove_item(self, item_id: str) -> bool:
        """Remove an item from the order."""
        if self.state != OrderState.ACKNOWLEDGED:
            raise ValueError("Cannot remove items from order that is not in ACKNOWLEDGED state")

        for i, item in enumerate(self.items):
            if item.id == item_id:
                self.total_amount -= item.total_price
                self.items.pop(i)
                self.updated_at = datetime.now()
                return True
        return False

    def transition_state(self, new_state: OrderState) -> bool:
        """Transition the order to a new state."""
        valid_transitions = {
            OrderState.ACKNOWLEDGED: [OrderState.IN_PROGRESS, OrderState.CANCELLED],
            OrderState.IN_PROGRESS: [OrderState.COMPLETED, OrderState.FAILED, OrderState.PARTIAL, OrderState.CANCELLED],
            OrderState.COMPLETED: [],
            OrderState.FAILED: [OrderState.IN_PROGRESS],  # Retry
            OrderState.PARTIAL: [OrderState.COMPLETED, OrderState.FAILED],
            OrderState.CANCELLED: []
        }

        if new_state in valid_transitions.get(self.state, []):
            self.state = new_state
            if new_state in [OrderState.COMPLETED, OrderState.FAILED, OrderState.CANCELLED]:
                self.actual_completion_date = datetime.now()
            self.updated_at = datetime.now()
            return True
        return False

    def get_item_state_summary(self) -> Dict[str, int]:
        """Get summary of item states."""
        summary = {state.value: 0 for state in OrderItemState}
        for item in self.items:
            summary[item.state.value] += 1
        return summary

    def is_complete(self) -> bool:
        """Check if all items are completed."""
        return all(item.state == OrderItemState.COMPLETED for item in self.items)

    def has_failures(self) -> bool:
        """Check if any items have failed."""
        return any(item.state == OrderItemState.FAILED for item in self.items)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['state'] = self.state.value
        data['items'] = [item.to_dict() for item in self.items]
        data['requested_completion_date'] = self.requested_completion_date.isoformat() if self.requested_completion_date else None
        data['expected_completion_date'] = self.expected_completion_date.isoformat() if self.expected_completion_date else None
        data['actual_completion_date'] = self.actual_completion_date.isoformat() if self.actual_completion_date else None
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


class QuoteManager:
    """
    Generates and manages quotes from product offerings.
    """

    def __init__(self):
        self.quotes: Dict[str, Quote] = {}

    def create_quote(self, customer_id: Optional[str] = None) -> Quote:
        """Create a new quote."""
        quote = Quote(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            state=QuoteState.DRAFT
        )
        self.quotes[quote.id] = quote
        return quote

    def get_quote(self, quote_id: str) -> Optional[Quote]:
        """Get a quote by ID."""
        return self.quotes.get(quote_id)

    def finalize_quote(self, quote_id: str, valid_for_hours: int = 24) -> Quote:
        """Finalize and validate a quote."""
        quote = self.quotes.get(quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        if not quote.items:
            raise ValueError("Cannot finalize quote with no items")

        quote.set_validity(valid_for_hours)
        return quote

    def list_quotes(self, customer_id: Optional[str] = None,
                   state: Optional[QuoteState] = None) -> List[Quote]:
        """List quotes, optionally filtered."""
        quotes = list(self.quotes.values())

        if customer_id:
            quotes = [q for q in quotes if q.customer_id == customer_id]

        if state:
            quotes = [q for q in quotes if q.state == state]

        return quotes

    def delete_quote(self, quote_id: str) -> bool:
        """Delete a quote (only if draft)."""
        quote = self.quotes.get(quote_id)
        if not quote:
            return False
        if quote.state != QuoteState.DRAFT:
            raise ValueError("Can only delete draft quotes")
        del self.quotes[quote_id]
        return True


class OrderValidationEngine:
    """
    Validates order feasibility, pricing, and eligibility.
    """

    def __init__(self):
        self.pricing_rules: Dict[str, Dict[str, Any]] = {}
        self.eligibility_rules: Dict[str, List[Dict[str, Any]]] = {}

    def validate_order(self, order: ProductOrder,
                      customer_context: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str]]:
        """
        Validate an order for feasibility, pricing, and eligibility.
        Returns (is_valid, errors).
        """
        errors = []

        # Check basic order structure
        if not order.customer_id:
            errors.append("Order must have a customer_id")

        if not order.items:
            errors.append("Order must have at least one item")

        # Validate each item
        for item in order.items:
            item_errors = self._validate_item(item, customer_context)
            errors.extend(item_errors)

        # Validate total pricing
        calculated_total = sum(item.total_price for item in order.items)
        if abs(calculated_total - order.total_amount) > 0.01:
            errors.append(f"Order total {order.total_amount} does not match item sum {calculated_total}")

        # Validate requested completion date
        if order.requested_completion_date and order.requested_completion_date < datetime.now():
            errors.append("Requested completion date cannot be in the past")

        return len(errors) == 0, errors

    def _validate_item(self, item: OrderItem,
                      customer_context: Optional[Dict[str, Any]]) -> List[str]:
        """Validate a single order item."""
        errors = []

        if item.quantity <= 0:
            errors.append(f"Item {item.id} has invalid quantity: {item.quantity}")

        if item.unit_price < 0:
            errors.append(f"Item {item.id} has negative unit price")

        if item.total_price != item.unit_price * item.quantity:
            errors.append(f"Item {item.id} total price calculation incorrect")

        # Check eligibility rules if customer context provided
        if customer_context and item.product_offering_id in self.eligibility_rules:
            for rule in self.eligibility_rules[item.product_offering_id]:
                if not self._check_elibility(rule, customer_context):
                    errors.append(f"Item {item.id}: {rule.get('message', 'Eligibility check failed')}")

        return errors

    def _check_elibility(self, rule: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check an eligibility rule."""
        field = rule.get('field')
        operator = rule.get('operator', '==')
        value = rule.get('value')

        if field not in context:
            return False

        context_value = context[field]

        if operator == '==':
            return context_value == value
        elif operator == '!=':
            return context_value != value
        elif operator == '>':
            return context_value > value
        elif operator == '<':
            return context_value < value
        elif operator == 'in':
            return context_value in value

        return True

    def add_pricing_rule(self, offering_id: str, rule: Dict[str, Any]) -> None:
        """Add a pricing rule for a product offering."""
        if offering_id not in self.pricing_rules:
            self.pricing_rules[offering_id] = []
        self.pricing_rules[offering_id].append(rule)

    def add_eligibility_rule(self, offering_id: str, field: str, operator: str,
                            value: Any, message: str) -> None:
        """Add an eligibility rule for a product offering."""
        if offering_id not in self.eligibility_rules:
            self.eligibility_rules[offering_id] = []
        self.eligibility_rules[offering_id].append({
            'field': field,
            'operator': operator,
            'value': value,
            'message': message
        })


class OrderFulfillmentEngine:
    """
    Orchestrates fulfillment across TMF931 resources and CAMARA services.
    """

    def __init__(self):
        self.fulfillment_handlers: Dict[str, Any] = {}
        self.fulfillment_log: List[Dict[str, Any]] = []

    def register_handler(self, offering_id: str, handler: Any) -> None:
        """Register a fulfillment handler for a product offering."""
        self.fulfillment_handlers[offering_id] = handler

    def fulfill_order(self, order: ProductOrder) -> Tuple[bool, List[str]]:
        """
        Fulfill an order by processing all items.
        Returns (success, errors).
        """
        order.transition_state(OrderState.IN_PROGRESS)
        errors = []

        for item in order.items:
            item_errors = self._fulfill_item(item, order)
            errors.extend(item_errors)

        # Determine final order state
        if all(item.state == OrderItemState.COMPLETED for item in order.items):
            order.transition_state(OrderState.COMPLETED)
        elif any(item.state == OrderItemState.FAILED for item in order.items):
            if any(item.state == OrderItemState.COMPLETED for item in order.items):
                order.transition_state(OrderState.PARTIAL)
            else:
                order.transition_state(OrderState.FAILED)

        return order.state in [OrderState.COMPLETED, OrderState.PARTIAL], errors

    def _fulfill_item(self, item: OrderItem, order: ProductOrder) -> List[str]:
        """Fulfill a single order item."""
        errors = []
        item.transition_state(OrderItemState.IN_PROGRESS)

        try:
            # Look up fulfillment handler
            handler = self.fulfillment_handlers.get(item.product_offering_id)

            if handler:
                # Simulate handler execution
                success = handler.fulfill(item, order)
                if success:
                    item.transition_state(OrderItemState.COMPLETED)
                else:
                    item.transition_state(OrderItemState.FAILED)
                    errors.append(f"Fulfillment failed for item {item.id}")
            else:
                # Default fulfillment (succeed by default for demo)
                item.transition_state(OrderItemState.COMPLETED)

        except Exception as e:
            item.transition_state(OrderItemState.FAILED)
            item.error_message = str(e)
            errors.append(f"Exception fulfilling item {item.id}: {e}")

        self.fulfillment_log.append({
            "timestamp": datetime.now().isoformat(),
            "order_id": order.id,
            "item_id": item.id,
            "offering_id": item.product_offering_id,
            "state": item.state.value,
            "errors": errors
        })

        return errors

    def get_fulfillment_log(self, order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get fulfillment log, optionally filtered by order."""
        if order_id:
            return [log for log in self.fulfillment_log if log['order_id'] == order_id]
        return self.fulfillment_log.copy()


class OrderCompensationHandler:
    """
    Handles rollback and compensation for failed orders.
    """

    def __init__(self):
        self.compensation_log: List[Dict[str, Any]] = []
        self.compensators: Dict[str, Any] = {}

    def register_compensator(self, offering_id: str, compensator: Any) -> None:
        """Register a compensator for a product offering."""
        self.compensators[offering_id] = compensator

    def compensate_order(self, order: ProductOrder) -> Tuple[bool, List[str]]:
        """
        Compensate/rollback a failed or cancelled order.
        Returns (success, errors).
        """
        errors = []

        for item in order.items:
            if item.state == OrderItemState.COMPLETED:
                item_errors = self._compensate_item(item, order)
                errors.extend(item_errors)
            elif item.state in [OrderItemState.IN_PROGRESS, OrderItemState.ACKNOWLEDGED]:
                # Cancel pending items
                item.transition_state(OrderItemState.CANCELLED)

        return len(errors) == 0, errors

    def _compensate_item(self, item: OrderItem, order: ProductOrder) -> List[str]:
        """Compensate a single fulfilled item."""
        errors = []

        try:
            compensator = self.compensators.get(item.product_offering_id)

            if compensator:
                success = compensator.compensate(item, order)
                if not success:
                    errors.append(f"Compensation failed for item {item.id}")
            else:
                # Default compensation (no-op for demo)
                pass

        except Exception as e:
            errors.append(f"Exception compensating item {item.id}: {e}")

        self.compensation_log.append({
            "timestamp": datetime.now().isoformat(),
            "order_id": order.id,
            "item_id": item.id,
            "offering_id": item.product_offering_id,
            "errors": errors
        })

        return errors

    def get_compensation_log(self, order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get compensation log, optionally filtered by order."""
        if order_id:
            return [log for log in self.compensation_log if log['order_id'] == order_id]
        return self.compensation_log.copy()


class OrderNotificationManager:
    """
    Sends order status notifications and webhooks.
    """

    def __init__(self):
        self.notification_log: List[Dict[str, Any]] = []
        self.webhooks: List[Dict[str, str]] = []

    def register_webhook(self, url: str, secret: Optional[str] = None) -> None:
        """Register a webhook for order notifications."""
        self.webhooks.append({
            "url": url,
            "secret": secret or ""
        })

    def send_notification(self, order: ProductOrder, event: str,
                         recipient: Optional[str] = None) -> bool:
        """
        Send a notification for an order event.
        Events: order_created, order_updated, order_completed, order_failed, order_cancelled
        """
        notification = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "order_id": order.id,
            "order_state": order.state.value,
            "customer_id": order.customer_id,
            "recipient": recipient
        }

        self.notification_log.append(notification)

        # In production, this would actually send emails/webhooks
        # For demo, we just log it
        return True

    def send_webhook(self, order: ProductOrder, event: str) -> Tuple[bool, List[str]]:
        """Send webhook notifications to all registered webhooks."""
        errors = []

        for webhook in self.webhooks:
            try:
                # In production, this would make actual HTTP requests
                # For demo, we just log the attempt
                self.notification_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "event": f"webhook_{event}",
                    "order_id": order.id,
                    "webhook_url": webhook["url"],
                    "status": "sent"
                })
            except Exception as e:
                errors.append(f"Webhook failed for {webhook['url']}: {e}")

        return len(errors) == 0, errors

    def get_notification_log(self, order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get notification log, optionally filtered by order."""
        if order_id:
            return [log for log in self.notification_log if log.get('order_id') == order_id]
        return self.notification_log.copy()


class OrderLifecycleManager:
    """
    Manages order state transitions and lifecycle events.
    """

    def __init__(self):
        self.orders: Dict[str, ProductOrder] = {}
        self.state_history: Dict[str, List[Dict[str, Any]]] = {}

    def create_order(self, customer_id: str, items: List[OrderItem],
                    priority: str = "normal", channel: str = "web",
                    requested_completion_date: Optional[datetime] = None) -> ProductOrder:
        """Create a new product order."""
        order = ProductOrder(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            items=items,
            priority=priority,
            channel=channel,
            requested_completion_date=requested_completion_date
        )
        self.orders[order.id] = order
        self._record_state_change(order, "created")
        return order

    def get_order(self, order_id: str) -> Optional[ProductOrder]:
        """Get an order by ID."""
        return self.orders.get(order_id)

    def list_orders(self, customer_id: Optional[str] = None,
                   state: Optional[OrderState] = None,
                   limit: int = 100) -> List[ProductOrder]:
        """List orders, optionally filtered."""
        orders = list(self.orders.values())

        if customer_id:
            orders = [o for o in orders if o.customer_id == customer_id]

        if state:
            orders = [o for o in orders if o.state == state]

        # Sort by created date descending
        orders.sort(key=lambda o: o.created_at, reverse=True)

        return orders[:limit]

    def update_order_state(self, order_id: str, new_state: OrderState,
                          reason: Optional[str] = None) -> bool:
        """Update the state of an order."""
        order = self.orders.get(order_id)
        if not order:
            return False

        success = order.transition_state(new_state)
        if success:
            self._record_state_change(order, new_state.value, reason)
        return success

    def cancel_order(self, order_id: str, reason: Optional[str] = None) -> bool:
        """Cancel an order."""
        return self.update_order_state(order_id, OrderState.CANCELLED, reason)

    def get_state_history(self, order_id: str) -> List[Dict[str, Any]]:
        """Get the state transition history for an order."""
        return self.state_history.get(order_id, [])

    def _record_state_change(self, order: ProductOrder, new_state: str,
                            reason: Optional[str] = None) -> None:
        """Record a state change in the history."""
        if order.id not in self.state_history:
            self.state_history[order.id] = []

        self.state_history[order.id].append({
            "timestamp": datetime.now().isoformat(),
            "from_state": order.state.value,
            "to_state": new_state,
            "reason": reason
        })


class ProductOrderManager:
    """
    Main manager for product orders (TMF622).
    Coordinates quote, validation, lifecycle, fulfillment, and notifications.
    """

    def __init__(self):
        self.lifecycle_manager = OrderLifecycleManager()
        self.quote_manager = QuoteManager()
        self.validation_engine = OrderValidationEngine()
        self.fulfillment_engine = OrderFulfillmentEngine()
        self.compensation_handler = OrderCompensationHandler()
        self.notification_manager = OrderNotificationManager()

    def create_order(self, customer_id: str, items: List[OrderItem],
                    priority: str = "normal", channel: str = "web",
                    requested_completion_date: Optional[datetime] = None,
                    validate: bool = True) -> Tuple[ProductOrder, List[str]]:
        """
        Create and optionally validate a new product order.
        Returns (order, errors).
        """
        order = self.lifecycle_manager.create_order(
            customer_id=customer_id,
            items=items,
            priority=priority,
            channel=channel,
            requested_completion_date=requested_completion_date
        )

        errors = []
        if validate:
            is_valid, validation_errors = self.validation_engine.validate_order(order)
            errors = validation_errors

        # Send notification
        self.notification_manager.send_notification(order, "order_created")

        return order, errors

    def get_order(self, order_id: str) -> Optional[ProductOrder]:
        """Get an order by ID."""
        return self.lifecycle_manager.get_order(order_id)

    def list_orders(self, customer_id: Optional[str] = None,
                   state: Optional[OrderState] = None,
                   limit: int = 100) -> List[ProductOrder]:
        """List orders, optionally filtered."""
        return self.lifecycle_manager.list_orders(customer_id, state, limit)

    def submit_order(self, order_id: str) -> Tuple[bool, List[str]]:
        """
        Submit and fulfill an order.
        Returns (success, errors).
        """
        order = self.lifecycle_manager.get_order(order_id)
        if not order:
            return False, ["Order not found"]

        # Validate before fulfillment
        is_valid, errors = self.validation_engine.validate_order(order)
        if not is_valid:
            return False, errors

        # Fulfill the order
        success, fulfillment_errors = self.fulfillment_engine.fulfill_order(order)
        errors.extend(fulfillment_errors)

        # Send notification
        event = "order_completed" if order.state == OrderState.COMPLETED else "order_failed"
        self.notification_manager.send_notification(order, event)
        self.notification_manager.send_webhook(order, event)

        return success, errors

    def cancel_order(self, order_id: str, reason: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Cancel an order and compensate fulfilled items.
        Returns (success, errors).
        """
        order = self.lifecycle_manager.get_order(order_id)
        if not order:
            return False, ["Order not found"]

        # Cancel the order
        cancelled = self.lifecycle_manager.cancel_order(order_id, reason)
        if not cancelled:
            return False, ["Cannot cancel order in current state"]

        # Compensate fulfilled items
        success, errors = self.compensation_handler.compensate_order(order)

        # Send notification
        self.notification_manager.send_notification(order, "order_cancelled")

        return success, errors

    def create_quote(self, customer_id: Optional[str] = None) -> Quote:
        """Create a new quote."""
        return self.quote_manager.create_quote(customer_id)

    def get_quote(self, quote_id: str) -> Optional[Quote]:
        """Get a quote by ID."""
        return self.quote_manager.get_quote(quote_id)

    def finalize_quote(self, quote_id: str, valid_for_hours: int = 24) -> Quote:
        """Finalize a quote."""
        return self.quote_manager.finalize_quote(quote_id, valid_for_hours)

    def convert_quote_to_order(self, quote_id: str, customer_id: str) -> Tuple[ProductOrder, List[str]]:
        """
        Convert a quote to a product order.
        Returns (order, errors).
        """
        quote = self.quote_manager.get_quote(quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        if not quote.validate():
            raise ValueError("Quote has expired or is invalid")

        # Convert quote items to order items
        order_items = []
        for quote_item in quote.items:
            order_item = OrderItem(
                id=str(uuid.uuid4()),
                product_offering_id=quote_item.product_offering_id,
                product_offering_name=quote_item.product_offering_name,
                quantity=quote_item.quantity,
                unit_price=quote_item.unit_price,
                total_price=quote_item.total_price,
                recurring_price=quote_item.recurring_price,
                description=quote_item.description
            )
            order_items.append(order_item)

        # Create order
        order, errors = self.create_order(
            customer_id=customer_id,
            items=order_items,
            validate=True
        )

        # Mark quote as accepted
        quote.accept()

        return order, errors

    def register_fulfillment_handler(self, offering_id: str, handler: Any) -> None:
        """Register a fulfillment handler for a product offering."""
        self.fulfillment_engine.register_handler(offering_id, handler)

    def register_compensator(self, offering_id: str, compensator: Any) -> None:
        """Register a compensator for a product offering."""
        self.compensation_handler.register_compensator(offering_id, compensator)

    def register_webhook(self, url: str, secret: Optional[str] = None) -> None:
        """Register a webhook for order notifications."""
        self.notification_manager.register_webhook(url, secret)

    def get_order_history(self, order_id: str) -> List[Dict[str, Any]]:
        """Get the full history of an order (state changes + fulfillment + compensation)."""
        state_history = self.lifecycle_manager.get_state_history(order_id)
        fulfillment_log = self.fulfillment_engine.get_fulfillment_log(order_id)
        compensation_log = self.compensation_handler.get_compensation_log(order_id)
        notification_log = self.notification_manager.get_notification_log(order_id)

        return {
            "state_history": state_history,
            "fulfillment_log": fulfillment_log,
            "compensation_log": compensation_log,
            "notification_log": notification_log
        }

    def add_pricing_rule(self, offering_id: str, rule: Dict[str, Any]) -> None:
        """Add a pricing rule."""
        self.validation_engine.add_pricing_rule(offering_id, rule)

    def add_eligibility_rule(self, offering_id: str, field: str, operator: str,
                            value: Any, message: str) -> None:
        """Add an eligibility rule."""
        self.validation_engine.add_eligibility_rule(offering_id, field, operator, value, message)
