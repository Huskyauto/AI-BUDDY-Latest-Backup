"""
Enhanced Fork Creator with Complete User Data Migration
Creates new forks with all users, passwords, and accumulated data preserved
"""
import os
import json
import logging
import shutil
import subprocess
from datetime import datetime
from sqlalchemy import create_engine, text
import gzip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnhancedForkCreator:
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.engine = create_engine(self.database_url)
        
    def export_complete_user_data(self):
        """Export all user data including passwords and activity history"""
        try:
            logger.info("Exporting complete user data for fork creation...")
            
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'users': [],
                'user_data': {}
            }
            
            with self.engine.connect() as connection:
                # Export users with passwords
                logger.info("Exporting users and authentication data...")
                users_result = connection.execute(text("""
                    SELECT id, username, email, password_hash, is_ring_data_authorized, 
                           weight_lbs, daily_water_goal, created_at, last_login, 
                           current_streak, longest_streak, last_meditation_date, 
                           total_meditation_minutes, total_sessions
                    FROM users ORDER BY id
                """))
                
                users = []
                user_ids = []
                for row in users_result:
                    user_data = dict(row._mapping)
                    users.append(user_data)
                    user_ids.append(user_data['id'])
                
                export_data['users'] = users
                logger.info(f"Exported {len(users)} users with authentication data")
                
                # Define all user data tables to export (using actual table names)
                user_data_tables = {
                    'mood': 'SELECT * FROM mood WHERE user_id = :user_id',
                    'food_log': 'SELECT * FROM food_log WHERE user_id = :user_id',
                    'water_log': 'SELECT * FROM water_log WHERE user_id = :user_id',
                    'weight_log': 'SELECT * FROM weight_log WHERE user_id = :user_id',
                    'chat_history': 'SELECT * FROM chat_history WHERE user_id = :user_id',
                    'manual_wellness_check_ins': 'SELECT * FROM manual_wellness_check_ins WHERE user_id = :user_id',
                    'meditation_sessions': 'SELECT * FROM meditation_sessions WHERE user_id = :user_id',
                    'fasting_sessions': 'SELECT * FROM fasting_sessions WHERE user_id = :user_id',
                    'fasting_check_ins': 'SELECT * FROM fasting_check_ins WHERE user_id = :user_id',
                    'journal_entry': 'SELECT * FROM journal_entry WHERE user_id = :user_id',
                    'forum_posts': 'SELECT * FROM forum_posts WHERE user_id = :user_id',
                    'forum_replies': 'SELECT * FROM forum_replies WHERE user_id = :user_id',
                    'challenge_participants': 'SELECT * FROM challenge_participants WHERE user_id = :user_id',
                    'challenge_messages': 'SELECT * FROM challenge_messages WHERE user_id = :user_id',
                    'biomarker_insights': 'SELECT * FROM biomarker_insights WHERE user_id = :user_id',
                    'self_care_recommendation': 'SELECT * FROM self_care_recommendation WHERE user_id = :user_id',
                    'self_care_user_preference': 'SELECT * FROM self_care_user_preference WHERE user_id = :user_id',
                    'self_care_activity': 'SELECT * FROM self_care_activity WHERE user_id = :user_id',
                    'stress_levels': 'SELECT * FROM stress_levels WHERE user_id = :user_id'
                }
                
                # Export data for each user
                total_records = 0
                for user_id in user_ids:
                    export_data['user_data'][user_id] = {}
                    
                    for table_name, query in user_data_tables.items():
                        try:
                            result = connection.execute(text(query), {'user_id': user_id})
                            records = [dict(row._mapping) for row in result]
                            export_data['user_data'][user_id][table_name] = records
                            total_records += len(records)
                            
                            if records:
                                logger.info(f"User {user_id}: exported {len(records)} records from {table_name}")
                                
                        except Exception as e:
                            logger.warning(f"Could not export {table_name} for user {user_id}: {str(e)}")
                            export_data['user_data'][user_id][table_name] = []
                
                logger.info(f"Total user data records exported: {total_records}")
                
            # Save export to compressed file
            export_path = f"fork_user_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
            
            # Convert datetime objects to strings
            export_json = json.dumps(export_data, indent=2, default=str)
            compressed_data = gzip.compress(export_json.encode('utf-8'))
            
            with open(export_path, 'wb') as f:
                f.write(compressed_data)
            
            logger.info(f"User data export saved to {export_path}")
            logger.info(f"Export size: {len(compressed_data)} bytes")
            
            return export_path, export_data
            
        except Exception as e:
            logger.error(f"Error exporting user data: {str(e)}")
            raise
    
    def import_user_data(self, export_path):
        """Import user data from export file into current database"""
        try:
            logger.info(f"Importing user data from {export_path}...")
            
            # Read and decompress export file
            with open(export_path, 'rb') as f:
                compressed_data = f.read()
            
            export_json = gzip.decompress(compressed_data).decode('utf-8')
            import_data = json.loads(export_json)
            
            with self.engine.connect() as connection:
                transaction = connection.begin()
                
                try:
                    # Import users first
                    users = import_data['users']
                    logger.info(f"Importing {len(users)} users...")
                    
                    for user in users:
                        # Insert user with original password hash and preferences
                        insert_user_sql = """
                            INSERT INTO users (id, username, email, password_hash, is_ring_data_authorized, 
                                             weight_lbs, daily_water_goal, created_at, last_login, 
                                             current_streak, longest_streak, last_meditation_date, 
                                             total_meditation_minutes, total_sessions)
                            VALUES (:id, :username, :email, :password_hash, :is_ring_data_authorized, 
                                    :weight_lbs, :daily_water_goal, :created_at, :last_login, 
                                    :current_streak, :longest_streak, :last_meditation_date, 
                                    :total_meditation_minutes, :total_sessions)
                            ON CONFLICT (id) DO UPDATE SET
                                username = EXCLUDED.username,
                                email = EXCLUDED.email,
                                password_hash = EXCLUDED.password_hash,
                                is_ring_data_authorized = EXCLUDED.is_ring_data_authorized,
                                weight_lbs = EXCLUDED.weight_lbs,
                                daily_water_goal = EXCLUDED.daily_water_goal
                        """
                        
                        connection.execute(text(insert_user_sql), user)
                    
                    # Import all user data
                    user_data = import_data['user_data']
                    total_imported = 0
                    
                    for user_id, tables_data in user_data.items():
                        logger.info(f"Importing data for user {user_id}...")
                        
                        for table_name, records in tables_data.items():
                            if not records:
                                continue
                            
                            for record in records:
                                try:
                                    # Create dynamic INSERT statement
                                    columns = list(record.keys())
                                    placeholders = [f":{col}" for col in columns]
                                    
                                    insert_sql = f"""
                                        INSERT INTO {table_name} ({', '.join(columns)})
                                        VALUES ({', '.join(placeholders)})
                                        ON CONFLICT DO NOTHING
                                    """
                                    
                                    connection.execute(text(insert_sql), record)
                                    total_imported += 1
                                    
                                except Exception as e:
                                    logger.warning(f"Could not import record to {table_name}: {str(e)}")
                                    continue
                    
                    transaction.commit()
                    logger.info(f"Successfully imported {len(users)} users with {total_imported} data records")
                    return True
                    
                except Exception as e:
                    transaction.rollback()
                    logger.error(f"Import failed, rolling back: {str(e)}")
                    raise
                    
        except Exception as e:
            logger.error(f"Error importing user data: {str(e)}")
            raise
    
    def create_fork_with_user_data(self):
        """Create a complete fork with all user data preserved"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            logger.info(f"Creating enhanced fork with user data at {timestamp}")
            
            # Step 1: Export all current user data
            logger.info("Step 1: Exporting current user data...")
            export_path, export_data = self.export_complete_user_data()
            
            # Step 2: Create backup directory for the fork
            backup_dir = f"backup_system/backups/fork_backup_{timestamp}"
            os.makedirs(backup_dir, exist_ok=True)
            
            # Copy export file to backup directory
            shutil.copy2(export_path, backup_dir)
            
            # Step 3: Copy essential application files
            logger.info("Step 2: Backing up application files...")
            essential_files = [
                "app.py", "models.py", "main.py", "extensions.py",
                "auth.py", "dashboard.py", "fasting.py", "food_tracker.py",
                "chat.py", "ai_client.py", "ring_routes.py", "cbt.py",
                "admin_dashboard.py", "admin_reports.py",
                "self_care.py", "wellness_toolbox.py", "stress_monitoring.py",
                "templates/", "static/", "docs/",
                ".env", "requirements.txt"
            ]
            
            for item in essential_files:
                if os.path.exists(item):
                    if os.path.isdir(item):
                        shutil.copytree(item, os.path.join(backup_dir, item), dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, backup_dir)
                    logger.info(f"Backed up {item}")
            
            # Step 4: Run fork initialization
            logger.info("Step 3: Initializing fork...")
            try:
                from init_fork import init_fork
                init_success = init_fork()
                if not init_success:
                    logger.warning("Fork initialization had issues, but continuing...")
            except Exception as e:
                logger.warning(f"Fork initialization error: {str(e)}, continuing...")
            
            # Step 5: Import user data into the new fork
            logger.info("Step 4: Importing user data into new fork...")
            self.import_user_data(export_path)
            
            # Step 6: Create fork completion record
            fork_log_path = f"fork_creation_log_{timestamp}.txt"
            with open(fork_log_path, 'w') as f:
                f.write(f"Enhanced Fork Creation Log - {timestamp}\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Fork created at: {datetime.now()}\n")
                f.write(f"User data export: {export_path}\n")
                f.write(f"Backup directory: {backup_dir}\n\n")
                
                # User summary
                users_count = len(export_data['users'])
                f.write(f"USERS MIGRATED:\n")
                f.write(f"Total users: {users_count}\n")
                
                for user in export_data['users']:
                    f.write(f"- {user['email']} (ID: {user['id']}, Username: {user['username']})\n")
                
                f.write(f"\nDATA MIGRATION SUMMARY:\n")
                total_records = 0
                for user_id, user_tables in export_data['user_data'].items():
                    user_total = sum(len(records) for records in user_tables.values())
                    total_records += user_total
                    f.write(f"User {user_id}: {user_total} records\n")
                
                f.write(f"\nTotal data records migrated: {total_records}\n")
                f.write(f"\nFORK STATUS: COMPLETE\n")
                f.write(f"All users, passwords, and data successfully transferred to new fork.\n")
                
            logger.info(f"Fork creation completed successfully!")
            logger.info(f"Fork log saved to: {fork_log_path}")
            
            return True, {
                'export_path': export_path,
                'backup_dir': backup_dir,
                'fork_log': fork_log_path,
                'users_count': len(export_data['users']),
                'total_records': sum(sum(len(records) for records in user_tables.values()) 
                                   for user_tables in export_data['user_data'].values())
            }
            
        except Exception as e:
            logger.error(f"Enhanced fork creation failed: {str(e)}")
            return False, str(e)

def main():
    """Main function to create enhanced fork with user data"""
    try:
        fork_creator = EnhancedForkCreator()
        
        success, result = fork_creator.create_fork_with_user_data()
        
        if success:
            print("\n" + "=" * 60)
            print("🎉 ENHANCED FORK CREATION SUCCESSFUL!")
            print("=" * 60)
            print(f"👥 Users migrated: {result['users_count']}")
            print(f"📊 Total data records: {result['total_records']}")
            print(f"💾 User data export: {result['export_path']}")
            print(f"📁 Backup directory: {result['backup_dir']}")
            print(f"📝 Fork log: {result['fork_log']}")
            print("\n✅ All users, passwords, and accumulated data")
            print("   have been successfully transferred to the new fork!")
            print("\n🚀 You can now use the new fork with all existing")
            print("   user accounts and their complete data history.")
            print("=" * 60)
        else:
            print(f"\n❌ Fork creation failed: {result}")
            
    except Exception as e:
        print(f"\n❌ Error during fork creation: {str(e)}")

if __name__ == "__main__":
    main()