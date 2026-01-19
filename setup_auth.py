#!/usr/bin/env python3
"""
Initialize the authentication system and create a default user
with ring data access rights.
"""

import os
import logging
from flask import Flask
from extensions import db
from models import User
from sqlalchemy import func
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def create_app():
    """Create a minimal Flask app for setup"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_key')
    
    db.init_app(app)
    return app

def setup_default_user(app):
    """Set up the default user with ring data access"""
    with app.app_context():
        try:
            # Create tables if they don't exist
            import models  # noqa: F401
            db.create_all()
            
            # Define default user details
            email = 'huskyauto@gmail.com'
            password = 'Rw-120764'  # Case sensitive as specified
            username = 'HuskyAuto'
            
            # Check if user already exists (case-insensitive email check)
            existing_user = User.query.filter(func.lower(User.email) == func.lower(email)).first()
            
            if existing_user:
                logger.info(f"User {email} already exists, updating credentials and permissions")
                existing_user.username = username
                existing_user.set_password(password)
                existing_user.is_ring_data_authorized = True
                db.session.commit()
                logger.info(f"User {email} updated with ring data access")
            else:
                logger.info(f"Creating new user {email} with ring data access")
                user = User(
                    email=email,
                    username=username,
                    is_ring_data_authorized=True,
                    daily_water_goal=64.0
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                logger.info(f"User {email} created successfully with ring data access")
                
            return True
        except Exception as e:
            logger.error(f"Error setting up default user: {str(e)}", exc_info=True)
            return False

def main():
    """Main setup function"""
    logger.info("Starting authentication setup...")
    
    # Create app
    app = create_app()
    
    # Set up default user
    success = setup_default_user(app)
    
    if success:
        logger.info("Authentication setup completed successfully")
        print("\nSetup completed successfully!")
        print(f"Default user created/updated:")
        print(f"  Email: huskyauto@gmail.com")
        print(f"  Password: Rw-120764")
        print(f"  Ring data access: Enabled")
    else:
        logger.error("Authentication setup failed")
        print("\nSetup failed. Check logs for details.")

if __name__ == "__main__":
    main()