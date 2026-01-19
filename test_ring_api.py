import requests
import json
import sys

# URL - use the public Replit URL with the correct port
base_url = "https://replit-dev-6b69e1c7-a68c-4ebc-b0c0-21cbda53a376-fxkekzpxlw.us.replit.dev"
login_url = f"{base_url}/login"
ring_data_url = f"{base_url}/api/ring-data"

# Auth credentials
username = "huskyauto@gmail.com"
password = "Rw-120764"

# Start a session
session = requests.Session()

# Login to get session cookie
print("Logging in...")
login_response = session.post(
    login_url,
    data={"username": username, "password": password},
    allow_redirects=True
)

if login_response.status_code != 200:
    print(f"Login failed with status code {login_response.status_code}")
    sys.exit(1)

print("Login successful. Getting ring data...")

# Get ring data
ring_data_response = session.get(ring_data_url)

print(f"Response status: {ring_data_response.status_code}")

try:
    ring_data = ring_data_response.json()
    print("Ring Data API response:")
    print(json.dumps(ring_data, indent=2))

    # Check if we have VO2 Max data from Ultrahuman
    if ring_data.get('ultrahuman', {}).get('vo2_max'):
        print(f"\nVO2 Max value from Ultrahuman: {ring_data['ultrahuman']['vo2_max']}")
    else:
        print("\nNo VO2 Max data found in response")

except json.JSONDecodeError:
    print("Failed to decode JSON response:")
    print(ring_data_response.text[:500])  # Print first 500 chars of response

except Exception as e:
    print(f"Error processing response: {str(e)}")