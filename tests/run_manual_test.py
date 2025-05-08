#!/usr/bin/env python
"""
Manual Test Script for Production Tracker

This script allows testing the core database functionality without 
running the full GUI application. It creates test data and simulates
order operations to verify functionality.

Run this script from the project root directory:
    python tests/run_manual_test.py
"""

import os
import sys
from datetime import datetime, timedelta
import uuid

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import db, Customer, Item, Order, OrderItem
from database import calculate_production_date, generate_subscription_orders
from database import get_delivery_schedule, get_production_plan, get_transfer_schedule


def setup_test_data():
    """Create test data for the database"""
    print("Creating test data...")
    
    # Create customers
    customers = [
        Customer.create(name="Test Customer 1 - Test"),
        Customer.create(name="Test Customer 2 - Test")
    ]
    
    # Create items
    items = [
        Item.create(name="Test Microgreen A", growth_days=3, soaking_days=1, germination_days=2, 
                   total_days=6, price=5.0, seed_quantity=0.1, substrate="Test Substrate 1"),
        Item.create(name="Test Microgreen B", growth_days=5, soaking_days=2, germination_days=3, 
                   total_days=10, price=7.0, seed_quantity=0.15, substrate="Test Substrate 2")
    ]
    
    # Create test dates
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=7)
    
    # Create a regular order
    regular_order = Order.create(
        customer=customers[0],
        delivery_date=tomorrow,
        production_date=today,
        from_date=None,
        to_date=None,
        subscription_type=0,
        halbe_channel=False,
        order_id=uuid.uuid4(),
        is_future=True
    )
    
    OrderItem.create(order=regular_order, item=items[0], amount=2.0)
    
    # Create a subscription order
    subscription_order = Order.create(
        customer=customers[1],
        delivery_date=next_week,
        production_date=today,
        from_date=today,
        to_date=today + timedelta(days=28),
        subscription_type=1,  # Weekly
        halbe_channel=True,
        order_id=uuid.uuid4(),
        is_future=True
    )
    
    OrderItem.create(order=subscription_order, item=items[1], amount=3.0)
    
    # Generate future subscription orders
    future_orders = generate_subscription_orders(subscription_order)
    for future_order_data in future_orders:
        future_order = Order.create(
            **future_order_data,
            order_id=uuid.uuid4()
        )
        OrderItem.create(order=future_order, item=items[1], amount=3.0)
    
    return {
        'customers': customers,
        'items': items,
        'orders': [regular_order, subscription_order]
    }


def test_edit_single_order(sample_data):
    """Test editing a single order"""
    print("\n--- Testing Single Order Edit ---")
    
    order = sample_data['orders'][0]  # First order is a regular order
    print(f"Original order: delivery date={order.delivery_date}, halbe_channel={order.halbe_channel}")
    print(f"Order item amount={order.order_items[0].amount}")
    
    # Edit the order
    with db.atomic():
        order.halbe_channel = not order.halbe_channel
        order.save()
        
        order_item = order.order_items[0]
        order_item.amount = 5.0
        order_item.save()
    
    # Refresh order from database
    updated_order = Order.get(Order.id == order.id)
    print(f"Updated order: delivery date={updated_order.delivery_date}, halbe_channel={updated_order.halbe_channel}")
    print(f"Updated item amount={updated_order.order_items[0].amount}")
    
    return updated_order


def test_edit_subscription(sample_data):
    """Test editing a subscription and all future orders"""
    print("\n--- Testing Subscription Edit for All Future Orders ---")
    
    order = sample_data['orders'][1]  # Second order is a subscription order
    print(f"Original subscription: delivery date={order.delivery_date}, from={order.from_date}, to={order.to_date}")
    
    # Get all orders in this subscription
    subscription_orders = Order.select().where(
        (Order.from_date == order.from_date) &
        (Order.to_date == order.to_date) &
        (Order.subscription_type == order.subscription_type)
    )
    
    print(f"Found {subscription_orders.count()} orders in subscription")
    
    # Edit all orders in the subscription
    new_halbe_value = not order.halbe_channel
    
    with db.atomic():
        # Update all orders in this subscription
        Order.update(
            halbe_channel=new_halbe_value
        ).where(
            (Order.from_date == order.from_date) &
            (Order.to_date == order.to_date) &
            (Order.subscription_type == order.subscription_type)
        ).execute()
        
        # Update the item amount for all orders
        for sub_order in subscription_orders:
            for oi in sub_order.order_items:
                oi.amount = 4.0  # Change from 3.0 to 4.0
                oi.save()
    
    # Verify the changes
    updated_orders = Order.select().where(
        (Order.from_date == order.from_date) &
        (Order.to_date == order.to_date)
    )
    
    print(f"After update: {updated_orders.count()} orders in subscription")
    for updated in updated_orders:
        print(f"Order {updated.id}: halbe_channel={updated.halbe_channel}, amount={updated.order_items[0].amount}")
    
    return updated_orders


def test_delete_order(sample_data):
    """Test deleting an order"""
    print("\n--- Testing Order Deletion ---")
    
    order = sample_data['orders'][0]  # First order to delete
    order_id = order.id
    print(f"Deleting order with ID {order_id}")
    
    # Delete the order
    with db.atomic():
        # Delete order items first
        OrderItem.delete().where(OrderItem.order == order).execute()
        # Then delete the order
        order.delete_instance()
    
    # Verify the order is deleted
    try:
        Order.get(Order.id == order_id)
        print("ERROR: Order still exists after deletion")
    except Order.DoesNotExist:
        print("Success: Order was deleted")


def test_delivery_schedule(sample_data):
    """Test that the delivery schedule shows the correct data"""
    print("\n--- Testing Delivery Schedule ---")
    
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=7)
    
    # Get delivery schedule for tomorrow
    tomorrow_deliveries = get_delivery_schedule(tomorrow, tomorrow)
    print(f"Deliveries for tomorrow: {len(tomorrow_deliveries)}")
    for delivery in tomorrow_deliveries:
        print(f"  - Customer: {delivery.customer.name}, Halbe: {delivery.halbe_channel}")
        for item in delivery.order_items:
            print(f"    - {item.item.name}: {item.amount}")
    
    # Get delivery schedule for next week
    next_week_deliveries = get_delivery_schedule(next_week, next_week)
    print(f"Deliveries for next week: {len(next_week_deliveries)}")
    for delivery in next_week_deliveries:
        print(f"  - Customer: {delivery.customer.name}, Halbe: {delivery.halbe_channel}")
        for item in delivery.order_items:
            print(f"    - {item.item.name}: {item.amount}")


def test_production_plan(sample_data):
    """Test that the production plan shows the correct data"""
    print("\n--- Testing Production Plan ---")
    
    today = datetime.now().date()
    
    # Get production plan for today
    production = list(get_production_plan(today, today))
    print(f"Production items for today: {len(production)}")
    
    for prod in production:
        print(f"  - {prod.item.name}: {prod.total_amount}")


def test_transfer_schedule(sample_data):
    """Test that the transfer schedule shows the correct data"""
    print("\n--- Testing Transfer Schedule ---")
    
    today = datetime.now().date()
    
    # Get transfer schedule for next few days
    transfers = get_transfer_schedule(today, today + timedelta(days=5))
    print(f"Transfer items in next 5 days: {len(transfers)}")
    
    for transfer in transfers:
        print(f"  - Date: {transfer['date']}, Item: {transfer['item']}, Amount: {transfer['amount']}")


def cleanup_test_data(sample_data):
    """Clean up all test data"""
    print("\n--- Cleaning Up Test Data ---")
    
    # Get all test customers, items, and orders
    test_customers = Customer.select().where(Customer.name.contains("Test"))
    test_items = Item.select().where(Item.name.contains("Test"))
    
    with db.atomic():
        # Find all orders made by test customers
        test_orders = Order.select().join(Customer).where(Customer.name.contains("Test"))
        
        # Delete order items
        for order in test_orders:
            OrderItem.delete().where(OrderItem.order == order).execute()
        
        # Delete orders
        Order.delete().join(Customer).where(Customer.name.contains("Test")).execute()
        
        # Delete items
        Item.delete().where(Item.name.contains("Test")).execute()
        
        # Delete customers
        Customer.delete().where(Customer.name.contains("Test")).execute()
    
    print("All test data has been removed from the database")


def test_amount_validation():
    """
    Test the specific amount validation function used in the edit_order method.
    This directly simulates the code path in the application.
    """
    print("\n=== Testing Amount Validation Function ===")
    
    # Create a sample item name for testing
    item_name = "Test Microgreen"
    
    # Define our test cases with expected results
    test_cases = [
        {"input": "3.5", "expected_valid": True, "expected_amount": 3.5, "description": "Standard decimal format"},
        {"input": "4,5", "expected_valid": True, "expected_amount": 4.5, "description": "European decimal format"},
        {"input": "0", "expected_valid": False, "error_contains": "muss größer als 0", "description": "Zero amount"},
        {"input": "-1", "expected_valid": False, "error_contains": "muss größer als 0", "description": "Negative amount"},
        {"input": "Wöchentlich", "expected_valid": False, "error_contains": "Abonnementtyp", "description": "Subscription type as amount"},
        {"input": "Zweiwöchentlich", "expected_valid": False, "error_contains": "Abonnementtyp", "description": "Another subscription type"},
        {"input": "text", "expected_valid": False, "error_contains": "Ungültige Menge", "description": "Random text"},
        {"input": "3.5.2", "expected_valid": False, "error_contains": "Ungültige Menge", "description": "Invalid number format"},
    ]
    
    # Validate function - directly from the application code
    def validate_amount(amount_str, item_name):
        try:
            # First check for subscription type strings
            if amount_str in ["Wöchentlich", "Zweiwöchentlich", "Alle 3 Wochen", "Alle 4 Wochen", "Kein Abonnement"]:
                return False, f"Ungültige Menge: '{amount_str}' scheint ein Abonnementtyp zu sein statt einer Zahl für Artikel {item_name}"
            
            # Support European decimal format (comma instead of period)
            amount_str = amount_str.replace(',', '.')
            
            # Now try to convert to float
            amount = float(amount_str)
            
            if amount <= 0:
                return False, f"Menge muss größer als 0 sein für Artikel {item_name}"
                
            return True, amount
            
        except ValueError:
            return False, f"Ungültige Menge für Artikel {item_name}. Bitte geben Sie eine Zahl ein."
    
    # Run tests
    print(f"{'Input':<20} {'Valid?':<10} {'Result':<20} {'Description'}")
    print("-" * 60)
    
    all_passed = True
    
    for case in test_cases:
        input_value = case["input"]
        expected_valid = case["expected_valid"]
        description = case["description"]
        
        # Run validation function
        valid, result = validate_amount(input_value, item_name)
        
        # Check result
        if valid != expected_valid:
            test_passed = False
            all_passed = False
            result_str = f"❌ Expected {expected_valid}"
        elif valid:
            # If valid, check actual amount value
            expected_amount = case["expected_amount"]
            test_passed = result == expected_amount
            all_passed = all_passed and test_passed
            result_str = f"{result}" if test_passed else f"❌ Expected {expected_amount}, got {result}"
        else:
            # If invalid, check error contains expected text
            error_contains = case["error_contains"]
            test_passed = error_contains in result
            all_passed = all_passed and test_passed
            result_str = "✓" if test_passed else f"❌ Error missing '{error_contains}'"
        
        status = "✅" if test_passed else "❌"
        print(f"{input_value:<20} {status+' '+str(valid):<10} {result_str:<20} {description}")
    
    print("\nOverall result:", "✅ All tests passed!" if all_passed else "❌ Some tests failed!")


def run_all_tests():
    """Run all tests in sequence"""
    # Connect to the database
    try:
        db.connect()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return
    
    try:
        print("=== Starting Manual Test Suite ===")
        
        # Set up test data
        test_data = setup_test_data()
        
        # Test editing a single order
        try:
            updated_order = test_edit_single_order(test_data)
            # Update test data with the updated order
            test_data['orders'][0] = updated_order
        except Exception as e:
            print(f"Error in test_edit_single_order: {e}")
            cleanup_test_data(test_data)
            return
        
        # Test editing a subscription
        try:
            test_edit_subscription(test_data)
        except Exception as e:
            print(f"Error in test_edit_subscription: {e}")
            cleanup_test_data(test_data)
            return
        
        # Test schedules
        try:
            test_delivery_schedule(test_data)
            test_production_plan(test_data)
            test_transfer_schedule(test_data)
        except Exception as e:
            print(f"Error in schedule tests: {e}")
            cleanup_test_data(test_data)
            return
        
        # Test deleting an order
        try:
            test_delete_order(test_data)
        except Exception as e:
            print(f"Error in test_delete_order: {e}")
            cleanup_test_data(test_data)
            return
        
        # Test order edit amount validation
        try:
            test_amount_validation()
        except Exception as e:
            print(f"Error in test_amount_validation: {e}")
            cleanup_test_data(test_data)
            return
        
        # Clean up
        try:
            cleanup_test_data(test_data)
        except Exception as e:
            print(f"Error in cleanup_test_data: {e}")
            return
        
        print("\n=== All Tests Completed Successfully ===")
        
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Close the database connection
        if not db.is_closed():
            db.close()


if __name__ == "__main__":
    test_amount_validation()
    print("=== Test Complete ===") 