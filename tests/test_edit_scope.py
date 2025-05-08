import pytest
from datetime import datetime, timedelta
import uuid
from models import Customer, Item, Order, OrderItem
from peewee import fn


def test_update_single_order_scope(test_db, sample_data):
    """Test updating only a single order in a subscription"""
    # Setup: Create a subscription with multiple orders
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=28)  # 4 weeks
    
    # Create initial order and future orders
    orders = []
    for i in range(5):  # Create 5 weekly orders
        order = Order.create(
            customer=customer,
            delivery_date=from_date + timedelta(days=7*i),
            production_date=from_date + timedelta(days=7*i - items[0].total_days),
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,  # Weekly
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        # Add items to order
        OrderItem.create(order=order, item=items[0], amount=2.0)
        OrderItem.create(order=order, item=items[1], amount=1.5)
        
        orders.append(order)
    
    # Test: Update only the second order
    target_order = orders[1]
    
    with test_db.atomic():
        # Update order properties
        target_order.halbe_channel = True
        target_order.save()
        
        # Update order items
        for oi in target_order.order_items:
            if oi.item.id == items[0].id:
                oi.amount = 3.0  # Change from 2.0 to 3.0
                oi.save()
    
    # Verify: Only the target order was updated
    for i, order in enumerate(orders):
        refreshed_order = Order.get(Order.id == order.id)
        
        if i == 1:  # The target order
            assert refreshed_order.halbe_channel is True
            
            # Find the item that should have been updated
            for oi in refreshed_order.order_items:
                if oi.item.id == items[0].id:
                    assert oi.amount == 3.0
        else:
            assert refreshed_order.halbe_channel is False
            
            # Check that other orders' items weren't changed
            for oi in refreshed_order.order_items:
                if oi.item.id == items[0].id:
                    assert oi.amount == 2.0


def test_update_future_orders_scope(test_db, sample_data):
    """Test updating an order and all its future instances"""
    # Setup: Create a subscription with multiple orders
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=28)  # 4 weeks
    
    # Create initial order and future orders
    orders = []
    for i in range(5):  # Create 5 weekly orders
        order = Order.create(
            customer=customer,
            delivery_date=from_date + timedelta(days=7*i),
            production_date=from_date + timedelta(days=7*i - items[0].total_days),
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,  # Weekly
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        # Add items to order
        OrderItem.create(order=order, item=items[0], amount=2.0)
        OrderItem.create(order=order, item=items[1], amount=1.5)
        
        orders.append(order)
    
    # Test: Update the second order and all future orders
    target_index = 1  # Second order
    
    with test_db.atomic():
        # Update subscription type for future orders
        Order.update(
            halbe_channel=True,
            subscription_type=2  # Change to bi-weekly
        ).where(
            (Order.from_date == from_date) & 
            (Order.to_date == to_date) &
            (Order.delivery_date >= orders[target_index].delivery_date)
        ).execute()
        
        # Update items for all future orders
        for i in range(target_index, len(orders)):
            order = orders[i]
            # First, delete existing items
            OrderItem.delete().where(OrderItem.order == order).execute()
            
            # Create new items with updated amounts
            OrderItem.create(order=order, item=items[0], amount=4.0)  # Changed from 2.0
            OrderItem.create(order=order, item=items[1], amount=3.0)  # Changed from 1.5
    
    # Verify: Orders from target_index onwards were updated
    for i, order in enumerate(orders):
        refreshed_order = Order.get(Order.id == order.id)
        
        if i >= target_index:
            # These orders should be updated
            assert refreshed_order.halbe_channel is True
            assert refreshed_order.subscription_type == 2
            
            # Check order items
            item_amounts = {oi.item.id: oi.amount for oi in refreshed_order.order_items}
            assert item_amounts.get(items[0].id) == 4.0
            assert item_amounts.get(items[1].id) == 3.0
        else:
            # Earlier orders should be unchanged
            assert refreshed_order.halbe_channel is False
            assert refreshed_order.subscription_type == 1
            
            # Check order items
            item_amounts = {oi.item.id: oi.amount for oi in refreshed_order.order_items}
            assert item_amounts.get(items[0].id) == 2.0
            assert item_amounts.get(items[1].id) == 1.5


def test_update_subscription_parameters(test_db, sample_data):
    """Test updating subscription parameters (from/to dates)"""
    # Setup similar to previous tests
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=28)  # 4 weeks
    
    # Create initial order and future orders
    orders = []
    for i in range(5):
        order = Order.create(
            customer=customer,
            delivery_date=from_date + timedelta(days=7*i),
            production_date=from_date + timedelta(days=7*i - items[0].total_days),
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,  # Weekly
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        OrderItem.create(order=order, item=items[0], amount=2.0)
        orders.append(order)
    
    # Test: Update subscription parameters for all orders
    new_from_date = from_date + timedelta(days=1)
    new_to_date = to_date + timedelta(days=14)  # Extend by 2 weeks
    
    with test_db.atomic():
        Order.update(
            from_date=new_from_date, 
            to_date=new_to_date
        ).where(
            (Order.from_date == from_date) & 
            (Order.to_date == to_date)
        ).execute()
    
    # Verify all orders have updated subscription parameters
    for order_id in [o.id for o in orders]:
        updated = Order.get(Order.id == order_id)
        assert updated.from_date == new_from_date
        assert updated.to_date == new_to_date


def test_delete_specific_order_from_subscription(test_db, sample_data):
    """Test deleting a specific order from the middle of a subscription"""
    # Setup
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=28)
    
    # Create initial order and future orders
    orders = []
    for i in range(5):
        order = Order.create(
            customer=customer,
            delivery_date=from_date + timedelta(days=7*i),
            production_date=from_date + timedelta(days=7*i - items[0].total_days),
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        OrderItem.create(order=order, item=items[0], amount=2.0)
        orders.append(order)
    
    # Test: Delete the middle order (index 2)
    target_index = 2
    target_id = orders[target_index].id
    
    with test_db.atomic():
        # Delete order items first
        OrderItem.delete().where(OrderItem.order == orders[target_index]).execute()
        
        # Then delete the order
        orders[target_index].delete_instance()
    
    # Verify: That specific order is gone, but others remain
    with pytest.raises(Order.DoesNotExist):
        Order.get(Order.id == target_id)
    
    # Verify other orders still exist
    for i, order in enumerate(orders):
        if i != target_index:
            assert Order.get(Order.id == order.id)
    
    # Verify we have only 4 orders with this subscription
    count = Order.select().where(
        (Order.from_date == from_date) & 
        (Order.to_date == to_date) &
        (Order.subscription_type == 1)
    ).count()
    
    assert count == 4


def test_delete_future_orders(test_db, sample_data):
    """Test deleting an order and all future orders in a subscription"""
    # Setup
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=28)
    
    # Create initial order and future orders
    orders = []
    for i in range(5):
        order = Order.create(
            customer=customer,
            delivery_date=from_date + timedelta(days=7*i),
            production_date=from_date + timedelta(days=7*i - items[0].total_days),
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        OrderItem.create(order=order, item=items[0], amount=2.0)
        orders.append(order)
    
    # Test: Delete from the third order onwards
    target_index = 2
    target_date = orders[target_index].delivery_date
    
    with test_db.atomic():
        # Get orders to delete
        future_orders = Order.select().where(
            (Order.from_date == from_date) & 
            (Order.to_date == to_date) &
            (Order.delivery_date >= target_date)
        )
        
        # Delete order items first
        for order in future_orders:
            OrderItem.delete().where(OrderItem.order == order).execute()
        
        # Delete the orders
        Order.delete().where(
            (Order.from_date == from_date) & 
            (Order.to_date == to_date) &
            (Order.delivery_date >= target_date)
        ).execute()
    
    # Verify: First two orders exist, last three are gone
    for i, order in enumerate(orders):
        if i < target_index:
            assert Order.get(Order.id == order.id)
        else:
            with pytest.raises(Order.DoesNotExist):
                Order.get(Order.id == order.id)
    
    # Verify we have only 2 orders left
    count = Order.select().where(
        (Order.from_date == from_date) & 
        (Order.to_date == to_date)
    ).count()
    
    assert count == 2


def test_add_new_order_to_existing_subscription(test_db, sample_data):
    """Test adding a new order to an existing subscription"""
    # Setup
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=28)
    
    # Create initial orders (just 3)
    orders = []
    for i in range(3):
        order = Order.create(
            customer=customer,
            delivery_date=from_date + timedelta(days=7*i),
            production_date=from_date + timedelta(days=7*i - items[0].total_days),
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        OrderItem.create(order=order, item=items[0], amount=2.0)
        orders.append(order)
    
    # Test: Add a new order to the subscription
    new_delivery_date = from_date + timedelta(days=7*5)  # Week 5
    new_production_date = new_delivery_date - timedelta(days=items[0].total_days)
    
    with test_db.atomic():
        new_order = Order.create(
            customer=customer,
            delivery_date=new_delivery_date,
            production_date=new_production_date,
            from_date=from_date,
            to_date=to_date,
            subscription_type=1,
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        )
        
        OrderItem.create(order=new_order, item=items[0], amount=2.0)
    
    # Verify: We now have 4 orders in this subscription
    count = Order.select().where(
        (Order.from_date == from_date) & 
        (Order.to_date == to_date) &
        (Order.subscription_type == 1)
    ).count()
    
    assert count == 4
    
    # Verify the new order has the correct date
    order = Order.get(Order.delivery_date == new_delivery_date)
    assert order.from_date == from_date
    assert order.to_date == to_date 