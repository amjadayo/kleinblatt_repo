import tkinter as tk
from tkinter import ttk, messagebox
from widgets import AutocompleteCombobox
from models import Item, OrderItem
from datetime import datetime, timedelta

class ItemView:
    def __init__(self, parent, app=None):
        self.parent = parent
        self.app = app  # Store reference to main app for undo system
        self.edit_mode = False
        self.current_item = None
        self.create_widgets()
        self.refresh_item_list()

    def create_widgets(self):
        # Input frame
        input_frame = ttk.LabelFrame(self.parent, text="Artikeldetails")
        input_frame.pack(fill='x', padx=10, pady=5)

        # Grid layout for item details
        # Name with autocomplete
        ttk.Label(input_frame, text="Name:").grid(row=0, column=0, padx=5, pady=5)
        self.name_entry = AutocompleteCombobox(input_frame)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)

        # Seed quantity
        ttk.Label(input_frame, text="Saatgutmenge (g):").grid(row=1, column=0, padx=5, pady=5)
        self.seed_qty_entry = ttk.Entry(input_frame)
        self.seed_qty_entry.grid(row=1, column=1, padx=5, pady=5)

        # Days inputs
        ttk.Label(input_frame, text="Einweichtage:").grid(row=2, column=0, padx=5, pady=5)
        self.soaking_days_entry = ttk.Entry(input_frame)
        self.soaking_days_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(input_frame, text="Keimungstage:").grid(row=3, column=0, padx=5, pady=5)
        self.germination_days_entry = ttk.Entry(input_frame)
        self.germination_days_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(input_frame, text="Wachstumstage:").grid(row=4, column=0, padx=5, pady=5)
        self.growth_days_entry = ttk.Entry(input_frame)
        self.growth_days_entry.grid(row=4, column=1, padx=5, pady=5)

        # Price
        ttk.Label(input_frame, text="Preis:").grid(row=5, column=0, padx=5, pady=5)
        self.price_entry = ttk.Entry(input_frame)
        self.price_entry.grid(row=5, column=1, padx=5, pady=5)

        # Substrate
        ttk.Label(input_frame, text="Substrat:").grid(row=6, column=0, padx=5, pady=5)
        self.substrate_entry = ttk.Entry(input_frame)
        self.substrate_entry.grid(row=6, column=1, padx=5, pady=5)

        # Buttons
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=10)

        self.save_btn = ttk.Button(btn_frame, text="Speichern", command=self.save_item)
        self.save_btn.pack(side='left', padx=5)

        self.cancel_btn = ttk.Button(btn_frame, text="Abbrechen", command=self.cancel_edit)
        self.cancel_btn.pack(side='left', padx=5)
        self.cancel_btn.pack_forget()  # Hidden by default

        # Item list
        list_frame = ttk.LabelFrame(self.parent, text="Artikelliste")
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Treeview for item list
        self.tree = ttk.Treeview(list_frame, columns=(
            'ID', 'Name', 'Saatgutmenge', 'Einweichen', 'Keimung', 
            'Wachstum', 'Preis', 'Substrat'), show='headings')
        
        # Configure column headings
        self.tree.heading('ID', text='ID')
        self.tree.heading('Name', text='Name')
        self.tree.heading('Saatgutmenge', text='Saatgutmenge (g)')
        self.tree.heading('Einweichen', text='Einweichtage')
        self.tree.heading('Keimung', text='Keimungstage')
        self.tree.heading('Wachstum', text='Wachstumstage')
        self.tree.heading('Preis', text='Preis')
        self.tree.heading('Substrat', text='Substrat')

        # Configure column widths
        self.tree.column('ID', width=50)
        self.tree.column('Name', width=150)
        self.tree.column('Saatgutmenge', width=100)
        self.tree.column('Einweichen', width=100)
        self.tree.column('Keimung', width=100)
        self.tree.column('Wachstum', width=100)
        self.tree.column('Preis', width=100)
        self.tree.column('Substrat', width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # Action buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Bearbeiten", command=self.edit_item).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Löschen", command=self.delete_item).pack(side='left', padx=5)

    def refresh_item_list(self):
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Fetch and display items
        items = Item.select()
        for item in items:
            self.tree.insert('', 'end', values=(
                item.id, 
                item.name,
                f"{item.seed_quantity:.1f}",
                item.soaking_days,
                item.germination_days,
                item.growth_days,
                f"{item.price:.2f}",
                item.substrate or ""
            ))

        # Update autocomplete list
        self.name_entry.set_completion_list([item.name for item in items])

    def save_item(self):
        # Validate inputs
        try:
            name = self.name_entry.get().strip()
            seed_qty = float(self.seed_qty_entry.get())
            soaking_days = int(self.soaking_days_entry.get())
            germination_days = int(self.germination_days_entry.get())
            growth_days = int(self.growth_days_entry.get())
            price = float(self.price_entry.get())
            substrate = self.substrate_entry.get().strip()

            if not name:
                raise ValueError("Bitte geben Sie einen Artikelnamen ein")

        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        try:
            if self.edit_mode and self.current_item:
                # Store original data for undo
                original_data = {
                    'item_id': self.current_item.id,
                    'name': self.current_item.name,
                    'seed_quantity': self.current_item.seed_quantity,
                    'soaking_days': self.current_item.soaking_days,
                    'germination_days': self.current_item.germination_days,
                    'growth_days': self.current_item.growth_days,
                    'price': self.current_item.price,
                    'substrate': self.current_item.substrate
                }
                
                # Update existing item
                self.current_item.name = name
                self.current_item.seed_quantity = seed_qty
                self.current_item.soaking_days = soaking_days
                self.current_item.germination_days = germination_days
                self.current_item.growth_days = growth_days
                self.current_item.price = price
                self.current_item.substrate = substrate
                self.current_item.save()
                
                # Record action for undo if app reference exists
                if self.app:
                    self.app.record_action(
                        "edit_item",
                        original_data,
                        {'item_id': self.current_item.id},
                        f"Änderung von Artikel: {name}"
                    )
                
                messagebox.showinfo("Erfolg", "Artikel erfolgreich aktualisiert")
                    # — recompute production & transfer dates for all existing orders of this item —
                for oi in OrderItem.select().where(OrderItem.item == self.current_item):
                    total_days      = self.current_item.germination_days + self.current_item.growth_days
                    prod_dt         = oi.order.delivery_date - timedelta(days=total_days)
                    trans_dt        = prod_dt + timedelta(days=self.current_item.germination_days)
                    oi.production_date = prod_dt
                    oi.transfer_date   = trans_dt
                    oi.save()

                # — reload in-memory lookups and redraw all 3 weekly tabs —
                if self.app:
                    self.app.load_data()
                    self.app.refresh_tables()

            else:
                # Create new item
                item = Item.create(
                    name=name,
                    seed_quantity=seed_qty,
                    soaking_days=soaking_days,
                    germination_days=germination_days,
                    growth_days=growth_days,
                    price=price,
                    substrate=substrate
                )
                
                # Record action for undo if app reference exists
                if self.app:
                    self.app.record_action(
                        "create_item",
                        None,  # No old data for creation
                        {'item_id': item.id},
                        f"Erstellung von Artikel: {name}"
                    )
                
                messagebox.showinfo("Erfolg", "Artikel erfolgreich hinzugefügt")

            self.cancel_edit()
            self.refresh_item_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def edit_item(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Warnung", "Bitte wählen Sie einen Artikel zum Bearbeiten aus")
            return

        # Get item ID from selected item
        item_id = self.tree.item(selected_item[0])['values'][0]
        self.current_item = Item.get_by_id(item_id)

        # Populate form with current values
        self.name_entry.set(self.current_item.name)
        self.seed_qty_entry.delete(0, tk.END)
        self.seed_qty_entry.insert(0, str(self.current_item.seed_quantity))
        self.soaking_days_entry.delete(0, tk.END)
        self.soaking_days_entry.insert(0, str(self.current_item.soaking_days))
        self.germination_days_entry.delete(0, tk.END)
        self.germination_days_entry.insert(0, str(self.current_item.germination_days))
        self.growth_days_entry.delete(0, tk.END)
        self.growth_days_entry.insert(0, str(self.current_item.growth_days))
        self.price_entry.delete(0, tk.END)
        self.price_entry.insert(0, str(self.current_item.price))
        self.substrate_entry.delete(0, tk.END)
        self.substrate_entry.insert(0, self.current_item.substrate or "")

        # Set edit mode
        self.edit_mode = True
        self.save_btn.configure(text="Aktualisieren")
        self.cancel_btn.pack(side='left', padx=5)

    def cancel_edit(self):
        self.edit_mode = False
        self.current_item = None
        
        # Clear all entries
        self.name_entry.set('')
        self.seed_qty_entry.delete(0, tk.END)
        self.soaking_days_entry.delete(0, tk.END)
        self.germination_days_entry.delete(0, tk.END)
        self.growth_days_entry.delete(0, tk.END)
        self.price_entry.delete(0, tk.END)
        self.substrate_entry.delete(0, tk.END)
        
        self.save_btn.configure(text="Speichern")
        self.cancel_btn.pack_forget()

    def delete_item(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Warnung", "Bitte wählen Sie einen Artikel zum Löschen aus")
            return

        if messagebox.askyesno("Bestätigung", "Sind Sie sicher, dass Sie diesen Artikel löschen möchten?"):
            item_id = self.tree.item(selected_item[0])['values'][0]
            item = Item.get_by_id(item_id)
            
            # Store original data for undo
            original_data = {
                'item_id': item.id,
                'name': item.name,
                'seed_quantity': item.seed_quantity,
                'soaking_days': item.soaking_days,
                'germination_days': item.germination_days,
                'growth_days': item.growth_days,
                'price': item.price,
                'substrate': item.substrate
            }
            
            item.delete_instance()
            
            # Record action for undo if app reference exists
            if self.app:
                self.app.record_action(
                    "delete_item",
                    original_data,
                    None,
                    f"Löschung von Artikel: {item.name}"
                )
            
            self.refresh_item_list()