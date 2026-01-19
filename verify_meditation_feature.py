#!/usr/bin/env python3
"""
Meditation Feature Verification Script

This script verifies that all required components for the meditation feature
are properly set up and functional after a fork operation. It should be run
as part of the fork initialization process.

Usage:
    python verify_meditation_feature.py

Author: AI-BUDDY Developer Team
Date: May 3, 2025
"""

import os
import sys
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("meditation_verification.log")
    ]
)

logger = logging.getLogger(__name__)

class MeditationVerifier:
    """Verifies the meditation feature components."""
    
    def __init__(self):
        """Initialize the verifier with paths to critical files."""
        self.required_files = [
            "static/js/meditation.js",
            "static/js/global_scroll_manager.js",
            "templates/wellness_toolbox/index.html",
            "static/css/custom.css"
        ]
        self.required_patterns = {
            "static/js/meditation.js": [
                "document.addEventListener('DOMContentLoaded'",
                "function speakText",
                "function initializeAudio",
                "document.querySelectorAll('.test-sound').forEach",
                "Promise.race"
            ],
            "templates/wellness_toolbox/index.html": [
                "meditation-guidance",
                "test-sound",
                "background-sound",
                "meditation-controls"
            ]
        }
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "file_checks": {},
            "pattern_checks": {},
            "issues": []
        }

    def check_files_exist(self):
        """Verify that all required files exist."""
        logger.info("Checking required files...")
        
        for file_path in self.required_files:
            full_path = os.path.join(os.getcwd(), file_path)
            exists = os.path.isfile(full_path)
            self.results["file_checks"][file_path] = exists
            
            if exists:
                logger.info(f"✓ File exists: {file_path}")
            else:
                logger.error(f"✗ File missing: {file_path}")
                self.results["issues"].append(f"Required file missing: {file_path}")
        
        return all(self.results["file_checks"].values())

    def check_file_patterns(self):
        """Check that files contain required code patterns."""
        logger.info("Checking required code patterns...")
        
        all_patterns_found = True
        
        for file_path, patterns in self.required_patterns.items():
            full_path = os.path.join(os.getcwd(), file_path)
            self.results["pattern_checks"][file_path] = {}
            
            if not os.path.isfile(full_path):
                logger.error(f"Cannot check patterns - file missing: {file_path}")
                for pattern in patterns:
                    self.results["pattern_checks"][file_path][pattern] = False
                all_patterns_found = False
                continue
                
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for pattern in patterns:
                    found = pattern in content
                    self.results["pattern_checks"][file_path][pattern] = found
                    
                    if found:
                        logger.info(f"✓ Pattern found in {file_path}: {pattern}")
                    else:
                        logger.error(f"✗ Pattern missing from {file_path}: {pattern}")
                        self.results["issues"].append(f"Required code pattern missing: {pattern} in {file_path}")
                        all_patterns_found = False
            except Exception as e:
                logger.error(f"Error checking patterns in {file_path}: {str(e)}")
                self.results["issues"].append(f"Error checking file: {file_path} - {str(e)}")
                all_patterns_found = False
        
        return all_patterns_found

    def check_database_tables(self):
        """Check that required database tables exist."""
        try:
            # Optional - only perform if within Flask context
            # This would require importing the Flask app and db
            # For now, we'll just log a reminder
            logger.info("Database verification requires manual check for:")
            logger.info("- meditation_sessions table")
            logger.info("- meditation_achievements table")
            return True
        except Exception as e:
            logger.error(f"Error checking database tables: {str(e)}")
            return False

    def run_verification(self):
        """Run all verification checks and return results."""
        logger.info("Starting meditation feature verification...")
        
        files_exist = self.check_files_exist()
        patterns_found = self.check_file_patterns()
        
        # Add overall status
        all_passed = files_exist and patterns_found
        self.results["verification_passed"] = all_passed
        
        if all_passed:
            logger.info("Meditation feature verification PASSED")
        else:
            logger.error("Meditation feature verification FAILED")
            logger.error(f"Issues found: {len(self.results['issues'])}")
            for issue in self.results["issues"]:
                logger.error(f"- {issue}")
                
        # Save results to file
        with open("meditation_verification_results.json", 'w') as f:
            json.dump(self.results, f, indent=2)
            
        logger.info("Verification results saved to meditation_verification_results.json")
        
        return all_passed, self.results

def print_summary(results):
    """Print a human-readable summary of verification results."""
    print("\n" + "=" * 50)
    print("MEDITATION FEATURE VERIFICATION SUMMARY")
    print("=" * 50)
    
    if results["verification_passed"]:
        print("\n✅ ALL CHECKS PASSED")
    else:
        print("\n❌ VERIFICATION FAILED")
        print("\nIssues Found:")
        for issue in results["issues"]:
            print(f"- {issue}")
    
    print("\nFile Checks:")
    for file_path, exists in results["file_checks"].items():
        status = "✓" if exists else "✗"
        print(f"{status} {file_path}")
        
    print("\nPattern Checks:")
    for file_path, patterns in results["pattern_checks"].items():
        print(f"File: {file_path}")
        for pattern, found in patterns.items():
            status = "✓" if found else "✗"
            print(f"  {status} {pattern}")
    
    print("\n" + "=" * 50)
    print("Next Steps:")
    if not results["verification_passed"]:
        print("1. Review the issues listed above")
        print("2. Consult docs/updated_voice_guidance_meditation_documentation.md")
        print("3. Fix missing files or code patterns")
        print("4. Run this verification script again")
    else:
        print("1. The meditation feature is correctly configured")
        print("2. No further action is needed")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    verifier = MeditationVerifier()
    passed, results = verifier.run_verification()
    print_summary(results)
    sys.exit(0 if passed else 1)