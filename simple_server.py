from app import app
import logging
import sys
import os
from extensions import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
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
    """Simple HTTP-only server for Replit preview"""
    
    # Initialize database
    if not init_db():
        logger.error("Failed to initialize database, exiting.")
        sys.exit(1)
    
    logger.info("Database initialized successfully. Starting simple HTTP server...")
    
    # Always use HTTP on port 5000 for Replit preview compatibility
    port = 5000
    logger.info(f"Starting HTTP server on port {port} for preview")
    
    # Run the Flask app with HTTP only (no SSL)
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)