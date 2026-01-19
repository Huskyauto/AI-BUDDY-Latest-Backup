"""
Deployment configuration management for the application.
Handles environment-specific settings and version control.
"""

import os
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DeploymentConfig:
    """Manages deployment configuration and version control"""

    def __init__(self):
        # Set to 'production' for deployment
        self.environment = 'production'
        self.version = os.environ.get('APP_VERSION', '1.0.0')
        self.deployment_timestamp = datetime.now().isoformat()

    def get_environment_config(self):
        """Get environment-specific configuration"""
        base_config = {
            'DEBUG': False,
            'TESTING': False,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'SQLALCHEMY_ENGINE_OPTIONS': {
                "pool_pre_ping": True,
                "pool_recycle": 300,
                "pool_size": 10,
                "max_overflow": 20
            }
        }

        return base_config

    def save_deployment_state(self):
        """Save current deployment state"""
        state = {
            'version': self.version,
            'environment': self.environment,
            'timestamp': self.deployment_timestamp,
            'features_enabled': {
                'fasting_program': True,
                'location_wellness': True,
                'database': bool(os.environ.get('DATABASE_URL'))
            }
        }

        try:
            with open('deployment_state.json', 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"[DEPLOYMENT] State saved: {json.dumps(state, indent=2)}")
            return True
        except Exception as e:
            logger.error(f"[DEPLOYMENT] Failed to save state: {e}")
            return False

    def verify_deployment(self):
        """Verify deployment configuration"""
        required_vars = [
            'DATABASE_URL', 
            'FLASK_SECRET_KEY',
            'GOOGLE_MAPS_API_KEY',
            'OURA_API_KEY',
            'ULTRAHUMAN_API_KEY'
        ]
        missing_vars = [var for var in required_vars if not os.environ.get(var)]

        if missing_vars:
            logger.error(f"[DEPLOYMENT] Missing required variables: {missing_vars}")
            return False

        return True

# Create global instance
deployment_config = DeploymentConfig()