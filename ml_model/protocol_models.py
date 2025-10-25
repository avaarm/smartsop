from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean, ForeignKey, Enum, JSON, Table, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from datetime import datetime
from .database import Base
from .models import generate_uuid, User, Experiment

# Protocol-related models for ELN
class Protocol(Base):
    __tablename__ = "protocols"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, index=True)
    description = Column(Text)
    version = Column(String)
    content = Column(Text)  # Rich text format
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String, ForeignKey("users.id"))
    is_template = Column(Boolean, default=False)
    category = Column(String)
    
    # Relationships
    steps = relationship("ProtocolStep", back_populates="protocol", cascade="all, delete-orphan")
    experiment_protocols = relationship("ExperimentProtocol", back_populates="protocol")
    created_by_user = relationship("User")

class ProtocolStep(Base):
    __tablename__ = "protocol_steps"

    id = Column(String, primary_key=True, default=generate_uuid)
    protocol_id = Column(String, ForeignKey("protocols.id"))
    step_number = Column(Integer)
    title = Column(String)
    description = Column(Text)
    expected_duration = Column(Integer)  # minutes
    warnings = Column(Text, nullable=True)
    image_urls = Column(JSON)  # Array of image URLs
    
    # Relationships
    protocol = relationship("Protocol", back_populates="steps")

class ExperimentProtocol(Base):
    __tablename__ = "experiment_protocols"

    id = Column(String, primary_key=True, default=generate_uuid)
    experiment_id = Column(String, ForeignKey("experiments.id"))
    protocol_id = Column(String, ForeignKey("protocols.id"))
    execution_date = Column(DateTime, nullable=True)
    executed_by = Column(String, ForeignKey("users.id"), nullable=True)
    status = Column(String)  # planned, in_progress, completed
    notes = Column(Text, nullable=True)
    
    # Relationships
    experiment = relationship("Experiment", back_populates="experiment_protocols")
    protocol = relationship("Protocol", back_populates="experiment_protocols")
    executed_by_user = relationship("User")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(String, primary_key=True, default=generate_uuid)
    content = Column(Text)
    entity_type = Column(String)  # project, experiment, task, protocol
    entity_id = Column(String)
    created_at = Column(DateTime, default=func.now())
    created_by = Column(String, ForeignKey("users.id"))
    parent_comment_id = Column(String, ForeignKey("comments.id"), nullable=True)
    
    # Relationships
    created_by_user = relationship("User")
    replies = relationship("Comment", 
                          backref=relationship("Comment", remote_side=[id]),
                          cascade="all, delete-orphan")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    action = Column(String)
    entity_type = Column(String)
    entity_id = Column(String)
    user_id = Column(String, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=func.now())
    details = Column(JSON)
    ip_address = Column(String)
    
    # Relationships
    user = relationship("User")

class ElectronicSignature(Base):
    __tablename__ = "electronic_signatures"

    id = Column(String, primary_key=True, default=generate_uuid)
    entity_type = Column(String)  # project, experiment, protocol
    entity_id = Column(String)
    signed_by = Column(String, ForeignKey("users.id"))
    signed_at = Column(DateTime, default=func.now())
    signature_type = Column(String)  # approval, review, witness
    reason = Column(String)
    ip_address = Column(String)
    
    # Relationships
    signed_by_user = relationship("User")
