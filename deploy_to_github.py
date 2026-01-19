#!/usr/bin/env python3
"""
GitHub deployment script for AI-BUDDY
Handles pushing the complete codebase to GitHub repository
"""

import os
import subprocess
import sys
from datetime import datetime

def run_command(command, description=""):
    """Run a shell command and handle errors"""
    print(f"Running: {description or command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Success: {description}")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ Error: {description}")
            if result.stderr:
                print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def deploy_to_github():
    """Deploy the complete AI-BUDDY codebase to GitHub"""
    
    # GitHub repository details
    github_token = "541145"
    username = "huskyauto"
    repo_url = "https://github.com/Huskyauto/AI-BUDDY-2025-05-05-TEAMS.git"
    auth_url = f"https://{username}:{github_token}@github.com/Huskyauto/AI-BUDDY-2025-05-05-TEAMS.git"
    
    print("🚀 Starting GitHub deployment for AI-BUDDY...")
    print(f"Repository: {repo_url}")
    
    # Get current timestamp for commit message
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if we're in a git repository
    if not os.path.exists('.git'):
        print("Initializing Git repository...")
        if not run_command("git init", "Initialize Git repository"):
            return False
    
    # Configure Git user
    run_command(f'git config user.email "huskyauto@gmail.com"', "Set Git email")
    run_command(f'git config user.name "huskyauto"', "Set Git username")
    
    # Add remote origin
    print("Setting up GitHub remote...")
    run_command("git remote remove origin 2>/dev/null || true", "Remove existing origin")
    if not run_command(f'git remote add origin "{auth_url}"', "Add GitHub remote"):
        return False
    
    # Add all files
    print("Adding all files to Git...")
    if not run_command("git add .", "Add all files"):
        return False
    
    # Create commit with detailed message
    commit_message = f"""AI-BUDDY Update {timestamp}

✅ Fixed wellness check-in timestamp synchronization issues
✅ Implemented database-level automatic timestamp correction  
✅ Enhanced mobile endpoint with forced server timestamps
✅ Created comprehensive documentation for fixes
✅ Corrected all existing corrupted database entries

Features included:
- Mobile and web wellness check-in compatibility
- PostgreSQL database triggers for data integrity
- Central Time timezone display consistency
- Comprehensive error handling and logging
- Full backup and restore system
- Authentication and user management
- Health prediction and AI chat features
- Meditation tracking and challenges
- Food tracking and water intake monitoring
- CBT, DBT, ACT, and IPT coaching modules
- Progressive Web App (PWA) functionality

This deployment ensures robust cross-platform wellness tracking."""
    
    if not run_command(f'git commit -m "{commit_message}"', "Create commit"):
        print("No changes to commit or commit failed")
    
    # Push to GitHub
    print("Pushing to GitHub...")
    if not run_command("git push -u origin main", "Push to GitHub main branch"):
        # Try master branch if main fails
        if not run_command("git push -u origin master", "Push to GitHub master branch"):
            return False
    
    print("🎉 Successfully deployed AI-BUDDY to GitHub!")
    print(f"Repository URL: {repo_url}")
    
    return True

if __name__ == "__main__":
    success = deploy_to_github()
    if success:
        print("\n✅ Deployment completed successfully!")
        print("Your complete AI-BUDDY codebase is now on GitHub with all latest improvements.")
    else:
        print("\n❌ Deployment failed. Please check the errors above.")
        sys.exit(1)