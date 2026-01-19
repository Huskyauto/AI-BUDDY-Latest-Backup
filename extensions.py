"""Flask extension instances"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with optimized connection pooling
db = SQLAlchemy(
    model_class=Base,
    engine_options={
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 20,
        "max_overflow": 30,
        "pool_timeout": 30
    }
)

# Initialize other extensions
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()