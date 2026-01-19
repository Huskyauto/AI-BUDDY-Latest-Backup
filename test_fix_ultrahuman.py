#!/usr/bin/env python3
"""
Ultrahuman Ring API Testing and Verification Script
This script verifies and tests the Ultrahuman API connection and provides diagnostic information.
"""

import os
import sys
import logging
import requests
from datetime import datetime, timedelta
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ultrahuman_test')

# Constants
ULTRAHUMAN_API_BASE_URL = "https://api.ultrahuman.com/v1"
ULTRAHUMAN_API_KEY = os.environ.get("ULTRAHUMAN_API_KEY")
ALTERNATE_API_URLS = [
    "https://api.ultrahuman.com/v1",
    "https://api.ultrahuman.com/api/v1",
    "https://app.ultrahuman.com/api/v1"
]

def test_api_connection():
    """Test basic connection to the Ultrahuman API"""
    logger.info("Testing Ultrahuman Ring API connection...")
    logger.info(f"Using API key: {ULTRAHUMAN_API_KEY[:4]}...{ULTRAHUMAN_API_KEY[-4:]}")
    
    success = False
    
    # Test all possible API base URLs
    for base_url in ALTERNATE_API_URLS:
        logger.info(f"Trying base URL: {base_url}")
        
        test_endpoints = [
            "/user/me",
            "/users/me",
            "/user/profile",
            "/user",
            "/ring/metrics",
            "/ring/data"
        ]
        
        for endpoint in test_endpoints:
            full_url = f"{base_url}{endpoint}"
            logger.info(f"Testing endpoint: {full_url}")
            
            try:
                headers = {
                    "Authorization": f"Bearer {ULTRAHUMAN_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                response = requests.get(
                    full_url,
                    headers=headers,
                    timeout=10
                )
                
                logger.info(f"Response code: {response.status_code}")
                
                if response.status_code != 404:
                    logger.info(f"Found working endpoint! Status: {response.status_code}")
                    logger.info(f"Response: {response.text[:200]}...")
                    success = True
                    return {
                        "success": True,
                        "working_url": full_url,
                        "status_code": response.status_code,
                        "response": response.text[:200]
                    }
                
            except Exception as e:
                logger.error(f"Error testing endpoint {full_url}: {str(e)}")
    
    logger.error("All API endpoints failed with 404 errors")
    return {
        "success": False,
        "error": "All API endpoints failed with 404 errors"
    }

def retrieve_metrics(base_url=None):
    """
    Attempt to retrieve metrics from the Ultrahuman API
    Args:
        base_url: Optional base URL to use instead of the default
    """
    if base_url is None:
        base_url = ULTRAHUMAN_API_BASE_URL
        
    logger.info(f"Attempting to retrieve metrics from {base_url}...")
    
    # Try different date ranges
    end_time = datetime.now()
    
    date_ranges = [
        (end_time - timedelta(days=1), end_time),
        (end_time - timedelta(days=7), end_time),
        (end_time - timedelta(days=30), end_time)
    ]
    
    for start_time, end_time in date_ranges:
        logger.info(f"Trying date range: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
        
        try:
            headers = {
                "Authorization": f"Bearer {ULTRAHUMAN_API_KEY}",
                "Content-Type": "application/json"
            }
            
            params = {
                "start_date": start_time.strftime("%Y-%m-%d"),
                "end_date": end_time.strftime("%Y-%m-%d")
            }
            
            endpoints = [
                "/ring/metrics",
                "/metrics",
                "/data/ring",
                "/ring/data"
            ]
            
            for endpoint in endpoints:
                full_url = f"{base_url}{endpoint}"
                logger.info(f"Testing endpoint with dates: {full_url}")
                
                response = requests.get(
                    full_url,
                    headers=headers,
                    params=params,
                    timeout=10
                )
                
                if response.status_code != 404:
                    logger.info(f"Found working metrics endpoint! Status: {response.status_code}")
                    logger.info(f"Response: {response.text[:200]}...")
                    return {
                        "success": True,
                        "working_url": full_url,
                        "status_code": response.status_code,
                        "response": response.text[:200]
                    }
                
        except Exception as e:
            logger.error(f"Error retrieving metrics: {str(e)}")
    
    logger.error("Failed to retrieve metrics from all endpoints")
    return {
        "success": False,
        "error": "Failed to retrieve metrics from all endpoints"
    }

def save_results(results):
    """Save test results to a file for reference"""
    with open("ultrahuman_api_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to ultrahuman_api_test_results.json")

def main():
    """Main function to run API tests"""
    if not ULTRAHUMAN_API_KEY:
        logger.error("ERROR: ULTRAHUMAN_API_KEY environment variable not set")
        sys.exit(1)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "api_key_present": bool(ULTRAHUMAN_API_KEY),
        "api_key_prefix": ULTRAHUMAN_API_KEY[:4] if ULTRAHUMAN_API_KEY else None,
        "api_key_suffix": ULTRAHUMAN_API_KEY[-4:] if ULTRAHUMAN_API_KEY else None,
        "connection_test": None,
        "metrics_test": None
    }
    
    # Run tests
    connection_result = test_api_connection()
    results["connection_test"] = connection_result
    
    if connection_result.get("success") and "working_url" in connection_result:
        base_url = connection_result["working_url"].rsplit("/", 1)[0]
        metrics_result = retrieve_metrics(base_url)
    else:
        metrics_result = retrieve_metrics()
    
    results["metrics_test"] = metrics_result
    
    # Save results
    save_results(results)
    
    # Report summary
    logger.info("\nUltrahuman API Test Summary:")
    logger.info("=" * 40)
    logger.info(f"API Key Present: {results['api_key_present']}")
    logger.info(f"Connection Test: {'SUCCESS' if results['connection_test']['success'] else 'FAILED'}")
    logger.info(f"Metrics Test: {'SUCCESS' if results['metrics_test']['success'] else 'FAILED'}")
    logger.info("=" * 40)
    
    if results['connection_test']['success'] or results['metrics_test']['success']:
        logger.info("RECOMMENDATION: Update the Ultrahuman API base URL in your application")
        if "working_url" in results['connection_test']:
            logger.info(f"Suggested base URL: {results['connection_test']['working_url'].rsplit('/', 1)[0]}")
    else:
        logger.info("RECOMMENDATION: Verify your Ultrahuman API key or contact Ultrahuman support")
    
    return results

if __name__ == "__main__":
    main()