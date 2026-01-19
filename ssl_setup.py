#!/usr/bin/env python3
"""
SSL Certificate Setup for ai-buddy.dev

This script automates the process of obtaining and configuring SSL certificates
for the ai-buddy.dev domain using Let's Encrypt with certbot.
"""
import os
import subprocess
import argparse
import sys
import datetime

def check_dependencies():
    """Check if required tools are installed"""
    try:
        subprocess.run(['openssl', 'version'], check=True, stdout=subprocess.PIPE)
        print("✓ OpenSSL is installed")
    except (subprocess.SubprocessError, FileNotFoundError):
        print("✗ OpenSSL is not installed. Please install it first.")
        sys.exit(1)
    
    try:
        subprocess.run(['certbot', '--version'], check=True, stdout=subprocess.PIPE)
        print("✓ Certbot is installed")
    except (subprocess.SubprocessError, FileNotFoundError):
        print("! Certbot is not installed. Using OpenSSL for self-signed certificates.")

def prepare_environment():
    """Prepare the environment for certificate generation"""
    # Create SSL certificates directory if it doesn't exist
    os.makedirs('ssl_certificates', exist_ok=True)
    print("✓ Created ssl_certificates directory")

def check_existing_certificates():
    """Check if certificates already exist and when they expire"""
    cert_path = "ssl_certificates/ai-buddy.dev.crt"
    
    if os.path.exists(cert_path):
        try:
            result = subprocess.run(
                ['openssl', 'x509', '-in', cert_path, '-noout', '-enddate'],
                check=True, capture_output=True, text=True
            )
            end_date_str = result.stdout.strip().split('=')[1]
            print(f"✓ Existing certificate found, expires on: {end_date_str}")
            
            # Parse date format to determine if it's close to expiration
            date_format = "%b %d %H:%M:%S %Y %Z"
            end_date = datetime.datetime.strptime(end_date_str, date_format)
            days_remaining = (end_date - datetime.datetime.now()).days
            
            if days_remaining < 30:
                print(f"! Certificate expires in {days_remaining} days. Consider renewal.")
            return True
        except Exception as e:
            print(f"! Error checking certificate expiration: {e}")
            return False
    else:
        print("✗ No existing certificates found")
        return False

def obtain_certificates(webroot_dir):
    """Obtain SSL certificates using Let's Encrypt certbot"""
    has_certbot = False
    try:
        subprocess.run(['certbot', '--version'], check=True, stdout=subprocess.PIPE)
        has_certbot = True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    
    if has_certbot:
        # Try to obtain Let's Encrypt certificates
        try:
            cmd = [
                'certbot', 'certonly', '--webroot',
                '-w', webroot_dir,
                '-d', 'ai-buddy.dev',
                '-d', 'www.ai-buddy.dev',
                '--agree-tos', '-n'
            ]
            subprocess.run(cmd, check=True)
            
            # Copy certificates to our ssl_certificates directory
            print("✓ Copying Let's Encrypt certificates to ssl_certificates/")
            subprocess.run([
                'cp', '/etc/letsencrypt/live/ai-buddy.dev/fullchain.pem',
                'ssl_certificates/ai-buddy.dev.crt'
            ], check=True)
            
            subprocess.run([
                'cp', '/etc/letsencrypt/live/ai-buddy.dev/privkey.pem',
                'ssl_certificates/ai-buddy.dev.key'
            ], check=True)
            
            print("✓ Let's Encrypt certificates obtained and installed")
            return True
        except subprocess.SubprocessError as e:
            print(f"! Failed to obtain Let's Encrypt certificates: {e}")
            print("! Falling back to self-signed certificates")
    
    # Create self-signed certificate if Let's Encrypt failed or isn't available
    try:
        print("Generating self-signed certificate (valid for 365 days)...")
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
            '-keyout', 'ssl_certificates/ai-buddy.dev.key',
            '-out', 'ssl_certificates/ai-buddy.dev.crt',
            '-days', '365', '-nodes',
            '-subj', '/CN=ai-buddy.dev'
        ], check=True)
        print("✓ Self-signed certificate generated")
        return True
    except subprocess.SubprocessError as e:
        print(f"✗ Failed to generate self-signed certificate: {e}")
        return False

def configure_flask_app():
    """Configure the Flask application to use SSL certificates"""
    # Check if main.py exists and update it
    if not os.path.exists('main.py'):
        print("✗ main.py not found. Cannot configure Flask app.")
        return False
    
    with open('main.py', 'r') as f:
        content = f.read()
    
    # Check if SSL configuration already exists
    if 'ssl_context' in content and 'get_ssl_context' in content:
        print("✓ Flask app already configured for SSL")
        return True
    
    # Look for app.run in main.py
    if 'app.run' in content:
        # Add the get_ssl_context function
        ssl_function = '''
def get_ssl_context():
    """Get SSL context for production or development"""
    ssl_dir = "ssl_certificates"
    cert_file = os.path.join(ssl_dir, "ai-buddy.dev.crt")
    key_file = os.path.join(ssl_dir, "ai-buddy.dev.key")
    
    # Check if SSL certificates exist
    if os.path.exists(cert_file) and os.path.exists(key_file):
        logger.info(f"Found SSL certificates: {cert_file}, {key_file}")
        return (cert_file, key_file)
    else:
        logger.warning("SSL certificates not found, using HTTP only")
        return None
'''
        
        # Replace the app.run call with one that uses SSL
        new_run_code = '''
    # Get SSL context if available
    ssl_context = get_ssl_context()
    
    if ssl_context:
        logger.info(f"Starting server with HTTPS (SSL) on port {port}")
        # Run the Flask app with SSL
        app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False, ssl_context=ssl_context)
    else:
        logger.info(f"Starting server with HTTP only on port {port}")
        # Run the Flask app without SSL
        app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
'''
        
        # Find the right spot to insert the get_ssl_context function
        init_db_pos = content.find('def init_db')
        if init_db_pos != -1:
            # Insert after init_db function
            next_def_pos = content.find('def ', init_db_pos + 1)
            if next_def_pos != -1:
                content = content[:next_def_pos] + ssl_function + content[next_def_pos:]
            else:
                # If no next function, insert before main block
                main_block_pos = content.find('if __name__ ==')
                if main_block_pos != -1:
                    content = content[:main_block_pos] + ssl_function + content[main_block_pos:]
        
        # Replace the app.run call
        run_pos = content.find('app.run')
        if run_pos != -1:
            # Find the end of the line or statement
            line_end = content.find('\n', run_pos)
            if line_end != -1:
                # Replace the entire app.run line with the new code
                content = content[:run_pos] + new_run_code + content[line_end+1:]
        
        # Write the updated content
        with open('main.py', 'w') as f:
            f.write(content)
        
        print("✓ Updated main.py to use SSL certificates")
        return True
    else:
        print("! Could not find app.run in main.py. Manual configuration required.")
        return False

def update_env_file():
    """Update the .env file to set SSL_ENABLED=true"""
    env_file = '.env'
    
    if not os.path.exists(env_file):
        # Create .env file if it doesn't exist
        with open(env_file, 'w') as f:
            f.write("SSL_ENABLED=true\n")
        print("✓ Created .env file with SSL_ENABLED=true")
        return True
    
    # Check if SSL_ENABLED is already in .env
    with open(env_file, 'r') as f:
        content = f.read()
    
    if 'SSL_ENABLED' in content:
        # Replace existing SSL_ENABLED value
        new_content = []
        for line in content.split('\n'):
            if line.startswith('SSL_ENABLED='):
                new_content.append('SSL_ENABLED=true')
            else:
                new_content.append(line)
        
        with open(env_file, 'w') as f:
            f.write('\n'.join(new_content))
        print("✓ Updated .env with SSL_ENABLED=true")
    else:
        # Add SSL_ENABLED to the end of the file
        with open(env_file, 'a') as f:
            f.write("\n# SSL Configuration\nSSL_ENABLED=true\n")
        print("✓ Added SSL_ENABLED=true to .env")
    
    return True

def update_nginx_config():
    """Create or update Nginx configuration for SSL if using Nginx"""
    # Check if Nginx is installed
    try:
        subprocess.run(['nginx', '-v'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.SubprocessError, FileNotFoundError):
        print("! Nginx not detected, skipping Nginx configuration")
        return False
    
    # Create Nginx configuration file
    nginx_config = """
server {
    listen 80;
    server_name ai-buddy.dev www.ai-buddy.dev;
    
    # Redirect all HTTP requests to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name ai-buddy.dev www.ai-buddy.dev;
    
    ssl_certificate /path/to/ssl_certificates/ai-buddy.dev.crt;
    ssl_certificate_key /path/to/ssl_certificates/ai-buddy.dev.key;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;
    
    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Proxy to the Flask application
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""
    
    # Update the path to the certificate files
    abs_path = os.path.abspath('ssl_certificates')
    nginx_config = nginx_config.replace('/path/to/ssl_certificates', abs_path)
    
    # Write the configuration to a file
    with open('ai-buddy.dev.nginx.conf', 'w') as f:
        f.write(nginx_config)
    
    print("✓ Created Nginx configuration file: ai-buddy.dev.nginx.conf")
    print("! To use this configuration with Nginx:")
    print("  1. Copy the file to /etc/nginx/sites-available/")
    print("     sudo cp ai-buddy.dev.nginx.conf /etc/nginx/sites-available/ai-buddy.dev")
    print("  2. Create a symbolic link to sites-enabled")
    print("     sudo ln -s /etc/nginx/sites-available/ai-buddy.dev /etc/nginx/sites-enabled/")
    print("  3. Test the configuration")
    print("     sudo nginx -t")
    print("  4. Reload Nginx")
    print("     sudo systemctl reload nginx")
    
    return True

def setup_ssl():
    """Main function to set up SSL certificates"""
    print("==== AI-BUDDY SSL Certificate Setup ====")
    check_dependencies()
    prepare_environment()
    
    if not check_existing_certificates():
        print("\nObtaining SSL certificates...")
        # Use the current directory as webroot by default
        if not obtain_certificates(os.getcwd()):
            print("✗ Failed to obtain SSL certificates")
            return False
    
    print("\nConfiguring application...")
    configure_flask_app()
    update_env_file()
    update_nginx_config()
    
    print("\n==== SSL Setup Complete ====")
    print("Your Flask application is now configured to use HTTPS.")
    print("Start the application with 'python main.py' to use the new SSL configuration.")
    return True

def main():
    """Script entry point with argument parsing"""
    parser = argparse.ArgumentParser(description='Set up SSL certificates for ai-buddy.dev')
    parser.add_argument('--force', action='store_true', help='Force certificate renewal even if existing certificates are valid')
    parser.add_argument('--webroot', default=os.getcwd(), help='Web root path for Let\'s Encrypt verification')
    args = parser.parse_args()
    
    if args.force:
        print("Forcing certificate renewal...")
        if os.path.exists('ssl_certificates/ai-buddy.dev.crt'):
            os.remove('ssl_certificates/ai-buddy.dev.crt')
        if os.path.exists('ssl_certificates/ai-buddy.dev.key'):
            os.remove('ssl_certificates/ai-buddy.dev.key')
    
    setup_ssl()

if __name__ == '__main__':
    main()