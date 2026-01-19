#!/usr/bin/env python3
"""
Test Ultrahuman API Integration
This script directly tests the Ultrahuman API to debug connection issues
"""

import os
import json
import logging
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("ultrahuman-api-test")

def test_ultrahuman_api():
    """Test direct connection to Ultrahuman API"""
    
    # Get API key from environment
    api_key = os.environ.get('ULTRAHUMAN_API_KEY')
    if not api_key:
        logger.error("ULTRAHUMAN_API_KEY not found in environment variables")
        return False
        
    # Set base URL and headers
    base_url = 'https://partner.ultrahuman.com/api/v1/'
    
    # Test three different header configurations
    header_configs = [
        {
            "name": "Direct API Key",
            "headers": {
                'Authorization': api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Cache-Control': 'no-cache'
            }
        },
        {
            "name": "Bearer Prefix",
            "headers": {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Cache-Control': 'no-cache'
            }
        },
        {
            "name": "ApiKey Header",
            "headers": {
                'ApiKey': api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Cache-Control': 'no-cache'
            }
        }
    ]
    
    # Try different auth methods
    for config in header_configs:
        try:
            # Format yesterday's date for the API request
            today = datetime.now()
            yesterday = today.replace(day=today.day-1)
            formatted_date = f"{yesterday.year}-{yesterday.month:02d}-{yesterday.day:02d}"
            logger.info(f"Using date: {formatted_date}")
            
            # Build API URL
            api_url = f"{base_url}metrics?email=huskyauto@gmail.com&date={formatted_date}"
            
            logger.info(f"Testing with {config['name']} method")
            logger.debug(f"Making request to: {api_url}")
            logger.debug(f"Using headers: {json.dumps(config['headers'])}")
            
            # Make the request
            response = requests.get(
                api_url,
                headers=config['headers'],
                timeout=15
            )
            
            # Check response
            status_code = response.status_code
            logger.info(f"Response status code: {status_code}")
            
            # If we got a successful response, print the data
            if status_code == 200:
                data = response.json()
                logger.info(f"Auth method {config['name']} successful!")
                
                # Extract and print metrics
                if 'data' in data and 'metric_data' in data['data']:
                    metric_data = data['data']['metric_data']
                    logger.info(f"Found {len(metric_data)} metrics:")
                    
                    # List all metric types
                    metric_types = [m.get('type') for m in metric_data]
                    logger.info(f"Metric types: {metric_types}")
                    
                    # Extract individual metrics
                    heart_rate = next((m for m in metric_data if m.get('type') == 'hr'), {}).get('object', {})
                    hrv = next((m for m in metric_data if m.get('type') == 'hrv'), {}).get('object', {})
                    temperature = next((m for m in metric_data if m.get('type') == 'temp'), {}).get('object', {})
                    recovery_index = next((m for m in metric_data if m.get('type') == 'recovery_index'), {}).get('object', {})
                    
                    # Try multiple variations for VO2 Max field
                    vo2_max_types = ['vo2_max', 'vo2max', 'cardio_fitness', 'aerobic_fitness', 'fitness']
                    vo2_max = None
                    
                    # Search for vo2_max in different types
                    for vo2_type in vo2_max_types:
                        vo2_data = next((m for m in metric_data if m.get('type') == vo2_type), None)
                        if vo2_data:
                            logger.info(f"Found VO2 Max data under type '{vo2_type}'")
                            vo2_max = vo2_data.get('object', {})
                            break
                    
                    # If we didn't find it in the metric types, do a deep search
                    if not vo2_max:
                        logger.warning("No VO2 Max found in standard metric types. Performing deep search...")
                        # Save the full response for analysis
                        with open(f"ultrahuman_full_response_{formatted_date}.json", "w") as f:
                            json.dump(data, f, indent=2)
                        logger.info(f"Saved full response to ultrahuman_full_response_{formatted_date}.json")
                        
                        # Deep search function for nested dictionaries
                        def find_keys_recursive(d, target_keys):
                            results = {}
                            
                            # Base case for dict
                            if isinstance(d, dict):
                                # Check each key in this dict
                                for k, v in d.items():
                                    if k in target_keys:
                                        results[k] = v
                                        logger.info(f"Found key {k} with value {v}")
                                    
                                    # If value is dict or list, search it too
                                    if isinstance(v, (dict, list)):
                                        nested = find_keys_recursive(v, target_keys)
                                        # Merge results
                                        for nk, nv in nested.items():
                                            results[nk] = nv
                            
                            # For lists, search each item
                            elif isinstance(d, list):
                                for item in d:
                                    nested = find_keys_recursive(item, target_keys)
                                    # Merge results
                                    for nk, nv in nested.items():
                                        results[nk] = nv
                            
                            return results
                        
                        # Search for VO2 Max in different formats
                        vo2_search_keys = ['vo2_max', 'vo2max', 'vo2Max', 'cardioFitness', 'aerobicFitness']
                        vo2_results = find_keys_recursive(data, vo2_search_keys)
                        
                        if vo2_results:
                            logger.info(f"Deep search found VO2 Max related fields: {json.dumps(vo2_results)}")
                            # Use the first result found
                            for k, v in vo2_results.items():
                                if isinstance(v, dict) and 'value' in v:
                                    vo2_max = v
                                    logger.info(f"Using {k} with value {json.dumps(v)}")
                                    break
                                elif not isinstance(v, (dict, list)) and v is not None:
                                    vo2_max = {'value': v}
                                    logger.info(f"Using direct value from {k}: {v}")
                                    break
                        else:
                            logger.warning("No VO2 Max related fields found in deep search")
                    
                    # Print each metric
                    logger.info(f"Heart rate: {json.dumps(heart_rate)}")
                    logger.info(f"HRV: {json.dumps(hrv)}")
                    logger.info(f"Temperature: {json.dumps(temperature)}")
                    logger.info(f"Recovery index: {json.dumps(recovery_index)}")
                    logger.info(f"VO2 Max: {json.dumps(vo2_max)}")
                    
                    # Additional detailed analysis of temperature data
                    logger.info("========================= TEMPERATURE ANALYSIS =========================")
                    # Basic check first
                    if not temperature:
                        logger.warning("Temperature object is empty or null")
                    else:
                        # Check values array
                        if 'values' in temperature:
                            if not temperature['values']:
                                logger.warning("Temperature values array is empty")
                            else:
                                logger.info(f"Temperature values array has {len(temperature['values'])} entries")
                                # Print first 3 entries for analysis
                                for i, entry in enumerate(temperature['values'][:3]):
                                    logger.info(f"Temperature entry {i}: {entry}")
                        
                        # Check for direct value
                        if 'value' in temperature:
                            logger.info(f"Temperature has direct value: {temperature['value']}")
                        else:
                            logger.warning("Temperature has no direct 'value' field")
                        
                        # List all keys
                        logger.info(f"Temperature object keys: {list(temperature.keys())}")
                    
                    # Also try to search for temperature-related fields in the entire response
                    logger.info("Searching for additional temperature fields in full response...")
                    temperature_fields = find_keys_recursive(data, ['temp', 'temperature', 'skinTemp', 'skin_temp', 'skin_temperature'])
                    if temperature_fields:
                        logger.info(f"Found additional temperature fields: {json.dumps(temperature_fields)}")
                    else:
                        logger.warning("No additional temperature fields found in response")
                    
                    # Check for empty values
                    def check_data(name, data_obj):
                        if not data_obj:
                            logger.warning(f"{name} object is null or empty")
                            return
                            
                        if 'values' in data_obj and not data_obj['values']:
                            logger.warning(f"{name} has empty values list")
                        if 'value' in data_obj and data_obj['value'] is None:
                            logger.warning(f"{name} has null value")
                    
                    logger.info("========================= GENERAL DATA ANALYSIS =========================")
                    check_data("Heart rate", heart_rate)
                    check_data("HRV", hrv)
                    check_data("Temperature", temperature)
                    check_data("Recovery index", recovery_index)
                    if vo2_max and 'value' in vo2_max and vo2_max['value'] is None:
                        logger.warning("VO2 Max has null value")
                
                return True
            else:
                logger.error(f"Failed with status code {status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"Error response: {json.dumps(error_data)}")
                except:
                    logger.error(f"Error text: {response.text}")
        
        except Exception as e:
            logger.error(f"Error with {config['name']} method: {str(e)}")
    
    return False

if __name__ == "__main__":
    success = test_ultrahuman_api()
    print(f"\nTest result: {'SUCCESS' if success else 'FAILED'}")