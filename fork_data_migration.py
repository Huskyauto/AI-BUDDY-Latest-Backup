"""
Fork Data Migration System for AI-BUDDY
Handles complete user data export and import during fork creation
"""
import os
import json
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash
import gzip
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ForkDataMigrator:
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.engine = create_engine(self.database_url)
        
    def export_all_user_data(self, export_path="fork_user_data_export.json.gz"):
        """
        Export all user data including passwords, preferences, and activity data
        """
        try:
            logger.info("Starting complete user data export...")
            
            # Define all user-related tables and their relationships
            user_tables = {
                'users': {
                    'query': "SELECT id, username, email, password_hash, created_at, last_login, timezone FROM users",
                    'key_field': 'id'
                },
                'mood_entries': {
                    'query': "SELECT id, user_id, mood, energy_level, stress_level, notes, created_at FROM mood_entries",
                    'user_field': 'user_id'
                },
                'food_logs': {
                    'query': "SELECT id, user_id, food_name, calories, protein, carbs, fat, fiber, sugar, sodium, serving_size, meal_type, logged_at FROM food_logs",
                    'user_field': 'user_id'
                },
                'water_logs': {
                    'query': "SELECT id, user_id, amount, logged_at FROM water_logs",
                    'user_field': 'user_id'
                },
                'weight_log': {
                    'query': "SELECT id, user_id, weight, recorded_at FROM weight_log",
                    'user_field': 'user_id'
                },
                'chat_history': {
                    'query': "SELECT id, user_id, message, response, emotion, created_at FROM chat_history",
                    'user_field': 'user_id'
                },
                'wellness_check_ins': {
                    'query': "SELECT id, user_id, mood, energy_level, stress_level, sleep_quality, physical_activity, social_connections, mindfulness_practice, notes, created_at FROM wellness_check_ins",
                    'user_field': 'user_id'
                },
                'manual_wellness_check_ins': {
                    'query': "SELECT id, user_id, mood, energy_level, stress_level, sleep_quality, physical_activity, social_connections, mindfulness_practice, notes, created_at, recorded_at FROM manual_wellness_check_ins",
                    'user_field': 'user_id'
                },
                'meditation_sessions': {
                    'query': "SELECT id, user_id, session_type, duration, completed, created_at FROM meditation_sessions",
                    'user_field': 'user_id'
                },
                'fasting_sessions': {
                    'query': "SELECT id, user_id, program_id, start_time, end_time, status, created_at FROM fasting_sessions",
                    'user_field': 'user_id'
                },
                'fasting_check_ins': {
                    'query': "SELECT id, session_id, user_id, day_number, hunger_level, energy_level, mood, notes, check_in_time FROM fasting_check_ins",
                    'user_field': 'user_id'
                },
                'intermittent_fasting_sessions': {
                    'query': "SELECT id, user_id, program_id, start_time, end_time, status, created_at FROM intermittent_fasting_sessions",
                    'user_field': 'user_id'
                },
                'journal_entries': {
                    'query': "SELECT id, user_id, title, content, mood, created_at FROM journal_entries",
                    'user_field': 'user_id'
                },
                'forum_posts': {
                    'query': "SELECT id, user_id, title, content, created_at FROM forum_posts",
                    'user_field': 'user_id'
                },
                'forum_replies': {
                    'query': "SELECT id, post_id, user_id, content, created_at FROM forum_replies",
                    'user_field': 'user_id'
                },
                'challenge_participants': {
                    'query': "SELECT id, challenge_id, user_id, joined_at, completed FROM challenge_participants",
                    'user_field': 'user_id'
                },
                'challenge_messages': {
                    'query': "SELECT id, challenge_id, user_id, message, created_at FROM challenge_messages",
                    'user_field': 'user_id'
                },
                'user_preferences': {
                    'query': "SELECT id, user_id, preference_key, preference_value, created_at FROM user_preferences",
                    'user_field': 'user_id'
                },
                'biomarker_insights': {
                    'query': "SELECT id, user_id, insight_type, data_source, insight_data, created_at FROM biomarker_insights",
                    'user_field': 'user_id'
                },
                'self_care_recommendation': {
                    'query': "SELECT id, user_id, recommendation_text, category, priority, is_completed, created_at FROM self_care_recommendation",
                    'user_field': 'user_id'
                },
                'self_care_user_preference': {
                    'query': "SELECT id, user_id, category, is_enabled, created_at FROM self_care_user_preference",
                    'user_field': 'user_id'
                },
                'self_care_activity': {
                    'query': "SELECT id, user_id, activity_name, duration_minutes, mood_before, mood_after, notes, completed_at FROM self_care_activity",
                    'user_field': 'user_id'
                },
                'api_logs': {
                    'query': "SELECT id, user_id, api_name, endpoint, response_time, success, status_code, created_at FROM api_logs",
                    'user_field': 'user_id'
                }
            }
            
            exported_data = {
                'export_timestamp': datetime.now().isoformat(),
                'export_version': '1.0',
                'tables': {}
            }
            
            with self.engine.connect() as connection:
                # First, get all users
                logger.info("Exporting users table...")
                result = connection.execute(text(user_tables['users']['query']))
                users_data = [dict(row._mapping) for row in result]
                exported_data['tables']['users'] = users_data
                logger.info(f"Exported {len(users_data)} users")
                
                # Get user IDs for filtering other tables
                user_ids = [user['id'] for user in users_data]
                
                # Export all other user-related tables
                for table_name, table_config in user_tables.items():
                    if table_name == 'users':
                        continue  # Already exported
                    
                    try:
                        logger.info(f"Exporting {table_name}...")
                        result = connection.execute(text(table_config['query']))
                        table_data = [dict(row._mapping) for row in result]
                        
                        # Filter data for existing users only
                        if 'user_field' in table_config:
                            table_data = [row for row in table_data 
                                        if row.get(table_config['user_field']) in user_ids]
                        
                        exported_data['tables'][table_name] = table_data
                        logger.info(f"Exported {len(table_data)} records from {table_name}")
                        
                    except Exception as e:
                        logger.warning(f"Could not export table {table_name}: {str(e)}")
                        exported_data['tables'][table_name] = []
            
            # Convert datetime objects to strings for JSON serialization
            exported_data = self._serialize_datetime_objects(exported_data)
            
            # Compress and save the export
            json_data = json.dumps(exported_data, indent=2, default=str)
            compressed_data = gzip.compress(json_data.encode('utf-8'))
            
            with open(export_path, 'wb') as f:
                f.write(compressed_data)
            
            tables_data = exported_data.get('tables', {})
            total_records = sum(len(table_data) for table_data in tables_data.values())
            logger.info(f"Complete user data export saved to {export_path}")
            logger.info(f"Total records exported: {total_records}")
            logger.info(f"Export file size: {len(compressed_data)} bytes")
            
            return export_path, exported_data
            
        except Exception as e:
            logger.error(f"Error during user data export: {str(e)}")
            raise
    
    def import_all_user_data(self, import_path="fork_user_data_export.json.gz"):
        """
        Import all user data into the current database
        """
        try:
            logger.info(f"Starting user data import from {import_path}...")
            
            # Read and decompress the export file
            with open(import_path, 'rb') as f:
                compressed_data = f.read()
            
            json_data = gzip.decompress(compressed_data).decode('utf-8')
            imported_data = json.loads(json_data)
            
            logger.info(f"Import file created at: {imported_data['export_timestamp']}")
            logger.info(f"Import version: {imported_data['export_version']}")
            
            with self.engine.connect() as connection:
                transaction = connection.begin()
                
                try:
                    # Import in specific order to respect foreign key constraints
                    import_order = [
                        'users',
                        'mood_entries',
                        'food_logs',
                        'water_logs',
                        'weight_log',
                        'chat_history',
                        'wellness_check_ins',
                        'manual_wellness_check_ins',
                        'meditation_sessions',
                        'fasting_sessions',
                        'fasting_check_ins',
                        'intermittent_fasting_sessions',
                        'journal_entries',
                        'forum_posts',
                        'forum_replies',
                        'challenge_participants',
                        'challenge_messages',
                        'user_preferences',
                        'biomarker_insights',
                        'self_care_recommendation',
                        'self_care_user_preference',
                        'self_care_activity',
                        'api_logs'
                    ]
                    
                    total_imported = 0
                    
                    for table_name in import_order:
                        if table_name not in imported_data['tables']:
                            logger.warning(f"Table {table_name} not found in import data")
                            continue
                        
                        table_data = imported_data['tables'][table_name]
                        if not table_data:
                            logger.info(f"No data to import for {table_name}")
                            continue
                        
                        # Clear existing data (optional - comment out to preserve existing data)
                        # connection.execute(text(f"DELETE FROM {table_name}"))
                        
                        # Import data
                        logger.info(f"Importing {len(table_data)} records to {table_name}...")
                        
                        for record in table_data:
                            # Convert string timestamps back to datetime objects
                            record = self._deserialize_datetime_objects(record)
                            
                            # Create INSERT statement
                            if isinstance(record, dict):
                                columns = list(record.keys())
                                placeholders = [f":{col}" for col in columns]
                            else:
                                logger.warning(f"Skipping invalid record in {table_name}: {record}")
                                continue
                            
                            insert_sql = f"""
                                INSERT INTO {table_name} ({', '.join(columns)})
                                VALUES ({', '.join(placeholders)})
                                ON CONFLICT DO NOTHING
                            """
                            
                            try:
                                connection.execute(text(insert_sql), record)
                            except Exception as e:
                                logger.warning(f"Could not insert record into {table_name}: {str(e)}")
                                continue
                        
                        total_imported += len(table_data)
                        logger.info(f"Successfully imported {len(table_data)} records to {table_name}")
                    
                    transaction.commit()
                    logger.info(f"User data import completed successfully!")
                    logger.info(f"Total records imported: {total_imported}")
                    
                    return True
                    
                except Exception as e:
                    transaction.rollback()
                    logger.error(f"Error during import, rolling back: {str(e)}")
                    raise
                    
        except Exception as e:
            logger.error(f"Error during user data import: {str(e)}")
            raise
    
    def _serialize_datetime_objects(self, obj):
        """Convert datetime objects to ISO format strings for JSON serialization"""
        if isinstance(obj, dict):
            return {key: self._serialize_datetime_objects(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime_objects(item) for item in obj]
        elif hasattr(obj, 'isoformat'):  # datetime object
            return obj.isoformat()
        else:
            return obj
    
    def _deserialize_datetime_objects(self, obj):
        """Convert ISO format strings back to datetime objects"""
        import re
        
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if isinstance(value, str) and re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', value):
                    try:
                        from datetime import datetime
                        result[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except:
                        result[key] = value
                else:
                    result[key] = self._deserialize_datetime_objects(value)
            return result
        elif isinstance(obj, list):
            return [self._deserialize_datetime_objects(item) for item in obj]
        else:
            return obj
    
    def create_user_data_backup(self, backup_name=None):
        """Create a timestamped backup of all user data"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"user_data_backup_{timestamp}.json.gz"
        
        backup_path = os.path.join("backup_system/backups", backup_name)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        export_path, data = self.export_all_user_data(backup_path)
        return export_path
    
    def verify_data_integrity(self, export_path="fork_user_data_export.json.gz"):
        """Verify the integrity of exported data"""
        try:
            logger.info("Verifying data integrity...")
            
            with open(export_path, 'rb') as f:
                compressed_data = f.read()
            
            json_data = gzip.decompress(compressed_data).decode('utf-8')
            data = json.loads(json_data)
            
            # Basic integrity checks
            if 'tables' not in data:
                raise ValueError("Export data missing 'tables' section")
            
            if 'users' not in data['tables']:
                raise ValueError("Export data missing users table")
            
            users_count = len(data['tables']['users'])
            total_records = sum(len(table_data) for table_data in data['tables'].values())
            
            logger.info(f"Data integrity verification passed")
            logger.info(f"Users found: {users_count}")
            logger.info(f"Total records: {total_records}")
            logger.info(f"Tables exported: {len(data['tables'])}")
            
            return True, {
                'users_count': users_count,
                'total_records': total_records,
                'tables_count': len(data['tables']),
                'export_timestamp': data.get('export_timestamp')
            }
            
        except Exception as e:
            logger.error(f"Data integrity verification failed: {str(e)}")
            return False, str(e)

def main():
    """Main function for testing the migration system"""
    try:
        migrator = ForkDataMigrator()
        
        # Create export
        export_path, data = migrator.export_all_user_data()
        
        # Verify integrity
        is_valid, info = migrator.verify_data_integrity(export_path)
        
        if is_valid:
            print(f"✅ User data export completed successfully!")
            print(f"📁 Export file: {export_path}")
            print(f"👥 Users exported: {info['users_count']}")
            print(f"📊 Total records: {info['total_records']}")
            print(f"🗂️ Tables exported: {info['tables_count']}")
        else:
            print(f"❌ Data integrity verification failed: {info}")
            
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")

if __name__ == "__main__":
    main()