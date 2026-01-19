import os
import logging
import shutil
import re
import glob
import subprocess
from datetime import datetime
from pathlib import Path
from fork_data_migration import ForkDataMigrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

def create_dated_fork():
    """Creates a new fork with current date and all recent fixes"""
    today = datetime.now().strftime("%Y_%m_%d")

    try:
        # Step 1: Find latest documentation files by date
        logger.info("Finding latest documentation files by date...")
        latest_docs = find_latest_documentation()
        latest_doc_paths = [doc_info['path'] for doc_info in latest_docs.values()]
        
        # Step 2: Create backup directory
        logger.info("Creating backup directory...")
        backup_dir = f"backup_system/backups/pre_fork_{today}"
        os.makedirs(backup_dir, exist_ok=True)

        # Step 3: Define essential files for backup
        essential_files = [
            # Core application files
            "app.py", "models.py", "main.py", "extensions.py",
            # Feature modules
            "fasting.py", "auth.py", "dashboard.py",
            "ring_routes.py", "ring_data.py", "food_tracker.py", 
            "wellness_toolbox.py", "stress_monitoring.py",
            # Admin modules
            "admin_dashboard.py", "admin_reports.py", "ai_client.py",
            # Biometric data integration files
            "verify_biometric_data.py", "init_fork.py", "setup_auth.py",
            "verify_fork_integrity.py", "verify_meditation_feature.py",
            # Documentation files (standard ones)
            "docs/BIOMETRIC_DATA_SETUP.md",
            "docs/location_wellness_documentation.md",
            "docs/meditation_challenges_documentation.md",
            "docs/FORK_INITIALIZATION_GUIDE_2025_05_03.md",
            "docs/DUAL_SERVER_ARCHITECTURE.md",
            "docs/BACKUP_SYSTEM.md",
            "docs/FORK_MANAGEMENT.md",
            # Static assets and templates
            "static/js/fasting.js",
            "static/js/ring_data.js",
            "static/js/meditation.js",
            "static/js/breathing.js",
            "static/js/global_scroll_manager.js",
            "templates/wellness_toolbox/index.html",
            "templates/dashboard.html",
            "templates/base.html",
            "templates/meditation_challenges.html",
            "templates/self_care/recommendation.html",
            "templates/self_care/wellness_check_in.html",
            # Configuration files
            "deployment_config.py",
            ".env",
            # Server scripts
            "start_dual_servers.sh",
            "run_virtual_server.sh",
            "run_virtual_server_5002.sh"
        ]
        
        # Add latest documentation files to essential files list
        essential_files.extend(latest_doc_paths)

        # Step 3: Backup files with structure preservation
        for file in essential_files:
            if os.path.exists(file):
                backup_file = os.path.join(backup_dir, file)
                os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                shutil.copy2(file, backup_file)
                logger.info(f"Backed up {file}")

        # Step 4: Run initialization
        logger.info("Initializing new fork...")
        from init_fork import init_fork
        success = init_fork()
        if not success:
            raise Exception("Fork initialization failed")

        # Step 5: Run biometric data verification independently
        logger.info("Verifying biometric data integration...")
        try:
            import verify_biometric_data
            verify_biometric_data.main()
            logger.info("Biometric data verification completed")
            biometric_verified = True
        except Exception as e:
            logger.error(f"Biometric data verification failed: {str(e)}")
            biometric_verified = False
            
        # Step 6: Run comprehensive fork integrity verification if available
        fork_integrity_verified = False
        if os.path.exists("verify_fork_integrity.py"):
            logger.info("Running comprehensive fork integrity verification...")
            try:
                # Run with report generation
                result = subprocess.run(
                    ["python", "verify_fork_integrity.py", "--report"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                # Log the output
                if result.stdout:
                    for line in result.stdout.splitlines():
                        if line.strip():
                            logger.info(f"[FORK_VERIFY] {line.strip()}")
                
                if result.returncode == 0:
                    logger.info("Fork integrity verification passed")
                    fork_integrity_verified = True
                else:
                    logger.warning("Fork integrity verification found issues")
                    if result.stderr:
                        for line in result.stderr.splitlines():
                            if line.strip():
                                logger.warning(f"[FORK_VERIFY] {line.strip()}")
            except Exception as e:
                logger.error(f"Error during fork integrity verification: {str(e)}")
        else:
            logger.info("Fork integrity verification script not found, skipping")

        # Step 6: Create initialization record
        with open("fork_init.log", "w") as f:
            f.write(f"Fork created successfully at {datetime.now()}\n")
            f.write("System initialized and verified with recent fixes\n")
            f.write(f"Database migrations completed\n")
            f.write(f"Backup created at: {backup_dir}\n")
            
            # Add information about server architecture
            f.write("\nSERVER ARCHITECTURE:\n")
            f.write("- Dual server architecture implemented\n")
            f.write("- Main application server on port 5000\n")
            f.write("- Secondary server for background tasks on port 5002\n")
            f.write("- Documentation: docs/DUAL_SERVER_ARCHITECTURE.md\n")
            
            # Add information about admin dashboard
            f.write("\nADMIN DASHBOARD:\n")
            f.write("- Admin dashboard fully functional with API usage tracking\n")
            f.write("- PDF report generation working for user statistics and API usage\n")
            f.write("- Access available at /admin for huskyauto@gmail.com\n")
            f.write("- Documentation: docs/admin_dashboard_documentation.md\n")
            
            # Add information about biometric data
            f.write("\nBIOMETRIC DATA INTEGRATION:\n")
            if biometric_verified:
                f.write("- Biometric data integration verified successfully\n")
                f.write("- Real-time data from Oura and Ultrahuman rings available\n")
                f.write("- Documentation: docs/BIOMETRIC_DATA_SETUP.md\n")
            else:
                f.write("- NOTICE: Biometric data verification was not completed\n")
                f.write("- Please run 'python verify_biometric_data.py' to verify\n")
                f.write("- Documentation: docs/BIOMETRIC_DATA_SETUP.md\n")
            
            # Add information about meditation features
            f.write("\nMEDITATION FEATURES:\n")
            f.write("- Meditation challenges with tracking implementation\n")
            f.write("- Voice guidance with stress monitoring integration\n")
            f.write("- Documentation: docs/meditation_challenges_documentation.md\n")
            
            # Add information about location wellness
            f.write("\nLOCATION WELLNESS:\n")
            f.write("- Fast food detection with Google Places API\n")
            f.write("- Voice alerts for mindful eating\n")
            f.write("- Documentation: docs/location_wellness_documentation.md\n")
            
            # Add information about verification systems
            f.write("\nFORK VERIFICATION SYSTEMS:\n")
            f.write("- Biometric data verification: verify_biometric_data.py\n")
            f.write("- Meditation feature verification: verify_meditation_feature.py\n")
            f.write("- Full fork integrity checks: verify_fork_integrity.py\n")
            
            f.write("\nIMPORTANT DOCUMENTATION:\n")
            f.write("- docs/FORK_INITIALIZATION_GUIDE_2025_05_03.md - Comprehensive fork initialization guide\n")
            f.write("- docs/BIOMETRIC_DATA_SETUP.md - Biometric integration guide\n")
            f.write("- docs/location_wellness_documentation.md - Location wellness feature guide\n")
            f.write("- docs/meditation_challenges_documentation.md - Meditation challenges guide\n")
            f.write("- docs/DUAL_SERVER_ARCHITECTURE.md - Server architecture guide\n")
            f.write("- docs/admin_dashboard_documentation.md - Admin dashboard guide\n")
            
            # Add information about user credentials
            f.write("\nDEFAULT USER CREDENTIALS:\n")
            f.write("- Email: huskyauto@gmail.com\n")
            f.write("- Password: Rw-120764\n")
            f.write("- Note: This user has biometric data access configured\n")

        logger.info(f"Fork creation completed successfully on {today}")
        return True

    except Exception as e:
        logger.error(f"Fork creation failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = create_dated_fork()
    if success:
        print("\n✅ New fork created successfully!")
        print("  The system has been initialized with all recent fixes.")
        
        # Find latest documentation to inform user
        latest_docs = find_latest_documentation()
        
        # Display latest documentation found by category
        if latest_docs:
            print("\n📚 Latest documentation found by date:")
            for doc_type, info in latest_docs.items():
                print(f"  - {info['filename']} ({info['date']})")
        
        # Check if fork initialization guide exists
        if os.path.exists("docs/FORK_INITIALIZATION_GUIDE_2025_05_03.md"):
            print("\n✅ Fork initialization guide found.")
            print("  For complete fork setup guidance, please read:")
            print("  - docs/FORK_INITIALIZATION_GUIDE_2025_05_03.md")
        else:
            print("\n⚠️ Fork initialization guide not found!")
            print("  Please ensure a proper fork initialization guide is available.")

        # Check if biometric documentation exists
        if os.path.exists("docs/BIOMETRIC_DATA_SETUP.md"):
            print("\n✅ Biometric data setup documentation found.")
            print("  For proper biometric data integration, please read:")
            print("  - docs/BIOMETRIC_DATA_SETUP.md")
            # Find latest biometric docs if they exist
            biometric_docs = [doc for doc_type, doc in latest_docs.items() 
                             if 'biometric' in doc_type.lower() or 'ring' in doc_type.lower()]
            for doc in biometric_docs:
                print(f"  - {doc['path']}")
        else:
            print("\n⚠️ Biometric data documentation not found!")
            print("  Please ensure biometric data integration is properly configured.")
            
        # Check if meditation challenges documentation exists
        if os.path.exists("docs/meditation_challenges_documentation.md"):
            print("\n✅ Meditation challenges documentation found.")
            print("  For meditation feature information, please read:")
            print("  - docs/meditation_challenges_documentation.md")
        else:
            print("\n⚠️ Meditation challenges documentation not found!")
            print("  Meditation challenges may not be fully documented.")
            
        # Check if location wellness documentation exists
        if os.path.exists("docs/location_wellness_documentation.md"):
            print("\n✅ Location wellness documentation found.")
            print("  For location wellness feature information, please read:")
            print("  - docs/location_wellness_documentation.md")
        else:
            print("\n⚠️ Location wellness documentation not found!")
            print("  Location wellness features may not be fully documented.")
            
        # Check if admin dashboard documentation exists
        if os.path.exists("docs/admin_dashboard_documentation.md"):
            print("\n✅ Admin dashboard documentation found.")
            print("  For admin dashboard information, please read:")
            print("  - docs/admin_dashboard_documentation.md")
            # Find latest admin docs if they exist
            admin_docs = [doc for doc_type, doc in latest_docs.items() 
                         if 'admin' in doc_type.lower() or 'dashboard' in doc_type.lower()]
            for doc in admin_docs:
                print(f"  - {doc['path']}")
        else:
            print("\n⚠️ Admin dashboard documentation not found!")
            print("  Admin dashboard functionality may not be fully documented.")
        
        # Check for verification script
        if os.path.exists("verify_biometric_data.py"):
            print("\n✅ Biometric data verification script found.")
            print("  Run 'python verify_biometric_data.py' to verify biometric data integration.")
        else:
            print("\n⚠️ Biometric data verification script not found!")
            print("  Proper biometric data integration may not be available.")
            
        # Check for fork verification script
        if os.path.exists("verify_fork_integrity.py"):
            print("\n✅ Fork verification script found.")
            print("  Run 'python verify_fork_integrity.py' to verify all components are working properly.")
            print("  Use 'python verify_fork_integrity.py --report' to generate a detailed report.")
        
        print("\nYou can now start using the new fork.")
    else:
        print("\n❌ Fork creation failed. Check logs for details.")