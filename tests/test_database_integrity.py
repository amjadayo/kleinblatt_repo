import pytest
from datetime import datetime, timedelta
import uuid
from models import Customer, Item, Order, OrderItem
from peewee import IntegrityError, DoesNotExist


def test_order_item_relationship_integrity(test_db, sample_data):
    """
    Test that deleting an order correctly cascades to its order items.
    """
    # Setup: Create an order with multiple items
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    delivery_date = today + timedelta(days=7)
    production_date = delivery_date - timedelta(days=items[0].total_days)
    
    # Create an order
    order = Order.create(
        customer=customer,
        delivery_date=delivery_date,
        production_date=production_date,
        from_date=None,
        to_date=None,
        subscription_type=0,
        halbe_channel=False,
        order_id=uuid.uuid4(),
        is_future=True
    )
    
    # Add items to the order
    order_items = []
    for item in items:
        order_item = OrderItem.create(
            order=order,
            item=item,
            amount=1.5
        )
        order_items.append(order_item)
    
    # Verify items are associated with the order
    assert OrderItem.select().where(OrderItem.order == order).count() == len(items)
    
    # Test: Delete the order and verify items are also deleted
    order.delete_instance(recursive=True)
    
    # Verify the order is deleted
    with pytest.raises(DoesNotExist):
        Order.get(Order.id == order.id)
    
    # Verify all order items are deleted
    for order_item in order_items:
        with pytest.raises(DoesNotExist):
            OrderItem.get(OrderItem.id == order_item.id)


def test_customer_relationship_integrity(test_db, sample_data):
    """
    Test that customer relationships are maintained correctly.
    """
    # Setup: Create customers and orders
    customer1 = sample_data['customers'][0]
    customer2 = sample_data['customers'][1]
    item = sample_data['items'][0]
    
    today = datetime.now().date()
    test_delivery_date = today + timedelta(days=7)
    
    # Store the IDs of orders we create in this test
    test_order_ids = []

    # Create orders for both customers
    order1_id = uuid.uuid4()
    order1 = Order.create(
        customer=customer1,
        delivery_date=test_delivery_date,
        production_date=today,
        from_date=None,
        to_date=None,
        subscription_type=0,
        halbe_channel=False,
        order_id=order1_id,
        is_future=True
    )
    test_order_ids.append(order1.id)

    order2_id = uuid.uuid4()
    order2 = Order.create(
        customer=customer2,
        delivery_date=test_delivery_date,
        production_date=today,
        from_date=None,
        to_date=None,
        subscription_type=0,
        halbe_channel=False,
        order_id=order2_id,
        is_future=True
    )
    test_order_ids.append(order2.id)
    
    # Add items to orders
    OrderItem.create(order=order1, item=item, amount=1.5)
    OrderItem.create(order=order2, item=item, amount=2.0)
    
    # Test: Change the customer for an order
    order1.customer = customer2
    order1.save()
    
    # Verify the customer was changed
    refreshed_order = Order.get(Order.id == order1.id)
    assert refreshed_order.customer.id == customer2.id
    
    # Verify customer2 now has 2 orders (that we created in this test)
    # Filter orders by the IDs we saved
    customer2_orders = Order.select().where(
        (Order.customer == customer2) &
        (Order.id.in_(test_order_ids))
    )
    assert customer2_orders.count() == 2


def test_subscription_data_consistency(test_db, sample_data):
    """
    Test that subscription data remains consistent when editing orders.
    """
    # Setup: Create a weekly subscription with orders
    customer = sample_data['customers'][0]
    item = sample_data['items'][0]
    
    today = datetime.now().date()
    from_date = today
    to_date = today + timedelta(days=28)  # 4 weeks
    
    # Create 4 weekly orders
    orders = []
    for i in range(4):
        delivery_date = from_date + timedelta(days=7*i)
        production_date = delivery_date - timedelta(days=item.total_days)
        
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
        
        OrderItem.create(order=order, item=item, amount=1.5)
        orders.append(order)
    
    # Test: Update subscription dates for all orders
    new_from_date = from_date + timedelta(days=1)
    new_to_date = to_date + timedelta(days=7)
    
    with test_db.atomic():
        Order.update(
            from_date=new_from_date,
            to_date=new_to_date
        ).where(
            (Order.from_date == from_date) & 
            (Order.to_date == to_date)
        ).execute()
    
    # Verify all orders have updated dates
    for order_id in [o.id for o in orders]:
        updated_order = Order.get(Order.id == order_id)
        assert updated_order.from_date == new_from_date
        assert updated_order.to_date == new_to_date


def test_item_reference_integrity(test_db, sample_data):
    """
    Test that references to items remain valid when editing orders.
    """
    # Setup: Create an order with multiple items
    customer = sample_data['customers'][0]
    items = sample_data['items']
    
    today = datetime.now().date()
    delivery_date = today + timedelta(days=7)
    production_date = delivery_date - timedelta(days=items[0].total_days)
    
    # Create an order
    order = Order.create(
        customer=customer,
        delivery_date=delivery_date,
        production_date=production_date,
        from_date=None,
        to_date=None,
        subscription_type=0,
        halbe_channel=False,
        order_id=uuid.uuid4(),
        is_future=True
    )
    
    # Add items to the order
    for item in items:
        OrderItem.create(
            order=order,
            item=item,
            amount=1.5
        )
    
    # Create a new item to use for updates
    new_item = Item.create(
        name="Test New Item",
        growth_days=4,
        soaking_days=1,
        germination_days=2,
        price=8.0,
        seed_quantity=0.2,
        substrate="Test Substrate"
    )
    
    # Test: Update an existing order item to reference the new item
    order_item = list(order.order_items)[0]
    order_item.item = new_item
    order_item.save()
    
    # Verify the reference was updated
    updated_item = OrderItem.get(OrderItem.id == order_item.id)
    assert updated_item.item.id == new_item.id
    assert updated_item.item.name == "Test New Item"
    
    # Verify we can still access the item's properties through the relationship
    assert updated_item.item.growth_days == 4
    assert updated_item.item.price == 8.0


def test_order_id_uniqueness(test_db, sample_data):
    """
    Test that order_id remains unique when creating or editing orders.
    """
    # Setup: Create a customer and an item
    customer = sample_data['customers'][0]
    item = sample_data['items'][0]
    
    today = datetime.now().date()
    
    # Generate a UUID to reuse
    duplicate_id = uuid.uuid4()
    
    # Create first order with the UUID
    order1 = Order.create(
        customer=customer,
        delivery_date=today + timedelta(days=7),
        production_date=today,
        from_date=None,
        to_date=None,
        subscription_type=0,
        halbe_channel=False,
        order_id=duplicate_id,
        is_future=True
    )
    
    # Test: Try to create another order with the same UUID
    with pytest.raises(IntegrityError):
        with test_db.atomic():
            order2 = Order.create(
                customer=customer,
                delivery_date=today + timedelta(days=14),
                production_date=today,
                from_date=None,
                to_date=None,
                subscription_type=0,
                halbe_channel=False,
                order_id=duplicate_id,  # Same UUID should cause error
                is_future=True
            )
    
    # Test: Update an existing order with a new UUID
    new_id = uuid.uuid4()
    order1.order_id = new_id
    order1.save()
    
    # Verify the ID was updated
    refreshed_order = Order.get(Order.id == order1.id)
    assert refreshed_order.order_id == new_id 