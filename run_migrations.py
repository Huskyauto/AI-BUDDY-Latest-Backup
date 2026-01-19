#!/usr/bin/env python3
"""
Database migration script for AI-BUDDY application.
This script will run any pending database migrations.
"""

import os
import logging
import sys
from flask import Flask
from flask_migrate import Migrate
from extensions import db
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('migration.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def create_app():
    """Create a minimal Flask app for migrations"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

def init_migrations(force_reinit=False):
    """Initialize and run database migrations
    
    Args:
        force_reinit (bool): If True, remove existing migrations and reinitialize
    """
    app = create_app()
    migrate = Migrate(app, db)
    
    with app.app_context():
        try:
            # Import models to register them with SQLAlchemy
            import models  # noqa: F401
            
            # Get the migrations directory
            migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
            
            # Force reinitialization if requested
            if force_reinit:
                import shutil
                logger.info("Forcing migration reinitialization...")
                
                # Delete the migrations directory if it exists
                if os.path.exists(migrations_dir):
                    shutil.rmtree(migrations_dir)
                    logger.info(f"Deleted existing migrations directory: {migrations_dir}")
                
                # Delete all alembic_version entries to start fresh
                logger.info("Clearing alembic version data...")
                try:
                    db.session.execute(db.text("DROP TABLE IF EXISTS alembic_version"))
                    db.session.commit()
                    logger.info("Cleaned up alembic version data")
                except Exception as e:
                    logger.warning(f"Could not clear alembic version data: {str(e)}")
                    db.session.rollback()
            
            # Create migrations directory if it doesn't exist (or was just deleted)
            if not os.path.exists(migrations_dir):
                logger.info("Migrations directory not found, creating and initializing...")
                from flask_migrate import init, migrate
                
                # Initialize migrations directory
                init()
                logger.info("Migrations directory initialized")
                
                # Create initial migration
                migrate(message="initial schema")
                logger.info("Initial migration created")
                
                # Import and stamp to establish current version
                from flask_migrate import stamp
                stamp(revision='head')
                logger.info("Stamped database with initial migration version")
            else:
                logger.info("Using existing migrations directory")
            
            # Import upgrade function
            from flask_migrate import upgrade
            
            # Apply all pending migrations
            logger.info("Applying database migrations...")
            upgrade()
            
            logger.info("Database migrations completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during database migration: {str(e)}", exc_info=True)
            return False

if __name__ == "__main__":
    logger.info("Starting database migration process...")
    
    # Check if force reinitialization is requested
    force_reinit = False
    if len(sys.argv) > 1 and sys.argv[1] == "--force-reinit":
        force_reinit = True
        logger.info("Force reinitialization requested")
    
    success = init_migrations(force_reinit=force_reinit)
    
    if success:
        print("\nDatabase migrations completed successfully!")
    else:
        print("\nDatabase migrations failed. Check logs for details.")
        sys.exit(1)