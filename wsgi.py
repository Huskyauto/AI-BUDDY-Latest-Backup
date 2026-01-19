from app import app
import logging

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

# Disable debug mode for production
app.config['DEBUG'] = False
app.config['TESTING'] = False

# Set up production-specific configurations
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 10,
    "max_overflow": 20
}

if __name__ == "__main__":
    # Production WSGI server entry point
    app.run()