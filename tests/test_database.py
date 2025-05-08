import pytest
from datetime import datetime, timedelta
import uuid
from models import Customer, Item, Order, OrderItem
from database import calculate_production_date, generate_subscription_orders, get_delivery_schedule
from database import get_production_plan, get_transfer_schedule


def test_calculate_production_date(test_db, sample_data):
    """Test production date calculation based on growth periods"""
    # Get items from sample data
    items = sample_data['items']
    order_items = [
        OrderItem(item=items[0], amount=1),  # 6 days growth
        OrderItem(item=items[1], amount=1)   # 10 days growth
    ]
    
    delivery_date = datetime.now().date() + timedelta(days=14)
    production_date = calculate_production_date(delivery_date, order_items)
    
    # Production date should be delivery date minus the longest growth period (10 days)
    assert production_date == delivery_date - timedelta(days=10)


def test_generate_subscription_orders(test_db, sample_data):
    """Test subscription order generation"""
    # Create an order with weekly subscription
    customer = sample_data['customers'][0]
    item = sample_data['items'][0]
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=28)  # 4 weeks
    
    order = Order.create(
        customer=customer,
        delivery_date=from_date,
        production_date=from_date - timedelta(days=item.total_days),
        from_date=from_date,
        to_date=to_date,
        subscription_type=1,  # Weekly
        halbe_channel=False,
        order_id=uuid.uuid4(),
        is_future=True
    )
    
    # Add an item to the order
    OrderItem.create(order=order, item=item, amount=2.0)
    
    # Generate subscription orders
    future_orders = generate_subscription_orders(order)
    
    # Should generate 4 future orders (4 weeks - 1 initial order)
    assert len(future_orders) == 4
    
    # Check the dates of the generated orders
    expected_dates = [from_date + timedelta(days=7*i) for i in range(1, 5)]
    for i, future_order in enumerate(future_orders):
        assert future_order['delivery_date'] == expected_dates[i]
        assert future_order['subscription_type'] == 1
        assert future_order['from_date'] == from_date
        assert future_order['to_date'] == to_date


def test_order_edit_current_only(test_db, sample_data):
    """Test editing a single order without affecting future orders"""
    # Get subscription order from sample data
    sub_order = sample_data['orders'][1]  # This is the subscription order
    customer = sub_order.customer
    item = sample_data['items'][0]
    
    today = datetime.now().date()
    
    # Save the original halbe_channel value
    original_halbe_channel = sub_order.halbe_channel
    
    # Create additional future orders in the same subscription
    future_orders = []
    for i in range(1, 4):  # Create 3 future orders
        future_order = Order.create(
            customer=customer,
            delivery_date=today + timedelta(days=7*(i+1)),  # Weekly delivery
            production_date=today + timedelta(days=7*i),
            from_date=sub_order.from_date,
            to_date=sub_order.to_date,
            subscription_type=sub_order.subscription_type,
            halbe_channel=original_halbe_channel,
            order_id=uuid.uuid4(),
            is_future=True
        )
        OrderItem.create(order=future_order, item=item, amount=3.0)
        future_orders.append(future_order)
    
    # Now edit the first order
    modified_order = sub_order
    modified_order.halbe_channel = not modified_order.halbe_channel  # Toggle halbe_channel
    modified_order.save()
    
    # Update order items - change the amount
    for oi in modified_order.order_items:
        oi.amount = 4.0  # Changed from 3.0
        oi.save()
    
    # Verify the first order was changed
    updated_order = Order.get(Order.id == modified_order.id)
    assert updated_order.halbe_channel == modified_order.halbe_channel
    assert updated_order.order_items[0].amount == 4.0
    
    # Verify future orders were NOT changed
    for future_order in future_orders:
        fo = Order.get(Order.id == future_order.id)
        assert fo.halbe_channel == original_halbe_channel


def test_order_edit_with_future(test_db, sample_data):
    """Test editing an order and all its future instances"""
    # Similar setup as previous test
    sub_order = sample_data['orders'][1]
    customer = sub_order.customer
    item = sample_data['items'][0]
    
    today = datetime.now().date()
    
    # Store the original halbe_channel value
    original_halbe_channel = sub_order.halbe_channel
    
    # Create additional future orders in the same subscription
    future_orders = []
    for i in range(1, 4):
        future_order = Order.create(
            customer=customer,
            delivery_date=today + timedelta(days=7*(i+1)),
            production_date=today + timedelta(days=7*i),
            from_date=sub_order.from_date,
            to_date=sub_order.to_date,
            subscription_type=sub_order.subscription_type,
            halbe_channel=original_halbe_channel,
            order_id=uuid.uuid4(),
            is_future=True
        )
        OrderItem.create(order=future_order, item=item, amount=3.0)
        future_orders.append(future_order)
    
    # Now edit all orders in the subscription
    # In real app this would be done with a scope parameter
    all_orders = [sub_order] + future_orders
    for order in all_orders:
        order.halbe_channel = not original_halbe_channel
        order.save()
        
        # Update order items
        for oi in order.order_items:
            oi.amount = 5.0
            oi.save()
    
    # Verify all orders were changed
    for order_id in [o.id for o in all_orders]:
        updated = Order.get(Order.id == order_id)
        assert updated.halbe_channel == (not original_halbe_channel)
        assert updated.order_items[0].amount == 5.0


def test_order_delete_current_only(test_db, sample_data):
    """Test deleting a single order without affecting future orders"""
    # Setup subscription with multiple orders
    sub_order = sample_data['orders'][1]
    customer = sub_order.customer
    item = sample_data['items'][0]
    
    today = datetime.now().date()
    
    # Create additional future orders in the same subscription
    future_orders = []
    for i in range(1, 4):
        future_order = Order.create(
            customer=customer,
            delivery_date=today + timedelta(days=7*(i+1)),
            production_date=today + timedelta(days=7*i),
            from_date=sub_order.from_date,
            to_date=sub_order.to_date,
            subscription_type=sub_order.subscription_type,
            halbe_channel=sub_order.halbe_channel,
            order_id=uuid.uuid4(),
            is_future=True
        )
        OrderItem.create(order=future_order, item=item, amount=3.0)
        future_orders.append(future_order)
    
    # Delete the first order only
    order_id_to_delete = sub_order.id
    
    # First delete its order items
    for oi in sub_order.order_items:
        oi.delete_instance()
    
    # Then delete the order
    sub_order.delete_instance()
    
    # Verify the order is deleted
    with pytest.raises(Order.DoesNotExist):
        Order.get(Order.id == order_id_to_delete)
    
    # Verify future orders still exist
    for future_order in future_orders:
        assert Order.get(Order.id == future_order.id)


def test_order_delete_with_future(test_db, sample_data):
    """Test deleting an order and all its future instances"""
    # Setup subscription with multiple orders
    sub_order = sample_data['orders'][1]
    customer = sub_order.customer
    item = sample_data['items'][0]
    
    today = datetime.now().date()
    
    # Create additional future orders in the same subscription
    future_orders = []
    for i in range(1, 4):
        future_order = Order.create(
            customer=customer,
            delivery_date=today + timedelta(days=7*(i+1)),
            production_date=today + timedelta(days=7*i),
            from_date=sub_order.from_date,
            to_date=sub_order.to_date,
            subscription_type=sub_order.subscription_type,
            halbe_channel=sub_order.halbe_channel,
            order_id=uuid.uuid4(),
            is_future=True
        )
        OrderItem.create(order=future_order, item=item, amount=3.0)
        future_orders.append(future_order)
    
    # Get all order IDs for later verification
    all_order_ids = [sub_order.id] + [fo.id for fo in future_orders]
    
    # Delete all orders with the same subscription parameters
    orders_to_delete = Order.select().where(
        (Order.from_date == sub_order.from_date) &
        (Order.to_date == sub_order.to_date) &
        (Order.subscription_type == sub_order.subscription_type)
    )
    
    # First delete their order items
    for order in orders_to_delete:
        OrderItem.delete().where(OrderItem.order == order).execute()
    
    # Then delete the orders
    Order.delete().where(
        (Order.from_date == sub_order.from_date) &
        (Order.to_date == sub_order.to_date) &
        (Order.subscription_type == sub_order.subscription_type)
    ).execute()
    
    # Verify all orders are deleted
    for order_id in all_order_ids:
        with pytest.raises(Order.DoesNotExist):
            Order.get(Order.id == order_id)


def test_get_delivery_schedule(test_db, sample_data):
    """Test retrieving the delivery schedule for a specific time period"""
    today = datetime.now().date()
    next_week = today + timedelta(days=7)
    
    # Get delivery schedule for next week
    deliveries = get_delivery_schedule(next_week, next_week)
    
    # Both sample orders have delivery dates next week
    assert len(deliveries) == 2
    
    # Get delivery schedule for a different week
    two_weeks_later = today + timedelta(days=14)
    deliveries = get_delivery_schedule(two_weeks_later, two_weeks_later)
    
    # No orders scheduled for two weeks later
    assert len(deliveries) == 0


def test_get_production_plan(test_db, sample_data):
    """Test retrieving the production plan for a specific time period"""
    today = datetime.now().date()
    
    # Get production plan for today
    production = get_production_plan(today, today)
    
    # Both sample orders have production dates of today
    results = list(production)
    assert len(results) > 0  # May have multiple rows for different items
    
    # Verify the results contain expected items
    item_names = []
    for result in results:
        # Access the item name correctly from the result
        if hasattr(result, 'item'):
            # If it's an OrderItem object
            item_names.append(result.item.name)
        elif hasattr(result, 'name'):
            # If it's a named tuple or has a direct name attribute
            item_names.append(result.name)
    
    # Get expected item names from sample data
    expected_items = set(item.name for item in sample_data['items'])
    assert any(name in expected_items for name in item_names)


def test_get_transfer_schedule(test_db, sample_data):
    """Test retrieving the transfer schedule for a specific time period"""
    today = datetime.now().date()
    
    # Calculate transfer dates for sample items
    item_a = sample_data['items'][0]
    
    # The transfer date is calculated as:
    # production_date + (soaking_days + germination_days)
    # For our test order, production_date is today
    transfer_date = today + timedelta(days=item_a.soaking_days + item_a.germination_days)
    
    # Get transfer schedule that includes this date
    start_date = transfer_date - timedelta(days=1)
    end_date = transfer_date + timedelta(days=1)
    
    transfers = get_transfer_schedule(start_date, end_date)
    
    # Should have transfers for our sample items
    assert len(transfers) > 0
    
    # Verify at least one item is scheduled for transfer
    found_transfer = False
    for transfer in transfers:
        if transfer['date'] == transfer_date and item_a.name in transfer['item']:
            found_transfer = True
            break
    
    assert found_transfer, "Expected transfer not found in schedule" 