import pytest
import os
import sys
from datetime import datetime, timedelta, date
import uuid

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import db, Customer, Item, Order, OrderItem

# Helper function for date handling in tests
def normalize_date(date_value):
    """Convert a date string to a date object, or return the date object unchanged."""
    if isinstance(date_value, date):
        return date_value
    if isinstance(date_value, str):
        try:
            # Try different date formats
            for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y'):
                try:
                    return datetime.strptime(date_value, fmt).date()
                except ValueError:
                    continue
            # If none of the formats match
            raise ValueError(f"Date string {date_value} doesn't match any expected format")
        except Exception as e:
            raise ValueError(f"Error converting date string {date_value}: {e}")
    raise TypeError(f"Expected date or string, got {type(date_value)}")

@pytest.fixture
def test_db():
    """Create an in-memory database for testing"""
    # Use in-memory SQLite database
    db.init(':memory:')
    db.connect()
    db.create_tables([Customer, Item, Order, OrderItem])
    
    yield db
    
    # Cleanup - ensure we close the connection even if tests fail
    if not db.is_closed():
        # Cleanup
        try:
            db.drop_tables([Customer, Item, Order, OrderItem])
        except:
            pass  # If dropping fails, we should still close the connection
        finally:
            db.close()

@pytest.fixture
def sample_data(test_db):
    """Create sample data for testing"""
    # Create customers
    customers = [
        Customer.create(name="Test Customer 1"),
        Customer.create(name="Test Customer 2")
    ]
    
    # Create items with different growth periods
    items = [
        Item.create(name="Microgreen A", growth_days=3, soaking_days=1, germination_days=2, 
                   price=5.0, seed_quantity=0.1, substrate="Substrate 1"),
        Item.create(name="Microgreen B", growth_days=5, soaking_days=2, germination_days=3, 
                   price=7.0, seed_quantity=0.15, substrate="Substrate 2")
    ]
    
    # Create orders
    today = datetime.now().date()
    orders = [
        # Regular order
        Order.create(
            customer=customers[0],
            delivery_date=today + timedelta(days=7),
            production_date=today,
            from_date=None,
            to_date=None,
            subscription_type=0,
            halbe_channel=False,
            order_id=uuid.uuid4(),
            is_future=True
        ),
        # Subscription order
        Order.create(
            customer=customers[1],
            delivery_date=today + timedelta(days=7),
            production_date=today,
            from_date=today,
            to_date=today + timedelta(days=30),
            subscription_type=1,  # Weekly
            halbe_channel=True,
            order_id=uuid.uuid4(),
            is_future=True
        )
    ]
    
    # Create order items
    order_items = [
        OrderItem.create(order=orders[0], item=items[0], amount=2.5),
        OrderItem.create(order=orders[0], item=items[1], amount=1.5),
        OrderItem.create(order=orders[1], item=items[0], amount=3.0)
    ]
    
    return {
        'customers': customers,
        'items': items,
        'orders': orders,
        'order_items': order_items
    } 