#!/usr/bin/env python3
"""
GitHub API uploader for AI-BUDDY complete codebase
Uses GitHub REST API to upload all files directly
"""

import os
import base64
import json
import requests
from datetime import datetime

class GitHubUploader:
    def __init__(self, username, token, repo_name):
        self.username = username
        self.token = token
        self.repo_name = repo_name
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
    
    def create_or_update_file(self, file_path, content, message):
        """Create or update a file in the repository"""
        url = f"{self.api_base}/repos/{self.username}/{self.repo_name}/contents/{file_path}"
        
        # Get existing file SHA if it exists
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                existing = response.json()
                sha = existing["sha"]
            else:
                sha = None
        except:
            sha = None
        
        # Prepare the content
        if isinstance(content, str):
            content_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        else:
            content_encoded = base64.b64encode(content).decode('utf-8')
        
        # Prepare the payload
        payload = {
            "message": message,
            "content": content_encoded
        }
        
        if sha:
            payload["sha"] = sha
        
        # Upload the file
        response = requests.put(url, headers=self.headers, json=payload)
        
        if response.status_code in [200, 201]:
            print(f"✅ Uploaded: {file_path}")
            return True
        else:
            print(f"❌ Failed to upload {file_path}: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    
    def upload_directory(self, local_path=".", exclude_patterns=None):
        """Upload entire directory to GitHub"""
        if exclude_patterns is None:
            exclude_patterns = [
                '.git', '__pycache__', '*.pyc', '.cache', 'node_modules', 
                '*.log', '.env', '.breakpoints', '.replit', 'venv', '.venv'
            ]
        
        uploaded_files = []
        failed_files = []
        
        for root, dirs, files in os.walk(local_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not any(pattern in d for pattern in exclude_patterns)]
            
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, local_path)
                
                # Skip excluded files
                if any(pattern in relative_path for pattern in exclude_patterns):
                    continue
                
                # Skip large files (>1MB for GitHub API)
                try:
                    if os.path.getsize(file_path) > 1024 * 1024:
                        print(f"⚠️ Skipping large file: {relative_path}")
                        continue
                except:
                    continue
                
                try:
                    # Read file content
                    if relative_path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.mp3', '.wav')):
                        with open(file_path, 'rb') as f:
                            content = f.read()
                    else:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    
                    # Upload file
                    message = f"Update {relative_path} - AI-BUDDY wellness fixes"
                    if self.create_or_update_file(relative_path, content, message):
                        uploaded_files.append(relative_path)
                    else:
                        failed_files.append(relative_path)
                        
                except Exception as e:
                    print(f"❌ Error reading {relative_path}: {str(e)}")
                    failed_files.append(relative_path)
        
        return uploaded_files, failed_files

def main():
    """Main upload function"""
    print("🚀 Starting GitHub API upload for AI-BUDDY...")
    
    # GitHub credentials
    username = "Huskyauto"
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")  # Your auth token
    repo_name = "AI-BUDDY-2025-05-05-TEAMS"
    
    # Create uploader
    uploader = GitHubUploader(username, token, repo_name)
    
    print(f"Repository: {username}/{repo_name}")
    print("Uploading files...")
    
    # Upload all files
    uploaded, failed = uploader.upload_directory()
    
    print(f"\n📊 Upload Summary:")
    print(f"✅ Successfully uploaded: {len(uploaded)} files")
    print(f"❌ Failed uploads: {len(failed)} files")
    
    if uploaded:
        print(f"\n✅ Successfully uploaded files:")
        for file in uploaded[:10]:  # Show first 10
            print(f"   • {file}")
        if len(uploaded) > 10:
            print(f"   ... and {len(uploaded) - 10} more files")
    
    if failed:
        print(f"\n❌ Failed files:")
        for file in failed[:5]:  # Show first 5 failures
            print(f"   • {file}")
    
    if len(uploaded) > 0:
        print(f"\n🎉 AI-BUDDY codebase successfully uploaded to GitHub!")
        print(f"Repository URL: https://github.com/{username}/{repo_name}")
    else:
        print(f"\n😞 Upload failed. Please check the errors above.")

if __name__ == "__main__":
    main()