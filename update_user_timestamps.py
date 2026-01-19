#!/usr/bin/env python3
"""
Database utility script to update user timestamps for AI-BUDDY application.
This will add created_at and last_login timestamps to existing users.
"""

import os
import logging
import sys
from datetime import datetime, timedelta
from flask import Flask
from extensions import db
from models import User, get_local_time
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('user_update.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def create_app():
    """Create a minimal Flask app for database operations"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

def update_user_timestamps():
    """Update timestamps for all users"""
    app = create_app()
    
    with app.app_context():
        try:
            # Import all models to ensure they are registered
            import models  # noqa: F401
            
            # Check if the columns exist
            try:
                # Try a test query to see if columns exist
                User.query.filter(User.created_at != None).first()
                User.query.filter(User.last_login != None).first()
                columns_exist = True
            except Exception as e:
                logger.warning(f"Columns don't exist yet, will add them: {str(e)}")
                columns_exist = False
            
            if not columns_exist:
                # Add columns if they don't exist
                logger.info("Adding missing columns to users table...")
                db.engine.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP")
                db.engine.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP")
                logger.info("Columns added successfully")
            
            # Update all users with timestamps
            users = User.query.all()
            now = get_local_time()
            
            for user in users:
                # Set created_at to 7 days ago if not set
                if not user.created_at:
                    user.created_at = now - timedelta(days=7)
                    logger.info(f"Set created_at for user {user.username} to {user.created_at}")
                
                # Set last_login to now if not set
                if not user.last_login:
                    user.last_login = now
                    logger.info(f"Set last_login for user {user.username} to {user.last_login}")
            
            # Commit changes
            db.session.commit()
            logger.info(f"Updated timestamps for {len(users)} users")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user timestamps: {str(e)}", exc_info=True)
            db.session.rollback()
            return False

if __name__ == "__main__":
    logger.info("Starting user timestamp update process...")
    success = update_user_timestamps()
    
    if success:
        print("\nUser timestamps updated successfully!")
    else:
        print("\nUser timestamp update failed. Check logs for details.")
        sys.exit(1)