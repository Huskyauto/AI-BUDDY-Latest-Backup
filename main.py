from app import app
import logging
import sys
import os
from extensions import db

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("flask_app.log")
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

def get_ssl_context():
    """Get SSL context for production or development"""
    ssl_dir = "ssl_certificates"
    cert_file = os.path.join(ssl_dir, "ai-buddy.dev.crt")
    key_file = os.path.join(ssl_dir, "ai-buddy.dev.key")
    
    # Check if SSL certificates exist
    if os.path.exists(cert_file) and os.path.exists(key_file):
        logger.info(f"Found SSL certificates: {cert_file}, {key_file}")
        return (cert_file, key_file)
    else:
        logger.warning("SSL certificates not found, using HTTP only")
        return None

if __name__ == "__main__":
    """
    Simple, direct server startup script with improved reliability
    """
    # Initialize database
    if not init_db():
        logger.error("Failed to initialize database, exiting.")
        sys.exit(1)
    
    logger.info("Database initialized successfully. Starting Flask server directly...")
    
    # Get port from environment variable if available, otherwise use default 5000
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")
    
    # Force HTTP mode for preview compatibility
    logger.info(f"Starting server with HTTP only on port {port} for preview compatibility")
    # Run the Flask app without SSL
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)