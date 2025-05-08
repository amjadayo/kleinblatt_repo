from peewee import (
    SqliteDatabase, Model, CharField, DateTimeField, 
    FloatField, IntegerField, ForeignKeyField, 
    DateField, BooleanField, UUIDField
)
from datetime import datetime, timedelta

db = SqliteDatabase('production.db')

class BaseModel(Model):
    class Meta:
        database = db

class Customer(BaseModel):
    name = CharField(unique=True)
    created_at = DateTimeField(default=datetime.now)

class Item(BaseModel):
    name = CharField(unique=True)
    seed_quantity = FloatField()
    soaking_days = IntegerField()
    germination_days = IntegerField()
    growth_days = IntegerField()
    price = FloatField()
    substrate = CharField(null=True)
    
    @property
    def total_days(self):
        return self.germination_days + self.growth_days

class Order(BaseModel):
    customer = ForeignKeyField(Customer, backref='orders')
    delivery_date = DateField()
    from_date = DateField(null=True)
    to_date = DateField(null=True)
    subscription_type = IntegerField(default=0)  # 0=none, 1=weekly, 2=biweekly, 3=every 3 weeks, 4=every 4 weeks
    halbe_channel = BooleanField(default=False)
    order_id = UUIDField(unique=True)
    is_future = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)
    
    @property
    def total_price(self):
        return sum(item.total_price for item in self.order_items)

    @property
    def items(self):
        return self.order_item

    @property
    def order_item(self):
        return self.order_items

class OrderItem(BaseModel):
    order = ForeignKeyField(Order, backref='order_items', on_delete='CASCADE')
    item = ForeignKeyField(Item)
    amount = FloatField()
    production_date = DateField()
    transfer_date = DateField(null=True)

    
    @property
    def total_price(self):
        return self.amount * self.item.price

def create_tables():
    with db:
        db.create_tables([Customer, Item, Order, OrderItem])
