from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from datetime import datetime
from .database import Base

# Generate UUID as string for IDs
def generate_uuid():
    return str(uuid.uuid4())

# Enum classes for status fields
class ProjectStatus(enum.Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class ExperimentStatus(enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskStatus(enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

# Core models for ELN
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    role = Column(String)
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)

    # Relationships
    projects = relationship("Project", back_populates="created_by_user")
    experiments = relationship("Experiment", back_populates="created_by_user")
    tasks = relationship("Task", back_populates="assigned_to_user")
    team_memberships = relationship("TeamMember", back_populates="user")

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, index=True)
    description = Column(Text)
    objectives = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String, ForeignKey("users.id"))
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PLANNED)
    project_metadata = Column(JSON, default={})

    # Relationships
    created_by_user = relationship("User", back_populates="projects")
    experiments = relationship("Experiment", back_populates="project", cascade="all, delete-orphan")
    team_members = relationship("TeamMember", back_populates="project", cascade="all, delete-orphan")

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"))
    title = Column(String, index=True)
    hypothesis = Column(Text)
    expected_outcome = Column(Text)
    status = Column(Enum(ExperimentStatus), default=ExperimentStatus.PLANNED)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String, ForeignKey("users.id"))
    experiment_metadata = Column(JSON, default={})

    # Relationships
    project = relationship("Project", back_populates="experiments")
    created_by_user = relationship("User", back_populates="experiments")
    tasks = relationship("Task", back_populates="experiment", cascade="all, delete-orphan")
    experiment_data = relationship("ExperimentData", back_populates="experiment", cascade="all, delete-orphan")
    experiment_protocols = relationship("ExperimentProtocol", back_populates="experiment", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=generate_uuid)
    experiment_id = Column(String, ForeignKey("experiments.id"))
    title = Column(String, index=True)
    description = Column(Text)
    status = Column(Enum(TaskStatus), default=TaskStatus.NOT_STARTED)
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String, ForeignKey("users.id"))
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)

    # Relationships
    experiment = relationship("Experiment", back_populates="tasks")
    assigned_to_user = relationship("User", back_populates="tasks")

class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    project_id = Column(String, ForeignKey("projects.id"))
    role = Column(String)  # owner, manager, contributor, viewer
    joined_at = Column(DateTime, default=func.now())
    invited_by = Column(String, ForeignKey("users.id"))

    # Relationships
    user = relationship("User", back_populates="team_memberships")
    project = relationship("Project", back_populates="team_members")

class ExperimentData(Base):
    __tablename__ = "experiment_data"

    id = Column(String, primary_key=True, default=generate_uuid)
    experiment_id = Column(String, ForeignKey("experiments.id"))
    title = Column(String)
    data_type = Column(String)  # numeric, text, image, file
    value = Column(JSON)
    unit = Column(String, nullable=True)
    timestamp = Column(DateTime, default=func.now())
    created_by = Column(String, ForeignKey("users.id"))
    data_metadata = Column(JSON, default={})

    # Relationships
    experiment = relationship("Experiment", back_populates="experiment_data")
