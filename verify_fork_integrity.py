#!/usr/bin/env python3
"""
Comprehensive Fork Verification Script for AI-BUDDY

This script performs extensive verification of a new fork to ensure
all features and components are correctly transferred and working:

1. Database schema validation
2. API endpoint testing
3. JavaScript file integrity checking
4. Environment variable verification
5. Component validation (breathing exercises, meditation, etc.)
6. Cross-component integration testing
7. File permission checking

Usage:
    python verify_fork_integrity.py [--fix] [--report]

Options:
    --fix       Attempt to fix any issues found
    --report    Generate a detailed report of verification results
"""

import argparse
import json
import logging
import os
import re
import requests
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

# Setup logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)
logger = logging.getLogger("fork_verifier")

# File handler for logging to a file
file_handler = logging.FileHandler('fork_verification.log')
file_handler.setFormatter(logging.Formatter(log_format))
logger.addHandler(file_handler)

# Add a stream handler for console output
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Constants
REQUIRED_STATIC_JS_FILES = [
    'static/js/meditation.js',
    'static/js/breathing.js',
    'static/js/global_scroll_manager.js',
    'static/js/fasting.js',
    'static/js/ring_data.js'
]

REQUIRED_TEMPLATES = [
    'templates/wellness_toolbox/index.html',
    'templates/base.html',
    'templates/dashboard.html',
    'templates/self_care/recommendation.html',
    'templates/self_care/wellness_check_in.html',
    'templates/meditation_challenges.html'
]

REQUIRED_PY_FILES = [
    'app.py',
    'main.py',
    'models.py',
    'extensions.py',
    'wellness_toolbox.py',
    'self_care.py',
    'ring_data.py',
    'ring_routes.py',
    'auth.py',
    'verify_biometric_data.py',
    'verify_meditation_feature.py',
    'init_fork.py',
    'create_new_fork.py',
    'challenge_routes.py'
]

REQUIRED_DOCUMENTATION_FILES = [
    'docs/BIOMETRIC_DATA_SETUP.md',
    'docs/location_wellness_documentation.md',
    'docs/meditation_challenges_documentation.md',
    'docs/FORK_INITIALIZATION_GUIDE_2025_05_03.md',
    'docs/DUAL_SERVER_ARCHITECTURE.md'
]

REQUIRED_CONFIGURATION_FILES = [
    'start_dual_servers.sh',
    'run_virtual_server.sh',
    'run_virtual_server_5002.sh'
]

API_ENDPOINTS_TO_TEST = [
    '/api/meditation/stress',
    '/api/breathing/guidance/478?duration=2',
    '/api/breathing/guidance/box?duration=2',
    '/api/ring/data'
]

# Component tests
COMPONENT_TESTS = {
    "meditation": {
        "files": [
            "static/js/meditation.js",
            "templates/wellness_toolbox/index.html"
        ],
        "patterns": {
            "static/js/meditation.js": [
                r"document\.addEventListener\('DOMContentLoaded'",
                r"function\s+speakText",
                r"function\s+initializeAudio",
                r"loadStressLevelData\(\)"
            ],
            "templates/wellness_toolbox/index.html": [
                r"meditation-guidance",
                r"test-sound",
                r"background-sound",
                r"meditation-controls",
                r"current-stress-level"
            ]
        }
    },
    "breathing": {
        "files": [
            "static/js/breathing.js"
        ],
        "patterns": {
            "static/js/breathing.js": [
                r"478\s+Breathing",
                r"Box\s+Breathing",
                r"await\s+speak",
                r"Inhale.*4\s+seconds",
                r"Hold.*7\s+seconds",
                r"Exhale.*8\s+seconds"
            ]
        }
    },
    "self_care": {
        "files": [
            "self_care.py",
            "templates/self_care/recommendation.html"
        ],
        "patterns": {
            "self_care.py": [
                r"get_ring_data",
                r"generate_self_care_recommendation",
                r"get_user_recommendations"
            ],
            "templates/self_care/recommendation.html": [
                r"recommendation-card",
                r"recommendation-source"
            ]
        }
    }
}


class ForkVerifier:
    """Main verification class for AI-BUDDY forks."""
    
    def __init__(self, fix_issues=False, generate_report=False):
        """Initialize the verifier."""
        self.fix_issues = fix_issues
        self.generate_report = generate_report
        self.issues = []
        self.flask_process = None
        self.flask_url = "http://localhost:5000"
        
    def log_issue(self, component, description, severity="HIGH", fix_instructions=None):
        """Log an issue found during verification."""
        issue = {
            "component": component,
            "description": description,
            "severity": severity,
            "fix_instructions": fix_instructions,
            "timestamp": datetime.now().isoformat()
        }
        self.issues.append(issue)
        if severity == "HIGH":
            logger.error(f"{component}: {description}")
        elif severity == "MEDIUM":
            logger.warning(f"{component}: {description}")
        else:
            logger.info(f"{component}: {description}")
            
    def verify_file_exists(self, filepath):
        """Verify that a file exists."""
        if not os.path.exists(filepath):
            self.log_issue(
                component="Files",
                description=f"Required file not found: {filepath}",
                severity="HIGH",
                fix_instructions=f"Restore {filepath} from the original repository"
            )
            return False
        return True
    
    def verify_database_schema(self):
        """Verify database schema."""
        logger.info("Verifying database schema...")
        
        try:
            # Import models to check schema without running migrations
            from app import create_app, db
            app = create_app({"TESTING": True})
            
            with app.app_context():
                # Get all table names
                table_names = []
                for table in db.metadata.tables.values():
                    table_names.append(table.name)
                
                logger.info(f"Found {len(table_names)} tables in the database schema")
                
                # Verify key required tables
                required_tables = [
                    'users', 'meditation_sessions', 'stress_levels', 
                    'food_log', 'water_log', 'fasting_sessions'
                ]
                
                for table in required_tables:
                    if table not in table_names:
                        self.log_issue(
                            component="Database",
                            description=f"Required table '{table}' missing from database schema",
                            severity="HIGH",
                            fix_instructions=f"Run migrations to create the '{table}' table"
                        )
            
            logger.info("Database schema verification complete")
        except Exception as e:
            self.log_issue(
                component="Database",
                description=f"Error verifying database schema: {str(e)}",
                severity="HIGH"
            )
    
    def verify_file_integrity(self):
        """Verify the integrity of required files."""
        logger.info("Verifying file integrity...")
        
        # Check all required files exist
        all_required_files = (
            REQUIRED_STATIC_JS_FILES +
            REQUIRED_TEMPLATES + 
            REQUIRED_PY_FILES + 
            REQUIRED_DOCUMENTATION_FILES + 
            REQUIRED_CONFIGURATION_FILES
        )
        missing_files = []
        
        # Check static JS files
        logger.info("Checking static JS files...")
        for filepath in REQUIRED_STATIC_JS_FILES:
            if not self.verify_file_exists(filepath):
                missing_files.append(filepath)
        
        # Check templates
        logger.info("Checking templates...")
        for filepath in REQUIRED_TEMPLATES:
            if not self.verify_file_exists(filepath):
                missing_files.append(filepath)
        
        # Check Python files
        logger.info("Checking Python files...")
        for filepath in REQUIRED_PY_FILES:
            if not self.verify_file_exists(filepath):
                missing_files.append(filepath)
        
        # Check documentation files
        logger.info("Checking documentation files...")
        for filepath in REQUIRED_DOCUMENTATION_FILES:
            if not self.verify_file_exists(filepath):
                missing_files.append(filepath)
                self.log_issue(
                    component="Documentation",
                    description=f"Required documentation file not found: {filepath}",
                    severity="MEDIUM",
                    fix_instructions=f"Restore {filepath} from the original repository or recreate it"
                )
        
        # Check configuration files
        logger.info("Checking configuration files...")
        for filepath in REQUIRED_CONFIGURATION_FILES:
            if not self.verify_file_exists(filepath):
                missing_files.append(filepath)
                self.log_issue(
                    component="Configuration",
                    description=f"Required configuration file not found: {filepath}",
                    severity="HIGH",
                    fix_instructions=f"Restore {filepath} from the original repository"
                )
            else:
                # Check if the file is executable and make it executable if needed
                if filepath.endswith('.sh') and not os.access(filepath, os.X_OK):
                    logger.warning(f"Configuration file not executable: {filepath}")
                    self.log_issue(
                        component="Configuration",
                        description=f"Shell script not executable: {filepath}",
                        severity="MEDIUM",
                        fix_instructions=f"Run 'chmod +x {filepath}' to make it executable"
                    )
                    
                    # Fix the issue if fix_issues is enabled
                    if self.fix_issues:
                        try:
                            os.chmod(filepath, os.stat(filepath).st_mode | 0o111)
                            logger.info(f"Fixed permissions for {filepath}")
                        except Exception as e:
                            logger.error(f"Failed to make {filepath} executable: {e}")
        
        if missing_files:
            logger.error(f"Missing {len(missing_files)} required files")
        else:
            logger.info("All required files are present")
            
        # Verify key files have minimum sizes (not zero or too small)
        for filepath in all_required_files:
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                if file_size < 100:  # Arbitrary minimum size to detect truncated files
                    self.log_issue(
                        component="Files",
                        description=f"File too small (possibly truncated): {filepath} ({file_size} bytes)",
                        severity="HIGH",
                        fix_instructions=f"Restore {filepath} from the original repository"
                    )
    
    def verify_component(self, component_name):
        """Verify a specific component."""
        logger.info(f"Verifying {component_name} component...")
        
        if component_name not in COMPONENT_TESTS:
            logger.warning(f"No tests defined for component: {component_name}")
            return
        
        component = COMPONENT_TESTS[component_name]
        
        # Verify all required files for this component exist
        for filepath in component["files"]:
            self.verify_file_exists(filepath)
        
        # Check for required patterns in each file
        for filepath, patterns in component["patterns"].items():
            if not os.path.exists(filepath):
                continue
                
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for pattern in patterns:
                if not re.search(pattern, content):
                    self.log_issue(
                        component=component_name,
                        description=f"Pattern not found in {filepath}: {pattern}",
                        severity="HIGH",
                        fix_instructions=f"Restore the code matching pattern '{pattern}' in {filepath}"
                    )
        
        logger.info(f"{component_name} component verification complete")
    
    def verify_all_components(self):
        """Verify all defined components."""
        logger.info("Starting component verification...")
        
        for component_name in COMPONENT_TESTS.keys():
            self.verify_component(component_name)
        
        logger.info("Component verification complete")
    
    def start_flask_server(self):
        """Start a Flask development server for API testing."""
        logger.info("Starting Flask server for API testing...")
        
        try:
            # Start the Flask server in a subprocess
            self.flask_process = subprocess.Popen(
                ["python", "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for server to start
            time.sleep(3)
            
            # Verify server is running
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    response = requests.get(f"{self.flask_url}/")
                    if response.status_code == 200:
                        logger.info("Flask server started successfully")
                        return True
                except:
                    if attempt < max_attempts - 1:
                        logger.info(f"Waiting for Flask server to start (attempt {attempt + 1}/{max_attempts})...")
                        time.sleep(2)
            
            self.log_issue(
                component="Flask",
                description="Failed to start Flask server for API testing",
                severity="HIGH"
            )
            return False
            
        except Exception as e:
            self.log_issue(
                component="Flask",
                description=f"Error starting Flask server: {str(e)}",
                severity="HIGH"
            )
            return False
    
    def stop_flask_server(self):
        """Stop the Flask development server."""
        if self.flask_process:
            logger.info("Stopping Flask server...")
            self.flask_process.terminate()
            self.flask_process.wait()
            self.flask_process = None
    
    def test_api_endpoints(self):
        """Test API endpoints."""
        if not self.start_flask_server():
            return
        
        try:
            logger.info("Testing API endpoints...")
            
            for endpoint in API_ENDPOINTS_TO_TEST:
                try:
                    url = f"{self.flask_url}{endpoint}"
                    logger.info(f"Testing endpoint: {url}")
                    
                    response = requests.get(url)
                    
                    if response.status_code != 200:
                        self.log_issue(
                            component="API",
                            description=f"Endpoint {endpoint} returned status code {response.status_code}",
                            severity="HIGH"
                        )
                        continue
                    
                    # Parse response as JSON
                    try:
                        data = response.json()
                        if data.get("status") != "success":
                            self.log_issue(
                                component="API",
                                description=f"Endpoint {endpoint} returned error status: {data.get('status')}",
                                severity="MEDIUM"
                            )
                    except:
                        self.log_issue(
                            component="API",
                            description=f"Endpoint {endpoint} returned invalid JSON response",
                            severity="MEDIUM"
                        )
                
                except Exception as e:
                    self.log_issue(
                        component="API",
                        description=f"Error testing endpoint {endpoint}: {str(e)}",
                        severity="HIGH"
                    )
            
            logger.info("API endpoint testing complete")
        
        finally:
            self.stop_flask_server()
    
    def verify_environment_variables(self):
        """Verify required environment variables."""
        logger.info("Verifying environment variables...")
        
        required_vars = [
            "DATABASE_URL",
            "FLASK_APP",
            "OPENAI_API_KEY"
        ]
        
        optional_vars = [
            "OURA_API_KEY",
            "ULTRAHUMAN_API_KEY",
            "GOOGLE_MAPS_API_KEY"
        ]
        
        for var in required_vars:
            if not os.environ.get(var):
                self.log_issue(
                    component="Environment",
                    description=f"Required environment variable not set: {var}",
                    severity="HIGH",
                    fix_instructions=f"Set the {var} environment variable in .env file"
                )
        
        for var in optional_vars:
            if not os.environ.get(var):
                self.log_issue(
                    component="Environment",
                    description=f"Optional environment variable not set: {var}",
                    severity="MEDIUM",
                    fix_instructions=f"Set the {var} environment variable in .env file if using related features"
                )
        
        logger.info("Environment variable verification complete")
    
    def verify_breathing_exercises(self):
        """Specifically verify the breathing exercises component."""
        logger.info("Verifying breathing exercises component...")
        
        breathing_js = "static/js/breathing.js"
        if not os.path.exists(breathing_js):
            self.log_issue(
                component="Breathing",
                description=f"Breathing exercises JavaScript file not found: {breathing_js}",
                severity="HIGH"
            )
            return
        
        with open(breathing_js, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify 478 breathing pattern
        if "// 4-7-8 Breathing Pattern" in content:
            # Check for correct timings
            inhale_pattern = re.search(r'await timer\((\d+)\);\s*//\s*4 second inhale', content)
            hold_pattern = re.search(r'await timer\((\d+)\);\s*//\s*7 second hold', content)
            exhale_pattern = re.search(r'await timer\((\d+)\);\s*//\s*8 second exhale', content)
            
            if not inhale_pattern or int(inhale_pattern.group(1)) != 4000:
                self.log_issue(
                    component="Breathing",
                    description="Incorrect inhale timing for 4-7-8 breathing pattern",
                    severity="HIGH",
                    fix_instructions="Set inhale timer to 4000ms (4 seconds) in breathing.js"
                )
            
            if not hold_pattern or int(hold_pattern.group(1)) != 7000:
                self.log_issue(
                    component="Breathing",
                    description="Incorrect hold timing for 4-7-8 breathing pattern",
                    severity="HIGH",
                    fix_instructions="Set hold timer to 7000ms (7 seconds) in breathing.js"
                )
            
            if not exhale_pattern or int(exhale_pattern.group(1)) != 8000:
                self.log_issue(
                    component="Breathing",
                    description="Incorrect exhale timing for 4-7-8 breathing pattern",
                    severity="HIGH",
                    fix_instructions="Set exhale timer to 8000ms (8 seconds) in breathing.js"
                )
        else:
            self.log_issue(
                component="Breathing",
                description="4-7-8 Breathing Pattern code section not found",
                severity="HIGH"
            )
        
        # Verify box breathing pattern
        if "// Box Breathing" in content:
            # Check for correct timings (all should be 4 seconds)
            box_patterns = re.findall(r'await timer\((\d+)\);\s*//.*4 second', content)
            if len(box_patterns) < 4 or any(int(p) != 4000 for p in box_patterns[:4]):
                self.log_issue(
                    component="Breathing",
                    description="Incorrect timing for box breathing pattern (should be 4-4-4-4)",
                    severity="HIGH",
                    fix_instructions="Set all box breathing timers to 4000ms (4 seconds) in breathing.js"
                )
        else:
            self.log_issue(
                component="Breathing",
                description="Box Breathing code section not found",
                severity="HIGH"
            )
        
        logger.info("Breathing exercises verification complete")
    
    def verify_documentation_content(self):
        """Verify the content of critical documentation files."""
        logger.info("Verifying documentation content...")
        
        # Check fork initialization guide
        fork_guide_path = 'docs/FORK_INITIALIZATION_GUIDE_2025_05_03.md'
        if os.path.exists(fork_guide_path):
            with open(fork_guide_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for key sections
                if 'Biometric Data Setup' not in content:
                    self.log_issue(
                        component="Documentation",
                        description="Fork initialization guide missing 'Biometric Data Setup' section",
                        severity="MEDIUM",
                        fix_instructions="Update the fork initialization guide to include biometric data setup instructions"
                    )
                
                if 'Database Migration' not in content:
                    self.log_issue(
                        component="Documentation",
                        description="Fork initialization guide missing 'Database Migration' section",
                        severity="MEDIUM",
                        fix_instructions="Update the fork initialization guide to include database migration instructions"
                    )
                    
                # Check for latest date
                date_match = re.search(r'Last Updated: (\w+ \d+, \d{4})', content)
                if date_match:
                    date_str = date_match.group(1)
                    try:
                        doc_date = datetime.strptime(date_str, "%B %d, %Y")
                        three_months_ago = datetime.now() - timedelta(days=90)
                        if doc_date < three_months_ago:
                            self.log_issue(
                                component="Documentation",
                                description=f"Fork initialization guide is outdated (last updated: {date_str})",
                                severity="LOW",
                                fix_instructions="Update the fork initialization guide with latest information"
                            )
                    except:
                        # Date parsing failed, ignore
                        pass
        
        # Check biometric data setup documentation
        biometric_doc_path = 'docs/BIOMETRIC_DATA_SETUP.md'
        if os.path.exists(biometric_doc_path):
            with open(biometric_doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for API key configuration sections
                if 'OURA_API_KEY' not in content or 'ULTRAHUMAN_API_KEY' not in content:
                    self.log_issue(
                        component="Documentation",
                        description="Biometric data setup documentation missing API key configuration instructions",
                        severity="MEDIUM",
                        fix_instructions="Update biometric data documentation to include instructions for both Oura and Ultrahuman API keys"
                    )
        
        # Check dual server architecture documentation
        dual_server_doc_path = 'docs/DUAL_SERVER_ARCHITECTURE.md'
        if os.path.exists(dual_server_doc_path):
            with open(dual_server_doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for required server configuration sections
                if 'port 5000' not in content.lower() or 'port 5002' not in content.lower():
                    self.log_issue(
                        component="Documentation",
                        description="Dual server architecture documentation missing port configuration details",
                        severity="MEDIUM",
                        fix_instructions="Update dual server documentation to include details for both port 5000 and 5002"
                    )
                    
                # Check for server startup instructions
                if 'start_dual_servers.sh' not in content:
                    self.log_issue(
                        component="Documentation",
                        description="Dual server architecture documentation missing startup script instructions",
                        severity="MEDIUM",
                        fix_instructions="Update dual server documentation to include instructions for start_dual_servers.sh"
                    )
                
        logger.info("Documentation content verification complete")

    def verify_all(self):
        """Run all verification tests."""
        logger.info("Starting comprehensive fork verification...")
        
        try:
            # Basic verification
            self.verify_file_integrity()
            self.verify_environment_variables()
            
            # Documentation verification
            self.verify_documentation_content()
            
            # Database verification
            self.verify_database_schema()
            
            # Component-specific verification
            self.verify_all_components()
            self.verify_breathing_exercises()
            
            # API testing (starts and stops a test server)
            self.test_api_endpoints()
            
            # Generate report if requested
            if self.generate_report:
                self.generate_verification_report()
            
            # Summary
            issue_count = len(self.issues)
            if issue_count == 0:
                logger.info("👍 Verification completed successfully with no issues found!")
                return True
            else:
                high_severity = sum(1 for issue in self.issues if issue["severity"] == "HIGH")
                medium_severity = sum(1 for issue in self.issues if issue["severity"] == "MEDIUM")
                low_severity = sum(1 for issue in self.issues if issue["severity"] == "LOW")
                
                logger.warning(f"❌ Verification completed with issues: {issue_count} total "
                              f"({high_severity} high, {medium_severity} medium, {low_severity} low)")
                return high_severity == 0  # Success if no high severity issues
                
        except Exception as e:
            logger.error(f"Error during verification: {str(e)}")
            return False
    
    def generate_verification_report(self):
        """Generate a detailed verification report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "issues": self.issues,
            "summary": {
                "total_issues": len(self.issues),
                "high_severity": sum(1 for issue in self.issues if issue["severity"] == "HIGH"),
                "medium_severity": sum(1 for issue in self.issues if issue["severity"] == "MEDIUM"),
                "low_severity": sum(1 for issue in self.issues if issue["severity"] == "LOW")
            },
            "documentation": {
                "files": {
                    path: {
                        "exists": os.path.exists(path),
                        "size": os.path.getsize(path) if os.path.exists(path) else 0
                    }
                    for path in REQUIRED_DOCUMENTATION_FILES
                },
                "dual_server_architecture": os.path.exists("docs/DUAL_SERVER_ARCHITECTURE.md"),
                "fork_initialization_guide": os.path.exists("docs/FORK_INITIALIZATION_GUIDE_2025_05_03.md"),
                "biometric_data_setup": os.path.exists("docs/BIOMETRIC_DATA_SETUP.md"),
                "meditation_challenges_docs": os.path.exists("docs/meditation_challenges_documentation.md"),
                "location_wellness_docs": os.path.exists("docs/location_wellness_documentation.md")
            },
            "configuration": {
                "files": {
                    path: {
                        "exists": os.path.exists(path),
                        "executable": os.access(path, os.X_OK) if os.path.exists(path) else False
                    }
                    for path in REQUIRED_CONFIGURATION_FILES
                }
            }
        }
        
        # Write report to file
        report_file = f"fork_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Verification report written to {report_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AI-BUDDY Fork Verification Tool")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix any issues found")
    parser.add_argument("--report", action="store_true", help="Generate a detailed report")
    
    args = parser.parse_args()
    
    verifier = ForkVerifier(fix_issues=args.fix, generate_report=args.report)
    success = verifier.verify_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()