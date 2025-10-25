"""
API routes for the SmartSOP ELN application.
This package contains all the API routes for the application.
"""

from .project_routes import project_bp
from .experiment_routes import experiment_bp
from .protocol_routes import protocol_bp
from .inventory_routes import inventory_bp
from .user_routes import user_bp

def register_api_routes(app):
    """Register all API routes with the Flask application."""
    app.register_blueprint(project_bp)
    app.register_blueprint(experiment_bp)
    app.register_blueprint(protocol_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(user_bp)
