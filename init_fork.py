#!/usr/bin/env python3
"""
Initialize a new fork of the AI-BUDDY application.
This script sets up the database, authentication, and verifies
all required integrations are working properly.

It also identifies and utilizes the latest documentation files
to ensure the fork is set up with the most current information.
"""

import os
import sys
import logging
import subprocess
import time
import re
import glob
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('fork_init.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def find_latest_documentation():
    """Find the latest documentation files by date in the docs folder.
    
    Looks for documents with dates in the filename (YYYY-MM-DD format)
    and returns the latest versions.
    """
    latest_docs = {}
    date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')
    
    # Get all markdown files in the docs directory
    doc_files = glob.glob("docs/*.md")
    
    for doc_file in doc_files:
        filename = os.path.basename(doc_file)
        match = date_pattern.search(filename)
        
        # Skip files without dates in the name
        if not match:
            continue
            
        date_str = match.group(1)
        base_name = re.sub(r'-\d{4}-\d{2}-\d{2}', '', filename)
        
        # Get the document type/category (before the date)
        doc_type = base_name.split('-')[0] if '-' in base_name else base_name
        
        # If we haven't seen this doc type or we've found a newer version
        if doc_type not in latest_docs or latest_docs[doc_type]['date'] < date_str:
            latest_docs[doc_type] = {
                'path': doc_file,
                'date': date_str,
                'filename': filename
            }
    
    logger.info(f"Found {len(latest_docs)} latest documentation files by date")
    for doc_type, info in latest_docs.items():
        logger.info(f"Latest {doc_type} documentation: {info['filename']} ({info['date']})")
    
    return latest_docs

def init_database():
    """Initialize database connection and verify access"""
    logger.info("Initializing database...")
    
    # Check if required environment variables are present
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable not found")
        return False
    
    try:
        # For fork initialization, we use --force-reinit to ensure a clean migration state
        logger.info("Running database migrations with forced reinitialization...")
        result = subprocess.run(
            ['python', 'run_migrations.py', '--force-reinit'],
            capture_output=True,
            text=True,
            check=False  # Don't raise exception on non-zero exit code, we'll handle it manually
        )
        
        if result.returncode == 0 and "Database migrations completed successfully" in result.stdout:
            logger.info("Database migrations completed successfully")
            return True
        else:
            logger.error(f"Database migration failed with exit code {result.returncode}")
            logger.error(f"Output: {result.stdout}")
            logger.error(f"Error output: {result.stderr}")
            
            # Try once more without forced reinitialization (just in case)
            logger.info("Retrying database migrations without forced reinitialization...")
            retry_result = subprocess.run(
                ['python', 'run_migrations.py'],
                capture_output=True,
                text=True,
                check=False
            )
            
            if retry_result.returncode == 0 and "Database migrations completed successfully" in retry_result.stdout:
                logger.info("Database migrations completed successfully on retry")
                return True
            else:
                logger.error("Database migrations failed on retry")
                logger.error(f"Output: {retry_result.stdout}")
                logger.error(f"Error output: {retry_result.stderr}")
                return False
            
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False

def verify_environment():
    """Verify required environment variables"""
    logger.info("Verifying environment variables...")
    
    required_vars = [
        'DATABASE_URL',
        'FLASK_SECRET_KEY'
    ]
    
    optional_apis = [
        'OPENAI_API_KEY',
        'OURA_API_KEY',
        'ULTRAHUMAN_API_KEY',
        'GOOGLE_MAPS_API_KEY'
    ]
    
    # Check required variables
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    # Check optional API keys
    missing_apis = [api for api in optional_apis if not os.environ.get(api)]
    if missing_apis:
        logger.warning(f"Missing optional API keys: {', '.join(missing_apis)}")
        logger.warning("Some features may not work without these API keys")
    
    logger.info("Environment verification completed")
    return True

def verify_biometric_data():
    """Verify biometric data integration"""
    logger.info("Verifying biometric data integration...")
    
    try:
        result = subprocess.run(
            ['python', 'verify_biometric_data.py'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Biometric data verification successful")
            logger.info(f"Output: {result.stdout}")
            return True
        else:
            logger.warning("Biometric data verification failed")
            logger.warning(f"Output: {result.stdout}")
            logger.error(f"Error: {result.stderr}")
            logger.warning("The application will still work, but smart ring features will be limited")
            return False
            
    except Exception as e:
        logger.error(f"Error during biometric data verification: {str(e)}")
        return False

def setup_default_user():
    """Set up the default user with ring data access"""
    logger.info("Setting up default user...")
    
    try:
        result = subprocess.run(
            ['python', 'setup_auth.py'],
            capture_output=True,
            text=True
        )
        
        if "Setup completed successfully" in result.stdout:
            logger.info("Default user setup completed successfully")
            return True
        else:
            logger.error("Default user setup failed")
            logger.error(f"Error output: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error setting up default user: {str(e)}")
        return False

def verify_meditation_feature():
    """Verify the meditation feature is properly set up"""
    logger.info("Verifying meditation feature functionality...")
    
    try:
        # Check if verification script exists
        if not os.path.isfile('verify_meditation_feature.py'):
            logger.warning("Meditation verification script not found. Skipping verification.")
            return True
            
        result = subprocess.run(
            ['python', 'verify_meditation_feature.py'],
            capture_output=True,
            text=True
        )
        
        # Log output regardless of success
        for line in result.stdout.splitlines():
            if line.strip():
                logger.info(f"[MEDITATION VERIFY] {line.strip()}")
        
        if result.returncode == 0:
            logger.info("Meditation feature verification successful")
            return True
        else:
            logger.warning("Meditation feature verification found issues")
            logger.warning("Some meditation functionality may not work correctly")
            logger.warning(f"Error output: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error during meditation feature verification: {str(e)}")
        return False

def init_fork():
    """Main initialization function"""
    start_time = datetime.now()
    logger.info(f"Starting fork initialization at {start_time}")
    
    # Find latest documentation files by date
    latest_docs = find_latest_documentation()
    latest_biometric_docs = [doc for doc_type, doc in latest_docs.items() 
                           if 'biometric' in doc_type.lower() or 'ring' in doc_type.lower()]
    latest_meditation_docs = [doc for doc_type, doc in latest_docs.items() 
                             if 'meditation' in doc_type.lower()]
    latest_fork_docs = [doc for doc_type, doc in latest_docs.items()
                       if 'fork' in doc_type.lower() or 'init' in doc_type.lower()]
    latest_location_docs = [doc for doc_type, doc in latest_docs.items()
                          if 'location' in doc_type.lower() or 'wellness' in doc_type.lower()]
                          
    # Check for manually created documentation files that might not have dates in filenames
    if os.path.exists('docs/BIOMETRIC_DATA_SETUP.md'):
        logger.info("Found biometric data setup documentation")
    if os.path.exists('docs/meditation_challenges_documentation.md'):
        logger.info("Found meditation challenges documentation")  
    if os.path.exists('docs/FORK_INITIALIZATION_GUIDE_2025_05_03.md'):
        logger.info("Found fork initialization guide (May 2025)")
    if os.path.exists('docs/location_wellness_documentation.md'):
        logger.info("Found location wellness documentation")
    
    # Print banner
    print("\n" + "="*50)
    print("  AI-BUDDY FORK INITIALIZATION")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*50 + "\n")
    
    # Verify environment first
    if not verify_environment():
        logger.error("Environment verification failed, aborting initialization")
        return False
    
    # Initialize database
    if not init_database():
        logger.error("Database initialization failed, aborting initialization")
        return False
    
    # Set up default user
    if not setup_default_user():
        logger.error("Default user setup failed, aborting initialization")
        return False
    
    # Verify biometric data integration
    biometric_status = verify_biometric_data()
    if not biometric_status:
        logger.warning("Biometric data verification failed, but continuing with initialization")
        logger.warning("You may need to add API keys for Oura and/or Ultrahuman rings")
        if latest_biometric_docs:
            latest_biometric_doc = latest_biometric_docs[0]
            logger.info(f"Latest biometric documentation available: {latest_biometric_doc['filename']} ({latest_biometric_doc['date']})")
    
    # Verify meditation feature
    meditation_status = verify_meditation_feature()
    if not meditation_status:
        logger.warning("Meditation feature verification found issues, but continuing with initialization")
        if latest_meditation_docs:
            latest_meditation_doc = latest_meditation_docs[0]
            logger.warning(f"Please check {latest_meditation_doc['path']} (dated {latest_meditation_doc['date']}) for details")
        else:
            logger.warning("Please check docs/updated_voice_guidance_meditation_documentation.md for details")
    
    # Print completion message
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "="*50)
    print("  AI-BUDDY FORK INITIALIZATION COMPLETE")
    print(f"  Duration: {duration:.2f} seconds")
    print("="*50)
    
    print("\nApplication has been initialized successfully.")
    print("Default user credentials:")
    print("  Email: huskyauto@gmail.com")
    print("  Password: Rw-120764")
    
    # Recommend important documentation
    print("\nIMPORTANT DOCUMENTATION AVAILABLE:")
    
    if os.path.exists('docs/FORK_INITIALIZATION_GUIDE_2025_05_03.md'):
        print("  - Fork Setup: docs/FORK_INITIALIZATION_GUIDE_2025_05_03.md")
    
    if os.path.exists('docs/BIOMETRIC_DATA_SETUP.md'):
        print("  - Biometric Setup: docs/BIOMETRIC_DATA_SETUP.md")
        
    if os.path.exists('docs/meditation_challenges_documentation.md'):
        print("  - Meditation Challenges: docs/meditation_challenges_documentation.md")
        
    if os.path.exists('docs/location_wellness_documentation.md'):
        print("  - Location Wellness: docs/location_wellness_documentation.md")
    
    # Biometric integration warning    
    if not biometric_status:
        print("\nWARNING: Biometric data integration not fully configured.")
        print("To enable smart ring features, add these environment variables:")
        print("  OURA_API_KEY - for Oura Ring integration")
        print("  ULTRAHUMAN_API_KEY - for Ultrahuman Ring integration")
        if latest_biometric_docs:
            latest_doc = latest_biometric_docs[0]
            print(f"\nFor the latest biometric setup instructions, see:")
            print(f"  {latest_doc['path']} (updated on {latest_doc['date']})")
        else:
            print("\nFor biometric setup instructions, see:")
            print("  docs/BIOMETRIC_DATA_SETUP.md")
    
    # Meditation feature warning
    if not meditation_status:
        print("\nWARNING: Meditation feature verification found issues.")
        if latest_meditation_docs:
            latest_doc = latest_meditation_docs[0]
            print(f"Please consult the latest meditation documentation:")
            print(f"  {latest_doc['path']} (updated on {latest_doc['date']})")
        else:
            print("Please consult docs/meditation_challenges_documentation.md")
        print("And run 'python verify_meditation_feature.py' for more details")
    
    # List all latest documentation files found
    if latest_docs:
        print("\nLatest documentation files found (by date):")
        for doc_type, info in latest_docs.items():
            print(f"  - {info['filename']} ({info['date']})")
    
    # Verification tools
    print("\nVERIFICATION TOOLS AVAILABLE:")
    if os.path.exists('verify_biometric_data.py'):
        print("  - Biometric Data: python verify_biometric_data.py")
    if os.path.exists('verify_meditation_feature.py'):
        print("  - Meditation Features: python verify_meditation_feature.py")
    if os.path.exists('verify_fork_integrity.py'):
        print("  - Complete Fork: python verify_fork_integrity.py --report")
    
    print("\nYou can now start the application with:")
    print("  python main.py")
    
    return True

if __name__ == "__main__":
    success = init_fork()
    sys.exit(0 if success else 1)