from sqlalchemy import String, Integer, Float, Text, ForeignKey, DateTime, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from .database import Base
class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(100))
    email: Mapped[str]=mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    membership_tier: Mapped[str]=mapped_column(String(30), default="Basic")
    preferences: Mapped[dict]=mapped_column(JSON, default=dict)
class Category(Base):
    __tablename__="categories"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(80), unique=True)
class Product(Base):
    __tablename__="products"
    id: Mapped[str]=mapped_column(String(30), primary_key=True)
    name: Mapped[str]=mapped_column(String(200), index=True)
    category_id: Mapped[int]=mapped_column(ForeignKey("categories.id"))
    brand: Mapped[str]=mapped_column(String(80), index=True)
    description: Mapped[str]=mapped_column(Text)
    price: Mapped[float]=mapped_column(Float)
    rating: Mapped[float]=mapped_column(Float, default=4.0)
    stock: Mapped[int]=mapped_column(Integer, default=0)
    image_url: Mapped[str]=mapped_column(Text)
    specs: Mapped[dict]=mapped_column(JSON, default=dict)
    category: Mapped[Category]=relationship()
class CartItem(Base):
    __tablename__="cart_items"; __table_args__=(UniqueConstraint("user_id","product_id"),)
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"))
    product_id: Mapped[str]=mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int]=mapped_column(Integer, default=1)
class WishlistItem(Base):
    __tablename__="wishlist_items"; __table_args__=(UniqueConstraint("user_id","product_id"),)
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"))
    product_id: Mapped[str]=mapped_column(ForeignKey("products.id"))
class Order(Base):
    __tablename__="orders"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"))
    total: Mapped[float]=mapped_column(Float)
    status: Mapped[str]=mapped_column(String(40), default="Confirmed")
    delivery_type: Mapped[str]=mapped_column(String(40), default="Standard")
    created_at: Mapped[datetime]=mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    items: Mapped[list["OrderItem"]]=relationship(cascade="all, delete-orphan")
    events: Mapped[list["ShipmentEvent"]]=relationship(cascade="all, delete-orphan", order_by="ShipmentEvent.timestamp")
class OrderItem(Base):
    __tablename__="order_items"
    id: Mapped[int]=mapped_column(primary_key=True)
    order_id: Mapped[int]=mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[str]=mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int]=mapped_column(Integer)
    price: Mapped[float]=mapped_column(Float)
    product: Mapped[Product]=relationship()
class ShipmentEvent(Base):
    __tablename__="shipment_events"
    id: Mapped[int]=mapped_column(primary_key=True)
    order_id: Mapped[int]=mapped_column(ForeignKey("orders.id"))
    status: Mapped[str]=mapped_column(String(80))
    timestamp: Mapped[datetime]=mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
class Document(Base):
    __tablename__="documents"
    id: Mapped[int]=mapped_column(primary_key=True)
    title: Mapped[str]=mapped_column(String(200))
    doc_type: Mapped[str]=mapped_column(String(50), default="policy")
    version: Mapped[str]=mapped_column(String(30), default="2026.1")
    effective_date: Mapped[str]=mapped_column(String(30), default="2026-01-01")
    category: Mapped[str]=mapped_column(String(80), default="General")
    region: Mapped[str]=mapped_column(String(80), default="Global")
    chunk_count: Mapped[int]=mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime]=mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
class AILog(Base):
    __tablename__="ai_logs"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int|None]=mapped_column(Integer, nullable=True)
    endpoint: Mapped[str]=mapped_column(String(80))
    query: Mapped[str]=mapped_column(Text)
    response_json: Mapped[dict]=mapped_column(JSON, default=dict)
    sources_json: Mapped[list]=mapped_column(JSON, default=list)
    latency_ms: Mapped[int]=mapped_column(Integer, default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
