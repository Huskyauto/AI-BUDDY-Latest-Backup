import logging
import os
from datetime import datetime
from flask import Flask
from sqlalchemy import text
from flask_sqlalchemy import SQLAlchemy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_fork():
    """Verify fork functionality"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Starting fork verification at {timestamp}")
    
    # Create Flask app and configure database
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    db = SQLAlchemy()
    db.init_app(app)
    
    try:
        with app.app_context():
            # Test database connection
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            logger.info("Database connection verified")
            
            # Check if tables exist
            result = db.session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            logger.info(f"Found tables: {', '.join(tables)}")
            
            # Verify required tables
            required_tables = ['users', 'meditation_sessions', 'chat_history']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                logger.error(f"Missing required tables: {', '.join(missing_tables)}")
                return False
                
            logger.info("All required tables present")
            return True
            
    except Exception as e:
        logger.error(f"Verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = verify_fork()
    if success:
        print("Fork verification completed successfully")
    else:
        print("Fork verification failed. Check logs for details")
