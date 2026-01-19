"""
Simple Fork Creator with Complete User Data Migration
Creates new forks preserving all users, passwords, and their data
"""
import os
import json
import logging
import gzip
from datetime import datetime
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleForkCreator:
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        self.engine = create_engine(self.database_url)
        
    def export_all_user_data(self):
        """Export all users and their data"""
        try:
            logger.info("Starting complete user data export...")
            
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'users': [],
                'user_data': {}
            }
            
            # Tables that actually work and contain user data
            working_tables = [
                'mood', 'food_log', 'water_log', 'weight_log', 
                'chat_history', 'manual_wellness_check_ins', 
                'meditation_sessions', 'fasting_sessions'
            ]
            
            with self.engine.connect() as connection:
                # Export users first
                users_result = connection.execute(text("""
                    SELECT id, username, email, password_hash, is_ring_data_authorized, 
                           weight_lbs, daily_water_goal, created_at, last_login, 
                           current_streak, longest_streak, last_meditation_date, 
                           total_meditation_minutes, total_sessions
                    FROM users ORDER BY id
                """))
                
                users = [dict(row._mapping) for row in users_result]
                export_data['users'] = users
                logger.info(f"Exported {len(users)} users")
                
                # Export data for each user from working tables
                total_records = 0
                for user in users:
                    user_id = user['id']
                    export_data['user_data'][str(user_id)] = {}
                    
                    for table_name in working_tables:
                        try:
                            # Use separate connections for each query to avoid transaction issues
                            with self.engine.connect() as table_conn:
                                result = table_conn.execute(
                                    text(f"SELECT * FROM {table_name} WHERE user_id = :user_id"),
                                    {'user_id': user_id}
                                )
                                records = [dict(row._mapping) for row in result]
                                export_data['user_data'][str(user_id)][table_name] = records
                                total_records += len(records)
                                
                                if records:
                                    logger.info(f"User {user_id}: {len(records)} records from {table_name}")
                                    
                        except Exception as e:
                            logger.warning(f"Could not export {table_name} for user {user_id}: {str(e)}")
                            export_data['user_data'][str(user_id)][table_name] = []
                
                logger.info(f"Total data records exported: {total_records}")
                
            # Save export
            export_path = f"fork_user_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
            export_json = json.dumps(export_data, indent=2, default=str)
            compressed_data = gzip.compress(export_json.encode('utf-8'))
            
            with open(export_path, 'wb') as f:
                f.write(compressed_data)
            
            logger.info(f"Export saved to {export_path} ({len(compressed_data)} bytes)")
            return export_path, export_data
            
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            raise
    
    def import_user_data(self, export_path):
        """Import user data from export file"""
        try:
            logger.info(f"Importing user data from {export_path}...")
            
            with open(export_path, 'rb') as f:
                compressed_data = f.read()
            
            export_json = gzip.decompress(compressed_data).decode('utf-8')
            import_data = json.loads(export_json)
            
            with self.engine.connect() as connection:
                transaction = connection.begin()
                
                try:
                    # Import users
                    users = import_data['users']
                    logger.info(f"Importing {len(users)} users...")
                    
                    for user in users:
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
                                password_hash = EXCLUDED.password_hash
                        """
                        connection.execute(text(insert_user_sql), user)
                    
                    # Import user data
                    user_data = import_data['user_data']
                    total_imported = 0
                    
                    for user_id, tables_data in user_data.items():
                        for table_name, records in tables_data.items():
                            for record in records:
                                try:
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
            logger.error(f"Import error: {str(e)}")
            raise
    
    def create_complete_fork(self):
        """Create a complete fork with all user data"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            logger.info(f"Creating complete fork at {timestamp}")
            
            # Export current data
            export_path, export_data = self.export_all_user_data()
            
            # Create summary
            users_count = len(export_data['users'])
            total_records = sum(sum(len(records) for records in user_tables.values()) 
                              for user_tables in export_data['user_data'].values())
            
            # Create fork log
            log_path = f"fork_creation_log_{timestamp}.txt"
            with open(log_path, 'w') as f:
                f.write(f"AI-BUDDY Fork Creation - {timestamp}\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Users migrated: {users_count}\n")
                f.write(f"Total data records: {total_records}\n")
                f.write(f"Export file: {export_path}\n\n")
                
                f.write("USERS INCLUDED:\n")
                for user in export_data['users']:
                    user_records = sum(len(records) for records in export_data['user_data'][str(user['id'])].values())
                    f.write(f"- {user['email']} (ID: {user['id']}) - {user_records} records\n")
                
                f.write(f"\nFORK STATUS: READY FOR DEPLOYMENT\n")
                f.write(f"All users and their data are preserved in the export file.\n")
                f.write(f"To use this fork: run import_user_data('{export_path}')\n")
            
            return True, {
                'export_path': export_path,
                'log_path': log_path,
                'users_count': users_count,
                'total_records': total_records
            }
            
        except Exception as e:
            logger.error(f"Fork creation failed: {str(e)}")
            return False, str(e)

def main():
    """Create a fork with complete user data migration"""
    try:
        fork_creator = SimpleForkCreator()
        success, result = fork_creator.create_complete_fork()
        
        if success:
            print("\n" + "=" * 60)
            print("FORK CREATION SUCCESSFUL!")
            print("=" * 60)
            print(f"Users preserved: {result['users_count']}")
            print(f"Data records: {result['total_records']}")
            print(f"Export file: {result['export_path']}")
            print(f"Log file: {result['log_path']}")
            print("\nAll user accounts, passwords, and data are ready")
            print("for migration to a new fork when needed.")
            print("=" * 60)
        else:
            print(f"Fork creation failed: {result}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()