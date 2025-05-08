from datetime import datetime, timedelta
from models import *
from peewee import fn


def calculate_itemwise_production_dates(delivery_date, items, allow_sunday=True):
    """
    Calculate production date for each item in a list.
    Returns a dict: {OrderItem: production_date}
    """
    production_dates = {}
    for order_item in items:
        days = order_item.item.total_days
        production_date = delivery_date - timedelta(days=days)
        if not allow_sunday and production_date.weekday() == 6:
            production_date -= timedelta(days=1)
        production_dates[order_item] = production_date
    return production_dates

def generate_subscription_orders(order):
    if order.subscription_type == 0 or not order.from_date or not order.to_date:
        return []
    
    frequencies = {1: 7, 2: 14, 3: 21, 4: 28}
    assert order.from_date and order.to_date, 'from_date or to_date is missing'
    delta = timedelta(days=frequencies[order.subscription_type])
    
    # Use delivery_date as the starting point, not from_date
    current_date = order.delivery_date + delta
    # Anchor off the very first subscription date so the weekly pattern never shifts
    #current_date = order.from_date + delta

    orders = []
    calculate_production_date = calculate_itemwise_production_dates

    while current_date <= order.to_date:
        # Pass the allow_sunday parameter based on the original order's production date
        # If the original order was allowed to be produced on Sunday, future orders should too
        production_dates = order.production_date if isinstance(order.production_date, dict) else {}
        sample_date = next(iter(production_dates.values()), None)
        allow_sunday = sample_date.weekday() != 6 if sample_date else True
        
        new_order = {
            'customer':          order.customer,
            'delivery_date':     current_date,
            'production_date':   calculate_production_date(
                                    current_date,
                                    list(order.order_items),   # use the real items
                                    allow_sunday
                                ),
            'halbe_channel':     order.halbe_channel,
            'is_future':         True,
            'subscription_type': order.subscription_type,
            'from_date':         order.from_date,
            'to_date':           order.to_date
        }

        orders.append(new_order)
        current_date += delta
    
    return orders

def get_delivery_schedule(start_date=None, end_date=None):
    """
    Get delivery schedule for the given date range.
    
    The application now correctly creates orders with the right subscription pattern,
    so we should simply display all orders in the database for the requested date range.
    """
    # Get base query with date range filter
    query = (Order
            .select(Order, Customer)
            .join(Customer)
    )
    
    if start_date and end_date:
        query = query.where((Order.delivery_date >= start_date) & 
                          (Order.delivery_date <= end_date))
    
    # Return all orders in the date range
    return list(query.order_by(Order.delivery_date))

def get_production_plan(start_date=None, end_date=None):
    """
    Get production plan for the given date range.
    
    The application now correctly creates orders with the right subscription pattern,
    so we should simply display all orders in the database for the requested date range.
    """
    query = (OrderItem.select(
        OrderItem.transfer_date,
        OrderItem.production_date,
            Order.delivery_date,
            Item.name,
            fn.SUM(OrderItem.amount).alias('total_amount'),
            Item.seed_quantity,
            Item.substrate
        )
        .join(Order)
        .switch(OrderItem)
        .join(Item)
        .where(
            (OrderItem.production_date >= start_date) & 
            (OrderItem.production_date <= end_date)
        )
        .group_by(OrderItem.production_date, Item.name, Item.seed_quantity, Item.substrate)
        .order_by(OrderItem.production_date))
    
    if start_date and end_date:
        query = query.where((OrderItem.production_date >= start_date) & 
                          (OrderItem.production_date <= end_date))
    
    # Return all results without subscription filtering
    results = list(query)
    
    # Debug code for Sunday orders (kept from original)
    sunday_orders = []
    for result in results:
        if result.production_date.weekday() == 6:  # 6 = Sunday
            sunday_orders.append(result)
    
    # This is useful to diagnose the issue but doesn't affect functionality
    if not sunday_orders and start_date and end_date:
        # Check if the date range includes a Sunday
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() == 6:  # Found a Sunday in the range
                break
            current_date += timedelta(days=1)
    
    return results

def get_transfer_schedule(start_date=None, end_date=None):
    """
    Gibt für jeden Transfer-Tag die Gesamtmenge pro Artikel zurück,
    unabhängig vom Kunden.
    """
    from datetime import datetime

    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()

    print("[DEBUG] get_transfer_schedule -> Zeitfenster:", start_date, "bis", end_date)

    query = (OrderItem
             .select(
                 OrderItem.transfer_date,
                 Item,
                 fn.SUM(OrderItem.amount).alias('total_amount')
             )
             .join(Item)
             .where(
                 (OrderItem.transfer_date >= start_date) &
                 (OrderItem.transfer_date <= end_date)
             )
             .group_by(OrderItem.transfer_date, Item)
             .order_by(OrderItem.transfer_date, Item.name))

    results = []
    for row in query:
        item_name = row.item.name if row.item else "Unbekannt"
        print("[DEBUG] MATCHED transfer:", item_name, row.transfer_date, row.total_amount)
        results.append({
            "date": row.transfer_date,
            "item": item_name,
            "amount": row.total_amount
        })

    return results



"""     from datetime import datetime
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()

    print("[DEBUG] get_transfer_schedule -> Zeitfenster:", start_date, "bis", end_date)

    results = []
    order_items = (
        OrderItem
        .select()
        .where(
            (OrderItem.transfer_date.is_null(False)) &
            (OrderItem.transfer_date >= start_date) &
            (OrderItem.transfer_date <= end_date)
        )
    )

    for oi in order_items:
        print("[DEBUG] MATCHED transfer:", oi.item.name, oi.transfer_date)
        results.append({
            "date": oi.transfer_date,
            "item": oi.item.name,
            "amount": oi.amount,
            "customer": oi.order.customer.name if oi.order and oi.order.customer else None
        })

    return results """


calculate_production_date = calculate_itemwise_production_dates