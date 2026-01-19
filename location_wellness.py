import os
import logging
import time
from datetime import datetime
import math
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
import requests

# Import API logging function
from ai_client import log_api_call

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Update restaurant detection parameters based on exact requirements
SEARCH_RADIUS = 5000  # meters (3 miles) - significantly increased to find more restaurants in Gurnee
ALERT_RADIUS = 150  # meters (~500 feet) - only trigger when actually in/near parking lot
MIN_SPEED = 0.5      # km/h (minimum speed for manual tracking)
SPEED_THRESHOLD = 16.1  # km/h (10 mph - maximum speed for alerts) - will trigger alerts when slowing under this speed
AUTO_START_SPEED = 24.14  # km/h (15 mph - required for auto-start) - system will reset when reaching this speed again
MIN_ACCURACY = 20    # meters (GPS accuracy threshold)

# Initialize blueprint
location_wellness = Blueprint('location_wellness', __name__)

# Initialize API configuration
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
if not GOOGLE_MAPS_API_KEY:
    logger.error("GOOGLE_MAPS_API_KEY environment variable is not set!")

PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# Update fast food detection parameters - now using global restaurant chains
fast_food_chains = {
    # North American chains
    'mcdonalds', 'burger king', 'wendys', 'taco bell', 'kfc', 
    'popeyes', 'white castle', 'subway', 'five guys', 'culvers',
    'arbys', 'chipotle', 'panera', 'jimmy johns', 'jersey mikes',
    'raising canes', 'chick-fil-a', 'panda express', 'dairy queen', 
    'baskin robbins', 'cold stone', 'haagen-dazs', 'ben & jerrys',
    'dunkin', 'krispy kreme', 'in-n-out', 'whataburger', 'shake shack',
    'zaxbys', 'wingstop', 'bojangles',
    
    # International chains
    'jollibee', 'tim hortons', 'mos burger', 'yoshinoya', 'lotteria', 
    'telepizza', 'supermacs', 'nordsee', 'hesburger', 'max burger',
    'vapiano', 'wagamama', 'pret a manger', 'greggs', 'nandos',
    'giraffe', 'wimpy', 'itsu', 'el pollo loco', 'goiko grill',
    
    # Coffee chains
    'starbucks', 'costa coffee', 'caffe nero', 'tim hortons', 
    'second cup', 'coffee bean', 'dutch bros', 'peets coffee',
    
    # Generic terms - should match in any language
    'restaurant', 'food', 'pizza', 'burger', 'cafe', 'diner',
    'ice cream', 'frozen yogurt', 'donut', 'doughnut', 'bakery',
    'steakhouse', 'grill', 'bar', 'pub', 'bistro', 'trattoria',
    'eatery', 'dining', 'fast food'
}

def is_fast_food_place(name, types):
    """Enhanced detection of fast food places, ice cream shops, and donut shops
    Most inclusive implementation to catch all potential food places"""
    name = name.lower()

    # In test mode, accept ANY establishment related to food
    # Expanded list of food-related types to be as inclusive as possible
    restaurant_related_types = [
        'restaurant', 'food', 'cafe', 'meal_delivery', 'meal_takeaway', 
        'bakery', 'bar', 'establishment', 'point_of_interest', 'store',
        'supermarket', 'grocery_or_supermarket', 'convenience_store'
    ]
    
    # More permissive check: as long as one type matches, consider it a potential restaurant
    # This will catch more places but might include some false positives
    if not any(t in types for t in restaurant_related_types):
        return False

    # Check for exact matches with known chains - highly permissive check
    if any(chain in name for chain in fast_food_chains):
        return True

    # Additional checks for ice cream shops - broader match
    if ('ice' in name or 'cream' in name or 'frozen' in name or 'yogurt' in name):
        return True

    # Additional checks for donut shops - broader match
    if ('donut' in name or 'doughnut' in name or 'bakery' in name or 'pastry' in name):
        return True
    
    # Check for common keywords that suggest fast food
    food_keywords = ['burger', 'pizza', 'sandwich', 'taco', 'chicken', 'fries', 
                     'grill', 'fast', 'drive', 'express', 'quick', 'wings']
    
    if any(keyword in name for keyword in food_keywords):
        return True
        
    # Added detection for common restaurant keywords
    common_keywords = ['grill', 'kitchen', 'pizza', 'burger', 'taco', 'mexican', 
                       'chinese', 'thai', 'italian', 'steakhouse', 'seafood', 
                       'café', 'cafe', 'diner', 'buffet', 'house']
                       
    if any(keyword in name for keyword in common_keywords):
        return True
    
    # Accept all restaurant types for better testing experience
    if 'restaurant' in types:
        return True

    return False

def get_nearby_places(lat, lon, radius=None):
    """Get nearby places using Google Places API with enhanced fast food detection"""
    try:
        if not GOOGLE_MAPS_API_KEY:
            logger.error("GOOGLE_MAPS_API_KEY is not configured!")
            return None

        logger.info(f"Searching for nearby places at ({lat:.6f}, {lon:.6f})")
        
        # Use provided radius or default to global constant
        search_radius = radius if radius and isinstance(radius, int) else SEARCH_RADIUS

        # Search parameters optimized for detecting ALL nearby food places
        # Using separate types to ensure we get comprehensive results
        restaurant_params = {
            'location': f"{lat},{lon}",
            'radius': search_radius,
            'type': 'restaurant',  # Primary type for restaurants
            'key': GOOGLE_MAPS_API_KEY
        }
        
        # Log the search radius being used
        logger.info(f"Using search radius of {search_radius} meters (~{search_radius/1609:.2f} miles)")

        logger.info(f"Making Places API request with params: {restaurant_params}")
        
        # Start timer for API call
        start_time_api = time.time()
        success = True
        status_code = 200
        
        try:
            response = requests.get(PLACES_NEARBY_URL, params=restaurant_params)
            status_code = response.status_code
            
            if response.status_code != 200:
                success = False
                logger.error(f"Places API error: {response.status_code}")
                logger.error(f"Response content: {response.text}")
                return None
        except Exception as e:
            success = False
            status_code = 500
            logger.error(f"Places API request exception: {str(e)}")
            raise
        finally:
            # Calculate response time
            response_time = time.time() - start_time_api
            
            # Log the API call
            log_api_call(
                api_name="Google Maps",
                endpoint="places/nearbysearch",
                response_time=response_time,
                success=success,
                status_code=status_code
            )

        results = response.json()

        if results.get('status') != 'OK':
            logger.error(f"Places API returned non-OK status: {results.get('status')}")
            logger.error(f"Error message: {results.get('error_message', 'No error message')}")
            return None

        results = results.get('results', [])
        logger.info(f"Found {len(results)} potential places in search")

        closest_restaurant = None
        closest_distance = float('inf')

        for place in results:
            place_types = place.get('types', [])
            name = place.get('name', '').lower()

            # Log each place being checked
            logger.debug(f"Checking place: {name} with types: {place_types}")

            if is_fast_food_place(name, place_types):
                place_loc = place.get('geometry', {}).get('location', {})
                if place_loc:
                    distance = calculate_distance(
                        lat, lon,
                        place_loc.get('lat'),
                        place_loc.get('lng')
                    )

                    logger.info(f"Found fast food restaurant: {name} at distance: {distance:.1f}m")

                    if distance <= ALERT_RADIUS:
                        logger.info(f"Restaurant within alert radius: {name} at {distance:.1f}m")
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_restaurant = place.get('name')

        if closest_restaurant:
            logger.info(f"Selected closest restaurant: {closest_restaurant} at {closest_distance:.1f}m")
            return {
                'restaurant': closest_restaurant,
                'distance': closest_distance
            }

        logger.info("No fast food restaurants found within alert radius")
        return None

    except Exception as e:
        logger.error(f"Error getting nearby places: {e}", exc_info=True)
        return None

@location_wellness.route('/api/nearby-places', methods=['POST'])
@login_required
def get_nearby_places_endpoint():
    """Endpoint for getting nearby fast food places"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400

        lat = float(data.get('latitude'))
        lon = float(data.get('longitude'))
        
        # Use client-provided radius if available, otherwise use default
        radius = data.get('radius')
        if radius and isinstance(radius, int):
            custom_radius = radius
            logger.info(f"Using client-specified search radius: {custom_radius} meters")
        else:
            custom_radius = SEARCH_RADIUS
            logger.info(f"Using default search radius: {custom_radius} meters")

        # Search for nearby places using the Places API with custom radius
        places = get_nearby_places(lat, lon, radius=custom_radius)

        if places:
            return jsonify({
                'status': 'success',
                'results': [places]
            })

        return jsonify({
            'status': 'success',
            'results': []
        })

    except Exception as e:
        logger.error(f"Error in get_nearby_places_endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@location_wellness.route('/')
@location_wellness.route('/location-wellness/')
@login_required
def index():
    """Main location wellness page"""
    return render_template(
        'location_wellness.html',
        google_maps_api_key=GOOGLE_MAPS_API_KEY,
        enable_speech=True
    )

class LocationTracker:
    def __init__(self):
        # Alert timing parameters (based on January 2025 documentation)
        self.last_alert_time = None
        self.last_alert_location = None
        self.alert_cooldown = 60  # seconds between different restaurants (standard cooldown)
        self.same_restaurant_cooldown = 300  # seconds for same restaurant (5 minutes)
        
        # Speed monitoring parameters
        self.last_speed = 0
        self.last_restaurant = None
        self.high_speed_count = 0  # Track consecutive high-speed readings
        self.speed_threshold = AUTO_START_SPEED  # 24.14 km/h (15 mph) for auto restart
        self.low_speed_threshold = SPEED_THRESHOLD  # 16.1 km/h (10 mph) for alert triggering
        self.min_speed = MIN_SPEED  # 0.5 km/h minimum speed for manual tracking
        
        # State tracking
        self.location_tracking_enabled = True
        self.manuallyStoppedTracking = False  # Used to prevent unwanted auto-restart
        self.hasReachedAutoStartSpeed = False # High-speed threshold flag
        
        # Device-specific data
        self.device_info = None
        
        logger.info("Initialized new LocationTracker instance with January 2025 configuration")

    def should_trigger_alert(self, current_time, restaurant_name, current_speed, is_parked=False):
        try:
            logger.debug(f"Checking alert trigger - Speed: {current_speed} km/h, Restaurant: {restaurant_name}, Is Parked: {is_parked}")

            # Special handling for Raising Cane's - always trigger alerts when nearby
            if restaurant_name and 'raising cane' in restaurant_name.lower():
                logger.debug(f"Special case: Raising Cane's detected - always triggering alert")
                return True

            # Always trigger for parked status near restaurants (highest priority)
            if is_parked:
                logger.debug(f"User is parked near restaurant: {restaurant_name} - triggering alert")
                return True
                
            # Reset last restaurant if speed is high enough (>15 mph / 24.14 km/h)
            if current_speed > self.speed_threshold:  # 24.14 km/h = 15 mph
                self.high_speed_count += 1
                if self.high_speed_count >= 2:  # Only need 2 consecutive high speed readings to reset
                    logger.debug(f"Resetting last restaurant due to sustained high speed: {current_speed} km/h (>15 mph)")
                    self.last_restaurant = None
                    self.last_alert_time = None
                return False
            # Trigger alert when speed is below the low threshold (<10 mph / 16.1 km/h) near restaurants
            elif current_speed < self.low_speed_threshold:  # 16.1 km/h = 10 mph
                self.high_speed_count = 0
                logger.debug(f"Speed below threshold of 10 mph ({current_speed} < {self.low_speed_threshold}), triggering alert")
                return True  # Trigger alert if below threshold and near restaurant
            else:
                # Speed is between 10-15 mph (16.1-24.14 km/h) - don't trigger here
                self.high_speed_count = 0  # Reset counter when speed is in the middle range

            # Skip if this is the same restaurant we just alerted for (except Raising Cane's)
            if restaurant_name == self.last_restaurant and 'raising cane' not in restaurant_name.lower():
                time_diff = (current_time - self.last_alert_time).total_seconds()
                if time_diff < self.same_restaurant_cooldown:
                    logger.debug(f"Skipping alert for same restaurant: {restaurant_name} (cooldown: {time_diff}s < {self.same_restaurant_cooldown}s)")
                    return False
                logger.debug(f"Same restaurant cooldown expired: {restaurant_name}")
                return True

            # First alert of the session
            if not self.last_alert_time:
                logger.debug("First alert of the session")
                return True

            # Calculate time since last alert
            time_diff = (current_time - self.last_alert_time).total_seconds()

            # Always return true for low cooldown to ensure alerts trigger more reliably
            should_trigger = time_diff >= self.alert_cooldown / 2  # Reduce cooldown time
            logger.debug(f"Alert check - Time diff: {time_diff}s, Should trigger: {should_trigger}")
            return should_trigger

        except Exception as e:
            logger.error(f"Error in should_trigger_alert: {e}", exc_info=True)
            return True  # Return True on error to ensure alerts still trigger

    def update_alert(self, restaurant_name):
        try:
            self.last_alert_time = datetime.now()
            self.last_restaurant = restaurant_name
            self.high_speed_count = 0  # Reset high speed counter
            logger.debug(f"Updated alert time and set last restaurant to: {restaurant_name}")
        except Exception as e:
            logger.error(f"Error updating alert: {e}", exc_info=True)

    def update_speed(self, speed):
        try:
            self.last_speed = speed
            # When speed exceeds 15 mph (24.14 km/h), consider it "driving away" from restaurants
            if speed > self.speed_threshold:  # 24.14 km/h = 15 mph
                self.high_speed_count += 1
                if self.high_speed_count >= 2:  # Only need 2 consecutive high speed readings to reset
                    logger.debug(f"Resetting tracking due to sustained high speed: {speed} km/h (>15 mph)")
                    self.reset_location()
            else:
                # Reset counter when speed drops below threshold
                self.high_speed_count = 0
            logger.debug(f"Updated speed: {speed} km/h (threshold: {self.speed_threshold} km/h)")
        except Exception as e:
            logger.error(f"Error updating speed: {e}", exc_info=True)

    def reset_location(self):
        try:
            if self.last_restaurant:
                logger.debug(f"Resetting last restaurant from: {self.last_restaurant}")
                self.last_restaurant = None
            self.last_alert_time = None
            self.high_speed_count = 0
        except Exception as e:
            logger.error(f"Error resetting location: {e}", exc_info=True)


# User-specific trackers dictionary
# This keeps separate location trackers for each user and device
_location_trackers = {}

def get_location_tracker(device_id=None):
    """
    Get a location tracker instance specific to the current user and device.
    This ensures each user has their own isolated tracking instance.
    
    Args:
        device_id (str, optional): Device identifier for multi-device users
    
    Returns:
        LocationTracker: Instance specific to this user and device
    """
    try:
        # Get the current user ID from Flask-Login
        user_id = current_user.id if current_user.is_authenticated else 0
        
        # Create a key using user_id and optional device_id to isolate tracking per user and device
        tracker_key = f"user_{user_id}"
        
        # Add device_id to tracker key if provided
        if device_id:
            tracker_key = f"{tracker_key}_{device_id}"
        
        # Initialize a new tracker if one doesn't exist for this user/device
        if tracker_key not in _location_trackers:
            logger.info(f"Creating new LocationTracker instance for {tracker_key}")
            _location_trackers[tracker_key] = LocationTracker()
            
        return _location_trackers[tracker_key]
    except Exception as e:
        # Fallback to prevent errors
        logger.error(f"Error getting location tracker: {e}", exc_info=True)
        return LocationTracker()

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in meters using Haversine formula"""
    try:
        R = 6371000  # Earth's radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * \
            math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        logger.debug(
            f"Distance calculated: {distance:.1f}m between ({lat1:.6f}, {lon1:.6f}) and ({lat2:.6f}, {lon2:.6f})")
        return distance
    except Exception as e:
        logger.error(f"Error calculating distance: {e}", exc_info=True)
        return float('inf')

def format_audio_message(place_data):
    try:
        message_parts = []

        if place_data and isinstance(place_data, dict) and 'restaurant' in place_data:
            restaurant_name = place_data['restaurant']
            distance = place_data.get('distance', 0)
            message_parts.append(
                f"Alert: You are near {restaurant_name}, approximately {int(distance)} meters away.")
        else:
            message_parts.append("Alert: You are near a fast food location.")

        message_parts.append("Let's consider some mindful eating suggestions.")

        # Complete list of mindful eating suggestions
        message_parts.extend([
            "Take a moment to check your hunger level on a scale of 1 to 10.",
            "Consider if you're eating from physical hunger or emotional needs.",
            "Remember your health goals and values.",
            "Think about how you'll feel after eating - will it align with your goals?",
            "Practice mindful eating by taking smaller bites and eating slowly.",
            "Listen to your body's natural hunger and fullness signals.",
            "Consider going for a short walk or drinking water first.",
            "Remember that every meal is an opportunity to nourish your body."
        ])

        return " ".join(message_parts)
    except Exception as e:
        logger.error(f"Error formatting audio message: {e}", exc_info=True)
        return "Alert: You are near a fast food location."

@location_wellness.route('/api/location-status', methods=['POST'])
@location_wellness.route('/location-wellness/api/location-status', methods=['POST'])
@login_required
def update_location():
    try:
        data = request.get_json()
        user_lat = float(data.get('latitude'))
        user_lon = float(data.get('longitude'))
        accuracy = float(data.get('accuracy', 100))
        current_speed = float(data.get('speed', 0))
        audio_completed = bool(data.get('audio_completed', True))
        is_parked = bool(data.get('is_parked', False))

        logger.info(f"Received location update - lat: {user_lat:.6f}, lon: {user_lon:.6f}, "
                    f"accuracy: {accuracy}m, speed: {current_speed}km/h, is_parked: {is_parked}")

        # Skip if accuracy is poor
        if accuracy > MIN_ACCURACY:
            logger.debug(f"Skipping update - poor accuracy: {accuracy}m")
            return jsonify({'status': 'scanning', 'message': 'Poor GPS accuracy'})

        # Skip if audio is still playing
        if not audio_completed:
            logger.debug("Skipping update - audio still playing")
            return jsonify({'status': 'scanning', 'message': 'Audio playing'})

        # Always check for nearby places
        logger.info("Making Places API request...")
        place_data = get_nearby_places(user_lat, user_lon)

        if place_data:
            logger.info(f"Place data received: {place_data}")
        else:
            logger.info("No place data received from Places API")

        # Don't force restaurant detection, let the API find real restaurants
        # Use the actual place_data returned from the API
        if not place_data:
            logger.info(f"No restaurants found near coordinates: {user_lat}, {user_lon}")
        else:
            logger.info(f"Restaurant found: {place_data['restaurant']} at distance: {place_data['distance']}m")
        
        # Safely extract restaurant information if available
        if place_data and isinstance(place_data, dict) and 'restaurant' in place_data:
            restaurant_name = place_data['restaurant']
            distance = place_data.get('distance', 0)

            # Special case for Raising Cane's - always trigger
            if 'raising cane' in restaurant_name.lower():
                logger.info(f"Special restaurant detected: {restaurant_name} - Always triggering alert")
                is_parked = True  # Force parked status for Raising Cane's
                current_speed = 0  # Force zero speed

            # Log the detection event (keep specific restaurant name in logs)
            logger.info(f"Restaurant detected: {restaurant_name} at {distance:.1f}m, "
                        f"speed: {current_speed:.1f}km/h, parked: {is_parked}")

            # Get device info if provided
            device_id = data.get('device_id', 'default')
            device_type = data.get('device_type', 'unknown')
            
            # Get location tracker with device context if available
            location_tracker = get_location_tracker(device_id)
            
            # Log device information
            if device_id and device_id != 'default':
                logger.info(f"Got location update from device: {device_id} ({device_type})")
            
            # Check if an alert should trigger based on conditions from January 2025 docs
            current_time = datetime.now()
            should_trigger = location_tracker.should_trigger_alert(
                current_time, 
                restaurant_name, 
                current_speed,
                is_parked
            )
            
            logger.info(f"Alert trigger check for {restaurant_name}: {should_trigger} (speed: {current_speed}, parked: {is_parked})")

            if should_trigger:
                logger.info(f"Triggering alert for fast food location: {restaurant_name} (parked: {is_parked})")

                audio_message = format_audio_message(place_data)
                suggestions = [
                    "Take a moment to check your hunger level (1-10)",
                    "Consider if you're eating from physical hunger or emotional needs",
                    "Remember your health goals and values",
                    "Think about how you'll feel after eating - will it align with your goals?",
                    "Practice mindful eating by taking smaller bites and eating slowly",
                    "Listen to your body's natural hunger and fullness signals",
                    "Consider going for a short walk or drinking water first",
                    "Remember that every meal is an opportunity to nourish your body"
                ]

                location_tracker.update_alert(restaurant_name)  # Update alert after successful trigger

                return jsonify({
                    'status': 'active',
                    'suggestions': suggestions,
                    'audio_message': audio_message,
                    'restaurant_name': restaurant_name,  # Use actual restaurant name
                    'distance': distance
                })
            else:
                logger.debug(f"Speed too high for alert: {current_speed:.1f}km/h")
                location_tracker.update_speed(current_speed)  # Update speed regardless of alert trigger

        else:
            # No restaurants found within alert radius - use actual GPS data only
            logger.debug("No restaurants found within alert radius")
            
            # Get device info if provided
            device_id = data.get('device_id', 'default')
            
            # Still use device-specific tracker even when no restaurants are found
            location_tracker = get_location_tracker(device_id)
            location_tracker.update_speed(current_speed)

        return jsonify({'status': 'scanning'})

    except Exception as e:
        logger.error(f"Error in update_location: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@location_wellness.route('/api/location-tracking', methods=['POST'])
@location_wellness.route('/location-wellness/api/location-tracking', methods=['POST'])
@login_required
def toggle_tracking():
    try:
        data = request.get_json()
        tracking_enabled = data.get('enabled', False)
        
        # Get the current user ID
        user_id = current_user.id if current_user.is_authenticated else 0
        tracker_key = f"user_{user_id}"
        
        # Include optional device_id if provided
        device_id = data.get('device_id', 'default')
        if device_id and device_id != 'default':
            tracker_key = f"{tracker_key}_{device_id}"
        
        logger.info(f"Toggle tracking for {tracker_key}: {tracking_enabled}")

        if not tracking_enabled:
            # Remove the user's tracker if disabling tracking
            global _location_trackers
            if tracker_key in _location_trackers:
                logger.info(f"Removing location tracker for {tracker_key}")
                del _location_trackers[tracker_key]
                
        return jsonify({
            'status': 'success',
            'tracking_enabled': tracking_enabled,
            'tracker_key': tracker_key
        })

    except Exception as e:
        logger.error(f"Error toggling tracking: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@location_wellness.route('/test-places')
@login_required
def test_places_interface():
    """Render the test interface for Places API"""
    return render_template(
        'location_wellness.html',
        google_maps_api_key=GOOGLE_MAPS_API_KEY,
        enable_speech=True,
        test_mode=True
    )

@location_wellness.route('/api/test-places', methods=['POST'])
@location_wellness.route('/location-wellness/api/test-places', methods=['POST'])
@login_required
def test_places():
    """Test endpoint to verify Places API functionality"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400

        lat = float(data.get('latitude'))
        lon = float(data.get('longitude'))

        logger.info(f"[TEST] Testing Places API for coordinates: ({lat}, {lon})")

        # Test direct API call with a more focused radius for local restaurants only
        params = {
            'location': f"{lat},{lon}",
            'radius': 5000,  # 5000 meters (3 miles) to ensure we find restaurants in Gurnee
            # Specific type for restaurants
            'type': 'restaurant',
            # No keyword to get the broadest possible results
            'key': GOOGLE_MAPS_API_KEY
        }

        logger.info(f"[TEST] Making direct Places API request with params: {params}")
        response = requests.get(PLACES_NEARBY_URL, params=params)

        if response.status_code != 200:
            logger.error(f"[TEST] Places API error: {response.status_code}")
            logger.error(f"[TEST] Response content: {response.text}")
            return jsonify({
                'status': 'api_error',
                'error': response.text
            }), 500

        results = response.json()

        # Now test our place detection logic
        place_data = get_nearby_places(lat, lon)

        # Safely extract restaurant name if place_data exists and has a restaurant key
        detected_restaurant = None
        if place_data and isinstance(place_data, dict) and 'restaurant' in place_data:
            detected_restaurant = place_data['restaurant']

        return jsonify({
            'status': 'success',
            'raw_results': results.get('results', []),
            'processed_results': place_data,
            'api_status': results.get('status'),
            'total_places': len(results.get('results', [])),
            'detected_restaurant': detected_restaurant
        })

    except Exception as e:
        logger.error(f"[TEST] Error testing places: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@location_wellness.route('/api/test-api-key', methods=['POST'])
@location_wellness.route('/location-wellness/api/test-api-key', methods=['POST'])
@login_required
def test_api_key():
    """Test endpoint to verify Google Maps API key functionality"""
    try:
        if not GOOGLE_MAPS_API_KEY:
            logger.error("GOOGLE_MAPS_API_KEY is not configured")
            return jsonify({
                'status': 'error',
                'message': 'Google Maps API key is not configured'
            }), 400

        # Test endpoint URL
        test_url = "https://maps.googleapis.com/maps/api/geocode/json"
        test_params = {
            'address': 'San Francisco, CA',
            'key': GOOGLE_MAPS_API_KEY
        }

        logger.info("Testing Google Maps API key with geocoding request")
        response = requests.get(test_url, params=test_params)

        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'OK':
                logger.info("Google Maps API key test successful")
                return jsonify({
                    'status': 'success',
                    'message': 'API key is valid and working'
                })
            else:
                logger.error(f"Google Maps API returned error status: {data.get('status')}")
                return jsonify({
                    'status': 'error',
                    'message': f"API Error: {data.get('status')}"
                }), 400
        else:
            logger.error(f"Google Maps API request failed with status code: {response.status_code}")
            return jsonify({
                'status': 'error',
                'message': f"Request failed with status code: {response.status_code}"
            }), response.status_code

    except Exception as e:
        logger.error(f"Error testing Google Maps API key: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500