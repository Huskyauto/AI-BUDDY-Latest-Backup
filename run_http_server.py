"""
HTTP Server Startup Script for AI-BUDDY

This script runs the Flask application using HTTP, primarily for development purposes
when testing features in environments that cannot access HTTPS with self-signed certificates.

IMPORTANT: The primary/production server should use HTTPS with valid SSL certificates.
"""

from app import app
import logging
import sys
from extensions import db

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("flask_app_http.log")
    ]
)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize database connection and tables"""
    try:
        with app.app_context():
            # Test database connection
            db.engine.connect()
            logger.info("Database connection successful")

            # Import models here to ensure they're registered
            import models  # noqa: F401

            # Create/verify tables
            db.create_all()
            logger.info("Database tables verified")
            return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    """
    Simple, direct server startup script with HTTP only for testing
    """
    # Initialize database
    if not init_db():
        logger.error("Failed to initialize database, exiting.")
        sys.exit(1)
    
    logger.info("Database initialized successfully. Starting Flask server directly...")
    
    # Run the Flask app directly with explicit host binding to ensure external access
    logger.info("Starting server with HTTP only on port 8080")
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)