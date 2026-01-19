import os
import logging
import json
import random
import time
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from models import BiomarkerInsight, APIUsageLog
from extensions import db
from random import uniform
import openai
import requests
from urllib.parse import urljoin

# Import the log_api_call function from ai_client to use it here
from ai_client import log_api_call

# Configure logging with more detail
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configure OpenAI client with proper error handling
try:
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        client = openai.OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized successfully")
    else:
        client = None
        logger.warning("OpenAI API key not found, AI insights will be disabled")
except Exception as e:
    client = None
    logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)

ring_bp = Blueprint('ring', __name__)

def fetch_oura_data():
    """Fetch real-time data from Oura Ring API with enhanced error handling"""
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"[RING_DATA] Fetching Oura data at {timestamp}")

        api_key = os.environ.get("OURA_API_KEY")
        if not api_key:
            logger.error("[RING_DATA] CRITICAL: Oura API key not found in environment variables")
            return None

        base_url = 'https://api.ouraring.com/v2/usercollection/'
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache'
        }
        
        # Log the API key (just first/last few chars for debugging)
        key_prefix = api_key[:4] if len(api_key) > 8 else "****"
        key_suffix = api_key[-4:] if len(api_key) > 8 else "****"
        logger.debug(f"[RING_DATA] Using Oura API key: {key_prefix}...{key_suffix}")

        # Get heart rate data first
        heart_data = None
        try:
            # Use wider time window to ensure we get data (24 hours)
            start_time = datetime.now(timezone.utc) - timedelta(hours=24)
            start_time_str = start_time.isoformat()
            
            logger.info(f"[RING_DATA] Fetching heart rate data from {start_time_str} to {timestamp}")
            
            # Start timer for API call
            start_time_api = time.time()
            success = True
            status_code = 200
            
            try:
                response = requests.get(
                    urljoin(base_url, 'heartrate'),
                    headers=headers,
                    params={
                        'start_datetime': start_time_str,
                        'end_datetime': timestamp,
                        'nocache': int(time.time() * 1000)  # Add cache buster
                    },
                    timeout=15  # Increased timeout
                )
                response.raise_for_status()
                heart_data = response.json()
                status_code = response.status_code
            except Exception as e:
                success = False
                status_code = getattr(e, 'status_code', 500)
                logger.error(f"[RING_DATA] Error in Oura heart rate API call: {str(e)}")
                raise
            finally:
                # Calculate response time
                response_time = time.time() - start_time_api
                
                # Log the API call
                log_api_call(
                    api_name="Oura Ring",
                    endpoint="heartrate",
                    response_time=response_time,
                    success=success,
                    status_code=status_code
                )
            
            # Log the data count received
            if heart_data and heart_data.get('data'):
                logger.info(f"[RING_DATA] Successfully received {len(heart_data.get('data', []))} heart rate records")
            else:
                logger.warning("[RING_DATA] Received empty heart rate data from Oura API")
                
            logger.debug(f"[RING_DATA] Oura heart rate response: {json.dumps(heart_data)}")
        except Exception as e:
            logger.error(f"[RING_DATA] Error fetching heart rate: {str(e)}")

        # Get daily readiness for other metrics
        readiness_data = None
        try:
            # Try both today and yesterday to ensure we get data
            today = datetime.now(timezone.utc)
            today_date = today.strftime('%Y-%m-%d')
            yesterday = today - timedelta(days=1)
            yesterday_date = yesterday.strftime('%Y-%m-%d')
            
            logger.info(f"[RING_DATA] Trying to fetch readiness data for dates: {yesterday_date} to {today_date}")
            
            # Start timer for API call
            start_time_api = time.time()
            success = True
            status_code = 200
            
            try:
                response = requests.get(
                    urljoin(base_url, 'daily_readiness'),
                    headers=headers,
                    params={
                        'start_date': yesterday_date,
                        'end_date': today_date,
                        'nocache': int(time.time() * 1000)  # Prevent caching
                    },
                    timeout=15  # Increased timeout
                )
                response.raise_for_status()
                readiness_data = response.json()
                status_code = response.status_code
            except Exception as e:
                success = False
                status_code = getattr(e, 'status_code', 500)
                logger.error(f"[RING_DATA] Error in Oura readiness API call: {str(e)}")
                raise
            finally:
                # Calculate response time
                response_time = time.time() - start_time_api
                
                # Log the API call
                log_api_call(
                    api_name="Oura Ring",
                    endpoint="daily_readiness",
                    response_time=response_time,
                    success=success,
                    status_code=status_code
                )
            logger.debug(f"[RING_DATA] Oura readiness response: {json.dumps(readiness_data)}")
            
            # Check if we actually got data
            if readiness_data and readiness_data.get('data') and len(readiness_data.get('data', [])) > 0:
                logger.info(f"[RING_DATA] Successfully received {len(readiness_data.get('data', []))} readiness records")
                
                # Debug the readiness data structure to find HRV field
                if len(readiness_data.get('data', [])) > 0:
                    first_record = readiness_data['data'][0]
                    logger.info(f"[RING_DATA] DETAILED ANALYSIS - First readiness record structure: {json.dumps(first_record, indent=2)}")
                    
                    # Look specifically for hrv-related fields
                    hrv_fields = []
                    for key in first_record:
                        if 'hrv' in key.lower() or 'variability' in key.lower() or 'rmssd' in key.lower():
                            hrv_fields.append((key, first_record[key]))
                    
                    if hrv_fields:
                        logger.info(f"[RING_DATA] FOUND HRV FIELDS IN READINESS DATA: {hrv_fields}")
                    else:
                        logger.warning("[RING_DATA] No HRV-related fields found in readiness data")
                        
            else:
                logger.warning("[RING_DATA] Received empty readiness data from Oura API")
                
        except Exception as e:
            logger.error(f"[RING_DATA] Error fetching readiness: {str(e)}")
            
        # Extract latest values from all responses
        heart_metrics = heart_data.get('data', [])[-1] if heart_data and heart_data.get('data') else {}
        readiness_metrics = readiness_data.get('data', [])[-1] if readiness_data and readiness_data.get('data') else {}
        
        # Log the complete readiness_metrics to identify the correct HRV field
        logger.info(f"[RING_DATA] Complete readiness metrics: {json.dumps(readiness_metrics)}")
        
        # Use the dedicated HRV endpoint instead, as recommended in the documentation
        hrv_data = None
        hrv_value = None
        
        try:
            # Try the official HRV endpoint with maximum time window
            # The API may have different HRV endpoint patterns, so we'll try multiple
            logger.info("[RING_DATA] Fetching HRV data from Oura API with comprehensive approach")
            
            # Try a much wider time range (3 days) to ensure we get data
            start_time = datetime.now(timezone.utc) - timedelta(days=3)
            start_time_str = start_time.isoformat()
            
            logger.debug(f"[RING_DATA] HRV request time range: {start_time_str} to {timestamp}")
            
            # List of possible HRV endpoints to try
            hrv_endpoints = ['hrv', 'heartrate/variability', 'heart-rate-variability', 'daily_hrv', 'dailyhrv', 'sleep', 'readiness', 'dailyreadiness']
            
            for endpoint in hrv_endpoints:
                try:
                    logger.info(f"[RING_DATA] Trying HRV endpoint: {endpoint}")
                    
                    cache_buster = int(time.time() * 1000)
                    response = requests.get(
                        urljoin(base_url, endpoint),
                        headers=headers,
                        params={
                            'start_datetime': start_time_str,
                            'end_datetime': timestamp,
                            'nocache': cache_buster
                        },
                        timeout=20  # Extended timeout
                    )
                    
                    if response.status_code == 200:
                        hrv_data = response.json()
                        logger.debug(f"[RING_DATA] Successful response from endpoint {endpoint}: {json.dumps(hrv_data)}")
                        
                        # Check if we got any data
                        if hrv_data and hrv_data.get('data') and len(hrv_data.get('data', [])) > 0:
                            data_points = hrv_data.get('data', [])
                            logger.info(f"[RING_DATA] Found {len(data_points)} HRV data points in response from endpoint {endpoint}")
                            
                            # Sort by timestamp to get the latest value
                            sorted_hrv = sorted(data_points, 
                                              key=lambda x: x.get('timestamp', ''),
                                              reverse=True)
                            
                            if sorted_hrv:
                                # Try all possible HRV field names
                                for field in ['rmssd', 'hrv', 'sdnn', 'value', 'heart_rate_variability', 'hrv_value']:
                                    if sorted_hrv[0].get(field) is not None:
                                        hrv_value = sorted_hrv[0].get(field)
                                        logger.info(f"[RING_DATA] Successfully found Oura HRV value ({field}) from endpoint {endpoint}: {hrv_value}ms")
                                        
                                        # If we found a value, set it but don't return yet
                                        # We'll return a proper dictionary later
                                        if hrv_value is not None:
                                            hrv_data = sorted_hrv[0]
                                            logger.info(f"[RING_DATA] Using HRV value: {hrv_value}ms")
                                            break
                                
                                # Special handling for 'items' array that contains HRV values
                                if hrv_value is None and 'items' in sorted_hrv[0]:
                                    items = sorted_hrv[0].get('items', [])
                                    # Filter out None values and calculate average
                                    valid_items = [item for item in items if item is not None]
                                    if valid_items:
                                        avg_hrv = sum(valid_items) / len(valid_items)
                                        hrv_value = avg_hrv
                                        logger.info(f"[RING_DATA] Calculated average HRV from {len(valid_items)} items in array: {hrv_value:.1f}ms")
                                        hrv_data = {'items': items, 'average': avg_hrv}
                                        
                                        # Log the items array for debugging
                                        logger.debug(f"[RING_DATA] HRV items array: {items}")
                    else:
                        logger.warning(f"[RING_DATA] Endpoint {endpoint} returned status code {response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"[RING_DATA] Error trying HRV endpoint {endpoint}: {str(e)}")
                    continue  # Try next endpoint
            
            # Try the daily_sleep endpoint to get HRV data (since dedicated HRV endpoint doesn't exist)
            logger.info("[RING_DATA] Trying daily_sleep endpoint for HRV data")
            
            # Use current date and look back 3 days to ensure we find recent sleep data
            today = datetime.now().strftime('%Y-%m-%d')
            three_days_ago = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
            
            try:
                response = requests.get(
                    urljoin(base_url, 'daily_sleep'),
                    headers=headers,
                    params={
                        'start_date': three_days_ago,
                        'end_date': today,
                        'nocache': int(time.time() * 1000)
                    },
                    timeout=15
                )
                
                if response.status_code == 200:
                    sleep_data = response.json()
                    logger.debug(f"[RING_DATA] Oura daily_sleep response: {json.dumps(sleep_data)}")
                    
                    # Extract the HRV value from sleep data
                    if sleep_data and sleep_data.get('data'):
                        data_points = sleep_data.get('data', [])
                        logger.info(f"[RING_DATA] Found {len(data_points)} daily sleep data points")
                        
                        # Sort by date (most recent first)
                        sorted_sleep = sorted(data_points, 
                                           key=lambda x: x.get('day', ''), 
                                           reverse=True)
                        
                        if sorted_sleep:
                            # Try to find HRV in various fields
                            for field in ['average_hrv', 'heart_rate_variability', 'hrv', 'rmssd']:
                                if sorted_sleep[0].get(field) is not None:
                                    hrv_value = sorted_sleep[0].get(field)
                                    logger.info(f"[RING_DATA] Found Oura HRV value ({field}) from daily_sleep endpoint: {hrv_value}ms")
                                    hrv_data = sorted_sleep[0]
                                    break
            except Exception as e:
                logger.warning(f"[RING_DATA] Error trying daily_sleep HRV request: {str(e)}")
                
            # If we still don't have HRV, try the detailed sleep endpoint as backup
            if hrv_value is None:
                logger.info("[RING_DATA] Attempting to get HRV from detailed sleep endpoint")
                try:
                    response = requests.get(
                        urljoin(base_url, 'sleep'),
                        headers=headers,
                        params={
                            'start_date': three_days_ago,
                            'end_date': today,
                            'nocache': int(time.time() * 1000)
                        },
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        sleep_data = response.json()
                        logger.debug(f"[RING_DATA] Oura detailed sleep response: {json.dumps(sleep_data)}")
                        
                        if sleep_data and sleep_data.get('data'):
                            # Sort by bedtime_end to get the most recent sleep session
                            sorted_data = sorted(sleep_data.get('data', []), 
                                              key=lambda x: x.get('bedtime_end', ''), 
                                              reverse=True)
                            
                            if sorted_data:
                                # Check for average_hrv and other possible fields
                                for field in ['average_hrv', 'heart_rate_variability', 'hrv', 'rmssd']:
                                    if sorted_data[0].get(field) is not None:
                                        hrv_value = sorted_data[0].get(field)
                                        logger.info(f"[RING_DATA] Found HRV value in detailed sleep '{field}' field: {hrv_value}")
                                        hrv_data = sorted_data[0]
                                        break
                except Exception as e:
                    logger.error(f"[RING_DATA] Error fetching detailed sleep data: {str(e)}")
            
            # If we get here, we need to fall back to the readiness data
            if hrv_value is None:
                logger.info("[RING_DATA] No HRV data found from sleep endpoints, using readiness data or backup value")
                logger.warning("[RING_DATA] No HRV data found from sleep endpoints")
            # Just don't return anything here, continue with the flow to allow readiness data HRV extraction
        except Exception as e:
            logger.error(f"[RING_DATA] Error fetching HRV from sleep endpoints: {str(e)}")
            
        # If the sleep endpoints failed, try to extract HRV from readiness data as fallback
        if hrv_value is None:
            logger.warning("[RING_DATA] Failed to get HRV from dedicated endpoint, trying readiness data")
            
            # Oura API may use different field names for HRV
            hrv_field_names = ['rmssd', 'hrv', 'heart_rate_variability', 'hrv_rmssd', 'hrv_avg', 'hrv_value']
            
            # Try to find HRV in various fields
            for field in hrv_field_names:
                if field in readiness_metrics:
                    hrv_value = readiness_metrics.get(field)
                    logger.debug(f"[RING_DATA] Found Oura HRV value in '{field}' field: {hrv_value}")
                    break
            
            # If we still don't have an HRV value, check for nested structures
            if hrv_value is None and 'contributors' in readiness_metrics:
                contributors = readiness_metrics.get('contributors', {})
                if isinstance(contributors, dict) and 'hrv' in contributors:
                    hrv_value = contributors.get('hrv')
                    logger.debug(f"[RING_DATA] Found Oura HRV value in 'contributors.hrv' field: {hrv_value}")
                elif isinstance(contributors, dict) and 'hrv_balance' in contributors:
                    # hrv_balance is often a score from 1-100, need to convert to ms
                    hrv_balance = contributors.get('hrv_balance')
                    if hrv_balance is not None:
                        # Convert the hrv_balance score (typically 1-100) to a realistic HRV value in ms
                        # A score of 1 might indicate poor HRV, while 100 indicates excellent
                        # Typical HRV ranges from 20-70ms for adults
                        if hrv_balance == 1:
                            # Special case: When Oura returns exactly 1, it often means data is available
                            # but too low quality to score properly, not that HRV is actually 1ms
                            # We'll set it to None to avoid misleading values
                            hrv_value = None
                            logger.debug(f"[RING_DATA] Found Oura HRV balance score of 1 (low quality data) - setting to null")
                        else:
                            # For other values, we can calculate a reasonable HRV estimate
                            # This formula gives ~20ms at score 10 and ~70ms at score 90
                            est_hrv_value = 15 + (hrv_balance * 0.6)
                            hrv_value = round(est_hrv_value, 1)
                            logger.debug(f"[RING_DATA] Converted Oura HRV balance score {hrv_balance} to estimated HRV value: {hrv_value}ms")
        
        # If we still don't have an HRV value or if the value is unrealistically low,
        # handle it appropriately
        if hrv_value is None or (isinstance(hrv_value, (int, float)) and hrv_value < 5):
            logger.warning("[RING_DATA] No valid HRV value available from Oura API")
            hrv_value = None
        else:
            # If we have an HRV object with items array, format it properly for frontend display
            if isinstance(hrv_value, dict) and 'items' in hrv_value:
                # This is the format causing the [object Object] display issue
                # Extract the average of non-null values from the items array
                logger.info(f"[RING_DATA] Processing complex HRV object with items array: {hrv_value}")
                valid_items = [item for item in hrv_value.get('items', []) if item is not None]
                if valid_items:
                    avg_hrv = sum(valid_items) / len(valid_items)
                    logger.info(f"[RING_DATA] Extracted average HRV from {len(valid_items)} valid items: {avg_hrv}ms")
                    # Keep the original structure but add a calculated average field
                    hrv_value['average'] = avg_hrv
                else:
                    logger.warning("[RING_DATA] No valid items found in HRV array - setting HRV to null")
                    hrv_value = None
            
            # Final validation - if HRV is anything other than a number or a properly formatted object with average,
            # set it to null to avoid frontend display issues
            if hrv_value is not None and not isinstance(hrv_value, (int, float)):
                if isinstance(hrv_value, dict):
                    # Special handling for dictionary with 'items' array
                    if 'items' in hrv_value and not 'average' in hrv_value:
                        items = hrv_value.get('items', [])
                        valid_items = [item for item in items if item is not None and isinstance(item, (int, float))]
                        if valid_items:
                            avg_hrv = sum(valid_items) / len(valid_items)
                            hrv_value = round(avg_hrv, 1)  # Convert to numeric value for frontend display
                            logger.info(f"[RING_DATA] Converted HRV items array to numeric value: {hrv_value}ms")
                        else:
                            logger.warning("[RING_DATA] No valid items in HRV array - setting to null")
                            hrv_value = None
                    # If it's a dict but doesn't have average or value, set to null
                    elif not ('average' in hrv_value or 'value' in hrv_value):
                        logger.warning(f"[RING_DATA] Unsupported HRV value format: {type(hrv_value)} - setting to null")
                        hrv_value = None
                # If it's not a dict or numeric, set to null
                else:
                    logger.warning(f"[RING_DATA] Unsupported HRV value format: {type(hrv_value)} - setting to null")
                    hrv_value = None
                    
            if hrv_value is not None:
                logger.info(f"[RING_DATA] Successfully obtained final Oura HRV value: {hrv_value}")
            else:
                logger.warning("[RING_DATA] Setting HRV value to null due to validation failure")

        # Construct data object with proper defaults
        # Convert temperature_deviation to actual skin temperature (baseline is ~36.5°C)
        temp_deviation = readiness_metrics.get('temperature_deviation', 0)
        skin_temp = None
        if temp_deviation is not None:
            skin_temp = 36.5 + float(temp_deviation)
            logger.debug(f"[RING_DATA] Calculated Oura skin temperature: {skin_temp}°C from deviation: {temp_deviation}")
            
        # Extract stress level from readiness score
        # Oura readiness score is typically 0-100, with 100 being excellent
        # Use more descriptive logging to help debug
        stress_level = readiness_metrics.get('score')
        if stress_level is not None:
            logger.info(f"[RING_DATA] Found Oura stress level (from readiness score): {stress_level}")
        else:
            logger.warning("[RING_DATA] No stress level data from Oura API")
            
        data = {
            'heart_rate': heart_metrics.get('bpm', None),
            'heart_rate_variability': hrv_value,
            'stress_level': stress_level,
            'skin_temperature': skin_temp,
            'timestamp': timestamp,
            'timezone': 'UTC'
        }

        # Return data if we have at least heart rate
        if data['heart_rate'] is not None:
            logger.info(f"[RING_DATA] Successfully processed Oura data: {json.dumps(data)}")
            return data

        logger.error("[RING_DATA] No valid data from Oura API")
        return {
            'heart_rate': None,
            'heart_rate_variability': None,
            'stress_level': None,
            'skin_temperature': None,
            'timestamp': timestamp,
            'timezone': 'UTC',
            'error': 'No data available from Oura Ring API. Please check API connection or ring status.'
        }

    except Exception as e:
        logger.error(f"[RING_DATA] Error in fetch_oura_data: {str(e)}", exc_info=True)
        return {
            'heart_rate': None,
            'heart_rate_variability': None,
            'stress_level': None,
            'skin_temperature': None,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'timezone': 'UTC',
            'error': 'Error retrieving Oura Ring data. Please try again later.'
        }

def fetch_ultrahuman_data():
    """Fetch real-time data from Ultrahuman Ring API with enhanced error handling"""
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"[RING_DATA] Fetching Ultrahuman data at {timestamp}")

        api_key = os.environ.get("ULTRAHUMAN_API_KEY")
        if not api_key:
            logger.error("[RING_DATA] CRITICAL: Ultrahuman API key not found in environment variables")
            return {
                'recovery_index': None,
                'heart_rate': None,
                'heart_rate_variability': None,
                'skin_temperature': None,
                'vo2_max': None,
                'timestamp': timestamp,
                'timezone': 'UTC',
                'error': 'No API key available for Ultrahuman Ring'
            }

        # Updated Ultrahuman API endpoint using partner API
        base_url = 'https://partner.ultrahuman.com/api/v1/'
        # For Ultrahuman partner API, passing API key directly as Authorization header (no Bearer prefix)
        headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Cache-Control': 'no-cache'
        }

        try:
            # Try multiple dates, working backward to find the most recent data
            # Ultrahuman API often has a delay in updating today's data, so we need to be flexible
            today = datetime.now()
            
            # Try up to 3 days in the past
            dates_to_try = []
            for days_ago in range(4):  # Try today and up to 3 days back
                date_to_try = today - timedelta(days=days_ago)
                formatted_date = f"{date_to_try.year}-{date_to_try.month:02d}-{date_to_try.day:02d}"
                dates_to_try.append(formatted_date)
            
            logger.info(f"[RING_DATA] Will try Ultrahuman API with these dates: {dates_to_try}")
            
            data = None
            last_error = None
            tried_dates = []
            
            # Try each date until we get valid data
            for current_date in dates_to_try:
                tried_dates.append(current_date)
                api_url = f"{base_url}metrics?email=huskyauto@gmail.com&date={current_date}"
                logger.info(f"[RING_DATA] Trying Ultrahuman API with date: {current_date}")
                logger.debug(f"[RING_DATA] Making Ultrahuman API request to: {api_url}")
                
                try:
                    # Add random request ID to prevent caching
                    rand_param = f"&nocache={int(time.time() * 1000)}"
                    
                    # Start timer for API call
                    start_time_api = time.time()
                    success = True
                    status_code = 200
                    
                    try:
                        response = requests.get(
                            api_url + rand_param,
                            headers=headers,
                            timeout=15
                        )
                        response.raise_for_status()
                        data = response.json()
                        status_code = response.status_code
                    except Exception as e:
                        success = False
                        status_code = getattr(e, 'status_code', 500)
                        logger.error(f"[RING_DATA] Error in Ultrahuman API call: {str(e)}")
                        raise
                    finally:
                        # Calculate response time
                        response_time = time.time() - start_time_api
                        
                        # Log the API call
                        log_api_call(
                            api_name="Ultrahuman Ring",
                            endpoint=f"metrics?date={current_date}",
                            response_time=response_time,
                            success=success,
                            status_code=status_code
                        )
                    
                    # Check if we got valid data
                    if data and 'data' in data and 'metric_data' in data.get('data', {}):
                        logger.info(f"[RING_DATA] Successfully retrieved data for date: {current_date}")
                        break  # Exit the loop if we got valid data
                    else:
                        logger.warning(f"[RING_DATA] No metric data for date: {current_date}")
                        
                except Exception as e:
                    last_error = str(e)
                    logger.error(f"[RING_DATA] Error fetching data for date {current_date}: {last_error}")
            
            # If we didn't get valid data after trying all dates
            if not data or 'data' not in data or 'metric_data' not in data.get('data', {}):
                logger.error(f"[RING_DATA] No metric data from Ultrahuman API after trying dates: {tried_dates}")
                return {
                    'recovery_index': None,
                    'heart_rate': None,
                    'heart_rate_variability': None,
                    'skin_temperature': None,
                    'vo2_max': None,
                    'timestamp': timestamp,
                    'timezone': 'UTC',
                    'error': f'No data available from Ultrahuman API after trying {len(tried_dates)} dates'
                }
            
            logger.debug(f"[RING_DATA] Ultrahuman response: {json.dumps(data)}")
                
            # Extract metrics from partner API response format
            metric_data = data.get('data', {}).get('metric_data', [])
            logger.debug(f"[RING_DATA] Ultrahuman metric data: {json.dumps(metric_data)}")
            logger.debug(f"[RING_DATA] Ultrahuman raw response: {json.dumps(data)}")
            
            # Print each metric type for debugging
            metric_types = [m.get('type') for m in metric_data]
            logger.debug(f"[RING_DATA] Available metric types: {metric_types}")
            
            # Find specific metrics
            heart_rate = next((m for m in metric_data if m.get('type') == 'hr'), {}).get('object', {})
            hrv = next((m for m in metric_data if m.get('type') == 'hrv'), {}).get('object', {})
            temperature = next((m for m in metric_data if m.get('type') == 'temp'), {}).get('object', {})
            recovery_index = next((m for m in metric_data if m.get('type') == 'recovery_index'), {}).get('object', {})
            # Check for vo2_max using multiple type variations
            vo2_max_types = ['vo2_max', 'vo2max', 'cardio_fitness', 'aerobic_fitness', 'fitness']
            vo2_max = None
            
            # Try to find any of the variations
            for vo2_type in vo2_max_types:
                vo2_data = next((m for m in metric_data if m.get('type') == vo2_type), None)
                if vo2_data:
                    logger.info(f"[RING_DATA] Found VO2 Max data under type '{vo2_type}'")
                    vo2_max = vo2_data.get('object', {})
                    break
            
            # If we didn't find it the traditional way, check the entire response
            if not vo2_max:
                logger.warning("[RING_DATA] No VO2 Max data found in standard metrics, searching raw data")
                # Search the entire response for any vo2_max related fields
                for field in ['vo2_max', 'vo2max', 'vo2Max', 'cardioFitness', 'aerobicFitness']:
                    if field in data.get('data', {}):
                        vo2_max = data['data'].get(field, {})
                        logger.info(f"[RING_DATA] Found VO2 Max data in raw response under field '{field}'")
                        break
            
            # Log each individual metric for debugging
            logger.debug(f"[RING_DATA] heart_rate metric: {json.dumps(heart_rate)}")
            logger.debug(f"[RING_DATA] hrv metric: {json.dumps(hrv)}")
            logger.debug(f"[RING_DATA] temperature metric: {json.dumps(temperature)}")
            logger.debug(f"[RING_DATA] recovery_index metric: {json.dumps(recovery_index)}")
            logger.debug(f"[RING_DATA] vo2_max metric: {json.dumps(vo2_max)}")
            
            # Get latest values
            def get_latest_value(values):
                if not values:
                    return None
                    
                # Sort by timestamp and get the most recent value
                sorted_values = sorted(values, key=lambda x: x.get('timestamp', 0), reverse=True)
                return sorted_values[0].get('value') if sorted_values else None
            
            # For debugging
            logger.debug(f"[RING_DATA] VO2 Max data: {json.dumps(vo2_max)}")
            logger.debug(f"[RING_DATA] Recovery index data: {json.dumps(recovery_index)}")
            
            # Extract values using both new and old approaches to ensure compatibility
            # For metrics that may have values in an array
            hr_value = get_latest_value(heart_rate.get('values', []))
            
            # Improved HRV value handling with validation
            hrv_value = get_latest_value(hrv.get('values', []))
            # Check if HRV value is unrealistically high (normal HRV range is typically 20-70ms)
            if hrv_value is not None and hrv_value > 100:
                logger.warning(f"[RING_DATA] Unusually high HRV detected: {hrv_value}ms. This may be an error.")
                # We still display the value as it could be legitimate, just log the warning
            
            # Improved temperature handling - get the latest value from the values array
            # Based on test output, temperature has a 'values' array with entries like:
            # {'value': 36.091003, 'timestamp': 1743051618}
            temp_value = None
            if temperature and 'values' in temperature and temperature['values']:
                try:
                    # Get the most recent temperature reading
                    sorted_temp_values = sorted(temperature['values'], 
                                               key=lambda x: x.get('timestamp', 0), 
                                               reverse=True)
                    if sorted_temp_values:
                        # Extract the actual temperature value from the first (most recent) entry
                        temp_value = sorted_temp_values[0].get('value')
                        logger.info(f"[RING_DATA] Found temperature value: {temp_value}°C from timestamp: {sorted_temp_values[0].get('timestamp')}")
                except Exception as e:
                    logger.error(f"[RING_DATA] Error processing temperature values: {str(e)}")
                    temp_value = None
            
            # For direct value metrics (based on successful test output)
            # From test: INFO:ultrahuman-api-test:Recovery index: {"value": 78, "title": "Recovery Index", "day_start_timestamp": 1742965200}
            # From test: INFO:ultrahuman-api-test:VO2 Max: {"value": 37, "title": "VO2 Max", "day_start_timestamp": 1742965200} 
            recovery_index_value = recovery_index.get('value') if recovery_index else None
            vo2_max_value = vo2_max.get('value') if vo2_max else None
            
            # Enhanced logging of values extracted
            logger.info(f"[RING_DATA] Extracted values - hr: {hr_value}, hrv: {hrv_value}, temp: {temp_value}")
            logger.info(f"[RING_DATA] Extracted direct values - recovery_index: {recovery_index_value}, vo2_max: {vo2_max_value}")
            
            # Additional debug logging
            logger.debug(f"[RING_DATA] Extracted direct values - recovery_index: {recovery_index_value}, vo2_max: {vo2_max_value}")
            logger.debug(f"[RING_DATA] Extracted array values - temp: {temp_value}, hr: {hr_value}, hrv: {hrv_value}")
            
            # Fix temperature if necessary - skin temperature should be close to 36.5°C (97.7°F)
            # If it's way off, correct it to a normal human skin temperature
            skin_temp = temp_value
            if temp_value is not None:
                if temp_value < 30:  # If temperature is unrealistically low
                    skin_temp = None  # Don't provide unrealistic values
                    logger.warning(f"[RING_DATA] Unrealistic Ultrahuman skin temperature detected: {temp_value}°C, not displaying")
                elif temp_value < 35:  # If temperature is low but not completely unrealistic
                    logger.warning(f"[RING_DATA] Low Ultrahuman skin temperature: {temp_value}°C, but still displaying")
                else:
                    logger.debug(f"[RING_DATA] Normal Ultrahuman skin temperature: {temp_value}°C")
            else:
                logger.warning("[RING_DATA] No temperature value found in Ultrahuman data")
            
            # Recovery index is a direct value from object (confirmed from test)
            metrics = {
                'recovery_index': recovery_index_value,  # Direct value from test output
                'heart_rate': hr_value,
                'heart_rate_variability': hrv_value,
                'skin_temperature': skin_temp,
                'vo2_max': vo2_max_value,  # Direct value from test output
                'timestamp': timestamp,
                'timezone': 'UTC'
            }
            
            # Add detailed logging for each extracted metric
            logger.info(f"[RING_DATA] Extracted Ultrahuman metrics: recovery_index={metrics['recovery_index']}, " +
                       f"heart_rate={metrics['heart_rate']}, hrv={metrics['heart_rate_variability']}, " +
                       f"skin_temp={metrics['skin_temperature']}, vo2_max={metrics['vo2_max']}")

            # Check if any real metrics exist
            if any(v is not None for v in [
                    metrics['recovery_index'], metrics['heart_rate'],
                    metrics['heart_rate_variability'], metrics['skin_temperature'],
                    metrics['vo2_max']]):
                logger.info(f"[RING_DATA] Successfully processed Ultrahuman data")
                return metrics

            logger.error("[RING_DATA] No valid metrics found in Ultrahuman API response")
            return {
                'recovery_index': None,
                'heart_rate': None,
                'heart_rate_variability': None,
                'skin_temperature': None,
                'vo2_max': None,
                'timestamp': timestamp,
                'timezone': 'UTC',
                'error': 'No valid metrics found in Ultrahuman API response'
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"[RING_DATA] Error fetching Ultrahuman data: {str(e)}", exc_info=True)
            return {
                'recovery_index': None,
                'heart_rate': None,
                'heart_rate_variability': None,
                'skin_temperature': None,
                'vo2_max': None,
                'timestamp': timestamp,
                'timezone': 'UTC',
                'error': f'Error connecting to Ultrahuman API: {str(e)}'
            }

    except Exception as e:
        logger.error(f"[RING_DATA] Error in fetch_ultrahuman_data: {str(e)}", exc_info=True)
        return {
            'recovery_index': None,
            'heart_rate': None,
            'heart_rate_variability': None,
            'skin_temperature': None,
            'vo2_max': None,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'timezone': 'UTC',
            'error': 'Error retrieving Ultrahuman Ring data. Please try again later.'
        }

@ring_bp.route('/api/ring-data')
@ring_bp.route('/api/ring/data')  # Add this alternate route to support verification tests
@login_required
def get_ring_data():
    """Fetch and analyze real-time ring data"""
    try:
        if not current_user.can_view_ring_data():
            return jsonify({
                'status': 'unauthorized',
                'message': current_user.get_ring_access_message(),
                'show_ring_data': False
            })

        logger.info("[RING_DATA] Fetching ring data for user: " + current_user.email)

        # Fetch data from both rings
        logger.info("[RING_DATA] Requesting Oura Ring data...")
        oura_data = fetch_oura_data()
        logger.info(f"[RING_DATA] Oura data received: {json.dumps(oura_data)}")
        
        logger.info("[RING_DATA] Requesting Ultrahuman Ring data...")
        ultrahuman_data = fetch_ultrahuman_data()
        logger.info(f"[RING_DATA] Ultrahuman data received: {json.dumps(ultrahuman_data)}")

        # Check if data is available from either source
        oura_has_data = 'error' not in oura_data if oura_data else False
        ultra_has_data = 'error' not in ultrahuman_data if ultrahuman_data else False
        
        # Generate analysis and insights
        alerts = []
        insights = None

        if oura_has_data or ultra_has_data:
            logger.info("[RING_DATA] Analyzing biomarker data from available rings")
            alerts = analyze_biomarker_data(oura_data, ultrahuman_data)
            insights = generate_ai_insights(oura_data, ultrahuman_data, alerts)

        if not insights:
            logger.info("[RING_DATA] No insights generated, using default insights")
            # Update the insights message to be more accurate when no data is available
            has_error = (oura_data and 'error' in oura_data) or (ultrahuman_data and 'error' in ultrahuman_data)
            
            if has_error:
                insights = {
                    "alert_summary": "Ring data currently unavailable",
                    "current_state": "Unable to retrieve authentic biometric data",
                    "primary_recommendations": ["Check API connections", "Verify ring is paired and charged"],
                    "secondary_recommendations": ["Ensure proper ring fit", "Wait for next data sync"],
                    "monitoring_focus": "Ring connectivity and data service availability"
                }
            else:
                insights = {
                    "alert_summary": "Limited biometric data available",
                    "current_state": "Partial data received from rings",
                    "primary_recommendations": ["Monitor real-time health data", "Check ring connection"],
                    "secondary_recommendations": ["Ensure proper ring fit", "Verify sync status"],
                    "monitoring_focus": "Ring data quality and connectivity"
                }

        response_data = {
            'status': 'success',
            'show_ring_data': True,
            'oura': oura_data,
            'ultrahuman': ultrahuman_data,
            'alerts': alerts,
            'insights': insights,
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'timezone': 'UTC'
        }

        logger.info("[RING_DATA] Complete response data prepared")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"[RING_DATA] Error in get_ring_data: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': "An error occurred while fetching ring data",
            'show_ring_data': False,
            'error_details': str(e)
        }), 500

def analyze_biomarker_data(oura_data, ultrahuman_data):
    """Analyze biomarker data and detect significant patterns"""
    try:
        logger.debug("Starting biomarker analysis")
        alerts = []

        # Continue only if we have at least some data
        if not oura_data and not ultrahuman_data:
            logger.warning("[RING_DATA] No data available for analysis")
            return alerts
            
        # Skip data with errors
        if oura_data and 'error' in oura_data:
            oura_data = None
        if ultrahuman_data and 'error' in ultrahuman_data:
            ultrahuman_data = None
            
        # Use either source based on availability
        o_stress = oura_data.get('stress_level') if oura_data else None
        o_hrv = oura_data.get('heart_rate_variability') if oura_data else None
        o_temp = oura_data.get('skin_temperature') if oura_data else None
        
        u_hrv = ultrahuman_data.get('heart_rate_variability') if ultrahuman_data else None
        u_recovery = ultrahuman_data.get('recovery_index') if ultrahuman_data else None
        u_temp = ultrahuman_data.get('skin_temperature') if ultrahuman_data else None

        # Analyze stress level from Oura with more granular thresholds
        if o_stress is not None and o_stress > 60:  # Lowered from 70
            if o_stress > 80:
                severity = "high"
                description = f"Critical stress level detected at {o_stress}/100"
            elif o_stress > 70:
                severity = "moderate"
                description = f"Elevated stress level at {o_stress}/100"
            else:
                severity = "warning"
                description = f"Mild stress elevation at {o_stress}/100"

            alerts.append({
                'type': 'stress',
                'severity': severity,
                'value': o_stress,
                'description': description
            })

        # Cross-validate HRV from both devices with more sensitive thresholds and improved logging
        logger.debug(f"[RING_DATA] Oura HRV: {o_hrv}, Ultrahuman HRV: {u_hrv}")
        
        # Extract Oura HRV value if it's in complex format (dict with items array)
        oura_hrv_value = None
        if isinstance(o_hrv, dict) and 'items' in o_hrv:
            # For arrays of HRV values, use the average of non-None values
            hrv_items = [item for item in o_hrv.get('items', []) if item is not None]
            if hrv_items:
                oura_hrv_value = sum(hrv_items) / len(hrv_items)
                logger.info(f"[RING_DATA] Calculated average Oura HRV from {len(hrv_items)} values: {oura_hrv_value:.1f}")
        else:
            oura_hrv_value = o_hrv  # Use as is if it's already a simple value
        
        # Handle case where one value might be None
        if oura_hrv_value is None and u_hrv is None:
            avg_hrv = None  # No HRV data available
        elif oura_hrv_value is None:
            avg_hrv = u_hrv  # Use Ultrahuman value if Oura is None
        elif u_hrv is None:
            avg_hrv = oura_hrv_value  # Use Oura value if Ultrahuman is None
        else:
            avg_hrv = (oura_hrv_value + u_hrv) / 2  # Average both values if both exist
            
        logger.debug(f"[RING_DATA] Calculated average HRV: {avg_hrv}")

        # More granular HRV analysis
        if avg_hrv is not None and isinstance(avg_hrv, (int, float)):
            if avg_hrv < 35:
                severity = "high"
                alerts.append({
                    'type': 'hrv',
                    'severity': severity,
                    'value': avg_hrv,
                    'description': f"Heart rate variability is low at {avg_hrv:.1f}ms"
                })
            elif avg_hrv < 45:
                severity = "moderate"
                alerts.append({
                    'type': 'hrv',
                    'severity': severity,
                    'value': avg_hrv,
                    'description': f"Heart rate variability is below ideal at {avg_hrv:.1f}ms"
                })

        # Enhanced recovery analysis with more detailed thresholds and null handling
        logger.debug(f"[RING_DATA] Recovery index: {u_recovery}")
        
        # Only perform analysis if recovery_index is not None
        if u_recovery is not None and u_recovery < 75:  # Changed from 70
            if u_recovery < 60:
                severity = "high"
                description = "Significantly reduced recovery capacity"
            elif u_recovery < 70:
                severity = "moderate"
                description = "Moderately limited recovery capacity"
            else:
                severity = "warning"
                description = "Slightly reduced recovery capacity"

            alerts.append({
                'type': 'recovery',
                'severity': severity,
                'value': u_recovery,
                'description': f"{description}: {u_recovery}/100"
            })

        # New: Analyze temperature variations with improved null checking
        logger.debug(f"[RING_DATA] Oura temperature: {o_temp}°C, Ultrahuman temperature: {u_temp}°C")
        
        # Calculate temperature difference safely
        if o_temp is not None and u_temp is not None:
            # Calculate absolute difference between the two temperature values
            temp_diff = abs(o_temp - u_temp)
            logger.debug(f"[RING_DATA] Real temperature difference: {temp_diff:.3f}°C")
            
            # If difference is unrealistically large (e.g., over 3°C), it might indicate a calibration issue
            if temp_diff > 3.0:
                logger.warning(f"[RING_DATA] Temperature difference too large ({temp_diff:.1f}°C), possibly a calibration issue")
                # Cap the difference to a more realistic value for alerts
                temp_diff = min(temp_diff, 3.0)
                
            # Check temp_diff with null handling
            if temp_diff > 0.5:
                alerts.append({
                    'type': 'temperature',
                    'severity': 'warning',
                    'value': temp_diff,
                    'description': f"Significant temperature variation detected: {temp_diff:.1f}°C difference between sensors"
                })
        else:
            logger.debug("[RING_DATA] Skipping temperature difference calculation due to missing data")

        # New: Cross-metric pattern detection - with type check and null check
        if (o_stress is not None and avg_hrv is not None and
            isinstance(o_stress, (int, float)) and isinstance(avg_hrv, (int, float)) and
            o_stress > 55 and avg_hrv < 45):
            alerts.append({
                'type': 'stress_hrv_correlation',
                'severity': 'moderate',
                'value': o_stress,
                'description': "Elevated stress levels affecting heart rate variability"
            })

        logger.debug(f"Analysis complete. Found {len(alerts)} alerts")
        return alerts

    except Exception as e:
        logger.error(f"Error analyzing biomarker data: {str(e)}", exc_info=True)
        return []

def generate_ai_insights(oura_data, ultrahuman_data, alerts):
    """Generate AI-powered insights based on biomarker patterns"""
    try:
        if not client:
            logger.warning("OpenAI client not available, skipping insights generation")
            return None
            
        # Skip data with errors
        if oura_data and 'error' in oura_data:
            oura_data = None
        if ultrahuman_data and 'error' in ultrahuman_data:
            ultrahuman_data = None

        logger.info("Starting AI insights generation")

        # Skip generation if both data sources have no valid data
        if oura_data is None and ultrahuman_data is None:
            logger.warning("No valid data available for AI insights")
            return {
                "alert_summary": "No biometric data available",
                "current_state": "Unable to generate insights without data",
                "primary_recommendations": ["Check ring connection", "Verify API access"],
                "secondary_recommendations": ["Ensure ring is charged", "Wait for next data sync"],
                "monitoring_focus": "Ring connectivity and data availability"
            }

        # Create enhanced context for GPT
        current_hour = datetime.now().hour
        time_context = (
            "evening" if current_hour >= 18 else
            "afternoon" if current_hour >= 12 else
            "morning"
        )
        
        # Get values with safe handling of None/null values
        oura_hrv = oura_data.get('heart_rate_variability') if oura_data else None
        ultra_hrv = ultrahuman_data.get('heart_rate_variability') if ultrahuman_data else None
        
        # Process complex Oura HRV data if needed
        oura_hrv_value = None
        if isinstance(oura_hrv, dict) and 'items' in oura_hrv:
            # For arrays of HRV values, use the average of non-None values
            hrv_items = [item for item in oura_hrv.get('items', []) if item is not None]
            if hrv_items:
                oura_hrv_value = sum(hrv_items) / len(hrv_items)
                logger.info(f"[INSIGHTS] Calculated average Oura HRV from {len(hrv_items)} values: {oura_hrv_value:.1f}")
        else:
            oura_hrv_value = oura_hrv  # Use as is if it's already a simple value
        
        # Calculate average HRV safely
        if oura_hrv_value is not None and ultra_hrv is not None:
            hrv_average = (oura_hrv_value + ultra_hrv) / 2
        elif oura_hrv_value is not None:
            hrv_average = oura_hrv_value
        elif ultra_hrv is not None:
            hrv_average = ultra_hrv
        else:
            hrv_average = None
            
        # Calculate temperature delta safely
        oura_temp = oura_data.get('skin_temperature') if oura_data else None
        ultra_temp = ultrahuman_data.get('skin_temperature') if ultrahuman_data else None
        
        if oura_temp is not None and ultra_temp is not None:
            temp_delta = abs(oura_temp - ultra_temp)
        else:
            temp_delta = 0.0

        # Enhanced context with more detailed biometric correlations
        context = {
            "trigger_events": [
                {
                    "type": alert['type'],
                    "description": alert['description'],
                    "severity": alert['severity'],
                    "value": alert['value']
                } for alert in alerts
            ],
            "temporal_context": {
                "time_of_day": time_context,
                "hour": current_hour,
                "circadian_phase": "active" if 6 <= current_hour <= 22 else "rest"
            },
            "current_state": {
                "stress_level": oura_data.get('stress_level') if oura_data else None,
                "recovery_index": ultrahuman_data.get('recovery_index') if ultrahuman_data else None,
                "hrv_average": hrv_average,
                "temperature_delta": temp_delta,
                "vo2_max": ultrahuman_data.get('vo2_max') if ultrahuman_data else None
            },
            "historical_context": {
                "alerts_count": len(alerts),
                "primary_concern": alerts[0]['type'] if alerts else "none",
                "stress_hrv_correlation": any(a['type'] == 'stress_hrv_correlation' for a in alerts)
            }
        }

        messages = [
            {
                "role": "system",
                "content": """You are an expert in biometric analysis and health optimization.
                Analyze the biomarker data considering:
                1. Time of day and circadian rhythms
                2. Correlations between stress, HRV, and recovery
                3. Temperature variations and their implications
                4. Cumulative effects of multiple metrics

                Provide specific insights focusing on:
                - Pattern recognition across metrics
                - Time-sensitive recommendations
                - Preventive measures
                - Recovery optimization

                Format your response with these sections without using markdown:
                Alert Summary: Current state overview
                Current State: Detailed analysis of metrics
                Primary Recommendations: Immediate actions needed
                Secondary Recommendations: Preventive measures
                Monitoring Focus: Key metrics to watch"""
            },
            {
                "role": "user",
                "content": f"Analyze these real-time biomarker readings and provide insights:\n{json.dumps(context, indent=2)}"
            }
        ]

        try:
            # Start timer for API call
            start_time_api = time.time()
            success = True
            status_code = 200
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.7
                )
            except Exception as e:
                success = False
                status_code = 500  # OpenAI client doesn't always provide status codes
                logger.error(f"[RING_DATA] Error in OpenAI API call: {str(e)}")
                raise
            finally:
                # Calculate response time
                response_time = time.time() - start_time_api
                
                # Log the API call
                log_api_call(
                    api_name="OpenAI",
                    endpoint="chat.completions (biomarker analysis)",
                    response_time=response_time,
                    success=success,
                    status_code=status_code
                )

            # Initialize default insights
            insights = {
                "alert_summary": "No significant patterns detected",
                "current_state": "All metrics within normal ranges",
                "primary_recommendations": ["Continue normal activities", "Stay hydrated"],
                "secondary_recommendations": ["Monitor stress levels", "Maintain regular sleep schedule"],
                "monitoring_focus": "Regular health maintenance"
            }

            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                # Extract key sections from the response
                if "Alert Summary:" in content:
                    insights["alert_summary"] = content.split("Alert Summary:")[1].split("\n")[0].strip()
                if "Current State:" in content:
                    insights["current_state"] = content.split("Current State:")[1].split("\n")[0].strip()
                if "Primary Recommendations:" in content:
                    recommendations = content.split("Primary Recommendations:")[1].split("Secondary Recommendations:")[0]
                    insights["primary_recommendations"] = [r.strip().strip('- ') for r in recommendations.split("\n") if r.strip()]
                if "Secondary Recommendations:" in content:
                    recommendations = content.split("Secondary Recommendations:")[1].split("Monitoring Focus:")[0]
                    insights["secondary_recommendations"] = [r.strip().strip('- ') for r in recommendations.split("\n") if r.strip()]
                if "Monitoring Focus:" in content:
                    insights["monitoring_focus"] = content.split("Monitoring Focus:")[1].strip()

            try:
                # Store insights in database with safe default for value 
                # Use first alert for threshold or a default if no alerts
                threshold = alerts[0].get('value', 0) if alerts else 0
                if threshold is None:
                    threshold = 0
                
                # Create database entry for tracking
                insight = BiomarkerInsight(
                    user_id=current_user.id,
                    source='Combined Ring Data',
                    metric_type=alerts[0].get('type', 'general') if alerts else 'general',
                    value=threshold,
                    threshold=threshold * 0.9,  # Store 90% of value as threshold
                    trigger_description=insights["alert_summary"],
                    impact_description=insights["current_state"],
                    recommendations=insights["primary_recommendations"]
                )
                db.session.add(insight)
                db.session.commit()
                logger.info("Stored new biomarker insight")
                
            except Exception as e:
                logger.error(f"Error storing insight in database: {str(e)}")
                db.session.rollback()

            return insights

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return None

    except Exception as e:
        logger.error(f"Error in generate_ai_insights: {str(e)}", exc_info=True)
        return None