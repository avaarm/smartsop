from database import engine
from models import Base as ModelsBase
from protocol_models import Base as ProtocolBase
from inventory_models import Base as InventoryBase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database by creating all tables."""
    logger.info("Creating database tables...")
    
    # Create tables from all model files
    ModelsBase.metadata.create_all(bind=engine)
    ProtocolBase.metadata.create_all(bind=engine)
    InventoryBase.metadata.create_all(bind=engine)
    
    logger.info("Database tables created successfully!")

if __name__ == "__main__":
    init_db()
