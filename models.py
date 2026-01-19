from datetime import datetime, timezone
from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from sqlalchemy import text, func, Index, desc
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Track creation/modification timestamps
class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def update_timestamp(self):
        self.updated_at = datetime.utcnow()

def get_local_time(tz_name=None):
    """
    Get current time in the specified timezone or UTC if not specified.
    The frontend will handle displaying this in the user's local timezone.
    
    Args:
        tz_name (str, optional): Timezone name. If None, uses UTC.
        
    Returns:
        datetime: Current time in the specified timezone
    """
    if tz_name:
        try:
            local_tz = ZoneInfo(tz_name)
            return datetime.now(local_tz)
        except Exception as e:
            print(f"Error with timezone {tz_name}: {e}")
    
    # Default to UTC
    return datetime.now(timezone.utc)

def format_timestamp(timestamp, tz_name=None):
    """
    Format timestamp to the specified timezone or leave in UTC if not specified.
    The frontend will handle displaying this in the user's local timezone.
    
    Args:
        timestamp (datetime): The timestamp to format
        tz_name (str, optional): Timezone name. If None, uses UTC.
        
    Returns:
        datetime: The timestamp converted to the specified timezone
    """
    if timestamp is None:
        return None
        
    # Ensure timestamp has timezone info (add UTC if missing)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
        
    # Convert to specified timezone if provided
    if tz_name:
        try:
            local_tz = ZoneInfo(tz_name)
            return timestamp.astimezone(local_tz)
        except Exception as e:
            print(f"Error with timezone {tz_name}: {e}")
            
    # Return in UTC by default
    return timestamp

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256))
    is_ring_data_authorized = db.Column(db.Boolean, default=False)
    weight_lbs = db.Column(db.Float, nullable=True)
    daily_water_goal = db.Column(db.Float, default=64.0)
    created_at = db.Column(db.DateTime, default=get_local_time)
    last_login = db.Column(db.DateTime, default=get_local_time)

    # Add meditation stats tracking
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_meditation_date = db.Column(db.Date)
    total_meditation_minutes = db.Column(db.Integer, default=0)
    total_sessions = db.Column(db.Integer, default=0)

    # Define relationships
    meditation_sessions = db.relationship('MeditationSession', backref='user', lazy=True)
    forum_posts = db.relationship('ForumPost', backref='author', lazy=True)
    forum_replies = db.relationship('ForumReply', backref='author', lazy=True)
    weight_logs = db.relationship('WeightLog', backref='user', lazy=True)
    biomarker_insights = db.relationship('BiomarkerInsight', backref='user', lazy=True)
    stress_levels = db.relationship('StressLevel', backref='user', lazy=True)
    achievements = db.relationship('MeditationAchievement', backref='user', lazy=True)
    fasting_sessions = db.relationship('FastingSession', backref='user', lazy=True)

    __table_args__ = (
        Index('ix_users_email_lower', func.lower(email), unique=True),
    )

    def set_password(self, password):
        """Set password with enhanced error handling"""
        try:
            if not password or len(password) < 6:
                logger.error("[AUTH] Password validation failed: Password too short or empty")
                raise ValueError("Password must be at least 6 characters long")
            self.password_hash = generate_password_hash(password)
            logger.info(f"[AUTH] Password successfully hashed for user {self.id}")
            return True
        except Exception as e:
            logger.error(f"[AUTH] Error setting password for user {self.id}: {str(e)}")
            raise

    def check_password(self, password):
        """Verify password with case sensitivity"""
        try:
            return check_password_hash(self.password_hash, password) if self.password_hash else False
        except Exception as e:
            logger.error(f"[AUTH] Error verifying password: {e}")
            return False

    def can_view_ring_data(self):
        """Check if user is authorized to view ring data"""
        try:
            # Explicit check for the authorized email
            AUTHORIZED_EMAIL = 'huskyauto@gmail.com'
            return (
                self.is_ring_data_authorized and 
                self.email and 
                self.email.lower() == AUTHORIZED_EMAIL.lower()
            )
        except Exception as e:
            logger.error(f"[ACCESS_CONTROL] Error checking ring data access: {e}")
            return False

    def get_ring_access_message(self):
        """Get message about ring data access status"""
        try:
            if not self.email:
                return "Ring data access requires a valid email address."
            elif self.email.lower() == 'huskyauto@gmail.com'.lower():
                if self.is_ring_data_authorized:
                    return "You have full access to smart ring data."
                else:
                    return "Your account is pending ring data authorization."
            else:
                return "Ring data access is restricted to authorized users only."
        except Exception as e:
            logger.error(f"[ACCESS_CONTROL] Error getting ring access message: {e}")
            return "Unable to determine ring data access status."
            
    def has_biometric_access(self):
        """
        Check if user has access to biometric data from smart rings or watches.
        This method is used to determine which features to show/hide in the UI.
        """
        try:
            return self.can_view_ring_data()
        except Exception as e:
            logger.error(f"[ACCESS_CONTROL] Error checking biometric access: {e}")
            return False
            
    def is_biometric_user(self):
        """Convenience method alias for has_biometric_access for template readability"""
        return self.has_biometric_access()

    @property
    def meditation_stats(self):
        """Get user's meditation statistics"""
        try:
            # Get recent sessions with stress reduction
            recent_sessions = MeditationSession.query\
                .filter_by(user_id=self.id, status='completed')\
                .filter(MeditationSession.stress_reduction.isnot(None))\
                .order_by(desc(MeditationSession.start_time))\
                .limit(30)\
                .all()

            avg_stress_reduction = None
            if recent_sessions:
                reductions = [s.stress_reduction for s in recent_sessions if s.stress_reduction is not None]
                if reductions:
                    avg_stress_reduction = sum(reductions) / len(reductions)

            return {
                'current_streak': self.current_streak,
                'longest_streak': self.longest_streak,
                'total_sessions': self.total_sessions,
                'total_minutes': self.total_meditation_minutes,
                'average_stress_reduction': avg_stress_reduction
            }
        except Exception as e:
            logger.error(f"Error getting meditation stats: {e}", exc_info=True)
            return None

    def update_meditation_streak(self):
        """Update meditation streak based on latest session"""
        try:
            latest_session = MeditationSession.query\
                .filter_by(user_id=self.id, status='completed')\
                .order_by(MeditationSession.end_time.desc())\
                .first()

            if not latest_session:
                return

            today = datetime.now(ZoneInfo("America/Chicago")).date()
            if self.last_meditation_date:
                days_diff = (today - self.last_meditation_date).days
                if days_diff <= 1:  # Maintain/increment streak
                    self.current_streak += 1
                else:  # Break streak
                    self.current_streak = 1
            else:  # First session
                self.current_streak = 1

            # Update longest streak
            if self.current_streak > self.longest_streak:
                self.longest_streak = self.current_streak

            self.last_meditation_date = today
            db.session.commit()

        except Exception as e:
            logger.error(f"Error updating meditation streak: {e}", exc_info=True)
            db.session.rollback()

class ChatHistory(db.Model):
    __tablename__ = 'chat_history'
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=get_local_time)
    emotion = db.Column(db.String(50))

    def __init__(self, **kwargs):
        super(ChatHistory, self).__init__(**kwargs)
        if not self.timestamp:
            self.timestamp = get_local_time()

class FoodLog(db.Model):
    __tablename__ = 'food_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    food_name = db.Column(db.String(200), nullable=False)
    serving_size = db.Column(db.Float, nullable=False)
    serving_unit = db.Column(db.String(50), nullable=False)
    meal_type = db.Column(db.String(50))
    location = db.Column(db.String(100))
    mindful_eating_rating = db.Column(db.Integer)
    hunger_before = db.Column(db.Integer)
    fullness_after = db.Column(db.Integer)
    emotional_state = db.Column(db.String(50))
    satisfaction_level = db.Column(db.Integer)  # Added field
    calories = db.Column(db.Float)  # Added nutritional information
    protein = db.Column(db.Float)
    carbs = db.Column(db.Float)
    fat = db.Column(db.Float)
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=get_local_time)

class WaterLog(db.Model):
    __tablename__ = 'water_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=get_local_time)

class Mood(db.Model):
    __tablename__ = 'mood'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mood = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=get_local_time)

class JournalEntry(db.Model):
    __tablename__ = 'journal_entry'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=get_local_time, nullable=False)
    
    @property
    def timestamp_with_timezone(self):
        """Return timestamp with timezone info for proper client-side conversion"""
        if self.timestamp:
            # Convert to UTC and add timezone info
            timestamp_utc = self.timestamp.replace(tzinfo=timezone.utc)
            return timestamp_utc
        return None

class WeightLog(db.Model):
    __tablename__ = 'weight_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    weight = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=get_local_time)

    def to_dict(self):
        """Convert weight log entry to dictionary format with validation"""
        try:
            # Validate weight range
            weight_value = float(self.weight)
            if weight_value <= 0 or weight_value > 1000:
                logger.error(f"[WEIGHT_LOG] Invalid weight value: {weight_value}")
                return None

            return {
                'id': self.id,
                'weight': weight_value,
                'notes': self.notes,
                'timestamp': self.timestamp.isoformat() if self.timestamp else None
            }
        except Exception as e:
            logger.error(f"[WEIGHT_LOG] Error converting weight log to dict: {e}", exc_info=True)
            return None

class WellnessQuotes(db.Model):
    __tablename__ = 'wellness_quotes'
    id = db.Column(db.Integer, primary_key=True)
    quote_text = db.Column(db.Text, nullable=False)  # Changed from quote to quote_text to match database
    author = db.Column(db.String(100))
    category = db.Column(db.String(50), nullable=False)
    context_tags = db.Column(db.String(200))  # Store as comma-separated string
    created_at = db.Column(db.DateTime, default=get_local_time)

class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='General Discussion')
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    likes = db.Column(db.Integer, default=0)

    # Define replies relationship
    replies = db.relationship('ForumReply', backref='post', lazy=True)

    def to_dict(self):
        try:
            return {
                'id': self.id,
                'title': self.title,
                'content': self.content,
                'category': self.category,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                'author': self.author.username if self.author else 'Unknown',
                'likes': self.likes or 0
            }
        except Exception as e:
            logger.error(f"Error converting forum post to dict: {e}", exc_info=True)
            return None

class BiomarkerInsight(db.Model):
    __tablename__ = 'biomarker_insights'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    source = db.Column(db.String(50), nullable=False)  # 'Oura Ring' or 'Ultrahuman Ring'
    metric_type = db.Column(db.String(50), nullable=False)  # 'stress', 'hrv', 'recovery'
    value = db.Column(db.Float, nullable=False)
    threshold = db.Column(db.Float, nullable=False)
    trigger_description = db.Column(db.Text)
    impact_description = db.Column(db.Text)
    recommendations = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=get_local_time)

class ForumReply(db.Model):
    __tablename__ = 'forum_replies'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id'), nullable=False)
    likes = db.Column(db.Integer, default=0)

    def to_dict(self):
        try:
            return {
                'id': self.id,
                'content': self.content,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                'author': self.author.username if self.author else 'Unknown',
                'post_id': self.post_id,
                'likes': self.likes or 0
            }
        except Exception as e:
            logger.error(f"Error converting forum reply to dict: {e}", exc_info=True)
            return None

class MeditationSession(db.Model):
    __tablename__ = 'meditation_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey('meditation_challenges.id'), nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer, nullable=False)  # in minutes
    meditation_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='in_progress')
    notes = db.Column(db.Text)

    # Rename stress tracking fields for clarity
    stress_level_start = db.Column(db.Float)
    stress_level_end = db.Column(db.Float)   
    stress_reduction = db.Column(db.Float)    # Calculated field

    def __init__(self, **kwargs):
        super(MeditationSession, self).__init__(**kwargs)
        if not self.start_time:
            self.start_time = get_local_time()

    def complete(self, actual_duration, final_stress=None):
        """Complete a meditation session with final measurements"""
        try:
            self.end_time = get_local_time()
            self.duration = actual_duration
            self.status = 'completed'

            # Only update final stress if provided and valid
            if final_stress is not None and isinstance(final_stress, (int, float)):
                self.stress_level_end = float(final_stress)
                # Calculate stress reduction if both start and end levels are available
                if self.stress_level_start is not None:
                    self.stress_reduction = self.stress_level_start - self.stress_level_end

            # Update user stats
            if self.user:
                self.user.total_sessions = (self.user.total_sessions or 0) + 1
                self.user.total_meditation_minutes += actual_duration

                # Update streak
                today = self.end_time.date()
                if self.user.last_meditation_date:
                    days_diff = (today - self.user.last_meditation_date).days
                    if days_diff <= 1:  # Maintain/increment streak
                        self.user.current_streak += 1
                    else:  # Break streak
                        self.user.current_streak = 1
                else:  # First session
                    self.user.current_streak = 1

                # Update longest streak
                if self.user.current_streak > (self.user.longest_streak or 0):
                    self.user.longest_streak = self.user.current_streak

                self.user.last_meditation_date = today

            logger.info(f"[MEDITATION] Session {self.id} completed successfully")
            return True

        except Exception as e:
            logger.error(f"[MEDITATION] Error completing session: {str(e)}", exc_info=True)
            return False


class MeditationChallenge(db.Model):
    __tablename__ = 'meditation_challenges'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    duration_requirement = db.Column(db.Integer)  # Minutes per session
    frequency_requirement = db.Column(db.Integer)  # Sessions per week
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_public = db.Column(db.Boolean, default=True)
    max_participants = db.Column(db.Integer)
    current_participants = db.Column(db.Integer, default=0)
    challenge_type = db.Column(db.String(50), default='solo')  # 'solo', 'group', 'community'
    status = db.Column(db.String(20), default='upcoming')  # 'upcoming', 'active', 'completed'
    achievement_badge = db.Column(db.String(100))  # Path to badge image
    leaderboard_enabled = db.Column(db.Boolean, default=True)
    chat_enabled = db.Column(db.Boolean, default=True)
    schedule = db.Column(db.JSON)  # Store recurring session schedule
    tags = db.Column(db.JSON)  # Store challenge categories/tags

    # Relationships
    sessions = db.relationship('MeditationSession', backref='challenge', lazy=True)
    participants = db.relationship('User', 
                               secondary='challenge_participants',
                               backref=db.backref('challenges', lazy='dynamic'))
    creator = db.relationship('User', backref='created_challenges', foreign_keys=[created_by])

    def to_dict(self):
        """Convert challenge to dictionary format"""
        try:
            return {
                'id': self.id,
                'name': self.name,
                'description': self.description,
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'end_date': self.end_date.isoformat() if self.end_date else None,
                'duration_requirement': self.duration_requirement,
                'frequency_requirement': self.frequency_requirement,
                'is_public': self.is_public,
                'max_participants': self.max_participants,
                'current_participants': self.current_participants,
                'challenge_type': self.challenge_type,
                'status': self.status,
                'creator': self.creator.username if self.creator else None,
                'leaderboard_enabled': self.leaderboard_enabled,
                'chat_enabled': self.chat_enabled,
                'schedule': self.schedule,
                'tags': self.tags
            }
        except Exception as e:
            logger.error(f"Error converting challenge to dict: {e}")
            return None

    @property
    def status(self):
        """Dynamically calculate challenge status based on dates"""
        today = datetime.now(ZoneInfo('UTC')).date()

        if self.end_date.date() < today:
            return 'completed'
        elif self.start_date.date() <= today <= self.end_date.date():
            return 'active'
        else:
            return 'upcoming'

    def get_registration_status(self, user):
        """Get the registration status for a specific user"""
        try:
            if user in self.participants:
                return 'registered'
            if not self.can_join(user):
                return 'closed'
            return 'open'
        except Exception as e:
            logger.error(f"Error getting registration status: {e}")
            return 'error'

    def can_join(self, user):
        """Check if user can join the challenge"""
        try:
            if not self.is_public and self.created_by != user.id:
                return False
            if self.max_participants and self.current_participants >= self.max_participants:
                return False
            if self.status not in ['upcoming', 'active']:  # Allow joining active challenges too
                return False
            if user in self.participants:
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking challenge join eligibility: {e}")
            return False

# Association table for challenge participants
challenge_participants = db.Table('challenge_participants',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('challenge_id', db.Integer, db.ForeignKey('meditation_challenges.id'), primary_key=True),
    db.Column('join_date', db.DateTime, default=get_local_time),
    db.Column('completed_sessions', db.Integer, default=0),
    db.Column('total_minutes', db.Integer, default=0)
)

class MeditationAchievement(db.Model):
    __tablename__ = 'meditation_achievements'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    achievement_type = db.Column(db.String(50), nullable=False)
    earned_date = db.Column(db.DateTime, default=get_local_time)
    description = db.Column(db.Text)
    milestone_value = db.Column(db.Integer)  # e.g., 7 for 7-day streak
    icon = db.Column(db.String(100))  # Path to achievement icon

class StressLevel(db.Model):
    __tablename__ = 'stress_levels'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    level = db.Column(db.Integer, nullable=False)  # 1-10 scale
    symptoms = db.Column(db.JSON)  # Store symptoms as JSON array
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), default=get_local_time)

    def to_dict(self):
        """Convert stress level to dictionary with proper timezone handling"""
        return {
            'id': self.id,
            'level': self.level,
            'symptoms': self.symptoms,
            'notes': self.notes,
            'timestamp': format_timestamp(self.timestamp).isoformat() if self.timestamp else None
        }

class ApiUsage(db.Model):
    """Track API usage statistics for admin dashboard"""
    __tablename__ = 'api_usage_stats'
    id = db.Column(db.Integer, primary_key=True)
    api_name = db.Column(db.String(50), nullable=False)
    endpoint = db.Column(db.String(100), nullable=False)
    response_time = db.Column(db.Float, nullable=False)  # in seconds
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=get_local_time)
    status_code = db.Column(db.Integer, nullable=True)
    
    def to_dict(self):
        """Convert API usage to dictionary"""
        return {
            'id': self.id,
            'api_name': self.api_name,
            'endpoint': self.endpoint,
            'response_time': self.response_time,
            'user_id': self.user_id,
            'timestamp': format_timestamp(self.timestamp).isoformat() if self.timestamp else None,
            'status_code': self.status_code
        }

class ChallengeMessage(db.Model):
    """Model for challenge group chat messages"""
    __tablename__ = 'challenge_messages'
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('meditation_challenges.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=get_local_time)

    # Relationships
    challenge = db.relationship('MeditationChallenge', backref='messages')
    user = db.relationship('User', backref='challenge_messages')

    def to_dict(self):
        """Convert message to dictionary format"""
        try:
            return {
                'id': self.id,
                'challenge_id': self.challenge_id,
                'user': self.user.username,
                'message': self.message,
                'timestamp': self.timestamp.isoformat()
            }
        except Exception as e:
            logger.error(f"Error converting challenge message to dict: {e}")
            return None

class FastingProgram(db.Model):
    """Model for different types of fasting programs"""
    __tablename__ = 'fasting_programs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    duration_days = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    benefits = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    daily_guidance = db.Column(db.JSON)  # Day-by-day guidance stored as JSON
    type = db.Column(db.String(20), default='extended')  # 'intermittent' or 'extended'
    contraindications = db.Column(db.Text)  # Medical warnings
    created_at = db.Column(db.DateTime, default=get_local_time)

    # Single relationship definition
    sessions = db.relationship('FastingSession', back_populates='program', lazy=True)

    def to_dict(self):
        """Convert program to dictionary format"""
        try:
            return {
                'id': self.id,
                'name': self.name,
                'duration_days': self.duration_days,
                'description': self.description,
                'benefits': self.benefits,
                'instructions': self.instructions,
                'daily_guidance': self.daily_guidance,
                'type': self.type,
                'contraindications': self.contraindications
            }
        except Exception as e:
            logger.error(f"[FASTING] Error converting program to dict: {e}")
            return None

class FastingSession(db.Model):
    """Model for tracking individual fasting attempts"""
    __tablename__ = 'fasting_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('fasting_programs.id'), nullable=False)
    start_date = db.Column(db.DateTime(timezone=True), nullable=False, default=get_local_time)
    end_date = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(20), default='active')  # active, completed, abandoned
    notes = db.Column(db.Text)

    # Relationships
    check_ins = db.relationship('FastingCheckIn', backref='session', lazy=True)
    program = db.relationship('FastingProgram', back_populates='sessions', lazy=True)

    def get_current_day(self):
        """Calculate current day of fast with improved timezone handling"""
        try:
            if not self.program or not self.start_date:
                logger.error(f"[FASTING] Session {self.id} missing required data: program={bool(self.program)}, start_date={bool(self.start_date)}")
                return 1

            # For completed sessions, return the final day
            if self.status == 'completed':
                return self.program.duration_days

            # Calculate days elapsed since start with proper timezone handling
            current_time = get_local_time()
            start_time = self.start_date
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)

            days_elapsed = (current_time - start_time).days

            # Ensure we return at least day 1, and don't exceed program duration
            current_day = max(1, min(days_elapsed + 1, self.program.duration_days))

            logger.info(f"[FASTING] Session {self.id} current day calculation: days_elapsed={days_elapsed}, current_day={current_day}")
            return current_day

        except Exception as e:
            logger.error(f"[FASTING] Error calculating current day: {e}", exc_info=True)
            return 1

    def to_dict(self):
        """Convert session to dictionary format"""
        try:
            current_day = self.get_current_day()
            total_days = self.program.duration_days if self.program else None

            return {
                'id': self.id,
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'end_date': self.end_date.isoformat() if self.end_date else None,
                'status': self.status,
                'notes': self.notes,
                'program': self.program.name if self.program else None,
                'current_day': current_day,
                'total_days': total_days,
                'display_day': f"Day {current_day} of {total_days}" if total_days else "Not started"
            }
        except Exception as e:
            logger.error(f"[FASTING] Error converting session to dict: {e}", exc_info=True)
            return None

class FastingCheckIn(db.Model):
    """Model for daily fasting check-ins"""
    __tablename__ = 'fasting_check_ins'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('fasting_sessions.id'), nullable=False)
    day_number = db.Column(db.Integer, nullable=False)
    check_in_time = db.Column(db.DateTime(timezone=True), default=get_local_time)
    completed = db.Column(db.Boolean, default=False)
    mood = db.Column(db.String(50))  # Changed to match frontend values: Excellent, Good, Neutral, etc.
    energy_level = db.Column(db.String(20))  # Changed to match frontend values: High, Moderate, Low, Very Low
    weight = db.Column(db.Float)  # Optional weight tracking
    symptoms = db.Column(db.JSON)  # Store any symptoms as JSON
    notes = db.Column(db.Text)

    # Add unique constraint to prevent duplicate check-ins for the same day in a session
    __table_args__ = (
        db.UniqueConstraint('session_id', 'day_number', name='unique_daily_checkin'),
    )

    def to_dict(self):
        """Convert check-in to dictionary with proper timezone handling"""
        try:
            check_in_time = format_timestamp(self.check_in_time)
            return {
                'id': self.id,
                'day_number': self.day_number,
                'check_in_time': check_in_time.isoformat() if check_in_time else None,
                'completed': self.completed,
                'mood': self.mood,
                'energy_level': self.energy_level,
                'weight': self.weight,
                'symptoms': self.symptoms,
                'notes': self.notes
            }
        except Exception as e:
            logger.error(f"Error converting check-in to dict: {e}")
            return None
            
class APIUsageLog(TimestampMixin, db.Model):
    """Log of API usage for monitoring and analytics"""
    __tablename__ = 'api_usage_logs'
    id = db.Column(db.Integer, primary_key=True)
    api_name = db.Column(db.String(64), nullable=False)  # e.g. 'OpenAI', 'Oura', 'Google Maps'
    endpoint = db.Column(db.String(128), nullable=False)  # Specific endpoint or method called
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    response_time = db.Column(db.Float, default=0.0)  # Response time in seconds
    success = db.Column(db.Boolean, default=True)  # Whether the API call was successful
    status_code = db.Column(db.Integer, default=200)  # HTTP status code
    request_size = db.Column(db.Integer, nullable=True)  # Size of request payload in bytes
    response_size = db.Column(db.Integer, nullable=True)  # Size of response payload in bytes
    
    # Define relationship with User - this is a one-to-many relationship
    # An API log belongs to one user, a user can have many API logs
    user = db.relationship('User', backref=db.backref('api_usage_logs', lazy=True))
    
    def to_dict(self):
        """Convert API usage log to dictionary"""
        try:
            return {
                'id': self.id,
                'api_name': self.api_name,
                'endpoint': self.endpoint,
                'user_id': self.user_id,
                'username': self.user.username if self.user else 'Unknown',
                'timestamp': self.created_at.isoformat() if self.created_at else None,
                'response_time': self.response_time,
                'success': self.success,
                'status_code': self.status_code
            }
        except Exception as e:
            logger.error(f"Error converting API usage log to dict: {e}", exc_info=True)
            return None
            
            
class ManualWellnessCheckIn(TimestampMixin, db.Model):
    """Model for manually tracking wellness metrics for users without biometric devices"""
    __tablename__ = 'manual_wellness_check_ins'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Physical sensations
    energy_level = db.Column(db.Integer)  # 1-10 scale
    physical_comfort = db.Column(db.Integer)  # 1-10 scale
    sleep_quality = db.Column(db.Integer)  # 1-10 scale
    breathing_quality = db.Column(db.Integer)  # 1-10 scale
    physical_tension = db.Column(db.Integer)  # 1-10 scale (higher means more tension)
    
    # Mental state
    stress_level = db.Column(db.Integer)  # 1-10 scale
    mood = db.Column(db.String(50))  # e.g. "happy", "anxious", "sad", etc.
    focus_level = db.Column(db.Integer)  # 1-10 scale
    
    # Physical activities & context
    exercise_minutes = db.Column(db.Integer, nullable=True)
    water_glasses = db.Column(db.Integer, nullable=True)
    weather_condition = db.Column(db.String(50), nullable=True)
    location_type = db.Column(db.String(50), nullable=True)  # e.g. "home", "work", "outdoors"
    
    # Timestamps and notes (explicitly using timezone-aware UTC format)
    recorded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text, nullable=True)
    
    # Ensure the timestamp is always timezone-aware when retrieved
    @property
    def timestamp_with_timezone(self):
        """Return a timezone-aware datetime object for proper display"""
        if self.recorded_at and self.recorded_at.tzinfo is None:
            return self.recorded_at.replace(tzinfo=timezone.utc)
        return self.recorded_at
    
    # Relationships
    user = db.relationship('User', backref=db.backref('wellness_checkins', lazy=True))
    
    def to_dict(self):
        """Convert check-in to dictionary"""
        return {
            'id': self.id,
            'energy_level': self.energy_level,
            'physical_comfort': self.physical_comfort,
            'sleep_quality': self.sleep_quality,
            'breathing_quality': self.breathing_quality,
            'physical_tension': self.physical_tension,
            'stress_level': self.stress_level,
            'mood': self.mood,
            'focus_level': self.focus_level,
            'exercise_minutes': self.exercise_minutes,
            'water_glasses': self.water_glasses,
            'weather_condition': self.weather_condition,
            'location_type': self.location_type,
            'recorded_at': self.timestamp_with_timezone.isoformat() if self.recorded_at else None,
            'notes': self.notes
        }