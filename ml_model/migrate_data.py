import os
import json
import logging
from datetime import datetime
import hashlib
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import User, Project, Experiment, Task, ExperimentData
from protocol_models import Protocol, ProtocolStep, ExperimentProtocol, AuditLog
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
COLLECTED_DATA_DIR = "collected_data"
SOP_DIR = os.path.join(COLLECTED_DATA_DIR, "sops")
BATCH_RECORD_DIR = os.path.join(COLLECTED_DATA_DIR, "batch_records")

def generate_password_hash(password):
    """Generate a simple password hash (for demo purposes only)."""
    return hashlib.sha256(password.encode()).hexdigest()

def create_default_user(db: Session):
    """Create a default admin user if no users exist."""
    user = db.query(User).first()
    if not user:
        admin_user = User(
            id=str(uuid.uuid4()),
            username="admin",
            email="admin@example.com",
            password_hash=generate_password_hash("admin"),
            first_name="Admin",
            last_name="User",
            role="admin",
            created_at=datetime.now(),
            last_login=datetime.now()
        )
        db.add(admin_user)
        db.commit()
        logger.info(f"Created default admin user: {admin_user.username}")
        return admin_user
    return user

def migrate_sop_data(db: Session, admin_user: User):
    """Migrate SOP data from JSON files to the new database structure."""
    # Create a default project for migrated SOPs
    default_project = Project(
        id=str(uuid.uuid4()),
        title="Migrated SOPs",
        description="Project containing SOPs migrated from the previous system",
        objectives="Maintain historical SOP data",
        created_by=admin_user.id,
        status="active",
        metadata={"migrated": True, "migration_date": datetime.now().isoformat()}
    )
    db.add(default_project)
    db.commit()
    logger.info(f"Created default project: {default_project.title}")

    # Process SOP files
    sop_count = 0
    if os.path.exists(SOP_DIR):
        for filename in os.listdir(SOP_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(SOP_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        sop_data = json.load(f)
                    
                    # Extract data from the SOP JSON
                    timestamp = sop_data.get('timestamp', '')
                    input_data = sop_data.get('input', {})
                    generated_content = sop_data.get('generated_content', '')
                    metadata = sop_data.get('metadata', {})
                    feedback = sop_data.get('feedback', {})
                    
                    # Create an experiment for this SOP
                    sop_title = input_data.get('title', f"SOP {timestamp}")
                    experiment = Experiment(
                        id=str(uuid.uuid4()),
                        project_id=default_project.id,
                        title=sop_title,
                        hypothesis="",  # SOPs don't have hypotheses
                        expected_outcome="",
                        status="completed",
                        start_date=datetime.strptime(timestamp, "%Y%m%d_%H%M%S") if timestamp else datetime.now(),
                        end_date=datetime.strptime(timestamp, "%Y%m%d_%H%M%S") if timestamp else datetime.now(),
                        created_by=admin_user.id,
                        metadata={
                            "migrated": True,
                            "original_file": filename,
                            "original_metadata": metadata
                        }
                    )
                    db.add(experiment)
                    db.commit()
                    
                    # Create a protocol from the SOP content
                    protocol = Protocol(
                        id=str(uuid.uuid4()),
                        title=sop_title,
                        description=input_data.get('description', ''),
                        version="1.0",
                        content=generated_content,
                        created_by=admin_user.id,
                        is_template=True,
                        category="SOP"
                    )
                    db.add(protocol)
                    db.commit()
                    
                    # Link the protocol to the experiment
                    experiment_protocol = ExperimentProtocol(
                        id=str(uuid.uuid4()),
                        experiment_id=experiment.id,
                        protocol_id=protocol.id,
                        execution_date=datetime.strptime(timestamp, "%Y%m%d_%H%M%S") if timestamp else datetime.now(),
                        executed_by=admin_user.id,
                        status="completed",
                        notes=""
                    )
                    db.add(experiment_protocol)
                    
                    # Store the original input data as experiment data
                    for key, value in input_data.items():
                        if key != 'title':  # Title is already used for the experiment name
                            experiment_data = ExperimentData(
                                id=str(uuid.uuid4()),
                                experiment_id=experiment.id,
                                title=key,
                                data_type="text",
                                value={"text": value},
                                created_by=admin_user.id
                            )
                            db.add(experiment_data)
                    
                    # If there's feedback, store it as experiment data
                    if feedback:
                        feedback_data = ExperimentData(
                            id=str(uuid.uuid4()),
                            experiment_id=experiment.id,
                            title="Feedback",
                            data_type="text",
                            value={
                                "score": feedback.get('score', 0),
                                "text": feedback.get('text', ''),
                                "timestamp": feedback.get('timestamp', '')
                            },
                            created_by=admin_user.id
                        )
                        db.add(feedback_data)
                    
                    # Create an audit log entry for this migration
                    audit_log = AuditLog(
                        id=str(uuid.uuid4()),
                        action="data_migration",
                        entity_type="experiment",
                        entity_id=experiment.id,
                        user_id=admin_user.id,
                        details={
                            "original_file": filename,
                            "migration_date": datetime.now().isoformat()
                        },
                        ip_address="127.0.0.1"  # Local migration
                    )
                    db.add(audit_log)
                    
                    db.commit()
                    sop_count += 1
                    
                except Exception as e:
                    db.rollback()
                    logger.error(f"Error migrating SOP file {filename}: {str(e)}")
    
    logger.info(f"Migrated {sop_count} SOP files to the new database structure")
    return sop_count

def migrate_batch_record_data(db: Session, admin_user: User):
    """Migrate batch record data from JSON files to the new database structure."""
    # Create a default project for migrated batch records
    default_project = Project(
        id=str(uuid.uuid4()),
        title="Migrated Batch Records",
        description="Project containing batch records migrated from the previous system",
        objectives="Maintain historical batch record data",
        created_by=admin_user.id,
        status="active",
        metadata={"migrated": True, "migration_date": datetime.now().isoformat()}
    )
    db.add(default_project)
    db.commit()
    logger.info(f"Created default project: {default_project.title}")

    # Process batch record files
    record_count = 0
    if os.path.exists(BATCH_RECORD_DIR):
        for filename in os.listdir(BATCH_RECORD_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(BATCH_RECORD_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        record_data = json.load(f)
                    
                    # Extract data from the batch record JSON
                    timestamp = record_data.get('timestamp', '')
                    input_data = record_data.get('input', {})
                    generated_content = record_data.get('generated_content', '')
                    metadata = record_data.get('metadata', {})
                    feedback = record_data.get('feedback', {})
                    
                    # Create an experiment for this batch record
                    record_title = input_data.get('title', f"Batch Record {timestamp}")
                    experiment = Experiment(
                        id=str(uuid.uuid4()),
                        project_id=default_project.id,
                        title=record_title,
                        hypothesis="",
                        expected_outcome="",
                        status="completed",
                        start_date=datetime.strptime(timestamp, "%Y%m%d_%H%M%S") if timestamp else datetime.now(),
                        end_date=datetime.strptime(timestamp, "%Y%m%d_%H%M%S") if timestamp else datetime.now(),
                        created_by=admin_user.id,
                        metadata={
                            "migrated": True,
                            "original_file": filename,
                            "original_metadata": metadata
                        }
                    )
                    db.add(experiment)
                    db.commit()
                    
                    # Create a protocol from the batch record content
                    protocol = Protocol(
                        id=str(uuid.uuid4()),
                        title=record_title,
                        description=input_data.get('description', ''),
                        version="1.0",
                        content=generated_content,
                        created_by=admin_user.id,
                        is_template=True,
                        category="Batch Record"
                    )
                    db.add(protocol)
                    db.commit()
                    
                    # Link the protocol to the experiment
                    experiment_protocol = ExperimentProtocol(
                        id=str(uuid.uuid4()),
                        experiment_id=experiment.id,
                        protocol_id=protocol.id,
                        execution_date=datetime.strptime(timestamp, "%Y%m%d_%H%M%S") if timestamp else datetime.now(),
                        executed_by=admin_user.id,
                        status="completed",
                        notes=""
                    )
                    db.add(experiment_protocol)
                    
                    # Store the original input data as experiment data
                    for key, value in input_data.items():
                        if key != 'title':  # Title is already used for the experiment name
                            experiment_data = ExperimentData(
                                id=str(uuid.uuid4()),
                                experiment_id=experiment.id,
                                title=key,
                                data_type="text",
                                value={"text": value},
                                created_by=admin_user.id
                            )
                            db.add(experiment_data)
                    
                    # If there's feedback, store it as experiment data
                    if feedback:
                        feedback_data = ExperimentData(
                            id=str(uuid.uuid4()),
                            experiment_id=experiment.id,
                            title="Feedback",
                            data_type="text",
                            value={
                                "score": feedback.get('score', 0),
                                "text": feedback.get('text', ''),
                                "timestamp": feedback.get('timestamp', '')
                            },
                            created_by=admin_user.id
                        )
                        db.add(feedback_data)
                    
                    # Create an audit log entry for this migration
                    audit_log = AuditLog(
                        id=str(uuid.uuid4()),
                        action="data_migration",
                        entity_type="experiment",
                        entity_id=experiment.id,
                        user_id=admin_user.id,
                        details={
                            "original_file": filename,
                            "migration_date": datetime.now().isoformat()
                        },
                        ip_address="127.0.0.1"  # Local migration
                    )
                    db.add(audit_log)
                    
                    db.commit()
                    record_count += 1
                    
                except Exception as e:
                    db.rollback()
                    logger.error(f"Error migrating batch record file {filename}: {str(e)}")
    
    logger.info(f"Migrated {record_count} batch record files to the new database structure")
    return record_count

def run_migration():
    """Run the complete data migration process."""
    logger.info("Starting data migration process...")
    
    # Create a database session
    db = SessionLocal()
    
    try:
        # Create a default admin user
        admin_user = create_default_user(db)
        
        # Migrate SOP data
        sop_count = migrate_sop_data(db, admin_user)
        
        # Migrate batch record data
        record_count = migrate_batch_record_data(db, admin_user)
        
        logger.info(f"Data migration completed successfully!")
        logger.info(f"Migrated {sop_count} SOPs and {record_count} batch records")
        
    except Exception as e:
        logger.error(f"Error during data migration: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
