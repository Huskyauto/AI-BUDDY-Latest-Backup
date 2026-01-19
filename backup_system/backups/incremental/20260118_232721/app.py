import os
import logging
import gzip
from io import BytesIO
from flask import Flask, render_template, session, jsonify, request, make_response, after_this_request
from markupsafe import Markup
import secrets
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base
from functools import wraps

from extensions import db, login_manager, migrate, mail
from flask_login import current_user
from models import ManualWellnessCheckIn

# Configure logging with more detailed format and DEBUG level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def verify_environment():
    """Verify all required environment variables are present"""
    required_vars = ['DATABASE_URL']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(f"[APP_INIT] {error_msg}")
        raise EnvironmentError(error_msg)

def create_app(test_config=None):
    """Application factory function with improved error handling and logging"""
    try:
        logger.info("[APP_INIT] Starting Flask application creation...")

        # Verify environment variables
        verify_environment()

        app = Flask(__name__, static_folder='static', template_folder='templates')

        # Add nl2br filter for templates
        @app.template_filter('nl2br')
        def nl2br_filter(text):
            if not text:
                return ""
            return Markup(text.replace('\n', '<br>'))

        logger.debug("[APP_INIT] Configuring application settings...")
        if test_config is None:
            app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
            app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                "pool_pre_ping": True,
                "pool_recycle": 300,
            }

            # Enhanced security configuration
            app.config['SESSION_COOKIE_SECURE'] = True
            app.config['SESSION_COOKIE_HTTPONLY'] = True
            app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 31  # 31 days
            app.config['SESSION_REFRESH_EACH_REQUEST'] = True
            app.config['REMEMBER_COOKIE_SECURE'] = True
            app.config['REMEMBER_COOKIE_HTTPONLY'] = True
        else:
            logger.debug("[APP_INIT] Using test configuration")
            app.config.update(test_config)

        # Initialize extensions with app
        logger.info("[APP_INIT] Initializing Flask extensions...")
        try:
            db.init_app(app)
            login_manager.init_app(app)
            login_manager.login_view = 'auth.login'
            login_manager.login_message = 'Please log in to access this page.'
            login_manager.session_protection = 'strong'
            login_manager.refresh_view = 'auth.login'
            login_manager.needs_refresh_message = 'Please reauthenticate to protect your session.'
            migrate.init_app(app, db)
            mail.init_app(app)
        except Exception as e:
            logger.error(f"[APP_INIT] Failed to initialize extensions: {str(e)}", exc_info=True)
            raise

        with app.app_context():
            try:
                # Test database connection
                logger.info("[APP_INIT] Testing database connection...")
                db.session.execute(text('SELECT 1'))
                db.session.commit()
                logger.info("[APP_INIT] Database connection test successful")

                # Import models and create tables
                logger.debug("[APP_INIT] Importing models and creating tables...")
                import models  # noqa: F401
                db.create_all()
                logger.info("[APP_INIT] Database tables created/verified")

                # Import and register blueprints
                logger.info("[APP_INIT] Registering blueprints...")
                try:
                    from auth import auth_bp
                    from chat import chat_bp
                    from food_tracker import food_tracker_bp
                    from dashboard import dashboard_bp
                    from ring_routes import ring_bp
                    from cbt import cbt_bp
                    from journal import journal_bp
                    from forum import forum
                    from location_wellness import location_wellness
                    from health_prediction import health_prediction_bp
                    from wellness_toolbox import wellness_toolbox_bp
                    from challenge_routes import challenges_bp
                    from stress_monitoring import stress_bp
                    from fasting import fasting_bp
                    from admin_dashboard import admin_dashboard
                    from admin_reports import admin_reports
                    from self_care import self_care_bp
                except ImportError as e:
                    logger.error(f"[APP_INIT] Failed to import blueprints: {str(e)}", exc_info=True)
                    raise

                blueprints = [
                    (auth_bp, "Authentication"),
                    (chat_bp, "Chat"),
                    (food_tracker_bp, "Food Tracker"),
                    (dashboard_bp, "Dashboard"),
                    (ring_bp, "Ring Integration"),
                    (cbt_bp, "CBT"),
                    (journal_bp, "Journal"),
                    (forum, "Forum"),
                    (location_wellness, "Location Wellness", "/location-wellness"),
                    (health_prediction_bp, "Health Prediction"),
                    (wellness_toolbox_bp, "Wellness Toolbox"),
                    (challenges_bp, "Meditation Challenges"),
                    (stress_bp, "Stress Monitoring"),
                    (fasting_bp, "Fasting Programs"),
                    (self_care_bp, "Self-Care Recommendations"),
                    (admin_dashboard, "Admin Dashboard", "/admin"),
                    (admin_reports, "Admin Reports", "/admin/reports")
                ]

                for blueprint_info in blueprints:
                    blueprint = blueprint_info[0]
                    name = blueprint_info[1]
                    url_prefix = blueprint_info[2] if len(blueprint_info) > 2 else None

                    try:
                        if url_prefix:
                            app.register_blueprint(blueprint, url_prefix=url_prefix)
                        else:
                            app.register_blueprint(blueprint)
                        logger.info(f"[APP_INIT] Registered {name} blueprint successfully")
                    except Exception as e:
                        logger.error(f"[APP_INIT] Failed to register {name} blueprint: {str(e)}", exc_info=True)
                        raise

                @app.route('/')
                def index():
                    return render_template('index.html')
                
                # CSRF token retrieval endpoint for PWA
                @app.route('/get-csrf-token', methods=['GET'])
                def get_csrf_token():
                    if not session.get('csrf_token'):
                        session['csrf_token'] = secrets.token_hex(16)
                    return jsonify({'csrf_token': session['csrf_token']})
                
                # PWA version info endpoint for cache invalidation
                @app.route('/pwa-version', methods=['GET'])
                def pwa_version():
                    """Return the current PWA version for cache invalidation"""
                    import time
                    return jsonify({
                        'version': '1.0.1',
                        'build_id': '20250524115800',
                        'timestamp': int(time.time()),
                        'updated': True
                    })

                # Mobile-friendly wellness check-in API endpoint (checks authentication first)
                @app.route('/api/mobile-wellness-checkin', methods=['POST'])
                def mobile_wellness_checkin():
                    """Mobile-compatible wellness check-in endpoint"""
                    from datetime import datetime
                    from models import ManualWellnessCheckIn
                    from extensions import db
                    from flask_login import current_user
                    
                    try:
                        if not request.is_json:
                            return jsonify({'status': 'error', 'message': 'JSON required'}), 400
                        
                        data = request.json
                        
                        # Check if user is authenticated, otherwise default to main user for mobile compatibility
                        if current_user.is_authenticated:
                            user_id = current_user.id
                        else:
                            user_id = 1  # Default to main user (huskyauto@gmail.com)
                        
                        # Create wellness check-in with EXACT same field names as web version
                        from datetime import datetime, timezone
                        import logging
                        
                        # Log the incoming data for debugging
                        logging.info(f"Mobile check-in data received: {data}")
                        
                        # ALWAYS use current UTC time - ignore any timestamp from mobile app
                        current_time = datetime.now(timezone.utc)
                        logging.info(f"Using current time: {current_time}")
                        
                        checkin = ManualWellnessCheckIn(
                            user_id=user_id,
                            energy_level=int(data.get('energy_level', 5)) if data.get('energy_level') else None,
                            physical_comfort=int(data.get('physical_comfort', 5)) if data.get('physical_comfort') else None,
                            sleep_quality=int(data.get('sleep_quality', 5)) if data.get('sleep_quality') else None,
                            breathing_quality=int(data.get('breathing_quality', 5)) if data.get('breathing_quality') else None,
                            physical_tension=int(data.get('physical_tension', 5)) if data.get('physical_tension') else None,
                            stress_level=int(data.get('stress_level', 5)) if data.get('stress_level') else None,
                            mood=data.get('mood', 'neutral'),  # String value like web version
                            focus_level=int(data.get('focus_level', 5)) if data.get('focus_level') else None,
                            exercise_minutes=int(data.get('exercise_minutes')) if data.get('exercise_minutes') else None,
                            water_glasses=int(data.get('water_glasses')) if data.get('water_glasses') else None,
                            weather_condition=data.get('weather_condition', ''),
                            location_type=data.get('location_type', ''),
                            notes=data.get('notes', ''),
                            recorded_at=current_time,  # Force current time
                            created_at=current_time    # Force current time
                        )
                        
                        db.session.add(checkin)
                        db.session.commit()
                        
                        return jsonify({
                            'status': 'success',
                            'message': 'Wellness check-in saved successfully'
                        })
                        
                    except Exception as e:
                        db.session.rollback()
                        return jsonify({
                            'status': 'error',
                            'message': f'Error saving check-in: {str(e)}'
                        }), 500



                # Configure session
                @app.before_request
                def before_request():
                    session.permanent = True

                # Gzip compression for responses
                @app.after_request
                def compress_response(response):
                    # Skip if already compressed or small response
                    if (response.status_code < 200 or 
                        response.status_code >= 300 or 
                        response.direct_passthrough or
                        'gzip' not in request.headers.get('Accept-Encoding', '').lower() or
                        'Content-Encoding' in response.headers or
                        len(response.get_data()) < 500):
                        return response
                    
                    # Only compress text-based content
                    content_type = response.content_type or ''
                    compressible_types = ['text/', 'application/json', 'application/javascript', 'application/xml']
                    if not any(ct in content_type for ct in compressible_types):
                        return response
                    
                    # Compress the response
                    gzip_buffer = BytesIO()
                    with gzip.GzipFile(mode='wb', fileobj=gzip_buffer, compresslevel=6) as f:
                        f.write(response.get_data())
                    
                    response.set_data(gzip_buffer.getvalue())
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Length'] = len(response.get_data())
                    response.headers['Vary'] = 'Accept-Encoding'
                    return response

                # Aggressive caching for static files only
                @app.after_request
                def add_cache_headers(response):
                    if request.path.startswith('/static/'):
                        # Cache static assets for 1 year (immutable with versioning)
                        if any(ext in request.path for ext in ['.css', '.js', '.png', '.jpg', '.svg', '.woff2', '.ico']):
                            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
                        # Cache manifest for 1 day
                        elif 'manifest.json' in request.path:
                            response.headers['Cache-Control'] = 'public, max-age=86400'
                    # Dynamic pages with user content must never be publicly cached
                    elif 'text/html' in (response.content_type or ''):
                        response.headers['Cache-Control'] = 'private, no-store, must-revalidate'
                    return response

                # Add error handlers
                @app.errorhandler(404)
                def not_found_error(error):
                    return render_template('404.html'), 404

                @app.errorhandler(500)
                def internal_error(error):
                    db.session.rollback()
                    return render_template('500.html'), 500

                logger.info("[APP_INIT] Flask application created and configured successfully")
                
                # Test the API logging functionality directly
                try:
                    from ai_client import log_api_call
                    logger.info("[APP_INIT] Testing API logging functionality...")
                    log_api_call(
                        api_name="Test API", 
                        endpoint="test/endpoint", 
                        response_time=0.1,
                        success=True,
                        status_code=200
                    )
                    logger.info("[APP_INIT] API logging test complete")
                except Exception as e:
                    logger.error(f"[APP_INIT] Error testing API logging: {str(e)}", exc_info=True)
                
                return app

            except SQLAlchemyError as e:
                logger.error(f"[APP_INIT] Database error during application initialization: {str(e)}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"[APP_INIT] Error during application initialization: {str(e)}", exc_info=True)
                raise

    except Exception as e:
        logger.error(f"[APP_INIT] Fatal error during application creation: {str(e)}", exc_info=True)
        raise

# Create the application instance
app = create_app()

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    try:
        from models import User
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"[AUTH] Error loading user {user_id}: {str(e)}", exc_info=True)
        return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)