"""Database migration script for the application"""
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from app import create_app, db

def init_migrations():
    """Initialize database migrations"""
    app = create_app()
    if not app:
        raise RuntimeError("Failed to create Flask application")

    migrate = Migrate(app, db)
    return app, migrate

if __name__ == '__main__':
    app, migrate = init_migrations()
    with app.app_context():
        from models import User, ChatHistory, FoodLog, WaterLog, Mood, JournalEntry