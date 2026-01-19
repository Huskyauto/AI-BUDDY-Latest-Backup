from app import app
from models import User
from extensions import db

with app.app_context():
    print('All users:')
    users = User.query.all()
    for user in users:
        print(f'ID: {user.id}, Username: {user.username}, Email: {user.email}')