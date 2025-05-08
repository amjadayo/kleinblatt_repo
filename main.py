import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta, date
from models import Item, Order, Customer, OrderItem, db
from database import calculate_itemwise_production_dates, generate_subscription_orders, get_delivery_schedule, get_production_plan, get_transfer_schedule
from peewee import fn, JOIN
import uuid
from weekly_view import WeeklyDeliveryView, WeeklyProductionView, WeeklyTransferView
from customers_view import CustomerView
from item_view import ItemView
from widgets import AutocompleteCombobox
from print_schedules import SchedulePrinter, ask_week_selection
import os
import requests
import re
import sys
import subprocess
import json
import copy
import time

# Check for updates
VERSION = "0.9"

# Define action types for undo system
ACTION_CREATE_ORDER = "create_order"
ACTION_DELETE_ORDER = "delete_order"
ACTION_EDIT_ORDER = "edit_order"
ACTION_CREATE_CUSTOMER = "create_customer"
ACTION_EDIT_CUSTOMER = "edit_customer"
ACTION_CREATE_ITEM = "create_item"
ACTION_EDIT_ITEM = "edit_item"

def check_for_updates():
    try:
        # Get latest release info from GitHub API
        response = requests.get("https://api.github.com/repos/GingerApe/kleinblatt/releases/latest")
        if response.status_code == 200:
            latest_version = response.json().get("tag_name", "").strip("v")
            
            # Compare versions
            if latest_version and latest_version > VERSION:
                update_choice = messagebox.askyesno(
                    "Update Available", 
                    f"New version {latest_version} available! (Current: {VERSION})\n\n"
                    f"Would you like to update now?")
                
                if update_choice:
                    try:
                        # Run the update script which will pull latest code
                        update_script = "./update_kleinblatt.sh"
                        subprocess.run([update_script], check=True)
                        messagebox.showinfo("Update Successful", 
                                           "Kleinblatt has been updated successfully!\n"
                                           "Please restart the application.")
                        sys.exit(0)
                    except Exception as e:
                        messagebox.showerror("Update Failed", 
                                            f"Could not update automatically. Please update manually:\n{str(e)}")
        return False
    except Exception as e:
        print(f"Update check failed: {str(e)}")
        return False

class ProductionApp(tk.Tk):
    
    def initialize_produktionsview(self):
        # Check if 'produktionsview' is created and properly assigned
        if not hasattr(self, 'produktionsview'):
            print("[DEBUG] 'produktionsview' not found. Initializing...")
            self.produktionsview = WeeklyProductionView(self)
        else:
            print("[DEBUG] 'produktionsview' already initialized.")
            print("[DEBUG] Initializing 'produktionsview' view.")
            self.produktionsview = WeeklyProductionView(self)

    def __init__(self):
        super().__init__()
        self.title("Production Tracker")
        self.geometry("1400x800")
        
        self.db = db
        self.printer = SchedulePrinter()
        
        # Initialize undo history stack
        self.undo_stack = []
        self.undo_pointer = -1
        self.max_undo_steps = 20  # Limit the number of undo actions
        
        # Throttling mechanism for refreshes
        self.last_refresh = 0
        self.refresh_throttle = 500  # ms minimum between refreshes
        
        style = ttk.Style()
        style.configure('Green.TFrame', background='green')

        # Create toolbar frame
        self.toolbar = ttk.Frame(self)
        self.toolbar.pack(fill='x', pady=5, padx=10)
        
        # Create undo button
        self.undo_button = ttk.Button(self.toolbar, text="Rückgängig (Ctrl+Z)", command=self.undo_last_action)
        self.undo_button.pack(side='left', padx=5)
        self.undo_button.config(state='disabled')  # Initially disabled until there are actions
        
        # Create refresh button with improved throttled refresh
        self.refresh_button = ttk.Button(self.toolbar, text="Alle Ansichten aktualisieren", command=self.throttled_refresh)
        self.refresh_button.pack(side='left', padx=5)
        
        # Create undo keyboard shortcut
        self.bind('<Control-z>', lambda event: self.undo_last_action())

        # Create main notebook
        self.notebook = ttk.Notebook(self)
        self.tab1 = ttk.Frame(self.notebook)  # New Order
        self.tab2 = ttk.Frame(self.notebook)  # Delivery Schedule
        self.tab3 = ttk.Frame(self.notebook)  # Production Plan
        self.tab4 = ttk.Frame(self.notebook)  # Transfer Schedule
        self.tab5 = ttk.Frame(self.notebook)  # Customers
        self.tab6 = ttk.Frame(self.notebook)  # Items  # Add this line
        self.tab7 = ttk.Frame(self.notebook)  # Orders

        #self.notebook.add(self.tab1, text="Bestellung")
        self.notebook.add(self.tab2, text="Lieferung")
        self.notebook.add(self.tab3, text="Produktion")
        self.notebook.add(self.tab4, text="Transfer")
        self.notebook.add(self.tab5, text="Kunden")
        self.notebook.add(self.tab6, text="Items")
        self.notebook.add(self.tab7, text="Bestellungen")
        
        self.notebook.pack(expand=True, fill='both', padx=10, pady=5)
        
        self.load_data()
        self.create_order_tab()
        self.create_delivery_tab()
        self.create_production_tab()
        self.create_transfer_tab()
        self.create_customers_tab()
        self.create_items_tab()
        self.create_orders_tab()

            # Add these lines to refresh data when app starts
        if hasattr(self, 'delivery_view'):
            self.delivery_view.refresh()
        if hasattr(self, 'production_view'):
            self.production_view.refresh()
        if hasattr(self, 'transfer_view'):
            self.transfer_view.refresh()

    def throttled_refresh(self):
        """Refresh all views but enforce a minimum time between refreshes to prevent flickering"""
        current_time = int(time.time() * 1000)  # Current time in ms
        if current_time - self.last_refresh > self.refresh_throttle:
            self.last_refresh = current_time
            print("[DEBUG] UI refresh triggered")
            self.refresh_tables()
            self.refresh_button.config(state='disabled')  # Temporarily disable button
            # Re-enable button after throttle period
            self.after(self.refresh_throttle, lambda: self.refresh_button.config(state='normal'))

    # Undo system methods
    def record_action(self, action_type, old_data=None, new_data=None, description=None):
        """Record an action for potential undo"""
        # Debug print to see what's being recorded
        print(f"Recording action: {action_type}, Description: {description}")
        
        # Remove any actions that were undone
        if self.undo_pointer < len(self.undo_stack) - 1:
            self.undo_stack = self.undo_stack[:self.undo_pointer + 1]
            
        # Add the new action
        self.undo_stack.append({
            'type': action_type,
            'old_data': old_data,
            'new_data': new_data,
            'description': description or f"Action: {action_type}"
        })
        
        # Limit the stack size
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)
        
        self.undo_pointer = len(self.undo_stack) - 1
        self.undo_button.config(state='normal')
        print(f"Undo stack now has {len(self.undo_stack)} entries, pointer at {self.undo_pointer}")
    
    def undo_last_action(self):
        """Undo the last recorded action"""
        if not self.undo_stack or self.undo_pointer < 0:
            self.undo_button.config(state='disabled')
            return
            
        action = self.undo_stack[self.undo_pointer]
        print(f"Undoing action: {action['type']}, {action['description']}")
        
        try:
            if action['type'] == ACTION_CREATE_ORDER:
                # Undo order creation by deleting the order
                if action['new_data'] and 'order_id' in action['new_data']:
                    order_id = action['new_data']['order_id']
                    
                    # Find and delete all orders with this order_id or related to the same subscription
                    orders = Order.select().where(Order.order_id == order_id)
                    if orders.exists():
                        # Get the first order to find related subscription orders
                        main_order = orders.get()
                        if main_order.from_date and main_order.to_date and main_order.subscription_type > 0:
                            # This is a subscription order, get all related orders
                            with db.atomic():
                                Order.delete().where(
                                    (Order.from_date == main_order.from_date) &
                                    (Order.to_date == main_order.to_date) &
                                    (Order.customer == main_order.customer)
                                ).execute()
                        else:
                            # Single order
                            with db.atomic():
                                Order.delete().where(Order.order_id == order_id).execute()
                            
                        messagebox.showinfo("Rückgängig", "Bestellerstellung rückgängig gemacht")
                
            elif action['type'] == ACTION_DELETE_ORDER:
                # Undo order deletion by recreating the order
                if action['old_data']:
                    print(f"Restoring deleted order from data: {type(action['old_data'])}")
                    self.recreate_order_from_data(action['old_data'])
                    messagebox.showinfo("Rückgängig", "Bestelllöschung rückgängig gemacht")
                
            elif action['type'] == ACTION_EDIT_ORDER:
                # Undo order edit by restoring the previous state
                if action['old_data']:
                    print(f"Restoring previous order state from data: {type(action['old_data'])}")
                    
                    if isinstance(action['old_data'], dict) and action['old_data'].get('order_id'):
                        # Single order edit (from delivery tab)
                        print("Restoring single order from delivery tab")
                        
                        # Check if the order still exists
                        order_id = action['old_data']['order_id']
                        existing_order = Order.get_or_none(Order.order_id == order_id)
                        
                        if existing_order:
                            print(f"Found existing order with ID {order_id}, updating it")
                            self.restore_order_from_data(action['old_data'])
                        else:
                            print(f"Order with ID {order_id} doesn't exist, recreating it")
                            self.recreate_order_from_data(action['old_data'])
                            
                    elif isinstance(action['old_data'], dict) and 'orders' in action['old_data']:
                        # Multiple orders edit (from order management)
                        print(f"Restoring multiple orders ({len(action['old_data']['orders'])}) from orders tab")
                        self.restore_order_from_data(action['old_data'])
                    else:
                        print(f"Unknown order data format for undo: {type(action['old_data'])}")
                        
                    messagebox.showinfo("Rückgängig", "Bestelländerung rückgängig gemacht")
                    
            elif action['type'] == ACTION_CREATE_CUSTOMER:
                # Undo customer creation
                if action['new_data'] and 'customer_id' in action['new_data']:
                    customer = Customer.get_or_none(Customer.id == action['new_data']['customer_id'])
                    if customer:
                        customer.delete_instance(recursive=True)
                        messagebox.showinfo("Rückgängig", "Kundenerstellung rückgängig gemacht")
                        
            elif action['type'] == ACTION_EDIT_CUSTOMER:
                # Undo customer edit
                if action['old_data'] and 'customer_id' in action['old_data']:
                    customer = Customer.get_or_none(Customer.id == action['old_data']['customer_id'])
                    if customer:
                        for key, value in action['old_data'].items():
                            if key != 'customer_id':
                                setattr(customer, key, value)
                        customer.save()
                        messagebox.showinfo("Rückgängig", "Kundenänderung rückgängig gemacht")
                        
            elif action['type'] == ACTION_CREATE_ITEM:
                # Undo item creation
                if action['new_data'] and 'item_id' in action['new_data']:
                    item = Item.get_or_none(Item.id == action['new_data']['item_id'])
                    if item:
                        item.delete_instance(recursive=True)
                        messagebox.showinfo("Rückgängig", "Artikelerstellung rückgängig gemacht")
                        
            elif action['type'] == ACTION_EDIT_ITEM:
                # Undo item edit
                if action['old_data'] and 'item_id' in action['old_data']:
                    item = Item.get_or_none(Item.id == action['old_data']['item_id'])
                    if item:
                        for key, value in action['old_data'].items():
                            if key != 'item_id':
                                setattr(item, key, value)
                        item.save()
                        messagebox.showinfo("Rückgängig", "Artikeländerung rückgängig gemacht")
            
            # Update UI after undo
            self.load_data()
            self.refresh_all_tables()  # Use our comprehensive refresh method
            
            # Update current customer view if open
            if hasattr(self, 'on_customer_select'):
                selected_customers = self.customer_tree.selection() if hasattr(self, 'customer_tree') else None
                if selected_customers:
                    self.on_customer_select(None)
            
            # Updating undo stack pointer
            self.undo_pointer -= 1
            if self.undo_pointer < 0:
                self.undo_button.config(state='disabled')
                
        except Exception as e:
            print(f"Undo error: {str(e)}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Undo Error", f"Fehler beim Rückgängigmachen: {str(e)}")
    
    def recreate_order_from_data(self, order_data):
        """Recreate an order from stored data"""
        with db.atomic():
            # Check if we have a batch of orders to restore
            if 'orders' in order_data:
                # Multiple orders
                for order in order_data['orders']:
                    self.recreate_order_from_data(order)
                return
                
            # Main order data
            order_items = order_data.pop('order_items', [])
            
            # Make a copy of the data to avoid modifying the original
            order_dict = order_data.copy()
            
            # Remove the 'id' field to avoid unique constraint violations
            if 'id' in order_dict:
                order_dict.pop('id')
            
            # Handle date fields explicitly
            for field in ['delivery_date', 'production_date', 'from_date', 'to_date']:
                if field in order_dict and isinstance(order_dict[field], str):
                    try:
                        order_dict[field] = datetime.strptime(order_dict[field], '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        # If conversion fails, remove the field
                        order_dict.pop(field, None)
            
            try:
                # Check if order with this order_id already exists
                order_id = order_dict.get('order_id')
                existing_order = Order.get_or_none(Order.order_id == order_id)
                
                if existing_order:
                    # Update existing order instead of creating a new one
                    for key, value in order_dict.items():
                        if key != 'order_id' and hasattr(existing_order, key):
                            setattr(existing_order, key, value)
                    existing_order.save()
                    order = existing_order
                    
                    # Delete existing items
                    OrderItem.delete().where(OrderItem.order == order).execute()
                else:
                    # Create new order
                    order = Order.create(**order_dict)
                
                # Recreate order items
                for item_data in order_items:
                    item = Item.get(Item.id == item_data['item_id'])
                    amount = item_data['amount']
                    # calculate dates
                    total_days = item.germination_days + item.growth_days
                    production_date = order.delivery_date - timedelta(days=total_days)
                    transfer_date = production_date + timedelta(days=item.germination_days)
                    OrderItem.create(
                        order=order,
                        item=item,
                        amount=amount,
                        production_date=production_date,
                        transfer_date=transfer_date
                    )
            except Exception as e:
                print(f"Error recreating order: {str(e)}")
                print(f"Order data: {order_dict}")
                raise
    
    def restore_order_from_data(self, order_data):
        """Restore an order to its previous state"""
        with db.atomic():
            # Check if we have a batch of orders to restore
            if 'orders' in order_data:
                # Multiple orders - could be from subscription edit
                print(f"Restoring {len(order_data['orders'])} orders from a subscription edit")
                
                # First determine what orders currently exist vs what needs to be recreated
                orders_to_update = {}
                orders_to_create = []
                
                for orig_order in order_data['orders']:
                    # Ensure order_id is properly formatted for comparison
                    orig_order_id = orig_order.get('order_id')
                    if orig_order_id:
                        # Convert to string if it's a UUID object
                        if isinstance(orig_order_id, uuid.UUID):
                            orig_order_id = str(orig_order_id)
                        orig_order['order_id'] = orig_order_id
                    
                    # Check if this order still exists
                    existing_order = None
                    if orig_order_id:
                        existing_order = Order.get_or_none(Order.order_id == orig_order_id)
                    
                    if existing_order:
                        # Add to update dictionary
                        orders_to_update[orig_order_id] = {
                            'order': existing_order,
                            'data': orig_order
                        }
                    else:
                        # Before creating a new order, check if there's already an order with the same:
                        # - customer
                        # - delivery_date 
                        # - from_date/to_date
                        # This would indicate an order that was edited and we should update it instead of creating a new one
                        if 'delivery_date' in orig_order and 'customer_id' in orig_order:
                            delivery_date = orig_order['delivery_date']
                            if isinstance(delivery_date, str):
                                delivery_date = datetime.strptime(delivery_date, '%Y-%m-%d').date()
                            
                            from_date = orig_order.get('from_date')
                            if isinstance(from_date, str):
                                from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
                                
                            to_date = orig_order.get('to_date')
                            if isinstance(to_date, str):
                                to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
                            
                            # Try to find an existing order with matching parameters
                            try:
                                customer = Customer.get_by_id(orig_order['customer_id'])
                                matching_order = Order.get_or_none(
                                    (Order.customer == customer) &
                                    (Order.delivery_date == delivery_date) &
                                    (Order.from_date == from_date) &
                                    (Order.to_date == to_date)
                                )
                                
                                if matching_order:
                                    # Found a matching order, update it instead of creating a new one
                                    print(f"Found matching order with ID {matching_order.order_id} for date {delivery_date}, updating instead of creating new")
                                    orders_to_update[orig_order_id] = {
                                        'order': matching_order,
                                        'data': orig_order
                                    }
                                    continue
                            except Exception as e:
                                print(f"Error finding matching order: {str(e)}")
                        
                        # If no matching order found, add to create list
                        orders_to_create.append(orig_order)
                
                # Delete any FUTURE orders that aren't in the original data
                # This prevents accidentally deleting past orders
                if len(orders_to_update) > 0:
                    # Get a sample order to find subscription details
                    sample_order_data = list(orders_to_update.values())[0]['data']
                    sample_order = list(orders_to_update.values())[0]['order']
                    
                    # Find original subscription parameters
                    original_from_date = sample_order_data.get('from_date')
                    original_to_date = sample_order_data.get('to_date')
                    original_customer_id = sample_order_data.get('customer_id')
                    
                    if original_from_date and original_to_date and original_customer_id:
                        # Format dates if they're strings
                        if isinstance(original_from_date, str):
                            original_from_date = datetime.strptime(original_from_date, '%Y-%m-%d').date()
                        if isinstance(original_to_date, str):
                            original_to_date = datetime.strptime(original_to_date, '%Y-%m-%d').date()
                        
                        # Get current date to ensure we only remove future orders
                        today = datetime.now().date()
                        
                        # Get all FUTURE orders in the subscription
                        customer = Customer.get_by_id(original_customer_id)
                        current_subscription_orders = Order.select().where(
                            (Order.from_date == sample_order.from_date) &
                            (Order.to_date == sample_order.to_date) &
                            (Order.customer == customer) &
                            (Order.delivery_date >= today)  # CRITICAL: Only consider future orders
                        )
                        
                        # Find orders that aren't in the original data
                        # Convert all order IDs to strings for consistent comparison
                        original_order_ids = [str(od['order_id']) for od in order_data['orders']]
                        
                        # Get delivery dates from original orders for comparison
                        original_delivery_dates = {}
                        for od in order_data['orders']:
                            if 'delivery_date' in od:
                                # Convert to date object if it's a string
                                if isinstance(od['delivery_date'], str):
                                    delivery_date = datetime.strptime(od['delivery_date'], '%Y-%m-%d').date()
                                else:
                                    delivery_date = od['delivery_date']
                                original_delivery_dates[str(od['order_id'])] = delivery_date
                        
                        for current_order in current_subscription_orders:
                            order_id_str = str(current_order.order_id)
                            
                            # Only delete if this order doesn't exist in original data
                            # AND it's not a past order that was recreated with a new ID
                            if order_id_str not in original_order_ids:
                                # Also check if there's a corresponding delivery date match
                                date_match_found = False
                                for orig_id, orig_date in original_delivery_dates.items():
                                    if orig_date == current_order.delivery_date:
                                        date_match_found = True
                                        break
                                        
                                if not date_match_found:
                                    # Delete this order as it wasn't in the original subscription
                                    print(f"Deleting future order {current_order.id} that wasn't in original subscription (delivery date: {current_order.delivery_date})")
                                    current_order.delete_instance(recursive=True)
                
                # Update existing orders
                for order_info in orders_to_update.values():
                    order = order_info['order']
                    data = order_info['data']
                    
                    # Make a copy to avoid modifying the original
                    order_dict = data.copy()
                    order_items = order_dict.pop('order_items', [])
                    
                    # Remove id to avoid conflicts
                    order_dict.pop('id', None)
                    
                    # Handle date fields
                    for field in ['delivery_date', 'production_date', 'from_date', 'to_date']:
                        if field in order_dict and isinstance(order_dict[field], str):
                            try:
                                order_dict[field] = datetime.strptime(order_dict[field], '%Y-%m-%d').date()
                            except (ValueError, TypeError):
                                pass
                    
                    # Update order fields
                    for key, value in order_dict.items():
                        if key != 'order_id' and key != 'id' and hasattr(order, key):
                            setattr(order, key, value)
                    order.save()
                    
                    # Delete existing items and recreate them
                    OrderItem.delete().where(OrderItem.order == order).execute()
                    
                    # Recreate order items
                    for item_data in order_items:
                        item = Item.get(Item.id == item_data['item_id'])
                        amount = item_data['amount']
                        # calculate dates
                        total_days = item.germination_days + item.growth_days
                        production_date = order.delivery_date - timedelta(days=total_days)
                        transfer_date = production_date + timedelta(days=item.germination_days)
                        OrderItem.create(
                            order=order,
                            item=item,
                            amount=amount,
                            production_date=production_date,
                            transfer_date=transfer_date
                        )
                
                # Create orders that no longer exist
                for order_data in orders_to_create:
                    self.recreate_order_from_data(order_data)
                
                return
                
            # Single order restoration logic
            # Ensure order_id is a string
            if 'order_id' in order_data and not isinstance(order_data['order_id'], str):
                order_data['order_id'] = str(order_data['order_id'])
                
            # Get the order
            order = Order.get_or_none(Order.order_id == order_data['order_id'])
            if not order:
                # Check if there's an order with the same delivery date and customer
                if 'delivery_date' in order_data and 'customer_id' in order_data:
                    delivery_date = order_data['delivery_date']
                    if isinstance(delivery_date, str):
                        delivery_date = datetime.strptime(delivery_date, '%Y-%m-%d').date()
                    
                    try:
                        customer = Customer.get_by_id(order_data['customer_id'])
                        matching_order = Order.get_or_none(
                            (Order.customer == customer) &
                            (Order.delivery_date == delivery_date)
                        )
                        
                        if matching_order:
                            # Found a matching order, update it instead of creating a new one
                            print(f"Found matching order with ID {matching_order.order_id} for customer {customer.id} and date {delivery_date}")
                            order = matching_order
                    except Exception as e:
                        print(f"Error finding matching order: {str(e)}")
                
                # If still no order found, recreate it
                if not order:
                    return self.recreate_order_from_data(order_data)
                
            # Make a copy to avoid modifying the original
            order_dict = order_data.copy()
            order_items = order_dict.pop('order_items', [])
            
            # Remove id to avoid conflicts
            order_dict.pop('id', None)
            
            # Handle date fields explicitly
            for field in ['delivery_date', 'production_date', 'from_date', 'to_date']:
                if field in order_dict and isinstance(order_dict[field], str):
                    try:
                        order_dict[field] = datetime.strptime(order_dict[field], '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        # If conversion fails, keep the original value
                        pass
            
            # Update main order data
            try:
                for key, value in order_dict.items():
                    if key != 'order_id' and key != 'id' and hasattr(order, key):
                        setattr(order, key, value)
                order.save()
                
                # Delete existing items
                OrderItem.delete().where(OrderItem.order == order).execute()
                
                # Recreate order items with updated production and transfer dates
                for item_data in order_items:
                    item = Item.get(Item.id == item_data['item_id'])
                    amount = item_data['amount']
                    total_days = item.germination_days + item.growth_days
                    production_date = order.delivery_date - timedelta(days=total_days)
                    transfer_date = production_date + timedelta(days=item.germination_days)
                    OrderItem.create(
                        order=order,
                        item=item,
                        amount=amount,
                        production_date=production_date,
                        transfer_date=transfer_date
                    )
            except Exception as e:
                print(f"Error restoring order: {str(e)}")
                print(f"Order data: {order_dict}")
                raise

    def serialize_order(self, order):
        """Serialize an order instance for the undo system"""
        order_data = {
            'id': order.id,
            'order_id': str(order.order_id),  # Convert UUID to string
            'customer_id': order.customer.id,
            'delivery_date': order.delivery_date,
            #aay 'production_date': item.production_date,
            'from_date': order.from_date,
            'to_date': order.to_date,
            'subscription_type': order.subscription_type,
            'halbe_channel': order.halbe_channel,
            'is_future': order.is_future,
            'order_items': []
        }
        
        # Convert date objects to strings
        for key, value in order_data.items():
            if isinstance(value, date):
                order_data[key] = value.strftime('%Y-%m-%d')
            elif isinstance(value, uuid.UUID):
                order_data[key] = str(value)
        
        # Add order items
        for item in order.order_items:
            order_data['order_items'].append({
                'id': item.id,
                'item_id': item.item.id,
                'amount': item.amount
            })
        
        return order_data

    def collect_orders_data(self, orders):
        """Collect data for multiple orders for the undo system"""
        return [self.serialize_order(order) for order in orders]

    # Add this method
    def create_items_tab(self):
        self.item_view = ItemView(self.tab6, self)
    
    def load_customers(self):
        # always re-query core data so new customers (and items) are loaded into self.customers
        self.load_data()

        # then clear & repopulate the customer_tree as you already do…
        for item in self.customer_tree.get_children():
            self.customer_tree.delete(item)
            
        # Fetch customers sorted by order count with total price calculation
        customers = (Customer
                    .select(Customer, 
                            fn.COUNT(Order.id).alias('order_count'),
                            fn.SUM(OrderItem.amount * Item.price).alias('total_price'),
                            fn.MAX(Order.delivery_date).alias('last_order_date'))
                    .join(Order, JOIN.LEFT_OUTER)
                    .join(OrderItem, JOIN.LEFT_OUTER)
                    .join(Item, JOIN.LEFT_OUTER)
                    .where(Order.is_future == False)  # Only include historical orders
                    .group_by(Customer)
                    .order_by(fn.COUNT(Order.id).desc()))
        
        total_customers = 0
        total_revenue = 0.0
        total_orders = 0
        
        for customer in customers:
            # Format the total price as currency or show €0.00 if None
            total_price = customer.total_price or 0
            formatted_price = f"€{total_price:.2f}".replace('.',',')
            
            # Calculate average order value
            avg_value = total_price / customer.order_count if customer.order_count > 0 and total_price else 0
            formatted_avg = f"€{avg_value:.2f}".replace('.',',')
            
            # Format last order date
            last_order = customer.last_order_date.strftime('%d.%m.%Y') if customer.last_order_date else "-"
            
            self.customer_tree.insert('', 'end', values=(
                customer.name, 
                customer.order_count, 
                formatted_price,
                formatted_avg,
                last_order
            ))
            
            # Update totals
            total_customers += 1
            total_revenue += total_price
            total_orders += customer.order_count
        
        # Update summary variables
        self.total_customers_var.set(f"Anzahl Kunden: {total_customers}")
        self.total_revenue_var.set(f"Gesamtumsatz: €{total_revenue:.2f}".replace('.',','))
        
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        self.avg_order_value_var.set(f"Durchschn. Bestellwert: €{avg_order_value:.2f}".replace('.',','))
        
        # Update the item metrics
        self.update_item_metrics()
    
    def update_item_metrics(self):
        """Update the top lists and metrics for items"""
        try:
            # Clear existing data
            for tree in [self.top_items_tree, self.least_items_tree, self.seasonal_tree]:
                for item in tree.get_children():
                    tree.delete(item)
            
            # Get item order statistics - most popular items by total amount sold
            item_stats = (Item
                        .select(Item,
                               fn.SUM(OrderItem.amount).alias('total_amount'),
                               fn.COUNT(OrderItem.id).alias('order_count'),
                               fn.SUM(OrderItem.amount * Item.price).alias('total_revenue'))
                        .join(OrderItem)
                        .join(Order)
                        .where(Order.is_future == False)
                        .group_by(Item))
            
            # Sort by total amount for top items
            top_items = sorted(item_stats, key=lambda x: x.total_amount or 0, reverse=True)[:5]
            
            # Add top items to tree
            for item in top_items:
                total_amount = item.total_amount or 0
                order_count = item.order_count or 0
                revenue = item.total_revenue or 0
                
                self.top_items_tree.insert('', 'end', values=(
                    item.name,
                    f"{total_amount:.1f}",
                    order_count,
                    f"€{revenue:.2f}".replace('.',',')
                ))
            
            # Sort by total amount for least ordered items (non-zero orders)
            non_zero_items = [item for item in item_stats if item.total_amount > 0]
            least_items = sorted(non_zero_items, key=lambda x: x.total_amount or 0)[:5]
            
            # Add least ordered items to tree
            for item in least_items:
                total_amount = item.total_amount or 0
                order_count = item.order_count or 0
                revenue = item.total_revenue or 0
                
                self.least_items_tree.insert('', 'end', values=(
                    item.name,
                    f"{total_amount:.1f}",
                    order_count,
                    f"€{revenue:.2f}".replace('.',',')
                ))
            
            # Get seasonal data for popular items
            seasonal_items = sorted(item_stats, key=lambda x: x.total_amount or 0, reverse=True)[:10]
            
            for item in seasonal_items:
                # Query quarterly data for this item
                q1_amount = self.get_quarterly_amount(item, 1, 3)
                q2_amount = self.get_quarterly_amount(item, 4, 6)
                q3_amount = self.get_quarterly_amount(item, 7, 9)
                q4_amount = self.get_quarterly_amount(item, 10, 12)
                
                # Determine trend
                trend = self.determine_trend([q1_amount, q2_amount, q3_amount, q4_amount])
                
                self.seasonal_tree.insert('', 'end', values=(
                    item.name,
                    f"{q1_amount:.1f}",
                    f"{q2_amount:.1f}",
                    f"{q3_amount:.1f}",
                    f"{q4_amount:.1f}",
                    trend
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update item metrics: {str(e)}")
    
    def get_quarterly_amount(self, item, start_month, end_month):
        """Get the total amount ordered for an item in a specific quarter"""
        try:
            result = (OrderItem
                    .select(fn.SUM(OrderItem.amount).alias('q_amount'))
                    .join(Order)
                    .where(
                        (OrderItem.item == item) &
                        (Order.is_future == False) &
                        (fn.EXTRACT('month', Order.delivery_date) >= start_month) &
                        (fn.EXTRACT('month', Order.delivery_date) <= end_month)
                    )
                    .scalar())
            return result or 0
        except Exception:
            return 0
    
    def determine_trend(self, quarterly_data):
        """Determine the trend based on quarterly data"""
        if all(x == 0 for x in quarterly_data):
            return "No data"
        
        # Simplified trend analysis
        if quarterly_data[0] < quarterly_data[1] < quarterly_data[2] < quarterly_data[3]:
            return "Strong upward ↑↑"
        elif quarterly_data[0] > quarterly_data[1] > quarterly_data[2] > quarterly_data[3]:
            return "Strong downward ↓↓"
        elif sum(quarterly_data[:2]) < sum(quarterly_data[2:]):
            return "Slight upward ↑"
        elif sum(quarterly_data[:2]) > sum(quarterly_data[2:]):
            return "Slight downward ↓"
        else:
            return "Stable →"
    
    # Modify refresh_tables method to include items
    def refresh_tables(self):
        if hasattr(self, 'delivery_view'):
            self.delivery_view.refresh()
        if hasattr(self, 'production_view'):
            self.production_view.refresh()
        if hasattr(self, 'transfer_view'):
            self.transfer_view.refresh()
        if hasattr(self, 'customer_view'):
            self.customer_view.refresh_customer_list()
        if hasattr(self, 'item_view'):
            self.item_view.refresh_item_list()
        
    def load_data(self):
        self.items = {item.name: item for item in Item.select()}
        self.customers = {customer.name: customer for customer in Customer.select()}
        self.order_items = []  # List to store items for current order
    
    def on_customer_select(self, event):
        selected_item = self.customer_tree.selection()
        if not selected_item:
            return
        
        customer_name = self.customer_tree.item(selected_item, 'values')[0]
        customer = self.customers[customer_name]
        
        # Clear previous orders
        for item in self.order_tree.get_children():
            self.order_tree.delete(item)
        
        # Fetch and display orders for the selected customer
        orders = (Order
                .select()
                .where(Order.customer == customer)
                .group_by(Order.subscription_type, Order.from_date, Order.to_date))
        
        for order in orders:
            items_summary = ', '.join(f"{oi.item.name} ({oi.amount})" for oi in order.order_items)
            
            # Handle single orders specially
            from_date = "Einmalige Bestellung" if order.subscription_type == 0 else order.from_date
            to_date = "" if order.subscription_type == 0 else order.to_date
            
            self.order_tree.insert('', 'end', values=(from_date, to_date, items_summary))
            
    def edit_order(self):
        selected_item = self.order_tree.selection()
        if not selected_item:
            return

        # Use the from_date and to_date from the selected order row as a grouping key.
        from_date_val, to_date_val, _ = self.order_tree.item(selected_item, 'values')
        try:
            # Retrieve all orders sharing the same subscription date range.
            subscription_orders = list(Order.select().where(
                (Order.from_date == from_date_val) & (Order.to_date == to_date_val)
            ))
            
            # Store the original state for undo
            original_orders_data = self.collect_orders_data(subscription_orders)
            
        except Order.DoesNotExist:
            messagebox.showerror("Error", "The selected order does not exist.")
            return

        edit_window = tk.Toplevel(self)
        edit_window.title("Edit Subscription Orders")
        edit_window.geometry("800x600")  # Set initial size

        # --- Overall Subscription Details ---
        sub_details_frame = ttk.Frame(edit_window)
        sub_details_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(sub_details_frame, text="Abonnement-Lieferzeiten:").pack(side='left', padx=5)
        ttk.Label(sub_details_frame, text="Von:").pack(side='left')
        overall_from_entry = ttk.Entry(sub_details_frame, width=10)
        overall_from_entry.pack(side='left', padx=5)
        overall_from_entry.insert(0, from_date_val)

        ttk.Label(sub_details_frame, text="Bis:").pack(side='left')
        overall_to_entry = ttk.Entry(sub_details_frame, width=10)
        overall_to_entry.pack(side='left', padx=5)
        overall_to_entry.insert(0, to_date_val)

        # Main container frame
        main_container = ttk.Frame(edit_window)
        main_container.pack(fill='both', expand=True, padx=10, pady=5)

        # --- Create a Canvas with Scrollbar ---
        canvas = tk.Canvas(main_container)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        
        # Create a frame inside the canvas which will be scrollable
        scrollable_frame = ttk.Frame(canvas)
        
        # Configure the canvas
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack the canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # This list will hold dictionaries representing each order row.
        order_rows = []

        def add_order_row(existing_order=None):
            """
            Create a new order row.
            If existing_order is provided, prepopulate with its delivery date and items.
            """
            row_frame = ttk.Frame(scrollable_frame, relief='groove', borderwidth=1, padding=5)
            row_frame.pack(fill='x', pady=5)

            # Delivery Date for this order row.
            ttk.Label(row_frame, text="Lieferdatum:").grid(row=0, column=0, padx=5, pady=2)
            delivery_entry = ttk.Entry(row_frame, width=12)
            delivery_entry.grid(row=0, column=1, padx=5, pady=2)
            if existing_order:
                # Format the date as dd.mm.yyyy
                delivery_entry.insert(0, existing_order.delivery_date.strftime("%d.%m.%Y"))
            else:
                delivery_entry.insert(0, overall_from_entry.get())

            # --- Items Container ---
            items_frame = ttk.Frame(row_frame)
            items_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=5)

            item_rows = []  # List to hold item-row data for this order.

            def add_item_row(existing_order_item=None):
                """
                Add a row for one order item.
                If existing_order_item is provided, prepopulate its fields.
                """
                item_row_frame = ttk.Frame(items_frame)
                item_row_frame.pack(fill='x', pady=2)

                ttk.Label(item_row_frame, text="Artikel:").pack(side='left', padx=5)
                item_cb = AutocompleteCombobox(item_row_frame, width=20)
                item_cb.set_completion_list(sorted(self.items.keys()))
                item_cb.pack(side='left', padx=5)
                if existing_order_item:
                    item_cb.set(existing_order_item.item.name)

                ttk.Label(item_row_frame, text="Menge:").pack(side='left', padx=5)
                amount_entry = ttk.Entry(item_row_frame, width=8)
                amount_entry.pack(side='left', padx=5)
                if existing_order_item:
                    amount_entry.insert(0, str(existing_order_item.amount))

                def delete_item():
                    # Remove this item row.
                    item_row_frame.destroy()
                    item_rows.remove(item_dict)

                del_button = ttk.Button(item_row_frame, text="Löschen", command=delete_item)
                del_button.pack(side='left', padx=5)

                item_dict = {
                    'frame': item_row_frame,
                    'item_cb': item_cb,
                    'amount_entry': amount_entry,
                    'existing': existing_order_item  # None for new items.
                }
                item_rows.append(item_dict)

            # Prepopulate with existing order items if available.
            if existing_order:
                for oi in existing_order.order_items:
                    add_item_row(existing_order_item=oi)
            else:
                # New order: start with one empty item row.
                add_item_row()

            add_item_btn = ttk.Button(row_frame, text="Artikel hinzufügen", command=lambda: add_item_row())
            add_item_btn.grid(row=0, column=2, padx=5, pady=2)

            def delete_order():
                if existing_order:
                    scope_options = ["Delete only this order", "Delete this and all future orders"]
                    
                    # Only show subscription options if this is a subscription order
                    has_subscription = existing_order.subscription_type > 0 and existing_order.from_date and existing_order.to_date
                    
                    if has_subscription:
                        choice = messagebox.askyesnocancel(
                            "Bestellung löschen", 
                            "Möchten Sie nur diese Bestellung löschen?\n\n"
                            "Ja - Nur diese Bestellung löschen\n"
                            "Nein - Diese und alle zukünftigen Bestellungen in diesem Abonnement löschen\n"
                            "Abbrechen - Nichts löschen"
                        )
                        
                        if choice is None:  # Cancel
                            return
                        
                        with db.atomic():  # Transaction to ensure all operations succeed or fail together
                            # First record the action for undo
                            if choice:  # Yes - Delete only this order
                                # Store the order data before deletion
                                order_data = self.serialize_order(existing_order)
                                self.record_action(
                                    ACTION_DELETE_ORDER,
                                    order_data,
                                    None,
                                    "Löschung einer Bestellung"
                                )
                                
                                existing_order.delete_instance(recursive=True)
                                messagebox.showinfo("Erfolg", "Bestellung erfolgreich gelöscht!")
                            else:  # No - Delete this and all future orders
                                today = datetime.now().date()
                                
                                # Get the items in this order to compare with other orders
                                current_order_items = set()
                                for order_item in existing_order.order_items:
                                    current_order_items.add(order_item.item.id)
                                
                                # Get weekday of the current order
                                current_weekday = existing_order.delivery_date.weekday()
                                
                                # Display confirmation dialog with more details
                                if messagebox.askokcancel("Bestätigen", 
                                    f"Sind Sie sicher, dass Sie diese Lieferung und alle zukünftigen Lieferungen für {existing_order.customer.name} am gleichen Wochentag löschen möchten?\n\n"
                                    f"Es werden nur Bestellungen mit identischen Artikeln gelöscht."):
                                    
                                    # First get all future orders for the same customer on same weekday
                                    future_orders_query = Order.select().where(
                                        (Order.customer == existing_order.customer) &
                                        (Order.delivery_date >= today)
                                    )
                                    
                                    # Filter for same weekday and same items
                                    matching_orders = []
                                    
                                    for order in future_orders_query:
                                        # Check if same weekday
                                        if order.delivery_date.weekday() != current_weekday:
                                            continue
                                            
                                        # Check if has the same items
                                        order_items = set()
                                        for order_item in order.order_items:
                                            order_items.add(order_item.item.id)
                                            
                                        # Only include if items match exactly (same count and same IDs)
                                        if order_items == current_order_items:
                                            matching_orders.append(order)
                                    
                                    # Store all the order data before deletion
                                    deleted_orders_data = self.collect_orders_data(matching_orders)
                                    self.record_action(
                                        ACTION_DELETE_ORDER,
                                        {'orders': deleted_orders_data},
                                        None,
                                        f"Löschung von {len(matching_orders)} Bestellungen"
                                    )
                                    
                                    # Delete the matching orders
                                    deleted_count = 0
                                    for future_order in matching_orders:
                                        future_order.delete_instance(recursive=True)
                                        deleted_count += 1
                                    
                                    messagebox.showinfo("Erfolg", f"{deleted_count} Bestellungen erfolgreich gelöscht!")
                                else:
                                    return  # User cancelled the deletion
                    else:
                        # Not a subscription order, simple confirmation
                        if messagebox.askyesno("Bestätigen", "Diese Bestellung löschen?"):
                            # Store the order data before deletion
                            order_data = self.serialize_order(existing_order)
                            self.record_action(
                                ACTION_DELETE_ORDER,
                                order_data,
                                None,
                                "Löschung einer Bestellung"
                            )
                            
                            existing_order.delete_instance(recursive=True)
                            messagebox.showinfo("Erfolg", "Bestellung erfolgreich gelöscht!")
                    
                    row_frame.destroy()
                    order_rows.remove(order_row_dict)
                else:
                    # For new rows that haven't been saved yet
                    row_frame.destroy()
                    order_rows.remove(order_row_dict)

            del_order_btn = ttk.Button(row_frame, text="Bestellung löschen", command=delete_order)
            del_order_btn.grid(row=0, column=3, padx=5, pady=2)

            order_row_dict = {
                'frame': row_frame,
                'delivery_entry': delivery_entry,
                'items': item_rows,
                'existing_order': existing_order
            }
            order_rows.append(order_row_dict)

        # Add rows for each existing subscription order.
        for order in subscription_orders:
            add_order_row(existing_order=order)

        # Button frame at the bottom
        buttons_frame = ttk.Frame(edit_window)
        buttons_frame.pack(side="bottom", fill="x", padx=10, pady=10)

        # Button to add a new order row.
        add_order_overall_btn = ttk.Button(buttons_frame, text="Neue Bestellung", command=lambda: add_order_row())
        add_order_overall_btn.pack(side="left", padx=5)

        def save_all_changes():
            try:
                overall_from_str = overall_from_entry.get()
                overall_to_str = overall_to_entry.get()
                
                # Convert to date objects for saving
                try:
                    overall_from = datetime.strptime(overall_from_str, "%d.%m.%Y").date() if "." in overall_from_str else datetime.strptime(overall_from_str, "%Y-%m-%d").date()
                    overall_to = datetime.strptime(overall_to_str, "%d.%m.%Y").date() if "." in overall_to_str else datetime.strptime(overall_to_str, "%Y-%m-%d").date()
                except ValueError:
                    messagebox.showerror("Fehler", "Ungültiges Datumsformat. Verwenden Sie entweder dd.mm.yyyy oder yyyy-mm-dd.")
                    return
                
                # Define the validation function that has been thoroughly tested
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
                
                with db.atomic():  # Use transaction to ensure all changes are saved or none
                    # Track edited and new orders for the undo system
                    edited_orders = []
                    
                    # Track if subscription type changed for any order
                    subscription_type_changed = False
                    subscription_type = None
                    
                    # First, delete any existing future orders that might need to be regenerated
                    # (we'll regenerate them based on the new subscription settings)
                    if subscription_orders and len(subscription_orders) > 0:
                        reference_order = subscription_orders[0]
                        old_subscription_type = reference_order.subscription_type
                        today = datetime.now().date()
                        
                        # Store the customer and other details
                        customer = reference_order.customer
                        halbe_channel = reference_order.halbe_channel
                        
                        # Loop through each order row to update/create orders and their items.
                        for row in order_rows:
                            delivery_date_str = row['delivery_entry'].get()
                            try:
                                delivery_date = datetime.strptime(delivery_date_str, "%d.%m.%Y").date()
                            except ValueError:
                                messagebox.showerror("Fehler", f"Ungültiges Datumsformat: {delivery_date_str}. Verwenden Sie dd.mm.yyyy.")
                                return

                            existing_order = row['existing_order']
                            
                            # Gather item data first and validate
                            order_items_data = []
                            for item_row in row['items']:
                                item_name = item_row['item_cb'].get()
                                
                                # Use our validated amount validation function
                                amount_str = item_row['amount_entry'].get().strip()
                                valid, result = validate_amount(amount_str, item_name)
                                
                                if not valid:
                                    messagebox.showerror("Fehler", result)
                                    return
                                
                                amount = result  # This is the validated float value
                                
                                if item_name not in self.items:
                                    messagebox.showerror("Fehler", f"Ungültiger Artikel: {item_name}")
                                    return
                                
                                order_items_data.append((item_name, amount))
                            
                            if existing_order:
                                # Store the original order state for undo
                                original_order_data = self.serialize_order(existing_order)
                                edited_orders.append(original_order_data)
                                
                                # Update existing order
                                existing_order.delivery_date = delivery_date
                                existing_order.from_date = overall_from
                                existing_order.to_date = overall_to
                                
                                # Check if the subscription type has changed - we'll need to regenerate futures
                                if old_subscription_type != subscription_type:
                                    subscription_type_changed = True
                                    
                                # Save changes to the order
                                existing_order.save()
                                
                                # Delete existing order items for this order
                                for oi in existing_order.order_items:
                                    oi.delete_instance()
                                
                                # Create new order items
                                for item_name, amount in order_items_data:
                                    OrderItem.create(
                                        order=existing_order,
                                        item=self.items[item_name],
                                        amount=amount
                                    )
                                
                                # Save the subscription type from the first order
                                if subscription_type is None:
                                    subscription_type = existing_order.subscription_type
                            else:
                                # For a new order, we need a customer
                                if subscription_orders:
                                    if subscription_type is None:
                                        subscription_type = subscription_orders[0].subscription_type
                                else:
                                    messagebox.showerror("Fehler", "Kunde für neue Bestellung kann nicht bestimmt werden.")
                                    return
                                
                                # Calculate production date based on max days
                                max_days = max(self.items[item_name].total_days for item_name, _ in order_items_data)
                                production_date = delivery_date - timedelta(days=max_days)
                                
                                # Create new order - make sure to use a unique order_id
                                new_order = Order.create(
                                    customer=customer,
                                    delivery_date=delivery_date,
                                    production_date=production_date,
                                    from_date=overall_from,
                                    to_date=overall_to,
                                    subscription_type=subscription_type,
                                    halbe_channel=halbe_channel,
                                    order_id=uuid.uuid4(),
                                    is_future=True
                                )
                                
                                # Create order items
                                for item_name, amount in order_items_data:
                                    OrderItem.create(
                                        order=new_order,
                                        item=self.items[item_name],
                                        amount=amount
                                    )
                        
                        # If subscription type changed, we need to regenerate all future orders
                        # Delete all future orders excluding those we just edited
                        if subscription_type_changed or old_subscription_type != subscription_type:
                            edited_order_ids = [row['existing_order'].id for row in order_rows if row['existing_order']]
                            
                            # Store original data for orders that will be deleted
                            future_orders_to_delete = Order.select().where(
                                (Order.from_date == overall_from) &
                                (Order.to_date == overall_to) &
                                (Order.customer == customer) &
                                (Order.delivery_date > today) &
                                ~(Order.id << edited_order_ids)
                            )
                            
                            # Save data for undo
                            for order_to_delete in future_orders_to_delete:
                                edited_orders.append(self.serialize_order(order_to_delete))
                                order_to_delete.delete_instance(recursive=True)
                            
                            # Find the earliest existing order to use as a template for regeneration
                            base_order = Order.select().where(
                                (Order.from_date == overall_from) &
                                (Order.to_date == overall_to) &
                                (Order.customer == customer)
                            ).order_by(Order.delivery_date).first()
                            
                            if base_order:
                                # Update the subscription type for the base order
                                base_order.subscription_type = subscription_type
                                base_order.save()
                                
                                # Generate new future orders with the updated subscription type
                                future_orders = generate_subscription_orders(base_order)
                                
                                # Get all items from the base order
                                base_items = list(base_order.order_items)
                                
                                # Create the new future orders with the same items
                                for future_order_data in future_orders:
                                    # Check if this date already exists in edited orders
                                    delivery_date = future_order_data['delivery_date']
                                    if not Order.select().where(
                                        (Order.from_date == overall_from) &
                                        (Order.to_date == overall_to) &
                                        (Order.customer == customer) &
                                        (Order.delivery_date == delivery_date)
                                    ).exists():
                                        future_order = Order.create(
                                            **future_order_data,
                                            order_id=uuid.uuid4()
                                        )
                                        
                                        # Copy items from base order
                                        for item_data in base_items:
                                            OrderItem.create(
                                                order=future_order,
                                                item=item_data.item,
                                                amount=item_data.amount
                                            )
                
                # Record action for undo after successful save
                self.record_action(
                    ACTION_EDIT_ORDER,
                    {'orders': original_orders_data},
                    {'orders': edited_orders},  # Add the edited orders data as new_data
                    "Änderung von Bestellungen"
                )
                
                messagebox.showinfo("Erfolg", "Bestellungen erfolgreich aktualisiert!")
                edit_window.destroy()
                self.on_customer_select(None)  # Refresh orders list
                print("[DEBUG] UI refresh triggered")
                self.refresh_tables()  # Refresh all views
                
            except Exception as e:
                messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {str(e)}")
        # Save button
        save_btn = ttk.Button(buttons_frame, text="Alle Änderungen speichern", command=save_all_changes)
        save_btn.pack(side="right", padx=5)

        # Add mouse wheel binding to the canvas for better scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)  # Windows and macOS
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))  # Linux
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))  # Linux
            
    def create_order_tab(self):
        # Customer Frame
        customer_frame = ttk.LabelFrame(self.tab1, text="Kundeninformationen", padding="10")
        customer_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(customer_frame, text="Kunde:").pack(side='left', padx=5)
        self.customer_combo = AutocompleteCombobox(customer_frame, width=50)
        self.customer_combo.set_completion_list(sorted(self.customers.keys()))
        self.customer_combo.pack(side='left', padx=5, fill='x', expand=True)
        
        # Items Frame
        items_frame = ttk.LabelFrame(self.tab1, text="Bestellte Artikel", padding="10")
        items_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Add item controls
        add_frame = ttk.Frame(items_frame)
        add_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(add_frame, text="Artikel:").pack(side='left', padx=5)
        self.item_combo = AutocompleteCombobox(add_frame, width=30)
        self.item_combo.set_completion_list(sorted(self.items.keys()))
        self.item_combo.pack(side='left', padx=5)
        
        ttk.Label(add_frame, text="Menge:").pack(side='left', padx=5)
        self.amount_var = tk.StringVar()
        amount_entry = ttk.Entry(add_frame, textvariable=self.amount_var, width=10)
        amount_entry.pack(side='left', padx=5)
        
        ttk.Button(add_frame, text="Artikel hinzufügen", command=self.add_item).pack(side='left', padx=5)
        
        # Items list
        columns = ('Artikel', 'Menge', 'Wachstumstage', 'Preis')
        self.items_tree = ttk.Treeview(items_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.items_tree.heading(col, text=col)
        self.items_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        ttk.Button(items_frame, text="Ausgewählte entfernen", 
                  command=self.remove_selected_item).pack(pady=5)
        
        # Order Details Frame
        details_frame = ttk.LabelFrame(self.tab1, text="Bestelldetails", padding="10")
        details_frame.pack(fill='x', padx=10, pady=5)
        
        # Delivery Date
        date_frame = ttk.Frame(details_frame)
        date_frame.pack(fill='x', pady=5)
        
        ttk.Label(date_frame, text="Lieferdatum:").pack(side='left', padx=5)
        self.delivery_date = self.create_date_entry(date_frame)
        
        # Set default date to today
        today = datetime.now()
        self.set_date_entry(self.delivery_date, today)
        
        # Subscription Frame
        sub_frame = ttk.Frame(details_frame)
        sub_frame.pack(fill='x', pady=5)
        
        self.sub_var = tk.IntVar(value=0)
        sub_types = {
            0: "Kein Abonnement",
            1: "Wöchentlich",
            2: "Zweiwöchentlich",
            3: "Alle 3 Wochen",
            4: "Alle 4 Wochen"
        }
        for val, text in sub_types.items():
            ttk.Radiobutton(sub_frame, text=text, variable=self.sub_var, 
                          value=val).pack(side='left', padx=5)
        
        # Date Range Frame
        range_frame = ttk.Frame(details_frame)
        range_frame.pack(fill='x', pady=5)
        
        ttk.Label(range_frame, text="Von:").pack(side='left', padx=5)
        self.from_date = self.create_date_entry(range_frame)
        
        ttk.Label(range_frame, text="Bis:").pack(side='left', padx=5)
        self.to_date = self.create_date_entry(range_frame)
        
        # Set default dates
        self.set_date_entry(self.from_date, today)
        self.set_date_entry(self.to_date, datetime(2025, 12, 31))
        
        # Halbe Channel
        self.halbe_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(details_frame, text="Halbe Channel", 
                       variable=self.halbe_var).pack(pady=5)
        
        # Save Button
        ttk.Button(self.tab1, text="Bestellung speichern", 
                  command=self.save_order).pack(pady=10)

        # Add this new code at the end
        button_frame = ttk.Frame(self.tab1)
        button_frame.pack(pady=10)
        
        # Save Order button
        ttk.Button(button_frame, text="Bestellung speichern", 
                command=self.save_order).pack(side='left', padx=5)
        
        # Master Print button
        ttk.Button(button_frame, text="Alle Zeitpläne drucken", 
                command=self.print_all_schedules).pack(side='left', padx=5)
    
    def create_orders_tab(self):
        # Frame for customer list
        customer_frame = ttk.LabelFrame(self.tab7, text="Kunden", padding="10")
        customer_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Treeview for customer list
        self.customer_tree = ttk.Treeview(customer_frame, columns=('Name', 'Anzahl Bestellungen', 'Umsatz', 'Durchschn. Wert', 'Letzte Bestellung'), show='headings')
        self.customer_tree.heading('Name', text='Name')
        self.customer_tree.heading('Anzahl Bestellungen', text='Anzahl Bestellungen')
        self.customer_tree.heading('Umsatz', text='Umsatz')
        self.customer_tree.heading('Durchschn. Wert', text='Durchschn. Wert')
        self.customer_tree.heading('Letzte Bestellung', text='Letzte Bestellung')
        
        # Set column widths
        self.customer_tree.column('Name', width=200)
        self.customer_tree.column('Anzahl Bestellungen', width=150)
        self.customer_tree.column('Umsatz', width=100)
        self.customer_tree.column('Durchschn. Wert', width=120)
        self.customer_tree.column('Letzte Bestellung', width=120)
        
        # Add vertical scrollbar
        customer_scrollbar = ttk.Scrollbar(customer_frame, orient="vertical", command=self.customer_tree.yview)
        self.customer_tree.configure(yscrollcommand=customer_scrollbar.set)
        
        # Pack tree and scrollbar
        self.customer_tree.pack(side="left", fill='both', expand=True, padx=5, pady=5)
        customer_scrollbar.pack(side="right", fill="y")
        
        # Summary frame - shows overall statistics
        summary_frame = ttk.LabelFrame(customer_frame, text="Zusammenfassung")
        summary_frame.pack(fill='x', padx=5, pady=5, anchor='s')
        
        # Total metrics display with larger font
        self.total_customers_var = tk.StringVar(value="Anzahl Kunden: 0")
        self.total_revenue_var = tk.StringVar(value="Gesamtumsatz: €0,00")
        self.avg_order_value_var = tk.StringVar(value="Durchschn. Bestellwert: €0,00")
        
        # Use larger and bolder font for the summary metrics
        ttk.Label(summary_frame, textvariable=self.total_customers_var, font=("", 14, "bold")).pack(side='left', padx=20, pady=5)
        ttk.Label(summary_frame, textvariable=self.total_revenue_var, font=("", 14, "bold")).pack(side='left', padx=20, pady=5)
        ttk.Label(summary_frame, textvariable=self.avg_order_value_var, font=("", 14, "bold")).pack(side='left', padx=20, pady=5)
        
        # Create metrics notebook for top lists and analysis
        metrics_notebook = ttk.Notebook(customer_frame)
        metrics_notebook.pack(fill='both', expand=True, padx=5, pady=5, before=summary_frame)
        
        # Tab for top ordered items
        top_items_frame = ttk.Frame(metrics_notebook)
        least_items_frame = ttk.Frame(metrics_notebook)
        seasonal_frame = ttk.Frame(metrics_notebook)
        
        metrics_notebook.add(top_items_frame, text="Top Artikel")
        metrics_notebook.add(least_items_frame, text="Wenig bestellte Artikel")
        metrics_notebook.add(seasonal_frame, text="Saisonale Analyse")
        
        # Create treeview for top items
        top_items_tree = ttk.Treeview(top_items_frame, columns=('Artikel', 'Kanäle Gesamt', 'Bestellungen', 'Umsatz'), show='headings', height=6)
        top_items_tree.heading('Artikel', text='Artikel')
        top_items_tree.heading('Kanäle Gesamt', text='Kanäle Gesamt')
        top_items_tree.heading('Bestellungen', text='Bestellungen')
        top_items_tree.heading('Umsatz', text='Umsatz')
        
        top_items_tree.column('Artikel', width=200)
        top_items_tree.column('Kanäle Gesamt', width=100)
        top_items_tree.column('Bestellungen', width=100)
        top_items_tree.column('Umsatz', width=100)
        
        top_items_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create treeview for least ordered items
        least_items_tree = ttk.Treeview(least_items_frame, columns=('Artikel', 'Kanäle Gesamt', 'Bestellungen', 'Umsatz'), show='headings', height=6)
        least_items_tree.heading('Artikel', text='Artikel')
        least_items_tree.heading('Kanäle Gesamt', text='Kanäle Gesamt')
        least_items_tree.heading('Bestellungen', text='Bestellungen')
        least_items_tree.heading('Umsatz', text='Umsatz')
        
        least_items_tree.column('Artikel', width=200)
        least_items_tree.column('Kanäle Gesamt', width=100)
        least_items_tree.column('Bestellungen', width=100)
        least_items_tree.column('Umsatz', width=100)
        
        least_items_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create treeview for seasonal analysis
        seasonal_tree = ttk.Treeview(seasonal_frame, columns=('Artikel', 'Q1', 'Q2', 'Q3', 'Q4', 'Trend'), show='headings', height=6)
        seasonal_tree.heading('Artikel', text='Artikel')
        seasonal_tree.heading('Q1', text='Q1 (Jan-Mär)')
        seasonal_tree.heading('Q2', text='Q2 (Apr-Jun)')
        seasonal_tree.heading('Q3', text='Q3 (Jul-Sep)')
        seasonal_tree.heading('Q4', text='Q4 (Okt-Dez)')
        seasonal_tree.heading('Trend', text='Trend')
        
        seasonal_tree.column('Artikel', width=150)
        seasonal_tree.column('Q1', width=100)
        seasonal_tree.column('Q2', width=100)
        seasonal_tree.column('Q3', width=100)
        seasonal_tree.column('Q4', width=100)
        seasonal_tree.column('Trend', width=150)
        
        seasonal_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Save tree references for updates
        self.top_items_tree = top_items_tree
        self.least_items_tree = least_items_tree
        self.seasonal_tree = seasonal_tree
        
        # Bind selection event
        self.customer_tree.bind('<<TreeviewSelect>>', self.on_customer_select)
        
        # Frame for order list
        order_frame = ttk.LabelFrame(self.tab7, text="Bestellungen", padding="10")
        order_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Treeview for order list
        self.order_tree = ttk.Treeview(order_frame, columns=('Von Datum', 'Bis Datum', 'Items'), show='headings')
        self.order_tree.heading('Von Datum', text='Von Datum')
        self.order_tree.heading('Bis Datum', text='Bis Datum')
        self.order_tree.heading('Items', text='Items')
        self.order_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(order_frame)
        button_frame.pack(fill='x', pady=5)
        
        # Button to edit selected order
        ttk.Button(button_frame, text="Bestellung bearbeiten", command=self.edit_order).pack(side='left', padx=5)
        
        # Refresh button
        ttk.Button(button_frame, text="Daten aktualisieren", command=self.load_customers).pack(side='right', padx=5)
        
        self.load_customers()

    def set_date_entry(self, date_frame, date):
        """Set date in a date entry frame"""
        day_entry = date_frame.children['!entry']
        month_entry = date_frame.children['!entry2']
        year_entry = date_frame.children['!entry3']
        
        day_entry.delete(0, tk.END)
        day_entry.insert(0, str(date.day))
        month_entry.delete(0, tk.END)
        month_entry.insert(0, str(date.month))
        year_entry.delete(0, tk.END)
        year_entry.insert(0, str(date.year))
    
    def create_date_entry(self, parent):
        """Create a custom date entry widget"""
        frame = ttk.Frame(parent)
        frame.pack(side='left', padx=5)
        
        # Day
        day_entry = ttk.Entry(frame, width=3)
        day_entry.pack(side='left')
        
        ttk.Label(frame, text=".").pack(side='left')
        
        # Month
        month_entry = ttk.Entry(frame, width=3)
        month_entry.pack(side='left')
        
        ttk.Label(frame, text=".").pack(side='left')
        
        # Year
        year_entry = ttk.Entry(frame, width=5)
        year_entry.pack(side='left')
        
        return frame
    
    def get_date_from_entry(self, date_frame):
        # Get all child widgets that are Entry widgets
        entries = [child for child in date_frame.winfo_children() if isinstance(child, (tk.Entry, ttk.Entry))]
        if len(entries) < 3:
            return datetime.now().date()
        try:
            day = int(entries[0].get())
            month = int(entries[1].get())
            year = int(entries[2].get())
            return datetime(year, month, day).date()
        except ValueError:
            return datetime.now().date()
    
    def add_item(self):
        try:
            item_name = self.item_combo.get()
            amount = float(self.amount_var.get())
            
            if not item_name or item_name not in self.items:
                raise ValueError("Please select a valid item")
            
            if amount <= 0:
                raise ValueError("Amount must be greater than 0")
            
            item = self.items[item_name]
            self.order_items.append({
                'item': item,
                'amount': amount
            })
            
            self.items_tree.insert('', 'end', values=(
                item.name,
                f"{amount:.1f}",
                item.total_days,
                f"€{item.price * amount:.2f}"
            ))
            
            # Clear inputs
            self.item_combo.set('')
            self.amount_var.set('')
            
        except ValueError as e:
            messagebox.showerror("Error", str(e))
    
    def remove_selected_item(self):
        selected = self.items_tree.selection()
        if not selected:
            return
        
        for item_id in selected:
            item_index = self.items_tree.index(item_id)
            self.order_items.pop(item_index)
            self.items_tree.delete(item_id)
    
    def save_order(self):
        try:
            if not self.customer_combo.get() or self.customer_combo.get() not in self.customers:
                raise ValueError("Please select a valid customer")
            
            if not self.order_items:
                raise ValueError("Please add at least one item to the order")
            
            customer = self.customers[self.customer_combo.get()]
            delivery_date = self.get_date_from_entry(self.delivery_date)
            
            # Calculate earliest production date based on longest growth period
            max_days = max(item['item'].total_days for item in self.order_items)
            production_date = delivery_date - timedelta(days=max_days)
            
            created_orders = []
            
            with db.atomic():
                # Generate a unique order_id
                order_id = uuid.uuid4()
                
                # Create order
                order = Order.create(
                    customer=customer,
                    delivery_date=delivery_date,
                    production_date=production_date,
                    from_date=self.get_date_from_entry(self.from_date) if self.sub_var.get() else None,
                    to_date=self.get_date_from_entry(self.to_date) if self.sub_var.get() else None,
                    subscription_type=self.sub_var.get(),
                    halbe_channel=self.halbe_var.get(),
                    order_id=order_id,
                    is_future=False
                )
                created_orders.append(order)
                
                # Create order items with production_date
                for item_data in self.order_items:
                    total_days = item_data['item'].germination_days + item_data['item'].growth_days
                    production_date = delivery_date - timedelta(days=total_days)
                    transfer_date = production_date + timedelta(days=item_data['item'].germination_days)

                    OrderItem.create(
                        order=order,
                        item=item_data['item'],
                        amount=item_data['amount'],
                        production_date=production_date,
                        transfer_date=transfer_date,
                    )
                    print(f"[DEBUG] Created OrderItem: {item_data['item'].name}, Prod: {production_date}, Trans: {transfer_date}, Amount: {item_data['amount']}")
                
                # Generate subscription orders if applicable
                if self.sub_var.get() > 0:
                    future_orders = generate_subscription_orders(order)
                    for future_order_data in future_orders:
                        future_order = Order.create(
                            **future_order_data,
                            order_id=uuid.uuid4()
                        )
                        created_orders.append(future_order)
                        # Copy items to future order
                        for item_data in self.order_items:
                            total_days = item_data['item'].germination_days + item_data['item'].growth_days
                            production_date = future_order.delivery_date - timedelta(days=total_days)
                            transfer_date = production_date + timedelta(days=item_data['item'].germination_days)

                            OrderItem.create(
                                order=future_order,
                                item=item_data['item'],
                                amount=item_data['amount'],
                                production_date=production_date,
                                transfer_date=transfer_date
                            )
            
            # Record action for undo
            self.record_action(
                ACTION_CREATE_ORDER,
                None,  # No old data for creation
                {'order_id': order_id, 'count': len(created_orders)},
                f"Erstellung von {len(created_orders)} Bestellungen"
            )
            
            messagebox.showinfo("Erfolg", "Bestellung erfolgreich gespeichert!")
            self.clear_form()
            print("[DEBUG] UI refresh triggered")
            self.refresh_tables()  # Refresh all views after saving the order
            
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
        try:
            if not self.customer_combo.get() or self.customer_combo.get() not in self.customers:
                raise ValueError("Please select a valid customer")
            
            if not self.order_items:
                raise ValueError("Please add at least one item to the order")
            
            customer = self.customers[self.customer_combo.get()]
            delivery_date = self.get_date_from_entry(self.delivery_date)
            
            # Calculate earliest production date based on longest growth period
            max_days = max(item['item'].total_days for item in self.order_items)
            production_date = delivery_date - timedelta(days=max_days)
            
            # Confirm with user if production date falls on Sunday
            if production_date.weekday() == 6:  # 6 = Sunday
                use_sunday = messagebox.askyesnocancel(
                    "Sonntagsproduktion",
                    f"Das Produktionsdatum dieser Bestellung fällt auf einen Sonntag ({production_date.strftime('%d.%m.%Y')}).\n\n"
                    "Ja: Sonntag als Produktionsdatum beibehalten\n"
                    "Nein: Stattdessen auf Samstag verschieben\n"
                    "Abbrechen: Speichern der Bestellung abbrechen"
                )
                
                if use_sunday is None:  # User clicked Cancel
                    return
                    
                if use_sunday is False:  # User clicked No, move to Saturday
                    production_date = production_date - timedelta(days=1)
            
            created_orders = []
            
            with db.atomic():
                # Generate a unique order_id
                order_id = uuid.uuid4()
                
                # Create order
                order = Order.create(
                    customer=customer,
                    delivery_date=delivery_date,
                    production_date=production_date,
                    from_date=self.get_date_from_entry(self.from_date) if self.sub_var.get() else None,
                    to_date=self.get_date_from_entry(self.to_date) if self.sub_var.get() else None,
                    subscription_type=self.sub_var.get(),
                    halbe_channel=self.halbe_var.get(),
                    order_id=order_id,
                    is_future=False
                )
                created_orders.append(order)
                
                # Create order items with production_date
                #from database import calculate_itemwise_production_dates
                #item_objects = [OrderItem(order=order, item=item_data['item']) for item_data in self.order_items]
                #itemwise_dates = calculate_itemwise_production_dates(delivery_date, item_objects)

                for item_data in self.order_items:
                    total_days = item_data['item'].germination_days + item_data['item'].growth_days
                    production_date = delivery_date - timedelta(days=total_days)
                    transfer_date = production_date + timedelta(days=item_data['item'].germination_days)

                    order_item_key = OrderItem(order=order, item=item_data['item'])
                    
                    OrderItem.create(
                        order=order,
                        item=item_data['item'],
                        amount=item_data['amount'],
                        production_date=production_date,
                        transfer_date=transfer_date,
                    )
                    print(f"[DEBUG] Created OrderItem: {item_data['item'].name}, Prod: {production_date}, Trans: {transfer_date}, Amount: {item_data['amount']}")
                
                # Generate subscription orders if applicable
                if self.sub_var.get() > 0:
                    future_orders = generate_subscription_orders(order)
                    for future_order_data in future_orders:
                        future_order = Order.create(
                            **future_order_data,
                            order_id=uuid.uuid4()
                        )
                        created_orders.append(future_order)
                        # Copy items to future order
                        for item_data in self.order_items:
                            total_days = item_data['item'].germination_days + item_data['item'].growth_days
                            production_date = future_order.delivery_date - timedelta(days=total_days)
                            transfer_date = production_date + timedelta(days=item_data['item'].germination_days)

                            OrderItem.create(
                                order=future_order,
                                item=item_data['item'],
                                amount=item_data['amount'],
                                production_date=production_date,
                                transfer_date=transfer_date
                            )
            
            # Record action for undo
            self.record_action(
                ACTION_CREATE_ORDER,
                None,  # No old data for creation
                {'order_id': order_id, 'count': len(created_orders)},
                f"Erstellung von {len(created_orders)} Bestellungen"
            )
            
            messagebox.showinfo("Erfolg", "Bestellung erfolgreich gespeichert!")
            self.clear_form()
            print("[DEBUG] UI refresh triggered")
            self.refresh_tables()
            
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def clear_form(self):
        self.customer_combo.set('')
        self.order_items.clear()
        for item in self.items_tree.get_children():
            self.items_tree.delete(item)
        self.item_combo.set('')
        self.amount_var.set('')
        self.sub_var.set(0)
        self.halbe_var.set(False)
        
        # Reset date entries to defaults
        today = datetime.now()
        self.set_date_entry(self.delivery_date, today)
        self.set_date_entry(self.from_date, today)
        self.set_date_entry(self.to_date, datetime(2025, 12, 31))
    
    def create_delivery_tab(self):
        # Create print button frame
        print_frame = ttk.Frame(self.tab2)
        print_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(print_frame, text="Lieferplan drucken",
                command=lambda: self.print_single_schedule("delivery")).pack(side='right')
        
        # Pass self (the ProductionApp instance) to WeeklyDeliveryView
        self.delivery_view = WeeklyDeliveryView(self.tab2, self, self.db)
        
        # Set up callbacks to enable undo
        def delivery_on_edit_order(order_data, new_data):
            # This will be called when an order is edited in the delivery tab
            print("Order edited in delivery tab, recording for undo")
            self.record_action(
                ACTION_EDIT_ORDER,
                order_data,  # Original order data
                new_data,    # New order data
                "Änderung von Bestellung in Lieferungsplan"
            )
        
        # Attach the callback
        self.delivery_view.set_edit_callback(delivery_on_edit_order)
    
    def create_production_tab(self):
        # Create print button frame
        print_frame = ttk.Frame(self.tab3)
        print_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(print_frame, text="Produktionsplan drucken",
                command=lambda: self.print_single_schedule("production")).pack(side='right')
        
        self.production_view = WeeklyProductionView(self.tab3, self, self.db)

    def create_transfer_tab(self):
        # Create print button frame
        print_frame = ttk.Frame(self.tab4)
        print_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(print_frame, text="Transferplan drucken",
                command=lambda: self.print_single_schedule("transfer")).pack(side='right')
        
        self.transfer_view = WeeklyTransferView(self.tab4, self, self.db)
    
    def create_customers_tab(self):
        self.customer_view = CustomerView(self.tab5, self)
    
    def print_all_schedules(self):
        """Print all schedules and open the PDF"""
        try:
            week_selection = ask_week_selection()
            if week_selection:
                week_date = date.today()
                if week_selection == "next":
                    week_date += timedelta(days=7)
                
                filepath = self.printer.print_all_schedules(week_date)
                self.open_pdf(filepath)
                messagebox.showinfo("Erfolg", "Alle Zeitpläne wurden erfolgreich gedruckt!")
        except Exception as e:
            messagebox.showerror("Fehler", f"Zeitpläne konnten nicht gedruckt werden: {str(e)}")

    def print_single_schedule(self, schedule_type):
        """Print a single schedule and open the PDF"""
        try:
            # Get the currently displayed week from the respective view
            current_week = None
            if schedule_type == "delivery" and hasattr(self, 'delivery_view'):
                current_week = self.delivery_view.current_week
            elif schedule_type == "production" and hasattr(self, 'production_view'):
                current_week = self.production_view.current_week
            elif schedule_type == "transfer" and hasattr(self, 'transfer_view'):
                current_week = self.transfer_view.current_week
            
            if current_week:
                filepath = self.printer.print_week_schedule(schedule_type, current_week)
                self.open_pdf(filepath)
                messagebox.showinfo("Erfolg", f"{schedule_type.title()}-Plan wurde erfolgreich gedruckt!")
            else:
                messagebox.showerror("Fehler", "Aktuelle Woche konnte nicht bestimmt werden")
        except Exception as e:
            messagebox.showerror("Fehler", f"{schedule_type}-Plan konnte nicht gedruckt werden: {str(e)}")

    def open_pdf(self, filepath):
        """Open the generated PDF file with the default system viewer"""
        try:
            if os.name == 'nt':  # Windows
                os.startfile(filepath)
            elif os.name == 'posix':  # macOS and Linux
                if os.system('which open') == 0:  # macOS
                    os.system(f'open "{filepath}"')
                else:  # Linux
                    os.system(f'xdg-open "{filepath}"')
        except Exception as e:
            messagebox.showwarning("Warnung", f"PDF wurde erstellt, konnte aber nicht automatisch geöffnet werden: {filepath}")

    def refresh_all_tables(self):
        """Comprehensive refresh of all UI components with delays between refreshes"""
        # Disable the refresh button temporarily
        if hasattr(self, 'refresh_button'):
            self.refresh_button.config(state='disabled')
            
        # Refresh views with small delays between each to reduce UI load
        if hasattr(self, 'delivery_view'):
            self.delivery_view.refresh()
            
        # Schedule other views to refresh with delays
        def refresh_production():
            if hasattr(self, 'production_view'):
                self.production_view.refresh()
                
        def refresh_transfer():
            if hasattr(self, 'transfer_view'):
                self.transfer_view.refresh()
                
        def refresh_other_tabs():
            if hasattr(self, 'customer_view'):
                self.customer_view.refresh_customer_list()
            if hasattr(self, 'item_view'):
                self.item_view.refresh_item_list()
            # Re-enable the refresh button
            if hasattr(self, 'refresh_button'):
                self.refresh_button.config(state='normal')
        
        # Schedule refreshes with delays between each
        self.after(100, refresh_production)
        self.after(200, refresh_transfer)
        self.after(300, refresh_other_tabs)

if __name__ == "__main__":
    check_for_updates()
    app = ProductionApp()
    app.mainloop()