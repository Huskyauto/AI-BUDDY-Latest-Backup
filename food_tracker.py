import os
import logging
import time
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, FoodLog, WaterLog, WeightLog, WellnessQuotes
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import text
import requests

# Import API logging function
from ai_client import log_api_call

food_tracker_bp = Blueprint('food_tracker', __name__)
logger = logging.getLogger(__name__)

# Get Spoonacular API credentials from environment
SPOONACULAR_API_KEY = os.environ.get('SPOONACULAR_API_KEY', '')
SPOONACULAR_BASE_URL = "https://api.spoonacular.com"

# Log API configuration (without sensitive details)
logger.info(f"Spoonacular API configuration - API Key present: {bool(SPOONACULAR_API_KEY)}")

@food_tracker_bp.route('/api/search-food')
@login_required
def search_food():
    query = request.args.get('query', '').strip()
    try:
        if not query:
            logger.warning("Empty search query received")
            return jsonify({'status': 'error', 'message': 'Search query is required'}), 400

        if not SPOONACULAR_API_KEY:
            logger.error("Spoonacular API key not configured")
            return jsonify({
                'status': 'error',
                'message': 'Food search API not configured. Please add SPOONACULAR_API_KEY.'
            }), 500

        logger.info(f"Searching for food: {query}")
        
        # Start timer for API call
        start_time_api = time.time()
        success = True
        status_code = 200
        
        try:
            # First, search for ingredients using Spoonacular
            search_url = f"{SPOONACULAR_BASE_URL}/food/ingredients/search"
            search_params = {
                'apiKey': SPOONACULAR_API_KEY,
                'query': query,
                'number': 10,
                'metaInformation': True
            }
            
            logger.debug(f"Making request to Spoonacular search API")
            response = requests.get(search_url, params=search_params, timeout=10)
            status_code = response.status_code
            
            if response.status_code != 200:
                success = False
                logger.error(f"Spoonacular API error: {response.status_code} - {response.text}")
                if response.status_code == 401:
                    return jsonify({
                        'status': 'error',
                        'message': 'API authentication failed. Please check your API configuration.'
                    }), 401
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to fetch food data'
                }), response.status_code
                
            search_data = response.json()
            ingredients = search_data.get('results', [])
            
            foods = []
            
            # Get nutrition info for each ingredient
            for ingredient in ingredients[:10]:
                ingredient_id = ingredient.get('id')
                if ingredient_id:
                    nutrition_url = f"{SPOONACULAR_BASE_URL}/food/ingredients/{ingredient_id}/information"
                    nutrition_params = {
                        'apiKey': SPOONACULAR_API_KEY,
                        'amount': 100,
                        'unit': 'grams'
                    }
                    
                    try:
                        nutrition_response = requests.get(nutrition_url, params=nutrition_params, timeout=10)
                        if nutrition_response.status_code == 200:
                            nutrition_data = nutrition_response.json()
                            nutrients = nutrition_data.get('nutrition', {}).get('nutrients', [])
                            
                            # Extract key nutrients
                            calories = next((n['amount'] for n in nutrients if n['name'] == 'Calories'), 0)
                            protein = next((n['amount'] for n in nutrients if n['name'] == 'Protein'), 0)
                            fat = next((n['amount'] for n in nutrients if n['name'] == 'Fat'), 0)
                            carbs = next((n['amount'] for n in nutrients if n['name'] == 'Carbohydrates'), 0)
                            
                            foods.append({
                                'name': nutrition_data.get('name', ingredient.get('name', 'Unknown')),
                                'nutrients': {
                                    'calories': float(calories),
                                    'protein': float(protein),
                                    'fat': float(fat),
                                    'carbs': float(carbs)
                                },
                                'category': nutrition_data.get('aisle', 'Generic foods'),
                                'image': f"https://spoonacular.com/cdn/ingredients_100x100/{nutrition_data.get('image', '')}",
                                'serving_unit': 'grams',
                                'serving_weight': 100
                            })
                    except Exception as e:
                        logger.warning(f"Error getting nutrition for ingredient {ingredient_id}: {e}")
                        # Still add the ingredient with basic info if nutrition fetch fails
                        foods.append({
                            'name': ingredient.get('name', 'Unknown'),
                            'nutrients': {
                                'calories': 0,
                                'protein': 0,
                                'fat': 0,
                                'carbs': 0
                            },
                            'category': 'Generic foods',
                            'image': f"https://spoonacular.com/cdn/ingredients_100x100/{ingredient.get('image', '')}",
                            'serving_unit': 'grams',
                            'serving_weight': 100
                        })
                        
        except Exception as e:
            success = False
            status_code = 500
            logger.error(f"Spoonacular API request exception: {str(e)}")
            raise
        finally:
            # Calculate response time
            response_time = time.time() - start_time_api
            
            # Log the API call
            log_api_call(
                api_name="Spoonacular Food",
                endpoint=f"food/ingredients/search?query={query}",
                response_time=response_time,
                success=success,
                status_code=status_code
            )
            
        if not foods:
            logger.warning(f"No foods found with nutrient data for query: {query}")
            return jsonify({
                'status': 'error',
                'message': 'No foods found with nutrient data'
            }), 404

        logger.info(f"Returning {len(foods)} food items")
        return jsonify({
            'status': 'success',
            'results': foods[:10]
        })

    except Exception as e:
        logger.error(f"Error searching food: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_cst_datetime():
    """Get current time in Central Time"""
    return datetime.now(ZoneInfo("America/Chicago"))

def get_current_tracking_date():
    """
    Get the current tracking date, considering 3 AM CST as the start of a new day
    Returns date object for the current tracking period
    """
    current_cst = get_cst_datetime()
    logger.info(f"Current CST time: {current_cst}")

    if current_cst.hour < 3:
        # If it's before 3 AM, use previous day's date
        tracking_date = (current_cst - timedelta(days=1)).date()
    else:
        tracking_date = current_cst.date()

    logger.info(f"Using tracking date: {tracking_date}")
    return tracking_date

def get_tracking_date_bounds():
    """
    Get the datetime bounds for the current tracking period
    Returns tuple of (start_datetime, end_datetime) in CST
    """
    tracking_date = get_current_tracking_date()
    cst = ZoneInfo("America/Chicago")

    # Create datetime objects at 3 AM CST for start and end
    start_datetime = datetime.combine(tracking_date, datetime.min.time().replace(hour=3)).replace(tzinfo=cst)
    end_datetime = start_datetime + timedelta(days=1)

    logger.info(f"Tracking period - Start: {start_datetime}, End: {end_datetime}")
    return (start_datetime, end_datetime)

def get_random_quote():
    """Helper function to fetch a random wellness quote."""
    try:
        # Get current tracking period to determine context
        start_datetime, end_datetime = get_tracking_date_bounds()

        # Get user's food logs for the period to determine context
        food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= start_datetime,
            FoodLog.timestamp < end_datetime
        ).all()

        # Determine the most relevant category based on user's activity
        category = 'emotional_eating'  # default category that matches our database
        if not food_logs:
            category = 'motivation'
        elif any(log.emotional_state in ['stressed', 'anxious'] for log in food_logs):
            category = 'mindfulness'

        # Get a random quote from the appropriate category
        quote = db.session.query(WellnessQuotes)\
            .filter(WellnessQuotes.category == category)\
            .order_by(db.func.random())\
            .first()

        if quote:
            return {
                'text': quote.quote_text,
                'author': quote.author,
                'category': quote.category
            }
        # Fallback quote if none found
        return {
            'text': "Every step towards healthy eating is a step towards your goals.",
            'author': "Wellness Team",
            'category': "motivation"
        }
    except Exception as e:
        logger.error(f"Error getting wellness quote: {str(e)}")
        return None


@food_tracker_bp.route('/api/log-water', methods=['POST'])
@login_required
def log_water():
    try:
        data = request.get_json()
        logger.info(f"Received water logging request with data: {data}")

        # Input validation
        if 'amount' not in data:
            logger.error("Water amount missing in request")
            return jsonify({'error': 'Water amount is required'}), 400

        try:
            amount = float(data['amount'])
            if amount <= 0:
                logger.error(f"Invalid water amount: {amount}")
                return jsonify({'error': 'Water amount must be greater than 0'}), 400
        except ValueError:
            logger.error(f"Invalid water amount format: {data['amount']}")
            return jsonify({'error': 'Invalid water amount format'}), 400

        # Create new water log with explicit transaction
        session = db.session
        try:
            # Get current tracking period bounds for total calculation
            start_datetime, end_datetime = get_tracking_date_bounds()

            # Create and add new water log
            water_log = WaterLog(
                user_id=current_user.id,
                amount=amount,
                timestamp=get_cst_datetime()
            )
            session.add(water_log)
            session.commit()

            # Calculate total after successful commit
            total_water = session.query(db.func.sum(WaterLog.amount)).filter(
                WaterLog.user_id == current_user.id,
                WaterLog.timestamp >= start_datetime,
                WaterLog.timestamp < end_datetime
            ).scalar() or 0.0

            logger.info(f"Water logged successfully: {amount} oz for user {current_user.id}, new total: {total_water}")

            return jsonify({
                'status': 'success',
                'message': 'Water logged successfully',
                'amount': amount,
                'totalWater': float(total_water)
            })

        except Exception as e:
            logger.error(f"Database error in log_water: {e}")
            session.rollback()
            raise

    except Exception as e:
        logger.error(f"Error logging water: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': 'Error logging water. Please try again.',
            'details': str(e)
        }), 500

@food_tracker_bp.route('/api/log-food', methods=['POST'])
@login_required
def log_food():
    try:
        data = request.get_json()
        food_log = FoodLog(
            user_id=current_user.id,
            food_name=data['foodName'],
            serving_size=float(data['servingSize']),
            serving_unit=data['unit'],
            meal_type=data['mealType'],
            location=data.get('location', ''),
            mindful_eating_rating=int(data.get('mindfulRating', 3)),
            hunger_before=int(data.get('hungerBefore', 5)),
            fullness_after=int(data.get('fullnessAfter', 5)),
            emotional_state=data.get('emotionalState', ''),
            satisfaction_level=int(data.get('satisfactionLevel', 3)),
            notes=data.get('notes', ''),
            calories=float(data.get('calories', 0)),
            protein=float(data.get('protein', 0)),
            carbs=float(data.get('carbs', 0)),
            fat=float(data.get('fat', 0)),
            timestamp=get_cst_datetime()
        )
        db.session.add(food_log)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error logging food: {e}")
        return jsonify({'error': str(e)}), 400

@food_tracker_bp.route('/api/update-water-settings', methods=['POST'])
@login_required
def update_water_settings():
    """Dedicated endpoint for updating water settings"""
    try:
        data = request.get_json()
        logger.info(f"Received water settings update request with data: {data}")

        session = db.session
        try:
            if 'weight' in data:
                # Handle weight update
                new_weight = float(data['weight'])
                if new_weight <= 0:
                    return jsonify({'error': 'Weight must be greater than 0'}), 400

                # Calculate water goal
                water_goal = round(new_weight * 0.67, 1)
                MIN_WATER_GOAL = 64.0
                final_goal = max(water_goal, MIN_WATER_GOAL)

                # Update user's weight and water goal
                current_user.weight_lbs = new_weight
                current_user.daily_water_goal = final_goal  # Set the new water goal
                session.add(current_user)

                # Create weight log entry
                weight_log = WeightLog(
                    user_id=current_user.id,
                    weight=new_weight,
                    timestamp=get_cst_datetime()
                )
                session.add(weight_log)

            elif 'waterGoal' in data:
                # Handle direct water goal update
                new_goal = float(data['waterGoal'])
                if new_goal < 0:
                    return jsonify({'error': 'Water goal cannot be negative'}), 400

                current_user.daily_water_goal = new_goal
                session.add(current_user)

            session.commit()
            session.refresh(current_user)

            # Calculate calorie goal using consistent multiplier
            calorie_goal = round(current_user.weight_lbs * 7.56) if current_user.weight_lbs else 2000

            return jsonify({
                'status': 'success',
                'weight': float(current_user.weight_lbs) if current_user.weight_lbs else None,
                'waterGoal': float(current_user.daily_water_goal),
                'calorieGoal': calorie_goal
            })

        except Exception as e:
            logger.error(f"Database update failed: {e}", exc_info=True)
            session.rollback()
            raise

    except Exception as e:
        logger.error(f"Error updating water settings: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 400

@food_tracker_bp.route('/api/update-water-goal', methods=['POST'])
@login_required
def update_water_goal():
    try:
        data = request.get_json()
        logger.info(f"Received water goal update request with data: {data}")

        # Begin transaction with explicit session management
        session = db.session
        session.begin()

        try:
            if 'weight' in data:
                new_weight = float(data['weight'])
                logger.info(f"Current weight before update: {current_user.weight_lbs}")
                logger.info(f"Attempting to update weight to: {new_weight}")

                # Update user's weight directly in the database first
                session.execute(
                    text("UPDATE users SET weight_lbs = :weight WHERE id = :user_id"),
                    {'weight': new_weight, 'user_id': current_user.id}
                )
                session.flush()

                # Refresh user object to get updated weight
                session.refresh(current_user)
                logger.info(f"Weight after refresh: {current_user.weight_lbs}")

                # Calculate and update water goal
                new_goal = current_user.calculate_water_goal()
                logger.info(f"Calculated new water goal: {new_goal}")

                # Update water goal directly in database
                session.execute(
                    text("UPDATE users SET daily_water_goal = :goal WHERE id = :user_id"),
                    {'goal': new_goal, 'user_id': current_user.id}
                )
                session.flush()

                # Commit all changes
                session.commit()
                logger.info("Transaction committed successfully")

                # Refresh user object again to verify changes
                session.refresh(current_user)
                logger.info(f"Final values - Weight: {current_user.weight_lbs}, Goal: {current_user.daily_water_goal}")

            elif 'goal' in data:
                new_goal = float(data['goal'])
                logger.info(f"Directly updating water goal to: {new_goal}")
                current_user.daily_water_goal = new_goal
                session.commit()
                session.refresh(current_user)

            response_data = {
                'status': 'success',
                'goal': current_user.daily_water_goal,
                'weight': current_user.weight_lbs
            }
            logger.info(f"Sending response: {response_data}")
            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error in transaction, rolling back: {e}", exc_info=True)
            session.rollback()
            raise

    except Exception as e:
        logger.error(f"Error updating water goal: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 400

@food_tracker_bp.route('/api/daily-summary')
@login_required
def get_daily_summary():
    try:
        start_datetime, end_datetime = get_tracking_date_bounds()
        logger.info(f"[DAILY_SUMMARY] Fetching summary for user {current_user.id}")

        # Force refresh user data from database to ensure latest values
        db.session.refresh(current_user)

        logger.info(f"[DAILY_SUMMARY] Current weight: {current_user.weight_lbs}")
        logger.info(f"[DAILY_SUMMARY] Current water goal: {current_user.daily_water_goal}")

        # Get water logs for current period
        water_logs = WaterLog.query.filter(
            WaterLog.user_id == current_user.id,
            WaterLog.timestamp >= start_datetime,
            WaterLog.timestamp < end_datetime
        ).all()

        total_water = sum(log.amount for log in water_logs)
        logger.info(f"[DAILY_SUMMARY] Total water intake: {total_water} oz")

        # Get food logs
        food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= start_datetime,
            FoodLog.timestamp < end_datetime
        ).order_by(FoodLog.timestamp.desc()).all()

        total_calories = sum(log.calories for log in food_logs if log.calories)

        # Calculate calorie goal using consistent multiplier
        calorie_goal = round(current_user.weight_lbs * 7.56) if current_user.weight_lbs else 2000

        # Get tracking date info
        current_date = get_current_tracking_date()
        tracking_start = start_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')
        tracking_end = end_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')

        logger.info(f"[DAILY_SUMMARY] Final water goal value: {current_user.daily_water_goal}")
        logger.info(f"[DAILY_SUMMARY] Final calorie goal value: {calorie_goal}")

        return jsonify({
            'status': 'success',
            'totalWater': total_water,
            'waterGoal': float(current_user.daily_water_goal),
            'totalCalories': total_calories,
            'calorieGoal': calorie_goal,
            'foodLogs': [format_food_log(log) for log in food_logs],
            'trackingDate': current_date.isoformat(),
            'dayStartsAt': '3:00 AM CST',
            'trackingPeriod': {
                'start': tracking_start,
                'end': tracking_end
            },
            'userWeight': float(current_user.weight_lbs) if current_user.weight_lbs else None
        })

    except Exception as e:
        logger.error(f"[DAILY_SUMMARY] Error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e), 'status': 'error'}), 400

@food_tracker_bp.route('/api/log-weight', methods=['POST'])
@login_required
def log_weight():
    try:
        data = request.get_json()
        logger.info(f"[WEIGHT_LOG] Received weight logging request: {data}")

        # Input validation
        if 'weight' not in data:
            logger.error("[WEIGHT_LOG] Weight value missing in request")
            return jsonify({'status': 'error', 'message': 'Weight is required'}), 400

        try:
            weight = float(data['weight'])
            if weight <= 0 or weight > 1000:  # Reasonable weight range check
                logger.error(f"[WEIGHT_LOG] Invalid weight value: {weight}")
                return jsonify({'status': 'error', 'message': 'Weight must be between 0 and 1000 lbs'}), 400
        except ValueError as e:
            logger.error(f"[WEIGHT_LOG] Invalid weight format: {data['weight']}")
            return jsonify({'status': 'error', 'message': 'Invalid weight format'}), 400

        # Begin transaction
        session = db.session
        try:
            # Create new weight log
            weight_log = WeightLog(
                user_id=current_user.id,
                weight=weight,
                notes=data.get('notes', ''),
                timestamp=get_cst_datetime()
            )
            logger.debug(f"[WEIGHT_LOG] Created weight log entry: {weight} lbs")

            # Update user's current weight 
            current_user.weight_lbs = weight
            logger.debug(f"[WEIGHT_LOG] Updating user weight to: {weight} lbs")

            # Add and commit changes
            session.add(weight_log)
            session.add(current_user)
            session.commit()
            logger.info(f"[WEIGHT_LOG] Weight logged successfully: {weight} lbs for user {current_user.id}")

            # Update water goal after successful weight log
            try:
                current_user.update_water_goal()
            except Exception as e:
                logger.warning(f"[WEIGHT_LOG] Non-critical error updating water goal: {e}")
                # Don't fail the weight logging if water goal update fails

            return jsonify({
                'status': 'success',
                'weight': weight,
                'timestamp': weight_log.timestamp.isoformat()
            })

        except Exception as e:
            session.rollback()
            logger.error(f"[WEIGHT_LOG] Database error while logging weight: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error', 
                'message': 'Failed to save weight entry. Please try again.',
                'error': str(e)
            }), 500

    except Exception as e:
        logger.error(f"[WEIGHT_LOG] Unexpected error: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred',
            'error': str(e)
        }), 500

@food_tracker_bp.route('/api/weight-history')
@login_required
def get_weight_history_api():
    """API endpoint for weight history data"""
    try:
        # Get all weight logs for the user, ordered by timestamp
        logger.info(f"Fetching weight history for user {current_user.id}")
        logs = WeightLog.query\
            .filter_by(user_id=current_user.id)\
            .order_by(WeightLog.timestamp.desc())\
            .all()

        logger.info(f"Found {len(logs)} weight logs")

        if not logs:
            logger.info("No weight history found")
            return jsonify({
                'status': 'success',
                'data': [],
                'chart_data': {
                    'labels': [],
                    'datasets': [{
                        'label': 'Weight History',
                        'data': [],
                        'fill': False,
                        'borderColor': 'rgb(75, 192, 192)',
                        'tension': 0.1
                    }]
                },
                'message': 'No weight history available'
            })

        weight_data = []
        chart_data = {
            'labels': [],
            'datasets': [{
                'label': 'Weight History',
                'data': [],
                'fill': False,
                'borderColor': 'rgb(75, 192, 192)',
                'tension': 0.1
            }]
        }

        # Convert timestamps to CST for consistency
        cst = ZoneInfo("America/Chicago")
        for log in logs:
            try:
                # Convert timestamp to CST
                cst_timestamp = log.timestamp.astimezone(cst)
                entry = {
                    'id': log.id,
                    'weight': float(log.weight),
                    'notes': log.notes,
                    'timestamp': cst_timestamp.isoformat()
                }
                weight_data.append(entry)

                # Add data for chart in reverse chronological order
                chart_data['labels'].insert(0, cst_timestamp.strftime('%Y-%m-%d %H:%M'))
                chart_data['datasets'][0]['data'].insert(0, float(log.weight))

            except Exception as e:
                logger.error(f"Error converting weight log {log.id}: {str(e)}")
                continue

        # Calculate progress metrics if there are at least 2 entries
        summary = None
        if len(weight_data) >= 2:
            initial_weight = float(logs[-1].weight)  # First recorded weight
            current_weight = float(logs[0].weight)   # Most recent weight
            total_change = current_weight - initial_weight

            milestone_message = None
            if abs(total_change) >= 5:
                direction = "lost" if total_change < 0 else "gained"
                milestone_message = f"🎉 You've {direction} {abs(total_change):.1f} lbs since starting!"

            summary = {
                'initial_weight': initial_weight,
                'current_weight': current_weight,
                'total_change': total_change,
                'milestone_message': milestone_message
            }

        logger.info("Successfully retrieved weight history")
        return jsonify({
            'status': 'success',
            'data': weight_data,
            'chart_data': chart_data,
            'summary': summary
        })

    except Exception as e:
        logger.error(f"Error getting weight history: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to retrieve weight history',
            'error': str(e)
        }), 500

@food_tracker_bp.route('/food-tracker')
@login_required
def index():
    try:
        logger.info(f"[INDEX] Loading food tracker for user {current_user.id}")

        # Force refresh user data from database to ensure latest values
        db.session.refresh(current_user)
        logger.info(f"[INDEX] Initial user weight: {current_user.weight_lbs}")

        # Get latest weight log for the user
        latest_weight_log = WeightLog.query\
            .filter_by(user_id=current_user.id)\
            .order_by(WeightLog.timestamp.desc())\
            .first()

        # Update user weight only if it's not already set
        if latest_weight_log and not current_user.weight_lbs:
            logger.info(f"[INDEX] Found latest weight log: {latest_weight_log.weight} lbs")
            logger.info(f"[INDEX] Setting initial weight to: {latest_weight_log.weight}")
            current_user.weight_lbs = latest_weight_log.weight
            current_user.daily_water_goal = round(latest_weight_log.weight * 0.67, 1)
            db.session.commit()
            db.session.refresh(current_user)

        logger.info(f"[INDEX] Current user weight after update: {current_user.weight_lbs}")

        # Get current tracking period
        start_datetime, end_datetime = get_tracking_date_bounds()
        logger.info(f"[INDEX] Getting data for period: {start_datetime} to {end_datetime}")

        # Default values for initial data
        initial_data = {
            'totalWater': 0.0,
            'waterGoal': 64.0,  # Minimum water goal
            'totalCalories': 0,
            'calorieGoal': 2000,  # Default calorie goal
            'userWeight': None,
            'foodLogs': [],
            'weightHistory': [],
            'quote': {
                'text': "Every step towards healthy eating is a step towards your goals.",
                'author': "Wellness Team",
                'category': "motivation"
            }
        }

        # Use current weight for calculations if available
        if current_user.weight_lbs:
            try:
                weight = float(current_user.weight_lbs)
                water_goal = max(round(weight * 0.67, 1), 64.0)  # Ensure minimum of 64 oz
                calorie_goal = round(weight * 7.56)

                initial_data.update({
                    'waterGoal': float(current_user.daily_water_goal or water_goal),
                    'calorieGoal': float(calorie_goal),
                    'userWeight': float(weight)
                })
            except (TypeError, ValueError) as e:
                logger.error(f"[INDEX] Error converting weight values: {e}")

        try:
            # Get water logs
            water_logs = WaterLog.query.filter(
                WaterLog.user_id == current_user.id,
                WaterLog.timestamp >= start_datetime,
                WaterLog.timestamp < end_datetime
            ).all()

            total_water = sum(float(log.amount) for log in water_logs if log.amount)
            initial_data['totalWater'] = float(total_water)
        except Exception as e:
            logger.error(f"[INDEX] Error calculating water total: {e}")

        try:
            # Get food logs
            food_logs = FoodLog.query.filter(
                FoodLog.user_id == current_user.id,
                FoodLog.timestamp >= start_datetime,
                FoodLog.timestamp < end_datetime
            ).order_by(FoodLog.timestamp.desc()).all()

            logger.info(f"[INDEX] Found {len(food_logs)} food logs for period")

            total_calories = sum(float(log.calories) for log in food_logs if log.calories)
            initial_data['totalCalories'] = float(total_calories)
            initial_data['foodLogs'] = [format_food_log(log) for log in food_logs]
        except Exception as e:
            logger.error(f"[INDEX] Error processing food logs: {e}")

        try:
            # Get weight history
            weight_logs = WeightLog.query.filter_by(user_id=current_user.id)\
                .order_by(WeightLog.timestamp.desc()).all()

            weight_history = []
            for log in weight_logs:
                try:
                    weight_history.append({
                        'id': log.id,
                        'weight': float(log.weight),
                        'timestamp': log.timestamp.astimezone(ZoneInfo("America/Chicago")).isoformat(),
                        'notes': log.notes or ''
                    })
                except Exception as e:
                    logger.error(f"[INDEX] Error formatting weight log {log.id}: {e}")

            initial_data['weightHistory'] = weight_history
        except Exception as e:
            logger.error(f"[INDEX] Error processing weight history: {e}")

        try:
            # Get wellness quote
            quote = get_random_quote()
            if quote:
                initial_data['quote'] = quote
        except Exception as e:
            logger.error(f"[INDEX] Error getting wellness quote: {e}")

        logger.info(f"[INDEX] Final data for rendering: {initial_data}")
        return render_template('food_tracker/index.html', initial_data=initial_data)

    except Exception as e:
        logger.error(f"[INDEX] Error loading food tracker: {e}", exc_info=True)
        # Provide default initial_data even in case of error
        error_initial_data = {
            'totalWater': 0.0,
            'waterGoal': 64.0,
            'totalCalories': 0,
            'calorieGoal': 2000,
            'userWeight': None,
            'foodLogs': [],
            'weightHistory': [],
            'quote': {
                'text': "Every step towards healthy eating is a step towards your goals.",
                'author': "Wellness Team",
                'category': "motivation"
            }
        }
        return render_template('food_tracker/index.html', initial_data=error_initial_data)

@food_tracker_bp.route('/api/get-wellness-quote')
@login_required
def get_wellness_quote():
    try:
        # Get current tracking period to determine context
        start_datetime, end_datetime = get_tracking_date_bounds()

        # Get user's food logs for the period to determine context
        food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= start_datetime,
            FoodLog.timestamp < end_datetime
        ).all()

        # Determine the most relevant category based on user's activity
        category = 'emotional_eating'  # default category that matches our database
        if not food_logs:
            category = 'motivation'
        elif any(log.emotional_state in ['stressed', 'anxious'] for log in food_logs):
            category = 'mindfulness'

        # Get a random quote from the appropriate category
        quote = db.session.query(WellnessQuotes)\
            .filter(WellnessQuotes.category == category)\
            .order_by(db.func.random())\
            .first()

        if quote:
            return jsonify({
                'status': 'success',
                'quote': quote.quote_text,
                'author': quote.author,
                'category': quote.category
            })

        # Fallback quote if none found
        return jsonify({
            'status':'success',
            'quote': "Every step towards healthy eating is a step towards your goals.",
            'author': "Wellness Team",
            'category': "motivation"
        })

    except Exception as e:
        logger.error(f"Error getting wellness quote: {str(e)}")
        return jsonify({'error': str(e)}), 4000

def format_food_log(log):
    """Helper function to format food log entries consistently"""
    # Convert timestamp to CST
    cst = ZoneInfo("America/Chicago")
    cst_timestamp = log.timestamp.astimezone(cst)

    return {
        'id': log.id,
        'foodName': log.food_name,
        'servingSize': float(log.serving_size) if log.serving_size else 0.0,
        'unit': log.serving_unit or 'serving',
        'mealType': log.meal_type or 'snack',
        'calories': float(log.calories) if log.calories else 0.0,
        'protein': float(log.protein) if log.protein else 0.0,
        'carbs': float(log.carbs) if log.carbs else 0.0,
        'fat': float(log.fat) if log.fat else 0.0,
        'timestamp': cst_timestamp.isoformat(),
        'emotionalState': log.emotional_state or '',
        'satisfactionLevel': int(log.satisfaction_level) if log.satisfaction_level else 3,
        'notes': log.notes or ''
    }

@food_tracker_bp.route('/api/food-history')
@login_required
def get_food_history():
    """API endpoint for food history data"""
    try:
        # Get current tracking period
        start_datetime, end_datetime = get_tracking_date_bounds()
        logger.info(f"[FOOD_HISTORY] Getting food history for period: {start_datetime} to {end_datetime}")

        # Get all food logs for the period
        food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= start_datetime,
            FoodLog.timestamp < end_datetime
        ).order_by(FoodLog.timestamp.desc()).all()

        logger.info(f"[FOOD_HISTORY] Found {len(food_logs)} food logs")

        if not food_logs:
            return jsonify({
                'status': 'success',
                'data': [],
                'message': 'No food history available for this period'
            })

        # Format food logs
        formatted_logs = []
        for log in food_logs:
            try:
                formatted_log = format_food_log(log)
                formatted_logs.append(formatted_log)
                logger.info(f"[FOOD_HISTORY] Formatted log: {formatted_log}")
            except Exception as e:
                logger.error(f"[FOOD_HISTORY] Error formatting log {log.id}: {str(e)}")
                continue

        logger.info(f"[FOOD_HISTORY] Formatted {len(formatted_logs)} logs")

        return jsonify({
            'status': 'success',
            'data': formatted_logs
        })

    except Exception as e:
        logger.error(f"[FOOD_HISTORY] Error getting food history: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to retrieve food history',
            'error': str(e)
        }), 500