#!/usr/bin/env python3
"""
Simple command to create a new fork with complete user data migration
Usage: python create_fork_with_users.py
"""
import sys
import os
from enhanced_fork_creator import EnhancedForkCreator

def main():
    print("AI-BUDDY Enhanced Fork Creator")
    print("=" * 40)
    print("This will create a new fork with ALL users and their data preserved.")
    print("Including:")
    print("- User accounts with original passwords")
    print("- All wellness check-ins and mood entries")
    print("- Food logs, water intake, and weight tracking")
    print("- Chat history and AI interactions")
    print("- Meditation sessions and fasting programs")
    print("- Journal entries and forum posts")
    print("- All preferences and settings")
    print()
    
    # Confirm with user
    response = input("Do you want to proceed with fork creation? (yes/no): ").lower().strip()
    
    if response not in ['yes', 'y']:
        print("Fork creation cancelled.")
        return
    
    try:
        # Check database connection
        if not os.environ.get('DATABASE_URL'):
            print("Error: DATABASE_URL environment variable not found.")
            print("Please ensure the database is properly configured.")
            return
        
        print("\nStarting enhanced fork creation...")
        
        # Create the fork
        fork_creator = EnhancedForkCreator()
        success, result = fork_creator.create_fork_with_user_data()
        
        if success:
            print("\n" + "=" * 50)
            print("SUCCESS! Fork created with complete user data migration")
            print("=" * 50)
            print(f"Users migrated: {result['users_count']}")
            print(f"Total data records: {result['total_records']}")
            print(f"Export file: {result['export_path']}")
            print(f"Backup location: {result['backup_dir']}")
            print(f"Log file: {result['fork_log']}")
            print("\nAll users can now log in with their original passwords")
            print("and will find all their data intact in the new fork.")
            print("=" * 50)
        else:
            print(f"\nFork creation failed: {result}")
            print("Please check the logs for more details.")
            
    except Exception as e:
        print(f"\nError during fork creation: {str(e)}")
        print("Please ensure:")
        print("1. Database is accessible")
        print("2. All required dependencies are installed")
        print("3. Sufficient disk space is available")

if __name__ == "__main__":
    main()