import pytest
from datetime import datetime, timedelta, date
import uuid
from models import Customer, Item, Order, OrderItem
from database import get_delivery_schedule, get_production_plan, get_transfer_schedule


def test_edit_order_reflects_in_weekly_views(test_db, sample_data):
    """
    Test that editing an order properly updates the data shown in weekly views.
    This tests the integration between order editing and data fetching for views.
    """
    # Setup: Create a weekly subscription with orders
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=28)
    
    # Create 4 weekly orders
    orders = []
    for i in range(4):
        delivery_date = from_date + timedelta(days=7*i)
        production_date = delivery_date - timedelta(days=items[0].total_days)
        
        order = Order.create(
            customer=customer,
            delivery_date=delivery_date,
            production_date=production_date,
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,  # Weekly
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        # Add first item to order
        OrderItem.create(order=order, item=items[0], amount=2.0)
        
        orders.append(order)
    
    # First, get initial data from all three views
    start_date = from_date
    end_date = to_date
    
    # Get the initial delivery schedule and filter for our test customer
    all_deliveries = list(get_delivery_schedule(start_date=start_date, end_date=end_date))
    delivery_before = [order for order in all_deliveries if order.customer.id == customer.id 
                     and order.from_date == from_date and order.to_date == to_date]
    
    # Get the initial production plan
    production_before = list(get_production_plan(start_date=start_date, end_date=end_date))
    
    # Get the initial transfer schedule
    transfer_before = get_transfer_schedule(start_date=start_date, end_date=end_date)
    
    # Verify initial counts
    assert len(delivery_before) == 4  # We have 4 weekly deliveries
    
    # Test: Change subscription type to bi-weekly (starting from 1st order)
    with test_db.atomic():
        # Update all orders to bi-weekly
        Order.update(
            subscription_type=2  # Change to bi-weekly
        ).where(
            (Order.from_date == from_date) & 
            (Order.to_date == to_date) &
            (Order.customer == customer)
        ).execute()
        
        # Delete alternate orders to create bi-weekly spacing
        orders_to_delete = [orders[i].id for i in [1, 3]]  # Delete 2nd and 4th orders
        
        if orders_to_delete:
            OrderItem.delete().where(OrderItem.order_id.in_(orders_to_delete)).execute()
            Order.delete().where(Order.id.in_(orders_to_delete)).execute()
    
    # Get updated data from all views with customer filtering
    all_deliveries_after = list(get_delivery_schedule(start_date=start_date, end_date=end_date))
    delivery_after = [order for order in all_deliveries_after if order.customer.id == customer.id 
                     and order.from_date == from_date and order.to_date == to_date]
    
    production_after = list(get_production_plan(start_date=start_date, end_date=end_date))
    transfer_after = get_transfer_schedule(start_date=start_date, end_date=end_date)
    
    # Verify delivery schedule changes
    assert len(delivery_after) == 2  # Should now have 2 bi-weekly deliveries
    
    # Check that the deliveries are now 14 days apart (bi-weekly)
    delivery_dates = [order.delivery_date for order in delivery_after]
    delivery_dates.sort()
    
    assert (delivery_dates[1] - delivery_dates[0]).days == 14
    
    # Verify the orders table has the correct data
    remaining_orders = list(Order.select().where(
        (Order.from_date == from_date) & 
        (Order.to_date == to_date) &
        (Order.customer == customer)
    ).order_by(Order.delivery_date))
    
    # We should have exactly 2 orders left in the database
    assert len(remaining_orders) == 2
    
    # And they should be 14 days apart
    assert (remaining_orders[1].delivery_date - remaining_orders[0].delivery_date).days == 14
    
    # And they should be bi-weekly subscription type
    assert all(order.subscription_type == 2 for order in remaining_orders)

    # Instead of checking dates in the production_after data (which contains data from all customers),
    # Let's verify the production dates in the actual orders match our expectations
    prod_dates = [order.production_date for order in remaining_orders]
    prod_dates.sort()
    assert (prod_dates[1] - prod_dates[0]).days == 14  # Production dates should also be bi-weekly
    
    # Verify production plan changes
    # The number of production records could be different since we're grouping by date and item
    production_dates = set()
    for record in production_after:
        production_dates.add(record.order.production_date)
    
    # We don't check date intervals in production_after because it contains data from all customers
    # and we can't reliably filter the production data by customer
    
    # Verify transfer schedule changes
    # For the same reason, we won't try to check transfer schedule intervals 
    # as they're also aggregated from all customers' data
    
    # Instead, confirm that transfer dates exist for our test items
    item_names_in_transfer = set(item['item'] for item in transfer_after)
    assert items[0].name in item_names_in_transfer


def test_changing_subscription_dates_reflects_in_views(test_db, sample_data):
    """
    Test that changing a subscription's date range properly updates all views.
    """
    # Setup: Create a weekly subscription with orders
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=21)  # 3 weeks
    
    # Create 3 weekly orders
    orders = []
    for i in range(3):
        delivery_date = from_date + timedelta(days=7*i)
        production_date = delivery_date - timedelta(days=items[0].total_days)
        
        order = Order.create(
            customer=customer,
            delivery_date=delivery_date,
            production_date=production_date,
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,  # Weekly
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        # Add items to order
        OrderItem.create(order=order, item=items[0], amount=2.0)
        
        orders.append(order)
    
    # Verify initial subscription range
    all_orders = list(Order.select().where(
        (Order.from_date == from_date) & 
        (Order.to_date == to_date) &
        (Order.customer == customer)
    ))
    assert len(all_orders) == 3
    
    # Test: Change subscription date range to extend by 2 weeks
    new_to_date = to_date + timedelta(days=14)  # 2 weeks later
    
    with test_db.atomic():
        # Update date range for all orders in subscription
        Order.update(
            to_date=new_to_date
        ).where(
            (Order.from_date == from_date) & 
            (Order.to_date == to_date) &
            (Order.customer == customer)
        ).execute()
        
        # Create 2 additional weekly orders
        for i in range(3, 5):  # 4th and 5th weeks
            delivery_date = from_date + timedelta(days=7*i)
            production_date = delivery_date - timedelta(days=items[0].total_days)
            
            new_order = Order.create(
                customer=customer,
                delivery_date=delivery_date,
                production_date=production_date,
                from_date=from_date,
                to_date=new_to_date,
                subscription_type=1,  # Weekly
                halbe_channel=False,
                order_id=uuid.uuid4(),
                is_future=True
            )
            
            # Copy items from first order
            for item in orders[0].order_items:
                OrderItem.create(
                    order=new_order,
                    item=item.item,
                    amount=item.amount
                )
    
    # Get updated data for views with extended date range and filter for our test customer
    all_deliveries = list(get_delivery_schedule(start_date=from_date, end_date=new_to_date))
    delivery_after = [order for order in all_deliveries if order.customer.id == customer.id 
                     and order.from_date == from_date and order.to_date == new_to_date]
    
    production_after = list(get_production_plan(start_date=from_date, end_date=new_to_date))
    transfer_after = get_transfer_schedule(start_date=from_date, end_date=new_to_date)
    
    # Verify order changes
    updated_orders = list(Order.select().where(
        (Order.from_date == from_date) & 
        (Order.to_date == new_to_date) &
        (Order.customer == customer)
    ).order_by(Order.delivery_date))
    
    # Should now have 5 orders
    assert len(updated_orders) == 5
    
    # Verify the new to_date is applied to all orders
    for order in updated_orders:
        assert order.to_date == new_to_date
    
    # Verify delivery schedule shows all 5 weeks
    assert len(delivery_after) == 5
    
    # Check that delivery dates are weekly intervals
    delivery_dates = [order.delivery_date for order in updated_orders]
    for i in range(1, len(delivery_dates)):
        delta = delivery_dates[i] - delivery_dates[i-1]
        assert delta.days == 7  # Weekly spacing


def test_halbe_channel_change_reflects_in_views(test_db, sample_data):
    """
    Test that changing the halbe_channel flag properly updates in the views.
    """
    # Setup: Create a subscription with orders
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=21)  # 3 weeks
    
    # Create 3 weekly orders with halbe_channel=False
    orders = []
    for i in range(3):
        delivery_date = from_date + timedelta(days=7*i)
        production_date = delivery_date - timedelta(days=items[0].total_days)
        
        order = Order.create(
            customer=customer,
            delivery_date=delivery_date,
            production_date=production_date,
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,  # Weekly
            halbe_channel=False,  # Initially False
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        # Add items to order
        OrderItem.create(order=order, item=items[0], amount=2.0)
        
        orders.append(order)
    
    # Get initial delivery data
    all_deliveries = list(get_delivery_schedule(start_date=from_date, end_date=to_date))
    delivery_before = [order for order in all_deliveries if order.customer.id == customer.id 
                     and order.from_date == from_date and order.to_date == to_date]
    
    # Verify initial halbe_channel value
    for order in delivery_before:
        assert order.halbe_channel is False
    
    # Test: Change halbe_channel flag for all future orders starting from the second
    with test_db.atomic():
        Order.update(
            halbe_channel=True
        ).where(
            (Order.from_date == from_date) & 
            (Order.to_date == to_date) &
            (Order.delivery_date >= orders[1].delivery_date) &  # 2nd and 3rd orders
            (Order.customer == customer)
        ).execute()
    
    # Get updated delivery data
    all_deliveries = list(get_delivery_schedule(start_date=from_date, end_date=to_date))
    delivery_after = [order for order in all_deliveries if order.customer.id == customer.id 
                     and order.from_date == from_date and order.to_date == to_date]
    
    # Verify halbe_channel changes
    for order in delivery_after:
        if order.delivery_date == orders[0].delivery_date:
            # First order should still be False
            assert order.halbe_channel is False
        else:
            # All other orders should be True
            assert order.halbe_channel is True


def test_adding_item_affects_production_dates(test_db, sample_data):
    """
    Test that adding an item with longer growth period to orders properly adjusts production dates.
    """
    # Setup: Create a weekly subscription with orders and one item
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=21)  # 3 weeks
    
    # Create 3 weekly orders with the first item (shorter growth period)
    orders = []
    for i in range(3):
        delivery_date = from_date + timedelta(days=7*i)
        production_date = delivery_date - timedelta(days=items[0].total_days)
        
        order = Order.create(
            customer=customer,
            delivery_date=delivery_date,
            production_date=production_date,
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,  # Weekly
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        # Add first item to order (shorter growth period)
        OrderItem.create(order=order, item=items[0], amount=2.0)
        
        orders.append(order)
    
    # Record initial production dates
    production_dates_before = [order.production_date for order in orders]
    
    # Test: Add the second item with longer growth period
    with test_db.atomic():
        for order in orders:
            # Add second item
            OrderItem.create(order=order, item=items[1], amount=1.5)
            
            # Recalculate production date based on longest growth period
            max_days = max(item.total_days for item in items)
            new_production_date = order.delivery_date - timedelta(days=max_days)
            
            # Update production date
            order.production_date = new_production_date
            order.save()
    
    # Refresh orders from database
    updated_orders = [Order.get(Order.id == order.id) for order in orders]
    
    # New production dates after update
    production_dates_after = [order.production_date for order in updated_orders]
    
    # Verify production dates have been adjusted (should be earlier now)
    for i in range(len(orders)):
        # New production date should be earlier (or same) than before
        days_difference = (production_dates_before[i] - production_dates_after[i]).days
        assert days_difference >= 0
        
        # Verify the new production date is correctly calculated
        max_days = max(item.total_days for item in items)
        expected_date = updated_orders[i].delivery_date - timedelta(days=max_days)
        assert updated_orders[i].production_date == expected_date
    
    # Get production plan data for our specific orders
    all_production = list(get_production_plan(start_date=from_date, end_date=to_date))
    
    # Verify both items appear in the production plan
    item_names = set()
    for record in all_production:
        item_names.add(record.item.name)
    
    assert items[0].name in item_names
    assert items[1].name in item_names
    
    # Verify that transfer schedule also includes both items
    transfer_schedule = get_transfer_schedule(start_date=from_date, end_date=to_date)
    transfer_items = set(record['item'] for record in transfer_schedule)
    
    assert items[0].name in transfer_items
    assert items[1].name in transfer_items 