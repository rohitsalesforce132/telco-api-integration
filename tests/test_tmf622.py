"""
Unit tests for TMF622 Product Ordering.
Tests all components: ProductOrderManager, OrderLifecycleManager, QuoteManager,
OrderValidationEngine, OrderFulfillmentEngine, OrderCompensationHandler,
OrderNotificationManager, and supporting classes (ProductOrder, OrderItem, Quote).
"""

import unittest
from datetime import datetime, timedelta
import json

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tmf622.ordering import (
    ProductOrderManager, OrderLifecycleManager, QuoteManager,
    OrderValidationEngine, OrderFulfillmentEngine, OrderCompensationHandler,
    OrderNotificationManager, ProductOrder, OrderItem, Quote, QuoteItem,
    OrderState, OrderItemState, QuoteState
)


class TestQuoteItem(unittest.TestCase):
    """Test QuoteItem functionality."""

    def test_create_quote_item(self):
        """Test creating a quote item."""
        item = QuoteItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Mobile Plan",
            quantity=1,
            unit_price=29.99,
            total_price=29.99
        )
        self.assertEqual(item.id, "item1")
        self.assertEqual(item.total_price, 29.99)

    def test_quote_item_with_recurring_price(self):
        """Test quote item with recurring pricing."""
        item = QuoteItem(
            id="item2",
            product_offering_id="off1",
            product_offering_name="Mobile Plan",
            quantity=1,
            unit_price=0.0,
            total_price=0.0,
            recurring_price=29.99
        )
        self.assertEqual(item.recurring_price, 29.99)

    def test_quote_item_to_dict(self):
        """Test quote item serialization."""
        item = QuoteItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=2,
            unit_price=10.0,
            total_price=20.0
        )
        data = item.to_dict()
        self.assertEqual(data['id'], "item1")
        self.assertEqual(data['total_price'], 20.0)


class TestQuote(unittest.TestCase):
    """Test Quote functionality."""

    def test_create_quote(self):
        """Test creating a quote."""
        quote = Quote(id="quote1", customer_id="cust1")
        self.assertEqual(quote.id, "quote1")
        self.assertEqual(quote.customer_id, "cust1")
        self.assertEqual(quote.state, QuoteState.DRAFT)

    def test_add_item(self):
        """Test adding items to quote."""
        quote = Quote(id="quote1")
        quote.add_item("off1", "Mobile Plan", 1, 29.99)
        self.assertEqual(len(quote.items), 1)
        self.assertEqual(quote.total_one_time_price, 29.99)

    def test_add_item_with_recurring(self):
        """Test adding item with recurring price."""
        quote = Quote(id="quote1")
        quote.add_item("off1", "Mobile Plan", 1, 0.0, recurring_price=29.99)
        self.assertEqual(quote.total_recurring_price, 29.99)

    def test_remove_item(self):
        """Test removing items from quote."""
        quote = Quote(id="quote1")
        quote.add_item("off1", "Plan A", 1, 10.0)
        item_id = quote.items[0].id
        self.assertTrue(quote.remove_item(item_id))
        self.assertEqual(len(quote.items), 0)

    def test_validate_quote(self):
        """Test quote validation."""
        quote = Quote(id="quote1")
        quote.set_validity(24)
        self.assertTrue(quote.validate())

    def test_expired_quote(self):
        """Test expired quote validation."""
        quote = Quote(id="quote1")
        quote.valid_until = datetime.now() - timedelta(hours=1)
        quote.state = QuoteState.VALID

        self.assertFalse(quote.validate())
        self.assertEqual(quote.state, QuoteState.EXPIRED)

    def test_set_validity(self):
        """Test setting quote validity."""
        quote = Quote(id="quote1")
        quote.set_validity(48)
        self.assertEqual(quote.state, QuoteState.VALID)
        self.assertIsNotNone(quote.valid_until)

    def test_accept_quote(self):
        """Test accepting a quote."""
        quote = Quote(id="quote1")
        quote.add_item("off1", "Plan", 1, 10.0)
        quote.set_validity(24)
        quote.accept()
        self.assertEqual(quote.state, QuoteState.ACCEPTED)

    def test_accept_expired_quote(self):
        """Test accepting an expired quote (should fail)."""
        quote = Quote(id="quote1")
        quote.valid_until = datetime.now() - timedelta(hours=1)
        quote.state = QuoteState.EXPIRED

        with self.assertRaises(ValueError):
            quote.accept()

    def test_reject_quote(self):
        """Test rejecting a quote."""
        quote = Quote(id="quote1")
        quote.reject()
        self.assertEqual(quote.state, QuoteState.REJECTED)

    def test_quote_to_dict(self):
        """Test quote serialization."""
        quote = Quote(id="quote1", customer_id="cust1")
        quote.add_item("off1", "Plan", 1, 10.0)
        data = quote.to_dict()
        self.assertEqual(data['id'], "quote1")
        self.assertEqual(data['customer_id'], "cust1")
        self.assertEqual(len(data['items']), 1)


class TestOrderItem(unittest.TestCase):
    """Test OrderItem functionality."""

    def test_create_order_item(self):
        """Test creating an order item."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Mobile Plan",
            quantity=1,
            unit_price=29.99,
            total_price=29.99
        )
        self.assertEqual(item.id, "item1")
        self.assertEqual(item.state, OrderItemState.ACKNOWLEDGED)

    def test_transition_state(self):
        """Test state transitions."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )

        # Valid: ACKNOWLEDGED -> IN_PROGRESS
        self.assertTrue(item.transition_state(OrderItemState.IN_PROGRESS))
        self.assertEqual(item.state, OrderItemState.IN_PROGRESS)

        # Valid: IN_PROGRESS -> COMPLETED
        self.assertTrue(item.transition_state(OrderItemState.COMPLETED))
        self.assertEqual(item.state, OrderItemState.COMPLETED)

    def test_invalid_state_transition(self):
        """Test invalid state transition."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )
        item.transition_state(OrderItemState.IN_PROGRESS)
        item.transition_state(OrderItemState.COMPLETED)

        # Invalid: COMPLETED -> IN_PROGRESS
        self.assertFalse(item.transition_state(OrderItemState.IN_PROGRESS))

    def test_failed_item_retry(self):
        """Test retrying a failed item."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )
        item.transition_state(OrderItemState.IN_PROGRESS)
        item.transition_state(OrderItemState.FAILED)

        # Should allow retry
        self.assertTrue(item.transition_state(OrderItemState.IN_PROGRESS))

    def test_cancel_item(self):
        """Test cancelling an item."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )
        self.assertTrue(item.transition_state(OrderItemState.CANCELLED))
        self.assertEqual(item.state, OrderItemState.CANCELLED)

    def test_item_to_dict(self):
        """Test item serialization."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=10.0,
            total_price=10.0
        )
        data = item.to_dict()
        self.assertEqual(data['id'], "item1")
        self.assertEqual(data['state'], "acknowledged")


class TestProductOrder(unittest.TestCase):
    """Test ProductOrder functionality."""

    def test_create_order(self):
        """Test creating a product order."""
        order = ProductOrder(
            id="order1",
            customer_id="cust1",
            items=[],
            total_amount=0.0
        )
        self.assertEqual(order.id, "order1")
        self.assertEqual(order.customer_id, "cust1")
        self.assertEqual(order.state, OrderState.ACKNOWLEDGED)

    def test_add_item(self):
        """Test adding items to order."""
        order = ProductOrder(id="order1", customer_id="cust1")
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=10.0,
            total_price=10.0
        )
        order.add_item(item)
        self.assertEqual(len(order.items), 1)
        self.assertEqual(order.total_amount, 10.0)

    def test_add_item_after_processing(self):
        """Test that items cannot be added after processing starts."""
        order = ProductOrder(id="order1", customer_id="cust1")
        order.transition_state(OrderState.IN_PROGRESS)

        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )

        with self.assertRaises(ValueError):
            order.add_item(item)

    def test_remove_item(self):
        """Test removing items from order."""
        order = ProductOrder(id="order1", customer_id="cust1")
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=10.0,
            total_price=10.0
        )
        order.add_item(item)
        self.assertTrue(order.remove_item("item1"))
        self.assertEqual(len(order.items), 0)
        self.assertEqual(order.total_amount, 0.0)

    def test_transition_state(self):
        """Test order state transitions."""
        order = ProductOrder(id="order1", customer_id="cust1")

        # ACKNOWLEDGED -> IN_PROGRESS
        self.assertTrue(order.transition_state(OrderState.IN_PROGRESS))
        self.assertEqual(order.state, OrderState.IN_PROGRESS)

        # IN_PROGRESS -> COMPLETED
        self.assertTrue(order.transition_state(OrderState.COMPLETED))
        self.assertEqual(order.state, OrderState.COMPLETED)

    def test_invalid_state_transition(self):
        """Test invalid state transition."""
        order = ProductOrder(id="order1", customer_id="cust1")
        order.transition_state(OrderState.IN_PROGRESS)
        order.transition_state(OrderState.COMPLETED)

        # Invalid: COMPLETED -> IN_PROGRESS
        self.assertFalse(order.transition_state(OrderState.IN_PROGRESS))

    def test_cancel_order(self):
        """Test cancelling an order."""
        order = ProductOrder(id="order1", customer_id="cust1")
        self.assertTrue(order.transition_state(OrderState.CANCELLED))
        self.assertEqual(order.state, OrderState.CANCELLED)
        self.assertIsNotNone(order.actual_completion_date)

    def test_get_item_state_summary(self):
        """Test getting item state summary."""
        order = ProductOrder(id="order1", customer_id="cust1")
        item1 = OrderItem(id="item1", product_offering_id="off1", product_offering_name="A", quantity=1)
        item2 = OrderItem(id="item2", product_offering_id="off2", product_offering_name="B", quantity=1)

        # Proper state transitions
        item1.transition_state(OrderItemState.IN_PROGRESS)
        item1.transition_state(OrderItemState.COMPLETED)
        item2.transition_state(OrderItemState.IN_PROGRESS)
        item2.transition_state(OrderItemState.FAILED)

        order.add_item(item1)
        order.add_item(item2)

        summary = order.get_item_state_summary()
        self.assertEqual(summary['completed'], 1)
        self.assertEqual(summary['failed'], 1)

    def test_is_complete(self):
        """Test checking if order is complete."""
        order = ProductOrder(id="order1", customer_id="cust1")
        item1 = OrderItem(id="item1", product_offering_id="off1", product_offering_name="A", quantity=1)
        item2 = OrderItem(id="item2", product_offering_id="off2", product_offering_name="B", quantity=1)

        # Proper state transitions
        item1.transition_state(OrderItemState.IN_PROGRESS)
        item1.transition_state(OrderItemState.COMPLETED)
        item2.transition_state(OrderItemState.IN_PROGRESS)
        item2.transition_state(OrderItemState.COMPLETED)

        order.add_item(item1)
        order.add_item(item2)

        self.assertTrue(order.is_complete())

    def test_has_failures(self):
        """Test checking if order has failures."""
        order = ProductOrder(id="order1", customer_id="cust1")
        item1 = OrderItem(id="item1", product_offering_id="off1", product_offering_name="A", quantity=1)
        item2 = OrderItem(id="item2", product_offering_id="off2", product_offering_name="B", quantity=1)

        # Proper state transitions
        item1.transition_state(OrderItemState.IN_PROGRESS)
        item1.transition_state(OrderItemState.COMPLETED)
        item2.transition_state(OrderItemState.IN_PROGRESS)
        item2.transition_state(OrderItemState.FAILED)

        order.add_item(item1)
        order.add_item(item2)

        self.assertTrue(order.has_failures())

    def test_order_to_dict(self):
        """Test order serialization."""
        order = ProductOrder(id="order1", customer_id="cust1")
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )
        order.add_item(item)

        data = order.to_dict()
        self.assertEqual(data['id'], "order1")
        self.assertEqual(data['customer_id'], "cust1")
        self.assertEqual(len(data['items']), 1)


class TestQuoteManager(unittest.TestCase):
    """Test QuoteManager functionality."""

    def setUp(self):
        """Set up quote manager."""
        self.manager = QuoteManager()

    def test_create_quote(self):
        """Test creating a quote."""
        quote = self.manager.create_quote(customer_id="cust1")
        self.assertIsNotNone(quote.id)
        self.assertEqual(quote.customer_id, "cust1")

    def test_get_quote(self):
        """Test getting a quote."""
        quote = self.manager.create_quote()
        retrieved = self.manager.get_quote(quote.id)
        self.assertEqual(retrieved.id, quote.id)

    def test_finalize_quote(self):
        """Test finalizing a quote."""
        quote = self.manager.create_quote()
        quote.add_item("off1", "Plan", 1, 10.0)

        finalized = self.manager.finalize_quote(quote.id, 24)
        self.assertEqual(finalized.state, QuoteState.VALID)
        self.assertIsNotNone(finalized.valid_until)

    def test_finalize_empty_quote(self):
        """Test finalizing an empty quote (should fail)."""
        quote = self.manager.create_quote()

        with self.assertRaises(ValueError):
            self.manager.finalize_quote(quote.id)

    def test_list_quotes(self):
        """Test listing quotes."""
        self.manager.create_quote(customer_id="cust1")
        self.manager.create_quote(customer_id="cust2")

        quotes = self.manager.list_quotes()
        self.assertEqual(len(quotes), 2)

    def test_list_quotes_filtered(self):
        """Test listing quotes with filters."""
        q1 = self.manager.create_quote(customer_id="cust1")
        q2 = self.manager.create_quote(customer_id="cust2")

        q1.state = QuoteState.ACCEPTED

        cust1_quotes = self.manager.list_quotes(customer_id="cust1")
        self.assertEqual(len(cust1_quotes), 1)

        accepted_quotes = self.manager.list_quotes(state=QuoteState.ACCEPTED)
        self.assertEqual(len(accepted_quotes), 1)

    def test_delete_quote(self):
        """Test deleting a quote."""
        quote = self.manager.create_quote()
        self.assertTrue(self.manager.delete_quote(quote.id))
        self.assertIsNone(self.manager.get_quote(quote.id))

    def test_delete_non_draft_quote(self):
        """Test deleting a non-draft quote (should fail)."""
        quote = self.manager.create_quote()
        quote.state = QuoteState.VALID

        with self.assertRaises(ValueError):
            self.manager.delete_quote(quote.id)


class TestOrderValidationEngine(unittest.TestCase):
    """Test OrderValidationEngine functionality."""

    def setUp(self):
        """Set up validation engine."""
        self.validator = OrderValidationEngine()

    def test_validate_valid_order(self):
        """Test validating a valid order."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=10.0,
            total_price=10.0
        )
        order = ProductOrder(
            id="order1",
            customer_id="cust1",
            items=[item],
            total_amount=10.0
        )

        is_valid, errors = self.validator.validate_order(order)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_order_missing_customer(self):
        """Test validating order without customer_id."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=10.0,
            total_price=10.0
        )
        order = ProductOrder(
            id="order1",
            customer_id="",
            items=[item],
            total_amount=10.0
        )

        is_valid, errors = self.validator.validate_order(order)
        self.assertFalse(is_valid)
        self.assertIn("customer_id", str(errors))

    def test_validate_empty_order(self):
        """Test validating an empty order."""
        order = ProductOrder(
            id="order1",
            customer_id="cust1",
            items=[],
            total_amount=0.0
        )

        is_valid, errors = self.validator.validate_order(order)
        self.assertFalse(is_valid)
        self.assertIn("at least one item", str(errors).lower())

    def test_validate_invalid_quantity(self):
        """Test validating item with invalid quantity."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=0,  # Invalid
            unit_price=10.0,
            total_price=0.0
        )
        order = ProductOrder(
            id="order1",
            customer_id="cust1",
            items=[item],
            total_amount=0.0
        )

        is_valid, errors = self.validator.validate_order(order)
        self.assertFalse(is_valid)

    def test_validate_negative_price(self):
        """Test validating item with negative price."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=-10.0,  # Invalid
            total_price=-10.0
        )
        order = ProductOrder(
            id="order1",
            customer_id="cust1",
            items=[item],
            total_amount=-10.0
        )

        is_valid, errors = self.validator.validate_order(order)
        self.assertFalse(is_valid)

    def test_validate_price_mismatch(self):
        """Test validating order with price mismatch."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=2,
            unit_price=10.0,
            total_price=15.0  # Should be 20.0
        )
        order = ProductOrder(
            id="order1",
            customer_id="cust1",
            items=[item],
            total_amount=15.0
        )

        is_valid, errors = self.validator.validate_order(order)
        self.assertFalse(is_valid)
        self.assertIn("total price", str(errors).lower())

    def test_validate_past_completion_date(self):
        """Test validating order with past completion date."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=10.0,
            total_price=10.0
        )
        order = ProductOrder(
            id="order1",
            customer_id="cust1",
            items=[item],
            total_amount=10.0,
            requested_completion_date=datetime.now() - timedelta(days=1)
        )

        is_valid, errors = self.validator.validate_order(order)
        self.assertFalse(is_valid)
        self.assertIn("past", str(errors).lower())

    def test_add_pricing_rule(self):
        """Test adding a pricing rule."""
        self.validator.add_pricing_rule("off1", {"type": "discount", "value": 10})
        self.assertIn("off1", self.validator.pricing_rules)

    def test_add_eligibility_rule(self):
        """Test adding an eligibility rule."""
        self.validator.add_eligibility_rule(
            "off1",
            "age",
            ">=",
            18,
            "Must be 18+"
        )
        self.assertIn("off1", self.validator.eligibility_rules)


class TestOrderFulfillmentEngine(unittest.TestCase):
    """Test OrderFulfillmentEngine functionality."""

    def setUp(self):
        """Set up fulfillment engine."""
        self.engine = OrderFulfillmentEngine()

    def test_register_handler(self):
        """Test registering a fulfillment handler."""
        handler = type('Handler', (), {
            'fulfill': lambda self, item, order: True
        })()
        self.engine.register_handler("off1", handler)
        self.assertIn("off1", self.engine.fulfillment_handlers)

    def test_fulfill_order_success(self):
        """Test successful order fulfillment."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )
        order = ProductOrder(id="order1", customer_id="cust1", items=[item])

        success, errors = self.engine.fulfill_order(order)
        self.assertTrue(success)
        self.assertEqual(item.state, OrderItemState.COMPLETED)

    def test_fulfill_order_with_handler(self):
        """Test fulfillment with custom handler."""
        handler = type('Handler', (), {
            'fulfill': lambda self, item, order: True
        })()
        self.engine.register_handler("off1", handler)

        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )
        order = ProductOrder(id="order1", customer_id="cust1", items=[item])

        success, errors = self.engine.fulfill_order(order)
        self.assertTrue(success)

    def test_fulfill_order_handler_failure(self):
        """Test fulfillment when handler fails."""
        handler = type('Handler', (), {
            'fulfill': lambda self, item, order: False
        })()
        self.engine.register_handler("off1", handler)

        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )
        order = ProductOrder(id="order1", customer_id="cust1", items=[item])

        success, errors = self.engine.fulfill_order(order)
        self.assertFalse(success)
        self.assertEqual(item.state, OrderItemState.FAILED)

    def test_fulfill_partial_success(self):
        """Test fulfillment with partial success."""
        handler_success = type('Handler', (), {
            'fulfill': lambda self, item, order: True
        })()
        handler_fail = type('Handler', (), {
            'fulfill': lambda self, item, order: False
        })()

        self.engine.register_handler("off1", handler_success)
        self.engine.register_handler("off2", handler_fail)

        item1 = OrderItem(id="item1", product_offering_id="off1", product_offering_name="A", quantity=1)
        item2 = OrderItem(id="item2", product_offering_id="off2", product_offering_name="B", quantity=1)

        order = ProductOrder(id="order1", customer_id="cust1", items=[item1, item2])

        success, errors = self.engine.fulfill_order(order)
        self.assertTrue(success)  # Partial success counts as success
        self.assertEqual(order.state, OrderState.PARTIAL)

    def test_get_fulfillment_log(self):
        """Test getting fulfillment log."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )
        order = ProductOrder(id="order1", customer_id="cust1", items=[item])

        self.engine.fulfill_order(order)

        logs = self.engine.get_fulfillment_log(order.id)
        self.assertEqual(len(logs), 1)


class TestOrderCompensationHandler(unittest.TestCase):
    """Test OrderCompensationHandler functionality."""

    def setUp(self):
        """Set up compensation handler."""
        self.compensator = OrderCompensationHandler()

    def test_register_compensator(self):
        """Test registering a compensator."""
        comp = type('Compensator', (), {
            'compensate': lambda self, item, order: True
        })()
        self.compensator.register_compensator("off1", comp)
        self.assertIn("off1", self.compensator.compensators)

    def test_compensate_order(self):
        """Test compensating an order."""
        item = OrderItem(id="item1", product_offering_id="off1", product_offering_name="Test", quantity=1)
        item.transition_state(OrderItemState.COMPLETED)

        order = ProductOrder(id="order1", customer_id="cust1", items=[item])

        success, errors = self.compensator.compensate_order(order)
        self.assertTrue(success)
        self.assertEqual(len(errors), 0)

    def test_compensate_with_compensator(self):
        """Test compensation with custom compensator."""
        comp = type('Compensator', (), {
            'compensate': lambda self, item, order: True
        })()
        self.compensator.register_compensator("off1", comp)

        item = OrderItem(id="item1", product_offering_id="off1", product_offering_name="Test", quantity=1)
        item.transition_state(OrderItemState.IN_PROGRESS)
        item.transition_state(OrderItemState.COMPLETED)

        order = ProductOrder(id="order1", customer_id="cust1", items=[item])

        success, errors = self.compensator.compensate_order(order)
        self.assertTrue(success)

    def test_get_compensation_log(self):
        """Test getting compensation log."""
        item = OrderItem(id="item1", product_offering_id="off1", product_offering_name="Test", quantity=1)
        item.transition_state(OrderItemState.IN_PROGRESS)
        item.transition_state(OrderItemState.COMPLETED)

        order = ProductOrder(id="order1", customer_id="cust1", items=[item])

        self.compensator.compensate_order(order)

        logs = self.compensator.get_compensation_log(order.id)
        self.assertEqual(len(logs), 1)


class TestOrderNotificationManager(unittest.TestCase):
    """Test OrderNotificationManager functionality."""

    def setUp(self):
        """Set up notification manager."""
        self.notifier = OrderNotificationManager()

    def test_register_webhook(self):
        """Test registering a webhook."""
        self.notifier.register_webhook("https://example.com/webhook", "secret123")
        self.assertEqual(len(self.notifier.webhooks), 1)

    def test_send_notification(self):
        """Test sending a notification."""
        order = ProductOrder(id="order1", customer_id="cust1")
        success = self.notifier.send_notification(order, "order_created", "cust1@example.com")
        self.assertTrue(success)

    def test_send_webhook(self):
        """Test sending webhooks."""
        self.notifier.register_webhook("https://example.com/webhook")
        order = ProductOrder(id="order1", customer_id="cust1")

        success, errors = self.notifier.send_webhook(order, "order_created")
        self.assertTrue(success)

    def test_get_notification_log(self):
        """Test getting notification log."""
        order = ProductOrder(id="order1", customer_id="cust1")
        self.notifier.send_notification(order, "order_created")

        logs = self.notifier.get_notification_log(order.id)
        self.assertEqual(len(logs), 1)


class TestOrderLifecycleManager(unittest.TestCase):
    """Test OrderLifecycleManager functionality."""

    def setUp(self):
        """Set up lifecycle manager."""
        self.manager = OrderLifecycleManager()

    def test_create_order(self):
        """Test creating an order."""
        items = []
        order = self.manager.create_order(
            customer_id="cust1",
            items=items,
            priority="high"
        )
        self.assertIsNotNone(order.id)
        self.assertEqual(order.customer_id, "cust1")
        self.assertEqual(order.priority, "high")

    def test_get_order(self):
        """Test getting an order."""
        order = self.manager.create_order(customer_id="cust1", items=[])
        retrieved = self.manager.get_order(order.id)
        self.assertEqual(retrieved.id, order.id)

    def test_list_orders(self):
        """Test listing orders."""
        self.manager.create_order(customer_id="cust1", items=[])
        self.manager.create_order(customer_id="cust2", items=[])

        orders = self.manager.list_orders()
        self.assertEqual(len(orders), 2)

    def test_list_orders_filtered(self):
        """Test listing orders with filters."""
        o1 = self.manager.create_order(customer_id="cust1", items=[])
        o2 = self.manager.create_order(customer_id="cust2", items=[])

        o1.transition_state(OrderState.IN_PROGRESS)
        o1.transition_state(OrderState.COMPLETED)

        cust1_orders = self.manager.list_orders(customer_id="cust1")
        self.assertEqual(len(cust1_orders), 1)

        completed_orders = self.manager.list_orders(state=OrderState.COMPLETED)
        self.assertEqual(len(completed_orders), 1)

    def test_update_order_state(self):
        """Test updating order state."""
        order = self.manager.create_order(customer_id="cust1", items=[])
        success = self.manager.update_order_state(order.id, OrderState.IN_PROGRESS)
        self.assertTrue(success)
        self.assertEqual(order.state, OrderState.IN_PROGRESS)

    def test_cancel_order(self):
        """Test cancelling an order."""
        order = self.manager.create_order(customer_id="cust1", items=[])
        success = self.manager.cancel_order(order.id, "Customer request")
        self.assertTrue(success)
        self.assertEqual(order.state, OrderState.CANCELLED)

    def test_get_state_history(self):
        """Test getting state history."""
        order = self.manager.create_order(customer_id="cust1", items=[])
        self.manager.update_order_state(order.id, OrderState.IN_PROGRESS)
        self.manager.update_order_state(order.id, OrderState.COMPLETED)

        history = self.manager.get_state_history(order.id)
        self.assertGreater(len(history), 0)


class TestProductOrderManager(unittest.TestCase):
    """Test ProductOrderManager functionality (integration)."""

    def setUp(self):
        """Set up product order manager."""
        self.manager = ProductOrderManager()

    def test_create_order(self):
        """Test creating an order."""
        items = []
        order, errors = self.manager.create_order(
            customer_id="cust1",
            items=items
        )
        self.assertIsNotNone(order.id)
        self.assertEqual(order.customer_id, "cust1")

    def test_create_order_with_validation(self):
        """Test creating an order with validation."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=10.0,
            total_price=10.0
        )
        order, errors = self.manager.create_order(
            customer_id="cust1",
            items=[item],
            validate=True
        )
        self.assertEqual(len(errors), 0)

    def test_submit_order(self):
        """Test submitting an order."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=10.0,
            total_price=10.0
        )
        order, errors = self.manager.create_order(
            customer_id="cust1",
            items=[item],
            validate=False
        )

        success, submit_errors = self.manager.submit_order(order.id)
        self.assertTrue(success)
        self.assertEqual(order.state, OrderState.COMPLETED)

    def test_cancel_order(self):
        """Test cancelling an order."""
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1
        )
        order, _ = self.manager.create_order(
            customer_id="cust1",
            items=[item],
            validate=False
        )

        success, errors = self.manager.cancel_order(order.id, "Customer request")
        self.assertTrue(success)
        self.assertEqual(order.state, OrderState.CANCELLED)

    def test_create_quote(self):
        """Test creating a quote."""
        quote = self.manager.create_quote(customer_id="cust1")
        self.assertIsNotNone(quote.id)

    def test_get_quote(self):
        """Test getting a quote."""
        quote = self.manager.create_quote()
        retrieved = self.manager.get_quote(quote.id)
        self.assertEqual(retrieved.id, quote.id)

    def test_finalize_quote(self):
        """Test finalizing a quote."""
        quote = self.manager.create_quote()
        quote.add_item("off1", "Test", 1, 10.0)

        finalized = self.manager.finalize_quote(quote.id)
        self.assertEqual(finalized.state, QuoteState.VALID)

    def test_convert_quote_to_order(self):
        """Test converting a quote to an order."""
        quote = self.manager.create_quote(customer_id="cust1")
        quote.add_item("off1", "Test", 1, 10.0, recurring_price=5.0)
        self.manager.finalize_quote(quote.id)

        order, errors = self.manager.convert_quote_to_order(quote.id, "cust1")
        self.assertIsNotNone(order)
        self.assertEqual(len(order.items), 1)
        self.assertEqual(quote.state, QuoteState.ACCEPTED)

    def test_register_handlers(self):
        """Test registering fulfillment and compensation handlers."""
        handler = type('Handler', (), {
            'fulfill': lambda self, item, order: True,
            'compensate': lambda self, item, order: True
        })()

        self.manager.register_fulfillment_handler("off1", handler)
        self.manager.register_compensator("off1", handler)

        self.assertIn("off1", self.manager.fulfillment_engine.fulfillment_handlers)
        self.assertIn("off1", self.manager.compensation_handler.compensators)

    def test_register_webhook(self):
        """Test registering a webhook."""
        self.manager.register_webhook("https://example.com/webhook", "secret")
        self.assertEqual(len(self.manager.notification_manager.webhooks), 1)

    def test_get_order_history(self):
        """Test getting full order history."""
        item = OrderItem(id="item1", product_offering_id="off1", product_offering_name="Test", quantity=1)
        order, _ = self.manager.create_order(customer_id="cust1", items=[item], validate=False)

        self.manager.submit_order(order.id)

        history = self.manager.get_order_history(order.id)
        self.assertIn("state_history", history)
        self.assertIn("fulfillment_log", history)

    def test_add_rules(self):
        """Test adding pricing and eligibility rules."""
        self.manager.add_pricing_rule("off1", {"type": "discount", "value": 10})
        self.manager.add_eligibility_rule("off1", "age", ">=", 18, "Must be 18+")

        self.assertIn("off1", self.manager.validation_engine.pricing_rules)
        self.assertIn("off1", self.manager.validation_engine.eligibility_rules)


class TestTMF622Integration(unittest.TestCase):
    """Integration tests for TMF622 components."""

    def test_full_order_workflow(self):
        """Test complete order workflow from quote to completion."""
        manager = ProductOrderManager()

        # Create quote
        quote = manager.create_quote(customer_id="cust1")
        quote.add_item("off1", "Mobile Plan", 1, 29.99, recurring_price=29.99)
        quote.add_item("off2", "Data Add-on", 2, 10.0)

        manager.finalize_quote(quote.id)

        # Convert to order
        order, errors = manager.convert_quote_to_order(quote.id, "cust1")
        self.assertEqual(len(errors), 0)

        # Submit order
        success, errors = manager.submit_order(order.id)
        self.assertTrue(success)
        self.assertEqual(order.state, OrderState.COMPLETED)

    def test_quote_to_order_with_validation(self):
        """Test quote to order with validation rules."""
        manager = ProductOrderManager()

        # Add eligibility rule
        manager.add_eligibility_rule("off1", "age", ">=", 18, "Must be 18+")

        # Create quote
        quote = manager.create_quote(customer_id="cust1")
        quote.add_item("off1", "Premium Plan", 1, 49.99)
        manager.finalize_quote(quote.id)

        # Convert with customer context
        order, errors = manager.convert_quote_to_order(quote.id, "cust1")

        # Note: This would fail if we passed customer context with age < 18
        self.assertIsNotNone(order)

    def test_order_with_fulfillment_and_compensation(self):
        """Test order fulfillment and compensation flow."""
        manager = ProductOrderManager()

        # Register handler
        handler = type('Handler', (), {
            'fulfill': lambda self, item, order: True,
            'compensate': lambda self, item, order: True
        })()
        manager.register_fulfillment_handler("off1", handler)
        manager.register_compensator("off1", handler)

        # Create and submit order
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=10.0,
            total_price=10.0
        )
        order, _ = manager.create_order(customer_id="cust1", items=[item], validate=False)

        # Submit the order
        success, errors = manager.submit_order(order.id)
        self.assertTrue(success)
        self.assertEqual(order.state, OrderState.COMPLETED)

        # Now try to cancel - should fail because order is completed
        success, errors = manager.cancel_order(order.id)
        self.assertFalse(success)

        # Check compensation log (should be empty because cancel failed)
        history = manager.get_order_history(order.id)
        self.assertEqual(len(history['compensation_log']), 0)

    def test_notification_workflow(self):
        """Test order notification workflow."""
        manager = ProductOrderManager()

        # Register webhook
        manager.register_webhook("https://example.com/webhook", "secret")

        # Create and submit order
        item = OrderItem(
            id="item1",
            product_offering_id="off1",
            product_offering_name="Test",
            quantity=1,
            unit_price=0.0,
            total_price=0.0
        )
        order, _ = manager.create_order(customer_id="cust1", items=[item], validate=False)

        manager.submit_order(order.id)

        # Check notifications
        history = manager.get_order_history(order.id)
        self.assertGreater(len(history['notification_log']), 0)


if __name__ == '__main__':
    unittest.main()
