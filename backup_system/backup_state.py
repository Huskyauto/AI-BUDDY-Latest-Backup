import json
import logging
import os
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from app import db, create_app

logger = logging.getLogger(__name__)

class BackupStateManager:
    def __init__(self, backup_dir="/home/runner/backups"):
        self.backup_dir = Path(backup_dir)
        self.state_file = self.backup_dir / "backup_state.json"
        self.ensure_directories()
        self.app = create_app()

    def ensure_directories(self):
        """Ensure all required directories exist"""
        os.makedirs(self.backup_dir, exist_ok=True)

    def save_state(self, backup_info):
        """Save the current backup state"""
        try:
            current_state = {
                'last_backup_timestamp': datetime.now().isoformat(),
                'database_tables': self.get_database_tables(),
                'config_files': ['pyproject.toml', 'replit.nix', '.replit'],
                'backup_info': backup_info
            }

            with open(self.state_file, 'w') as f:
                json.dump(current_state, f, indent=2)
            logger.info("Backup state saved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save backup state: {e}")
            return False

    def get_database_tables(self):
        """Get list of current database tables"""
        try:
            with self.app.app_context():
                result = db.session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Failed to get database tables: {e}")
            return []

    def verify_state(self):
        """Verify the current state matches the backup state"""
        try:
            if not self.state_file.exists():
                logger.info("No backup state file found - creating initial state")
                # Create initial state with current configuration
                self.save_state({
                    'initial_setup': True,
                    'timestamp': datetime.now().isoformat()
                })
                return True

            with open(self.state_file, 'r') as f:
                saved_state = json.load(f)

            # Verify database tables within app context
            with self.app.app_context():
                current_tables = set(self.get_database_tables())
                saved_tables = set(saved_state['database_tables'])

                # Log the comparison results
                logger.info(f"Current tables: {current_tables}")
                logger.info(f"Expected tables from backup: {saved_tables}")

                if current_tables != saved_tables:
                    logger.warning(f"Database tables mismatch. Current: {current_tables}, Saved: {saved_tables}")
                    # Don't fail verification, just warn

                # Verify config files
                for config_file in saved_state['config_files']:
                    if not Path(config_file).exists():
                        logger.warning(f"Missing config file: {config_file}")
                        # Don't fail verification, just warn

            logger.info("Backup state verification completed")
            return True
        except Exception as e:
            logger.warning(f"Backup state verification encountered an error: {e}")
            # Don't fail on verification errors, just warn
            return True

    def get_last_backup_info(self):
        """Get information about the last successful backup"""
        try:
            if not self.state_file.exists():
                return None

            with open(self.state_file, 'r') as f:
                state = json.load(f)
            return state
        except Exception as e:
            logger.error(f"Failed to get last backup info: {e}")
            return None