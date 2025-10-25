from sqlalchemy.orm import scoped_session
from .database import SessionLocal, engine

# Create a scoped session for Flask requests
db_session = scoped_session(SessionLocal)

# Function to initialize database session for Flask
def init_db_session(app):
    """Initialize database session for Flask application."""
    
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Remove the database session at the end of the request."""
        db_session.remove()
        
    return db_session
