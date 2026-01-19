from app import app, db
from models import User

with app.app_context():
    user = User.query.filter_by(email='huskyauto@gmail.com').first()
    print(f'User exists: {user is not None}')
    if user:
        print(f'Username: {user.username}')
        print(f'Has password: {user.password_hash is not None}')
        print(f'Has ring data authorization: {user.is_ring_data_authorized}')
        print(f'Can view ring data: {user.can_view_ring_data()}')
        print(f'Ring access message: {user.get_ring_access_message()}')