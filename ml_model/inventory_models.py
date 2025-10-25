from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from .database import Base
from .models import generate_uuid, User, Experiment

# Inventory-related models for ELN
class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, index=True)
    category = Column(String, index=True)
    description = Column(Text)
    location = Column(String)
    quantity = Column(Float)
    unit = Column(String)
    barcode = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    expiry_date = Column(DateTime, nullable=True)
    min_quantity = Column(Float, default=0)
    item_metadata = Column(JSON, default={})
    
    # Relationships
    usages = relationship("InventoryUsage", back_populates="item")

class InventoryUsage(Base):
    __tablename__ = "inventory_usage"

    id = Column(String, primary_key=True, default=generate_uuid)
    item_id = Column(String, ForeignKey("inventory_items.id"))
    experiment_id = Column(String, ForeignKey("experiments.id"))
    quantity = Column(Float)
    used_by = Column(String, ForeignKey("users.id"))
    used_at = Column(DateTime, default=func.now())
    notes = Column(Text, nullable=True)
    
    # Relationships
    item = relationship("InventoryItem", back_populates="usages")
    experiment = relationship("Experiment")
    user = relationship("User")

class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(String, primary_key=True, default=generate_uuid)
    item_id = Column(String, ForeignKey("inventory_items.id"))
    transaction_type = Column(String)  # restock, consume, adjust
    quantity = Column(Float)
    previous_quantity = Column(Float)
    new_quantity = Column(Float)
    transaction_date = Column(DateTime, default=func.now())
    performed_by = Column(String, ForeignKey("users.id"))
    notes = Column(Text, nullable=True)
    
    # Relationships
    item = relationship("InventoryItem")
    user = relationship("User")

class InventoryAlert(Base):
    __tablename__ = "inventory_alerts"

    id = Column(String, primary_key=True, default=generate_uuid)
    item_id = Column(String, ForeignKey("inventory_items.id"))
    alert_type = Column(String)  # low_stock, expired, expiring_soon
    message = Column(Text)
    created_at = Column(DateTime, default=func.now())
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    item = relationship("InventoryItem")
    resolver = relationship("User")
