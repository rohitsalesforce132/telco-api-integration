#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

from tmf622.ordering import ProductOrderManager, OrderItem

def test_order_with_fulfillment_and_compensation():
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

    success, errors = manager.submit_order(order.id)
    print(f'Submit success: {success}')
    print(f'Submit errors: {errors}')

    assert success, f"Expected success but got: {errors}"

    # Cancel and compensate
    success, errors = manager.cancel_order(order.id)
    assert success, f"Expected cancel success but got: {errors}"

    # Check compensation log
    history = manager.get_order_history(order.id)
    assert len(history['compensation_log']) == 1, f"Expected 1 compensation log entry but got {len(history['compensation_log'])}"

    print("All assertions passed!")

if __name__ == '__main__':
    test_order_with_fulfillment_and_compensation()
