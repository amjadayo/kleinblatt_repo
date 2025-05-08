import pytest
from datetime import datetime, timedelta
import uuid
from models import Customer, Item, Order, OrderItem
from database import calculate_production_date, generate_subscription_orders
from database import get_delivery_schedule, get_production_plan, get_transfer_schedule
from conftest import normalize_date

def test_complete_order_workflow(test_db, sample_data):
    """Test the complete workflow from order creation to schedule updates and deletion"""
    # 1. SETUP - Get test data
    customer = sample_data['customers'][0]
    items = sample_data['items']
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    # 2. CREATE ORDER
    order = Order.create(
        customer=customer,
        delivery_date=tomorrow,
        production_date=today,
        from_date=None,
        to_date=None,
        subscription_type=0,
        halbe_channel=False,
        order_id=uuid.uuid4(),
        is_future=True
    )
    
    # Add multiple items to the order
    OrderItem.create(order=order, item=items[0], amount=2.0)
    OrderItem.create(order=order, item=items[1], amount=1.5)
    
    # 3. VERIFY ORDER IS IN DELIVERY SCHEDULE
    deliveries = get_delivery_schedule(tomorrow, tomorrow)
    assert len(deliveries) >= 1
    
    found_order = False
    for delivery in deliveries:
        if delivery.id == order.id:
            found_order = True
            assert delivery.customer.id == customer.id
            assert delivery.halbe_channel is False
            # Check items
            found_items = set()
            for item in delivery.order_items:
                found_items.add(item.item.id)
                if item.item.id == items[0].id:
                    assert item.amount == 2.0
                elif item.item.id == items[1].id:
                    assert item.amount == 1.5
            assert items[0].id in found_items
            assert items[1].id in found_items
    
    assert found_order, "The new order was not found in the delivery schedule"
    
    # 4. VERIFY ORDER IS IN PRODUCTION PLAN
    production = list(get_production_plan(today, today))
    assert len(production) > 0
    
    # Production plan returns aggregated amounts by item and date
    found_items = set()
    for prod in production:
        # The production plan records return item objects, not names
        if prod.item.name in [items[0].name, items[1].name]:
            found_items.add(prod.item.name)
    
    assert len(found_items) > 0, "None of the order items found in production plan"
    
    # 5. VERIFY ORDER IS IN TRANSFER SCHEDULE
    # Calculate expected transfer dates for each item
    transfer_date_0 = today + timedelta(days=items[0].soaking_days + items[0].germination_days)
    transfer_date_1 = today + timedelta(days=items[1].soaking_days + items[1].germination_days)
    
    # Get transfer schedule for the date range
    start_date = min(transfer_date_0, transfer_date_1) - timedelta(days=1)
    end_date = max(transfer_date_0, transfer_date_1) + timedelta(days=1)
    
    transfers = get_transfer_schedule(start_date, end_date)
    assert len(transfers) > 0
    
    # Check if our items are in the transfer schedule
    found_items = set()
    for transfer in transfers:
        if transfer['item'] in [items[0].name, items[1].name]:
            found_items.add(transfer['item'])
    
    assert len(found_items) > 0, "None of the order items found in transfer schedule"
    
    # 6. EDIT ORDER
    with test_db.atomic():
        # Change the halbe_channel flag
        order.halbe_channel = True
        order.save()
        
        # Update the amounts
        for oi in order.order_items:
            if oi.item.id == items[0].id:
                oi.amount = 3.0  # Change from 2.0 to 3.0
                oi.save()
    
    # 7. VERIFY CHANGES REFLECTED IN DELIVERY SCHEDULE
    deliveries_after = get_delivery_schedule(tomorrow, tomorrow)
    found_updated = False
    for delivery in deliveries_after:
        if delivery.id == order.id:
            found_updated = True
            assert delivery.halbe_channel is True  # Should be updated
            # Check items
            for item in delivery.order_items:
                if item.item.id == items[0].id:
                    assert item.amount == 3.0  # Should be updated
    
    assert found_updated, "Updated order not found in delivery schedule"
    
    # 8. DELETE ORDER
    with test_db.atomic():
        # Delete order items first
        OrderItem.delete().where(OrderItem.order == order).execute()
        
        # Then delete the order
        order.delete_instance()
    
    # 9. VERIFY ORDER IS REMOVED FROM DELIVERY SCHEDULE
    final_deliveries = get_delivery_schedule(tomorrow, tomorrow)
    for delivery in final_deliveries:
        assert delivery.id != order.id, "Order found in delivery schedule after deletion"
    
    # Success!
    assert True


def test_subscription_order_updates_future_schedules(test_db, sample_data):
    """Test that updates to subscription orders properly affect future schedules"""
    # 1. SETUP - Get test data
    customer = sample_data['customers'][0]
    item = sample_data['items'][0]
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=28)  # 4 weeks
    
    # 2. CREATE SUBSCRIPTION ORDER
    order = Order.create(
        customer=customer,
        delivery_date=from_date,
        production_date=calculate_production_date(from_date, [OrderItem(item=item, amount=1)]),
        from_date=from_date,
        to_date=to_date,
        subscription_type=1,  # Weekly
        halbe_channel=False,
        order_id=uuid.uuid4(),
        is_future=True
    )
    
    OrderItem.create(order=order, item=item, amount=2.0)
    
    # Generate subscription orders
    future_orders_data = generate_subscription_orders(order)
    future_orders = []
    
    for future_order_data in future_orders_data:
        future_order = Order.create(
            **future_order_data,
            order_id=uuid.uuid4()
        )
        OrderItem.create(order=future_order, item=item, amount=2.0)
        future_orders.append(future_order)
    
    # 3. VERIFY ALL ORDERS APPEAR IN SCHEDULES
    all_orders = [order] + future_orders
    all_dates = [o.delivery_date for o in all_orders]
    
    # Check each date in the delivery schedule
    for date_val in all_dates:
        deliveries = get_delivery_schedule(date_val, date_val)
        found = False
        for delivery in deliveries:
            if delivery.customer.id == customer.id and normalize_date(delivery.delivery_date) == date_val:
                found = True
                break
        assert found, f"Order for {date_val} not found in delivery schedule"
    
    # 4. UPDATE ALL FUTURE ORDERS (from 2nd order onwards)
    target_index = 1  # Second order onwards
    target_date = all_orders[target_index].delivery_date
    
    with test_db.atomic():
        # Update halbe_channel for future orders
        Order.update(
            halbe_channel=True
        ).where(
            (Order.from_date == from_date) & 
            (Order.to_date == to_date) &
            (Order.delivery_date >= target_date)
        ).execute()
        
        # Update amounts for future orders
        for i in range(target_index, len(all_orders)):
            for oi in all_orders[i].order_items:
                oi.amount = 3.0  # Change from 2.0 to 3.0
                oi.save()
    
    # 5. VERIFY UPDATES REFLECTED IN SCHEDULES
    for i, o in enumerate(all_orders):
        delivery_date = o.delivery_date
        deliveries = get_delivery_schedule(delivery_date, delivery_date)
        
        for delivery in deliveries:
            if delivery.id == o.id:
                if i >= target_index:
                    # Future orders should be updated
                    assert delivery.halbe_channel is True
                    assert delivery.order_items[0].amount == 3.0
                else:
                    # First order should be unchanged
                    assert delivery.halbe_channel is False
                    assert delivery.order_items[0].amount == 2.0
    
    # 6. DELETE FUTURE ORDERS
    with test_db.atomic():
        # Delete order items
        for future_order in all_orders[target_index:]:
            OrderItem.delete().where(OrderItem.order == future_order).execute()
        
        # Delete orders
        Order.delete().where(
            (Order.from_date == from_date) & 
            (Order.to_date == to_date) &
            (Order.delivery_date >= target_date)
        ).execute()
    
    # 7. VERIFY FIRST ORDER STILL EXISTS IN SCHEDULE BUT FUTURE ONES DON'T
    for i, o in enumerate(all_orders):
        delivery_date = o.delivery_date
        deliveries = get_delivery_schedule(delivery_date, delivery_date)
        
        found = False
        for delivery in deliveries:
            if delivery.id == o.id:
                found = True
                break
        
        if i < target_index:
            assert found, f"Order {i} should still exist in delivery schedule"
        else:
            assert not found, f"Order {i} should be deleted from delivery schedule"
    
    # Success!
    assert True 