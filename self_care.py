"""
Interactive Self-Care Recommendations Engine for AI-BUDDY

This module provides personalized wellness recommendations based on:
1. Biometric data from smart rings
2. User location and context
3. Historical user preferences and responses
4. Time-sensitive interventions

Author: AI-BUDDY Developer Team
Date: May 3, 2025
"""

import os
import json
import logging
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import desc, and_, or_, func
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField, SelectField
from wtforms.validators import Optional

from extensions import db
from ai_client import generate_health_insight
from ring_data import get_ring_data
from models import User, ManualWellnessCheckIn
from location_wellness import calculate_distance, get_nearby_places

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
self_care_bp = Blueprint('self_care', __name__, url_prefix='/self-care')

# ----------------------
# Forms
# ----------------------

class WellnessCheckInForm(FlaskForm):
    """Form for wellness check-in"""
    energy_level = IntegerField('Energy Level', validators=[Optional()])
    physical_comfort = IntegerField('Physical Comfort', validators=[Optional()])
    sleep_quality = IntegerField('Sleep Quality', validators=[Optional()])
    breathing_quality = IntegerField('Breathing Quality', validators=[Optional()])
    physical_tension = IntegerField('Physical Tension', validators=[Optional()])
    stress_level = IntegerField('Stress Level', validators=[Optional()])
    mood = SelectField('Mood', choices=[
        ('very_negative', 'Very Negative'),
        ('negative', 'Negative'),
        ('neutral', 'Neutral'),
        ('positive', 'Positive'),
        ('very_positive', 'Very Positive')
    ], validators=[Optional()])
    focus_level = IntegerField('Focus Level', validators=[Optional()])
    exercise_minutes = IntegerField('Exercise Minutes', validators=[Optional()])
    water_glasses = IntegerField('Water Glasses', validators=[Optional()])
    weather_condition = StringField('Weather Condition', validators=[Optional()])
    location_type = StringField('Location Type', validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])

# ----------------------
# Database Models
# ----------------------

class SelfCareRecommendation(db.Model):
    """Model for storing self-care recommendations"""
    __tablename__ = 'self_care_recommendation'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recommendation_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    reasoning = db.Column(db.Text)
    context_data = db.Column(db.Text)  # JSON string with context that generated this recommendation
    suggested_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    priority = db.Column(db.Integer, default=1)  # 1-5 scale, 5 being highest
    status = db.Column(db.String(20), default="pending")  # pending, accepted, declined, completed
    effectiveness = db.Column(db.Integer)  # 1-5 rating provided by user
    
    # Relationships
    user = db.relationship('User', backref=db.backref('self_care_recommendations', lazy=True))
    
    def to_dict(self):
        """Convert recommendation to dictionary"""
        return {
            'id': self.id,
            'type': self.recommendation_type,
            'title': self.title,
            'description': self.description,
            'reasoning': self.reasoning,
            'suggested_at': self.suggested_at.isoformat() if self.suggested_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'priority': self.priority,
            'status': self.status,
            'effectiveness': self.effectiveness
        }


class SelfCareUserPreference(db.Model):
    """Model for storing user preferences for self-care recommendations"""
    __tablename__ = 'self_care_user_preference'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    preference_key = db.Column(db.String(50), nullable=False)
    preference_value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('self_care_preferences', lazy=True))
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'preference_key'),)


class SelfCareActivity(db.Model):
    """Model for tracking completed self-care activities"""
    __tablename__ = 'self_care_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recommendation_id = db.Column(db.Integer, db.ForeignKey('self_care_recommendation.id'), nullable=True)
    activity_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_rating = db.Column(db.Integer)  # 1-5 rating
    mood_before = db.Column(db.String(50))
    mood_after = db.Column(db.String(50))
    
    # Relationships
    user = db.relationship('User', backref=db.backref('self_care_activities', lazy=True))
    recommendation = db.relationship('SelfCareRecommendation', backref=db.backref('activities', lazy=True))
    
    def to_dict(self):
        """Convert activity to dictionary"""
        return {
            'id': self.id,
            'activity_type': self.activity_type,
            'title': self.title,
            'description': self.description,
            'duration_minutes': self.duration_minutes,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'user_rating': self.user_rating,
            'mood_before': self.mood_before,
            'mood_after': self.mood_after
        }


# ----------------------
# Recommendation Engine
# ----------------------

class RecommendationEngine:
    """Core engine for generating self-care recommendations"""
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.user = User.query.get(user_id)
        self.biometric_data = None
        self.location_data = None
        self.time_context = datetime.utcnow()
        self.user_preferences = {}
        self.recommendation_history = []
        
        # Load user preferences
        self._load_preferences()
        
    def _load_preferences(self):
        """Load user preferences from database"""
        preferences = SelfCareUserPreference.query.filter_by(user_id=self.user_id).all()
        for pref in preferences:
            try:
                self.user_preferences[pref.preference_key] = json.loads(pref.preference_value)
            except json.JSONDecodeError:
                self.user_preferences[pref.preference_key] = pref.preference_value
    
    def _load_recommendation_history(self, days=7):
        """Load recent recommendation history"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        history = SelfCareRecommendation.query.filter(
            SelfCareRecommendation.user_id == self.user_id,
            SelfCareRecommendation.suggested_at >= cutoff_date
        ).order_by(desc(SelfCareRecommendation.suggested_at)).all()
        
        self.recommendation_history = history
        return history
        
    def fetch_biometric_data(self):
        """Fetch latest biometric data from smart rings or fall back to manual wellness data"""
        try:
            # Try to get real-time biometric data from smart rings first
            ring_data = get_ring_data()
            if ring_data and ring_data.get('status') == 'success':
                # Real smart ring data available
                self.biometric_data = {
                    'oura': ring_data.get('oura', {}),
                    'ultrahuman': ring_data.get('ultrahuman', {}),
                    'timestamp': datetime.utcnow().isoformat(),
                    'data_source': 'smart_rings'
                }
                logger.info(f"Retrieved real-time biometric data for user {self.user_id}")
                return self.biometric_data
            else:
                # Smart ring data unavailable, try to use manual wellness check-in data
                logger.warning(f"Failed to fetch biometric data: {ring_data}")
                return self._use_manual_wellness_data()
        except Exception as e:
            logger.error(f"Error fetching biometric data: {str(e)}")
            # Fall back to manual check-in data for non-biometric users
            return self._use_manual_wellness_data()
    
    def _use_manual_wellness_data(self):
        """Use manual wellness check-in data when smart ring data is unavailable"""
        # Check if we have manual wellness check-ins for this user
        recent_check_in = ManualWellnessCheckIn.query.filter_by(
            user_id=self.user_id
        ).order_by(desc(ManualWellnessCheckIn.recorded_at)).first()
        
        current_time = datetime.utcnow()
        
        if recent_check_in:
            # Use the user's most recent manual wellness check-in data
            logger.info(f"Using manual wellness check-in data for user {self.user_id}")
            
            # Create a structure compatible with the smart ring data format
            self.biometric_data = {
                'timestamp': current_time.isoformat(),
                'data_source': 'manual_check_in',
                'oura': {},  # Initialize with empty dicts
                'ultrahuman': {}
            }
            
            # Map wellness check-in data to equivalent biometric metrics
            if recent_check_in.stress_level is not None:
                # Convert 1-10 stress level to equivalent format used by ring data (0-100 scale)
                stress_value = recent_check_in.stress_level * 10
                self.biometric_data['oura']['stress_level'] = stress_value
                
            if recent_check_in.sleep_quality is not None:
                # Convert 1-10 sleep quality to equivalent format used by ring data (0-100 scale)
                sleep_score = recent_check_in.sleep_quality * 10
                self.biometric_data['oura']['sleep_score'] = sleep_score
                
            if recent_check_in.energy_level is not None:
                # Convert 1-10 energy level to equivalent readiness score (0-100 scale)
                readiness = recent_check_in.energy_level * 10
                self.biometric_data['oura']['readiness_score'] = readiness
                
            # Store the raw check-in data too for additional context
            self.biometric_data['manual_data'] = {
                'energy_level': recent_check_in.energy_level,
                'physical_comfort': recent_check_in.physical_comfort,
                'sleep_quality': recent_check_in.sleep_quality,
                'breathing_quality': recent_check_in.breathing_quality,
                'physical_tension': recent_check_in.physical_tension,
                'stress_level': recent_check_in.stress_level,
                'mood': recent_check_in.mood,
                'focus_level': recent_check_in.focus_level,
                'recorded_at': recent_check_in.timestamp_with_timezone.isoformat() if recent_check_in.recorded_at else None
            }
            
            return self.biometric_data
        else:
            # No manual check-in data available, use time-based default values
            logger.info(f"Using default values for user {self.user_id} (no manual check-in available)")
            
            hour = current_time.hour
            
            # Adjust default stress level based on time of day (higher in morning and evening)
            stress_level = 5
            if hour < 9:  # Morning
                stress_level = 6
            elif hour >= 17:  # Evening
                stress_level = 6
                
            # Set reasonable default values based on time of day
            self.biometric_data = {
                'timestamp': current_time.isoformat(),
                'data_source': 'default_values',
                'oura': {
                    'stress_level': stress_level * 10,
                    'sleep_score': 65,
                    'readiness_score': 70
                },
                'ultrahuman': {},
                'manual_data': {
                    'energy_level': 5,
                    'stress_level': stress_level,
                    'mood': 'neutral'
                }
            }
            
            return self.biometric_data
            
    def has_biometric_data(self):
        """Check if user has real biometric data available (or manual data/defaults)"""
        if not self.biometric_data:
            self.fetch_biometric_data()
        
        # Check if we have any data structure at all
        if not self.biometric_data:
            return False
        
        # Check data source
        data_source = self.biometric_data.get('data_source', '')
        
        # For smart ring data, check if we have meaningful metrics
        if data_source == 'smart_rings':
            # Check if we have data from either Oura or Ultrahuman
            has_oura = self.biometric_data.get('oura') and len(self.biometric_data.get('oura', {})) > 0
            has_ultrahuman = self.biometric_data.get('ultrahuman') and len(self.biometric_data.get('ultrahuman', {})) > 0
            return has_oura or has_ultrahuman
        
        # For manual check-in or default data, those already have basic metrics
        # so we'll return True to allow the system to continue
        return True
    
    def set_location_data(self, latitude, longitude):
        """Set user location data"""
        self.location_data = {
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Try to fetch nearby places if location is provided
        try:
            if latitude and longitude:
                nearby_places = get_nearby_places(latitude, longitude)
                if nearby_places and 'places' in nearby_places:
                    self.location_data['nearby_places'] = nearby_places['places']
        except Exception as e:
            logger.error(f"Error fetching nearby places: {str(e)}")
            
        return self.location_data
    
    def analyze_stress_level(self):
        """Analyze current stress level from biometric data or manual check-in"""
        data_source = None
        if not self.biometric_data:
            self.fetch_biometric_data()
            
        stress_level = None
        confidence = 0.5
        
        # Try Oura data first
        if 'oura' in self.biometric_data and self.biometric_data['oura']:
            oura_data = self.biometric_data['oura']
            if 'stress_level' in oura_data:
                try:
                    stress_value = int(oura_data['stress_level'])
                    confidence = 0.8
                    if stress_value > 80:
                        stress_level = 'high'
                    elif stress_value > 60:
                        stress_level = 'moderate'
                    else:
                        stress_level = 'low'
                    data_source = 'oura_api'
                except (ValueError, TypeError):
                    pass
                
        # If no stress level from Oura, try Ultrahuman
        if stress_level is None and 'ultrahuman' in self.biometric_data and self.biometric_data['ultrahuman']:
            ultrahuman_data = self.biometric_data['ultrahuman']
            if 'recovery_index' in ultrahuman_data:
                try:
                    recovery_index = int(ultrahuman_data['recovery_index'])
                    confidence = 0.7
                    if recovery_index < 40:
                        stress_level = 'high'
                    elif recovery_index < 65:
                        stress_level = 'moderate'
                    else:
                        stress_level = 'low'
                    data_source = 'ultrahuman_api'
                except (ValueError, TypeError):
                    pass
        
        # If still no data, use HRV as proxy for stress
        if stress_level is None:
            hrv = None
            hrv_source = None
            if 'oura' in self.biometric_data and self.biometric_data['oura'] and 'heart_rate_variability' in self.biometric_data['oura']:
                try:
                    hrv = int(self.biometric_data['oura']['heart_rate_variability'])
                    confidence = 0.6
                    hrv_source = 'oura_api'
                except (ValueError, TypeError):
                    pass
            elif 'ultrahuman' in self.biometric_data and self.biometric_data['ultrahuman'] and 'heart_rate_variability' in self.biometric_data['ultrahuman']:
                try:
                    hrv = int(self.biometric_data['ultrahuman']['heart_rate_variability'])
                    confidence = 0.6
                    hrv_source = 'ultrahuman_api'
                except (ValueError, TypeError):
                    pass
                
            if hrv is not None:
                if hrv < 30:
                    stress_level = 'high'
                elif hrv < 50:
                    stress_level = 'moderate'
                else:
                    stress_level = 'low'
                data_source = hrv_source
        
        # Check if there's a recent manual check-in
        if stress_level is None or confidence < 0.7:
            # Get the most recent check-in from the last 4 hours
            four_hours_ago = datetime.utcnow() - timedelta(hours=4)
            recent_check_in = ManualWellnessCheckIn.query.filter(
                ManualWellnessCheckIn.user_id == self.user_id,
                ManualWellnessCheckIn.recorded_at >= four_hours_ago
            ).order_by(desc(ManualWellnessCheckIn.recorded_at)).first()
            
            if recent_check_in:
                stress_value = recent_check_in.stress_level
                if stress_value > 7:
                    new_stress_level = 'high' 
                elif stress_value > 4:
                    new_stress_level = 'moderate'
                else:
                    new_stress_level = 'low'
                
                # Use manual check-in if it's newer than biometric data or if no biometric data
                if stress_level is None or confidence < 0.5:
                    stress_level = new_stress_level
                    confidence = 0.7
                    data_source = 'manual_check_in'
        
        # Default if no data available
        if stress_level is None:
            stress_level = 'unknown'
            confidence = 0.0
            data_source = 'no_data'
            
        return {
            'level': stress_level,
            'confidence': confidence,
            'data_source': data_source
        }
    
    def analyze_activity_level(self):
        """Analyze recent activity level"""
        # Default implementation based on time - this should be expanded
        # with actual activity tracking data
        hour = datetime.utcnow().hour
        
        data_source = 'time_based'
        if self.biometric_data:
            if 'oura' in self.biometric_data and self.biometric_data['oura'] and 'activity_score' in self.biometric_data['oura']:
                data_source = 'oura_api'
                # This would be implemented when API provides activity data
                # Currently using time-based fallback
            elif 'ultrahuman' in self.biometric_data and self.biometric_data['ultrahuman'] and 'activity_score' in self.biometric_data['ultrahuman']:
                data_source = 'ultrahuman_api'
                # This would be implemented when API provides activity data
                # Currently using time-based fallback
        
        if 9 <= hour <= 17:  # Work hours
            return {'level': 'moderate', 'confidence': 0.6, 'data_source': data_source}
        elif 6 <= hour < 9 or 17 < hour <= 20:  # Morning/evening
            return {'level': 'active', 'confidence': 0.5, 'data_source': data_source}
        else:  # Early morning or late night
            return {'level': 'low', 'confidence': 0.7, 'data_source': data_source}
    
    def generate_context_aware_recommendations(self, count=3):
        """Generate personalized recommendations based on current context"""
        recommendations = []
        
        # Check if biometric data is available for this user
        has_biometric = self.has_biometric_data()
        
        # Get stress analysis (will work with or without biometric data)
        stress_analysis = self.analyze_stress_level()
        activity_analysis = self.analyze_activity_level()
        
        # Load recent recommendation history to avoid duplicates
        self._load_recommendation_history(days=3)
        recent_types = [r.recommendation_type for r in self.recommendation_history[:5]]
        
        # Get current time context
        now = datetime.utcnow()
        hour = now.hour
        
        # Get user preferences that might help with personalization
        user_preferences = {}
        for pref in SelfCareUserPreference.query.filter_by(user_id=self.user_id).all():
            user_preferences[pref.preference_key] = pref.preference_value
        
        # Get recent mood data if available
        mood_data = None
        try:
            from models import Mood
            recent_moods = Mood.query.filter_by(user_id=self.user_id).order_by(Mood.timestamp.desc()).limit(5).all()
            if recent_moods:
                mood_data = [mood.mood for mood in recent_moods]
        except Exception as e:
            logger.warning(f"Could not retrieve mood data: {str(e)}")
            
        # Get recent food journal entries if available
        food_data = None
        try:
            from models import FoodLog
            recent_food = FoodLog.query.filter_by(user_id=self.user_id).order_by(FoodLog.timestamp.desc()).limit(5).all()
            if recent_food:
                food_data = [food.food_name for food in recent_food]
        except Exception as e:
            logger.warning(f"Could not retrieve food data: {str(e)}")
            
        # Context object to pass to AI
        context = {
            'time_of_day': 'morning' if 5 <= hour < 12 else 'afternoon' if 12 <= hour < 18 else 'evening',
            'stress_level': stress_analysis['level'],
            'activity_level': activity_analysis['level'],
            'has_biometric_data': has_biometric,
            'is_biometric_user': self.user.is_biometric_user() if self.user else False,
            'data_source': stress_analysis.get('data_source', 'unknown'),
            'has_location_data': self.location_data is not None,
            'recent_recommendation_types': recent_types,
            'weekday': now.strftime('%A'),
            'user_preferences': user_preferences
        }
        
        # Add mood data if available
        if mood_data:
            context['recent_moods'] = mood_data
            
        # Add food data if available
        if food_data:
            context['recent_foods'] = food_data
        
        # Add biometric details if available
        if has_biometric and self.biometric_data:
            if 'oura' in self.biometric_data and self.biometric_data['oura']:
                context['heart_rate'] = self.biometric_data['oura'].get('heart_rate')
                context['hrv'] = self.biometric_data['oura'].get('heart_rate_variability')
                
        # Generate recommendations using AI
        try:
            input_prompt = self._build_recommendation_prompt(context, count)
            ai_response = generate_health_insight(input_prompt, response_format="json")
            
            if isinstance(ai_response, str):
                try:
                    ai_response = json.loads(ai_response)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse AI response as JSON: {ai_response}")
                    return self._fallback_recommendations(context, count)
            
            if 'recommendations' in ai_response and isinstance(ai_response['recommendations'], list):
                ai_recommendations = ai_response['recommendations']
                
                for rec in ai_recommendations:
                    if len(recommendations) >= count:
                        break
                        
                    recommendation = SelfCareRecommendation(
                        user_id=self.user_id,
                        recommendation_type=rec.get('type', 'general'),
                        title=rec.get('title', 'Self-care recommendation'),
                        description=rec.get('description', ''),
                        reasoning=rec.get('reasoning', ''),
                        context_data=json.dumps(context),
                        suggested_at=datetime.utcnow(),
                        expires_at=datetime.utcnow() + timedelta(hours=12),
                        priority=rec.get('priority', 3)
                    )
                    
                    recommendations.append(recommendation)
                
            else:
                logger.warning(f"AI response didn't contain recommendations array: {ai_response}")
                return self._fallback_recommendations(context, count)
                
        except Exception as e:
            logger.error(f"Error generating AI recommendations: {str(e)}")
            return self._fallback_recommendations(context, count)
        
        # Save recommendations to database
        for rec in recommendations:
            try:
                db.session.add(rec)
                db.session.commit()
            except Exception as e:
                logger.error(f"Error saving recommendation: {str(e)}")
                db.session.rollback()
        
        return recommendations
    
    def _build_recommendation_prompt(self, context, count):
        """Build prompt for AI recommendation generation"""
        prompt = f"""Generate {count} personalized self-care recommendations based on the following context:

Time of day: {context.get('time_of_day')}
Day of week: {context.get('weekday')}
Current stress level: {context.get('stress_level')}
Current activity level: {context.get('activity_level')}
Is biometric user: {context.get('is_biometric_user', False)}
Has biometric data: {context.get('has_biometric_data', False)}
Data source: {context.get('data_source', 'not_available')}
"""

        # Add biometric data if available
        if context.get('heart_rate'):
            prompt += f"Heart rate: {context.get('heart_rate')} bpm\n"
            
        if context.get('hrv'):
            prompt += f"Heart rate variability: {context.get('hrv')} ms\n"
        
        # Add mood data if available
        if context.get('recent_moods'):
            prompt += f"Recent moods: {', '.join(context.get('recent_moods'))}\n"
            
        # Add food data if available
        if context.get('recent_foods'):
            prompt += f"Recent foods: {', '.join(context.get('recent_foods')[:3])}\n"
        
        # Add user preferences if available
        if context.get('user_preferences') and len(context.get('user_preferences', {})) > 0:
            prompt += "User preferences:\n"
            for key, value in context.get('user_preferences', {}).items():
                prompt += f"- {key}: {value}\n"
        
        # Add recent recommendation types to avoid duplication
        if context.get('recent_recommendation_types'):
            prompt += f"Recent recommendation types: {', '.join(context.get('recent_recommendation_types'))}\n"
            
        # Special instructions based on the user's biometric access status
        if not context.get('is_biometric_user', False):
            # Non-biometric user (no smart ring or watch)
            prompt += """
IMPORTANT: This user does not have any biometric device. Generate recommendations that:
1. Do not rely on or reference any biometric data
2. Focus on general wellbeing practices based on time of day and reported stress/activity levels
3. Suggest simple ways to check in with their body and emotions
4. Include recommendations that might help them become more aware of their physical state
5. Emphasize activities that can be done without any technology or devices
"""
        elif not context.get('has_biometric_data', False):
            # Biometric user but no data currently available
            prompt += """
IMPORTANT: This user has a biometric device but data is not currently available. Generate recommendations that:
1. Can work with or without biometric readings
2. Reference the user's smart ring/watch in general terms but don't rely on specific readings
3. Focus on activities that complement biometric tracking
4. Include suggestions for activities that might improve measurable biometric markers
"""
        
        prompt += f"""
Each recommendation should be:
1. Specific and actionable
2. Appropriate for the time of day and stress level
3. Varied in type (not all the same kind of activity)
4. Different from recent recommendations
5. Personalized based on available context

Respond with a JSON object containing an array of recommendations, each with:
- type: category of recommendation (meditation, movement, social, nature, creative, etc.)
- title: short title for the recommendation
- description: detailed description of what to do
- reasoning: why this would be helpful right now
- priority: number 1-5 indicating importance (5 is highest)

Return ONLY valid JSON with no explanations outside the JSON.
"""
        return prompt
    
    def _fallback_recommendations(self, context, count):
        """Provide fallback recommendations if AI generation fails"""
        recommendations = []
        
        # Basic recommendation types based on time and stress
        stress_level = context.get('stress_level', 'unknown')
        time_of_day = context.get('time_of_day', 'unknown')
        
        recommendation_options = {
            'high': [
                {
                    'type': 'breathing',
                    'title': 'Box Breathing Exercise',
                    'description': 'Find a quiet place to sit. Breathe in for 4 counts, hold for 4 counts, exhale for 4 counts, and hold empty lungs for 4 counts. Repeat for 2-3 minutes.',
                    'reasoning': 'Box breathing quickly reduces stress by activating your parasympathetic nervous system.',
                    'priority': 5
                },
                {
                    'type': 'meditation',
                    'title': 'Quick Stress Reset Meditation',
                    'description': 'Take 5 minutes to focus on your breath. Sit comfortably, close your eyes, and simply observe your natural breathing pattern without trying to change it.',
                    'reasoning': 'Brief meditation can quickly lower stress levels and bring you back to center.',
                    'priority': 5
                },
                {
                    'type': 'movement',
                    'title': 'Tension Release Stretches',
                    'description': 'Stand up and gently stretch your neck, shoulders, and back. Roll your shoulders backward 5 times, then forward 5 times. Gently tilt your head side to side.',
                    'reasoning': 'Physical tension often accompanies mental stress. These stretches release tight muscles where you hold stress.',
                    'priority': 4
                }
            ],
            'moderate': [
                {
                    'type': 'nature',
                    'title': 'Brief Nature Connection',
                    'description': 'Step outside for 10 minutes. Focus on the natural elements around you - feel the air, listen to birds or leaves, notice plants or sky.',
                    'reasoning': 'Nature exposure has been shown to reduce cortisol levels and improve mood.',
                    'priority': 3
                },
                {
                    'type': 'mindfulness',
                    'title': 'Mindful Tea or Water Break',
                    'description': 'Prepare a cup of tea or glass of water. As you drink it, focus entirely on the experience - the temperature, taste, and sensations.',
                    'reasoning': 'Mindful drinking creates a small reset in your day and brings you to the present moment.',
                    'priority': 3
                },
                {
                    'type': 'creativity',
                    'title': 'Quick Doodle Session',
                    'description': 'Take 5 minutes to doodle freely on paper without judgment. Don\'t try to create anything specific - just let your pen move.',
                    'reasoning': 'Creative activities engage different brain regions and provide relief from analytical thinking.',
                    'priority': 3
                }
            ],
            'low': [
                {
                    'type': 'social',
                    'title': 'Gratitude Message',
                    'description': 'Send a brief message to someone expressing appreciation for something specific they\'ve done or how they\'ve positively impacted you.',
                    'reasoning': 'Expressing gratitude increases positive emotions and strengthens social connections.',
                    'priority': 2
                },
                {
                    'type': 'learning',
                    'title': 'Learn Something New',
                    'description': 'Spend 10 minutes reading an article or watching a video about a topic that interests you but isn\'t related to work.',
                    'reasoning': 'Learning new things activates your brain\'s reward system and creates positive emotions.',
                    'priority': 2
                },
                {
                    'type': 'self-reflection',
                    'title': 'Quick Journal Check-in',
                    'description': 'Write down three things that went well today and one thing you\'re looking forward to.',
                    'reasoning': 'Brief positive reflection helps maintain perspective and builds optimism.',
                    'priority': 2
                }
            ]
        }
        
        # Time-specific adjustments
        time_adjustments = {
            'morning': [
                {
                    'type': 'movement',
                    'title': 'Morning Stretch Routine',
                    'description': 'Spend 5 minutes gently stretching your body to wake up. Reach your arms overhead, do gentle side bends, and roll your shoulders.',
                    'reasoning': 'Morning stretching improves circulation and prepares your body for the day ahead.',
                    'priority': 4
                },
                {
                    'type': 'mindfulness',
                    'title': 'Intention Setting',
                    'description': 'Take 2 minutes to set a simple intention for your day - a word or short phrase to guide your actions and decisions.',
                    'reasoning': 'Setting intentions creates focus and provides a touchstone to return to throughout the day.',
                    'priority': 3
                }
            ],
            'afternoon': [
                {
                    'type': 'movement',
                    'title': 'Afternoon Energy Reset',
                    'description': 'Stand up and do 10 gentle jumping jacks, 5 arm circles in each direction, and 5 deep squats to reactivate your body.',
                    'reasoning': 'Brief movement breaks combat afternoon energy dips and improve focus.',
                    'priority': 4
                },
                {
                    'type': 'mindfulness',
                    'title': 'Midday Breathing Reset',
                    'description': 'Take 10 deep breaths, counting to 4 on the inhale and 6 on the exhale. Place a hand on your belly to feel it rise and fall.',
                    'reasoning': 'Extended exhales activate the parasympathetic nervous system, helping you reset during a busy day.',
                    'priority': 3
                }
            ],
            'evening': [
                {
                    'type': 'relaxation',
                    'title': 'Progressive Relaxation',
                    'description': 'Lie down and tense then release each muscle group, starting from your feet and moving up to your head. Hold each tension for 5 seconds before releasing.',
                    'reasoning': 'Progressive relaxation helps transition from the active day to a restful evening state.',
                    'priority': 4
                },
                {
                    'type': 'self-reflection',
                    'title': 'Daily Highlight Reflection',
                    'description': 'Take a moment to identify and appreciate the best moment from your day, no matter how small it seemed.',
                    'reasoning': 'Ending your day by recalling positive moments improves mood and primes your brain for positive thinking.',
                    'priority': 3
                }
            ]
        }
        
        # Select recommendations based on stress level and time
        option_pool = []
        
        # Add stress-based recommendations
        if stress_level in recommendation_options:
            option_pool.extend(recommendation_options[stress_level])
        else:
            # If unknown stress level, add some from each category
            for options in recommendation_options.values():
                option_pool.extend(options[:1])  # Add first option from each stress level
        
        # Add time-specific recommendations
        if time_of_day in time_adjustments:
            option_pool.extend(time_adjustments[time_of_day])
        
        # Avoid duplicates from recent recommendations
        recent_types = context.get('recent_recommendation_types', [])
        filtered_options = [opt for opt in option_pool if opt['type'] not in recent_types[:3]]
        
        # If filtering removed too many options, add some back
        if len(filtered_options) < count:
            filtered_options.extend([opt for opt in option_pool if opt not in filtered_options][:count-len(filtered_options)])
        
        # Randomize and select options
        random.shuffle(filtered_options)
        selected_options = filtered_options[:count]
        
        # Create recommendation objects
        for opt in selected_options:
            recommendation = SelfCareRecommendation(
                user_id=self.user_id,
                recommendation_type=opt['type'],
                title=opt['title'],
                description=opt['description'],
                reasoning=opt['reasoning'],
                context_data=json.dumps(context),
                suggested_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=12),
                priority=opt['priority']
            )
            
            recommendations.append(recommendation)
            
            # Save to database
            try:
                db.session.add(recommendation)
                db.session.commit()
            except Exception as e:
                logger.error(f"Error saving fallback recommendation: {str(e)}")
                db.session.rollback()
        
        return recommendations
    
    def get_active_recommendations(self, limit=5):
        """Get active recommendations for the user"""
        now = datetime.utcnow()
        return SelfCareRecommendation.query.filter(
            SelfCareRecommendation.user_id == self.user_id,
            SelfCareRecommendation.expires_at > now,
            SelfCareRecommendation.status.in_(['pending', 'accepted'])
        ).order_by(desc(SelfCareRecommendation.priority), desc(SelfCareRecommendation.suggested_at)).limit(limit).all()
    
    def update_recommendation_status(self, recommendation_id, status, effectiveness=None):
        """Update status and effectiveness of a recommendation"""
        recommendation = SelfCareRecommendation.query.get(recommendation_id)
        
        if not recommendation or recommendation.user_id != self.user_id:
            return False
        
        try:
            recommendation.status = status
            
            if effectiveness is not None:
                recommendation.effectiveness = effectiveness
                
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating recommendation status: {str(e)}")
            db.session.rollback()
            return False
    
    def log_self_care_activity(self, activity_data, recommendation_id=None):
        """Log a completed self-care activity"""
        try:
            activity = SelfCareActivity(
                user_id=self.user_id,
                recommendation_id=recommendation_id,
                activity_type=activity_data.get('activity_type', 'general'),
                title=activity_data.get('title', 'Self-care activity'),
                description=activity_data.get('description', ''),
                duration_minutes=activity_data.get('duration_minutes'),
                completed_at=activity_data.get('completed_at', datetime.utcnow()),
                user_rating=activity_data.get('user_rating'),
                mood_before=activity_data.get('mood_before'),
                mood_after=activity_data.get('mood_after')
            )
            
            db.session.add(activity)
            
            # If this activity is from a recommendation, update its status
            if recommendation_id:
                recommendation = SelfCareRecommendation.query.get(recommendation_id)
                if recommendation and recommendation.user_id == self.user_id:
                    recommendation.status = 'completed'
                    recommendation.effectiveness = activity_data.get('user_rating')
            
            db.session.commit()
            return activity
        except Exception as e:
            logger.error(f"Error logging self-care activity: {str(e)}")
            db.session.rollback()
            return None
    
    def get_recent_activities(self, days=30, limit=10):
        """Get recent self-care activities"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return SelfCareActivity.query.filter(
            SelfCareActivity.user_id == self.user_id,
            SelfCareActivity.completed_at >= cutoff_date
        ).order_by(desc(SelfCareActivity.completed_at)).limit(limit).all()
    
    def set_user_preference(self, key, value):
        """Set or update a user preference"""
        try:
            # Convert value to JSON string if not already a string
            if not isinstance(value, str):
                value_str = json.dumps(value)
            else:
                value_str = value
                
            # Check if preference already exists
            preference = SelfCareUserPreference.query.filter_by(
                user_id=self.user_id, 
                preference_key=key
            ).first()
            
            if preference:
                preference.preference_value = value_str
                preference.updated_at = datetime.utcnow()
            else:
                preference = SelfCareUserPreference(
                    user_id=self.user_id,
                    preference_key=key,
                    preference_value=value_str
                )
                db.session.add(preference)
                
            db.session.commit()
            
            # Update local cache
            self.user_preferences[key] = value
            
            return True
        except Exception as e:
            logger.error(f"Error setting user preference: {str(e)}")
            db.session.rollback()
            return False
    
    def get_user_preference(self, key, default=None):
        """Get a user preference"""
        # First check local cache
        if key in self.user_preferences:
            return self.user_preferences[key]
            
        # Then check database
        preference = SelfCareUserPreference.query.filter_by(
            user_id=self.user_id, 
            preference_key=key
        ).first()
        
        if preference:
            try:
                value = json.loads(preference.preference_value)
                self.user_preferences[key] = value
                return value
            except json.JSONDecodeError:
                self.user_preferences[key] = preference.preference_value
                return preference.preference_value
        
        return default


# ----------------------
# API Routes
# ----------------------

@self_care_bp.route('/api/recommendations', methods=['GET'])
@login_required
def get_recommendations_api():
    """API endpoint to get active recommendations"""
    try:
        engine = RecommendationEngine(current_user.id)
        active_recommendations = engine.get_active_recommendations()
        
        # If there are no active recommendations, generate new ones
        if not active_recommendations:
            # Get location data if provided
            lat = request.args.get('latitude', type=float)
            lon = request.args.get('longitude', type=float)
            
            if lat and lon:
                engine.set_location_data(lat, lon)
                
            # Fetch biometric data
            engine.fetch_biometric_data()
            
            # Generate new recommendations
            new_recommendations = engine.generate_context_aware_recommendations(count=3)
            if new_recommendations:
                active_recommendations = new_recommendations
        
        return jsonify({
            'status': 'success',
            'recommendations': [rec.to_dict() for rec in active_recommendations]
        })
    except Exception as e:
        logger.error(f"Error in get_recommendations_api: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to retrieve recommendations'
        }), 500


@self_care_bp.route('/api/recommendations/<int:recommendation_id>/status', methods=['POST'])
@login_required
def update_recommendation_status_api(recommendation_id):
    """API endpoint to update recommendation status"""
    try:
        data = request.json
        status = data.get('status')
        effectiveness = data.get('effectiveness')
        
        if not status:
            return jsonify({
                'status': 'error',
                'message': 'Status is required'
            }), 400
            
        engine = RecommendationEngine(current_user.id)
        success = engine.update_recommendation_status(recommendation_id, status, effectiveness)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Recommendation status updated'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update recommendation status'
            }), 404
    except Exception as e:
        logger.error(f"Error in update_recommendation_status_api: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred'
        }), 500


@self_care_bp.route('/api/activities', methods=['POST'])
@login_required
def log_activity_api():
    """API endpoint to log a self-care activity"""
    try:
        data = request.json
        recommendation_id = data.pop('recommendation_id', None)
        
        if not data.get('title'):
            return jsonify({
                'status': 'error',
                'message': 'Activity title is required'
            }), 400
            
        engine = RecommendationEngine(current_user.id)
        activity = engine.log_self_care_activity(data, recommendation_id)
        
        if activity:
            return jsonify({
                'status': 'success',
                'message': 'Activity logged successfully',
                'activity': activity.to_dict()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to log activity'
            }), 500
    except Exception as e:
        logger.error(f"Error in log_activity_api: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred'
        }), 500


@self_care_bp.route('/api/activities', methods=['GET'])
@login_required
def get_activities_api():
    """API endpoint to get recent self-care activities"""
    try:
        days = request.args.get('days', default=30, type=int)
        limit = request.args.get('limit', default=10, type=int)
        
        engine = RecommendationEngine(current_user.id)
        activities = engine.get_recent_activities(days=days, limit=limit)
        
        return jsonify({
            'status': 'success',
            'activities': [activity.to_dict() for activity in activities]
        })
    except Exception as e:
        logger.error(f"Error in get_activities_api: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to retrieve activities'
        }), 500


@self_care_bp.route('/api/preferences', methods=['POST'])
@login_required
def set_preference_api():
    """API endpoint to set a user preference"""
    try:
        data = request.json
        key = data.get('key')
        value = data.get('value')
        
        if not key:
            return jsonify({
                'status': 'error',
                'message': 'Preference key is required'
            }), 400
            
        engine = RecommendationEngine(current_user.id)
        success = engine.set_user_preference(key, value)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Preference updated successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update preference'
            }), 500
    except Exception as e:
        logger.error(f"Error in set_preference_api: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred'
        }), 500


@self_care_bp.route('/api/preferences', methods=['GET'])
@login_required
def get_preferences_api():
    """API endpoint to get user preferences"""
    try:
        key = request.args.get('key')
        
        engine = RecommendationEngine(current_user.id)
        
        if key:
            value = engine.get_user_preference(key)
            return jsonify({
                'status': 'success',
                'key': key,
                'value': value
            })
        else:
            # Return all preferences
            return jsonify({
                'status': 'success',
                'preferences': engine.user_preferences
            })
    except Exception as e:
        logger.error(f"Error in get_preferences_api: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to retrieve preferences'
        }), 500



# ----------------------
# Web Routes
# ----------------------

@self_care_bp.route('/', methods=['GET'])
@login_required
def self_care_index():
    """Main self-care dashboard page"""
    logger.info(f"[SELF-CARE] Accessing self-care index for user {current_user.id}")
    
    try:
        engine = RecommendationEngine(current_user.id)
        
        # Get active recommendations
        logger.info("[SELF-CARE] Getting active recommendations")
        active_recommendations = engine.get_active_recommendations()
        logger.info(f"[SELF-CARE] Found {len(active_recommendations) if active_recommendations else 0} active recommendations")
        
        # If no active recommendations, generate new ones
        if not active_recommendations:
            logger.info("[SELF-CARE] No active recommendations found, generating new ones")
            try:
                engine.fetch_biometric_data()
                active_recommendations = engine.generate_context_aware_recommendations()
                logger.info(f"[SELF-CARE] Generated {len(active_recommendations) if active_recommendations else 0} new recommendations")
            except Exception as e:
                logger.error(f"[SELF-CARE] Error generating recommendations: {str(e)}")
                # Continue without recommendations if generation fails
                active_recommendations = []
        
        # Get recent activities
        logger.info("[SELF-CARE] Getting recent activities")
        recent_activities = engine.get_recent_activities(limit=5)
        
        # Analyze current state
        logger.info("[SELF-CARE] Analyzing stress level")
        stress_analysis = engine.analyze_stress_level()
        
        logger.info("[SELF-CARE] Analyzing activity level")
        activity_analysis = engine.analyze_activity_level()
        
        logger.info("[SELF-CARE] Rendering self-care index template")
        return render_template(
            'self-care/index.html',
            recommendations=active_recommendations,
            activities=recent_activities,
            stress_level=stress_analysis.get('level', 'unknown'),
            stress_data_source=stress_analysis.get('data_source', 'unknown'),
            activity_level=activity_analysis.get('level', 'unknown'),
            activity_data_source=activity_analysis.get('data_source', 'unknown'),
            is_biometric_user=current_user.is_biometric_user(),
            page_title="Self-Care Recommendations | AI-BUDDY"
        )
    except Exception as e:
        logger.error(f"[SELF-CARE] Error in self_care_index: {str(e)}")
        # Return a simple error page instead of crashing
        return render_template(
            'error.html',
            error_message="There was an error loading the self-care page. Please try again later.",
            page_title="Error | AI-BUDDY"
        )


@self_care_bp.route('/history', methods=['GET'])
@login_required
def activity_history():
    """View activity history page"""
    engine = RecommendationEngine(current_user.id)
    activities = engine.get_recent_activities(days=90, limit=50)
    
    return render_template(
        'self-care/history.html',
        activities=activities,
        page_title="Self-Care History | AI-BUDDY"
    )


@self_care_bp.route('/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    """User preferences page"""
    engine = RecommendationEngine(current_user.id)
    
    if request.method == 'POST':
        # Update preferences from form
        preferences_updated = False
        
        # Process each preference from the form
        for key, value in request.form.items():
            if key.startswith('pref_'):
                pref_key = key[5:]  # Remove 'pref_' prefix
                if engine.set_user_preference(pref_key, value):
                    preferences_updated = True
        
        if preferences_updated:
            flash('Preferences updated successfully', 'success')
        else:
            flash('No changes were made to preferences', 'info')
            
        return redirect(url_for('self_care.preferences'))
    
    # For GET request, display current preferences
    return render_template(
        'self-care/preferences.html',
        preferences=engine.user_preferences,
        page_title="Self-Care Preferences | AI-BUDDY"
    )


@self_care_bp.route('/recommendation/<int:recommendation_id>', methods=['GET', 'POST'])
@login_required
def view_recommendation(recommendation_id):
    """View a specific recommendation"""
    recommendation = SelfCareRecommendation.query.get_or_404(recommendation_id)
    
    # Ensure the recommendation belongs to the current user
    if recommendation.user_id != current_user.id:
        flash('You do not have permission to view this recommendation', 'danger')
        return redirect(url_for('self_care.self_care_index'))
    
    if request.method == 'POST':
        # Handle form submission (accepting/declining/completing)
        action = request.form.get('action')
        
        engine = RecommendationEngine(current_user.id)
        
        if action == 'accept':
            engine.update_recommendation_status(recommendation_id, 'accepted')
            flash('Recommendation accepted', 'success')
        elif action == 'decline':
            engine.update_recommendation_status(recommendation_id, 'declined')
            flash('Recommendation declined', 'info')
        elif action == 'complete':
            # Log activity from form data
            activity_data = {
                'activity_type': recommendation.recommendation_type,
                'title': recommendation.title,
                'description': request.form.get('notes', ''),
                'duration_minutes': request.form.get('duration', type=int),
                'user_rating': request.form.get('rating', type=int),
                'mood_before': request.form.get('mood_before'),
                'mood_after': request.form.get('mood_after')
            }
            
            engine.log_self_care_activity(activity_data, recommendation_id)
            flash('Activity completed and logged', 'success')
            
            return redirect(url_for('self_care.self_care_index'))
        
        return redirect(url_for('self_care.view_recommendation', recommendation_id=recommendation_id))
    
    # Parse context data
    context_data = {}
    if recommendation.context_data:
        try:
            context_data = json.loads(recommendation.context_data)
        except json.JSONDecodeError:
            pass
    
    return render_template(
        'self-care/recommendation.html',
        recommendation=recommendation,
        context_data=context_data,
        page_title=f"Self-Care: {recommendation.title} | AI-BUDDY"
    )


@self_care_bp.route('/api/wellness-check-in', methods=['POST'])
@login_required
def api_wellness_check_in():
    """API endpoint for mobile wellness check-in submissions"""
    try:
        logger.info(f"[API WELLNESS] Mobile API wellness check-in request from user {current_user.id}")
        
        # Get JSON data from the request
        data = request.get_json()
        if not data:
            logger.error("[API WELLNESS] No JSON data received")
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        logger.info(f"[API WELLNESS] Received data keys: {list(data.keys())}")
        
        # Create wellness check-in record
        wellness_checkin = ManualWellnessCheckIn(
            user_id=current_user.id,
            energy_level=int(data.get('energy_level', 5)),
            physical_comfort=int(data.get('physical_comfort', 5)),
            stress_level=int(data.get('stress_level', 5)),
            mood=int(data.get('mood', 5)),
            focus=int(data.get('focus', 5)),
            notes=data.get('notes', '').strip()[:500]  # Limit notes length
        )
        
        db.session.add(wellness_checkin)
        db.session.commit()
        
        logger.info(f"[API WELLNESS] Successfully saved wellness check-in for user {current_user.id}")
        
        return jsonify({
            'status': 'success',
            'message': 'Wellness check-in saved successfully!'
        })
        
    except Exception as e:
        logger.error(f"[API WELLNESS] Error saving wellness check-in: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Error saving wellness check-in. Please try again.'
        }), 500

@self_care_bp.route('/wellness-check-in-api', methods=['POST'])
@login_required
def wellness_check_in_api():
    """JSON API endpoint for wellness check-ins - matches working water logging approach"""
    try:
        data = request.get_json()
        logger.info(f"Received wellness check-in API request with data: {data}")
        
        # Create new wellness check-in
        check_in = ManualWellnessCheckIn(
            user_id=current_user.id,
            energy_level=int(data.get('energy_level', 5)),
            physical_comfort=int(data.get('physical_comfort', 5)),
            sleep_quality=int(data.get('sleep_quality', 5)),
            breathing_quality=int(data.get('breathing_quality', 5)),
            physical_tension=int(data.get('physical_tension', 5)),
            stress_level=int(data.get('stress_level', 5)),
            mood=data.get('mood', 'neutral'),
            focus_level=int(data.get('focus_level', 5)),
            exercise_minutes=int(data.get('exercise_minutes', 0)) if data.get('exercise_minutes') else None,
            water_glasses=int(data.get('water_glasses', 0)) if data.get('water_glasses') else None,
            weather_condition=data.get('weather_condition', ''),
            location_type=data.get('location_type', ''),
            notes=data.get('notes', ''),
            recorded_at=datetime.now()
        )
        
        db.session.add(check_in)
        db.session.commit()
        
        logger.info(f"Successfully saved wellness check-in with ID: {check_in.id}")
        return jsonify({'success': True, 'message': 'Wellness check-in saved successfully'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving wellness check-in via API: {str(e)}")
        return jsonify({'success': False, 'message': 'Error saving check-in'}), 500



@self_care_bp.route('/wellness-check-in', methods=['GET', 'POST'])
@login_required
def wellness_check_in():
    """Interactive wellness check-in for manual data collection"""
    form = WellnessCheckInForm()
    
    if request.method == 'POST':
        try:
            # Add detailed logging for mobile debugging
            logger.info(f"[WELLNESS CHECK-IN] *** FORM SUBMISSION RECEIVED ***")
            logger.info(f"[WELLNESS CHECK-IN] Processing form submission from user {current_user.id}")
            logger.info(f"[WELLNESS CHECK-IN] Request method: {request.method}")
            logger.info(f"[WELLNESS CHECK-IN] Content type: {request.content_type}")
            logger.info(f"[WELLNESS CHECK-IN] Form data keys: {list(request.form.keys())}")
            logger.info(f"[WELLNESS CHECK-IN] User agent: {request.headers.get('User-Agent', 'Unknown')}")
            logger.info(f"[WELLNESS CHECK-IN] Remote address: {request.remote_addr}")
            print(f"[WELLNESS CHECK-IN] *** MOBILE FORM SUBMISSION RECEIVED FROM USER {current_user.id} ***")
            
            # SIMPLIFIED: Skip form validation entirely to avoid any issues with optional fields
            # Instead, process form fields directly from request.form
            
            # Set default values
            energy_level = 5
            physical_comfort = 5
            sleep_quality = 5
            breathing_quality = 5
            physical_tension = 5
            stress_level = 5
            focus_level = 5
            mood = request.form.get('mood', 'neutral')
            exercise_minutes = None
            water_glasses = None
            weather_condition = request.form.get('weather_condition', '')
            location_type = request.form.get('location_type', '')
            notes = request.form.get('notes', '')
            
            # Process each field with safe conversion
            # Energy level
            try:
                if request.form.get('energy_level'):
                    energy_level = int(request.form.get('energy_level'))
            except:
                pass
            
            # Physical comfort
            try:
                if request.form.get('physical_comfort'):
                    physical_comfort = int(request.form.get('physical_comfort'))
            except:
                pass
            
            # Sleep quality
            try:
                if request.form.get('sleep_quality'):
                    sleep_quality = int(request.form.get('sleep_quality'))
            except:
                pass
            
            # Breathing quality
            try:
                if request.form.get('breathing_quality'):
                    breathing_quality = int(request.form.get('breathing_quality'))
            except:
                pass
            
            # Physical tension
            try:
                if request.form.get('physical_tension'):
                    physical_tension = int(request.form.get('physical_tension'))
            except:
                pass
            
            # Stress level
            try:
                if request.form.get('stress_level'):
                    stress_level = int(request.form.get('stress_level'))
            except:
                pass
            
            # Focus level
            try:
                if request.form.get('focus_level'):
                    focus_level = int(request.form.get('focus_level'))
            except:
                pass
            
            # Exercise minutes (optional)
            try:
                if request.form.get('exercise_minutes'):
                    exercise_minutes = int(request.form.get('exercise_minutes'))
            except:
                pass
            
            # Water glasses (optional)
            try:
                if request.form.get('water_glasses'):
                    water_glasses = int(request.form.get('water_glasses'))
            except:
                pass
                
            # Create and save the wellness check-in with current timestamp
            from datetime import datetime, timezone
            check_in = ManualWellnessCheckIn(
                user_id=current_user.id,
                energy_level=energy_level,
                physical_comfort=physical_comfort,
                sleep_quality=sleep_quality,
                breathing_quality=breathing_quality,
                physical_tension=physical_tension,
                stress_level=stress_level,
                mood=mood,
                focus_level=focus_level,
                exercise_minutes=exercise_minutes,
                water_glasses=water_glasses,
                weather_condition=weather_condition,
                location_type=location_type,
                notes=notes,
                recorded_at=datetime.now(timezone.utc)  # Explicitly set current timestamp
            )
            
            db.session.add(check_in)
            db.session.commit()
            
            flash('Your wellness check-in has been recorded! Your recommendations are being updated in the background.', 'success')
            
            # Schedule recommendation generation to happen asynchronously
            # This prevents delays in the user interface
            from threading import Thread
            
            # Create a copy of the user ID for use in the background thread
            user_id = current_user.id
            
            def generate_recommendations_async():
                # Import Flask app directly from main module
                from main import app
                
                # Create an application context for the background thread
                with app.app_context():
                    try:
                        # Create database session specific to this thread
                        engine = RecommendationEngine(user_id)
                        recommendations = engine.generate_context_aware_recommendations(count=3)
                        logger.info(f"Asynchronously generated {len(recommendations)} recommendations for user {user_id}")
                    except Exception as e:
                        logger.error(f"Error generating recommendations asynchronously: {str(e)}")
            
            # Start the recommendation generation in a background thread
            Thread(target=generate_recommendations_async).start()
            
            # Redirect immediately, don't wait for recommendations
            return redirect(url_for('self_care.self_care_index'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving wellness check-in: {str(e)}")
            flash('There was an error saving your check-in. Please try again.', 'danger')
    
    # Get recent check-ins for this user - show more entries to include mobile submissions
    try:
        logger.info(f"Fetching recent check-ins for user_id: {current_user.id}")
        recent_check_ins = ManualWellnessCheckIn.query.filter_by(
            user_id=current_user.id
        ).order_by(desc(ManualWellnessCheckIn.created_at)).limit(15).all()
        logger.info(f"Found {len(recent_check_ins)} recent check-ins")
        for check_in in recent_check_ins:
            logger.info(f"Check-in: {check_in.id}, recorded_at: {check_in.recorded_at}, mood: {check_in.mood}")
    except Exception as e:
        logger.error(f"Error fetching recent check-ins: {str(e)}")
        recent_check_ins = []
    
    return render_template(
        'self-care/wellness_check_in.html',
        title="Wellness Check-In",
        recent_check_ins=recent_check_ins,
        form=form
    )


@self_care_bp.route('/api/wellness/check-in', methods=['POST'])
@login_required
def wellness_check_in_json_api():
    """JSON API endpoint for wellness check-in (mobile-friendly like stress logging)"""
    try:
        logger.info(f"[WELLNESS_API] *** JSON API SUBMISSION RECEIVED ***")
        logger.info(f"[WELLNESS_API] Processing JSON wellness check-in from user {current_user.id}")
        
        # Get JSON data (same pattern as working stress check-in)
        data = request.get_json()
        if not data:
            logger.error("[WELLNESS_API] No JSON data provided")
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
            
        logger.info(f"[WELLNESS_API] Received JSON data: {data}")
        
        # Extract values with defaults (same as form processing)
        energy_level = int(data.get('energy_level', 5))
        physical_comfort = int(data.get('physical_comfort', 5))
        sleep_quality = int(data.get('sleep_quality', 5))
        breathing_quality = int(data.get('breathing_quality', 5))
        physical_tension = int(data.get('physical_tension', 5))
        stress_level = int(data.get('stress_level', 5))
        focus_level = int(data.get('focus_level', 5))
        mood = data.get('mood', 'neutral')
        exercise_minutes = data.get('exercise_minutes')
        water_glasses = data.get('water_glasses')
        weather_condition = data.get('weather_condition', '')
        location_type = data.get('location_type', '')
        notes = data.get('notes', '')
        
        # Create wellness check-in record (same as form)
        check_in = ManualWellnessCheckIn(
            user_id=current_user.id,
            energy_level=energy_level,
            physical_comfort=physical_comfort,
            sleep_quality=sleep_quality,
            breathing_quality=breathing_quality,
            physical_tension=physical_tension,
            stress_level=stress_level,
            focus_level=focus_level,
            mood=mood,
            exercise_minutes=exercise_minutes,
            water_glasses=water_glasses,
            weather_condition=weather_condition,
            location_type=location_type,
            notes=notes,
            recorded_at=datetime.now(ZoneInfo("America/Chicago"))
        )
        
        try:
            db.session.add(check_in)
            db.session.commit()
            logger.info(f"[WELLNESS_API] Successfully saved JSON check-in (ID: {check_in.id})")
            
            return jsonify({
                'status': 'success',
                'message': 'Wellness check-in saved successfully',
                'check_in_id': check_in.id
            })
            
        except Exception as save_error:
            logger.error(f"[WELLNESS_API] Error saving JSON check-in: {str(save_error)}", exc_info=True)
            db.session.rollback()
            return jsonify({
                'status': 'error', 
                'message': 'Failed to save wellness check-in'
            }), 500
            
    except Exception as e:
        logger.error(f"[WELLNESS_API] JSON API Error: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@self_care_bp.route('/pwa/wellness-check-in', methods=['POST'])
@login_required
def pwa_wellness_check_in():
    """Special simplified endpoint just for PWA mode wellness check-ins"""
    import traceback
    
    logger.info(f"===== [PWA WELLNESS] NEW REQUEST START =====")
    logger.info(f"[PWA WELLNESS] Received wellness check-in from PWA for user {current_user.id}")
    
    try:
        # This endpoint uses form data rather than JSON to avoid SSL/JSON parsing errors
        # No CSRF validation for this special endpoint since we're in PWA mode already
        
        # Enhanced logging for troubleshooting
        logger.info(f"[PWA WELLNESS] Request method: {request.method}")
        logger.info(f"[PWA WELLNESS] Request content type: {request.content_type}")
        logger.info(f"[PWA WELLNESS] User agent: {request.headers.get('User-Agent', 'Unknown')}")
        logger.info(f"[PWA WELLNESS] Referrer: {request.referrer}")
        logger.info(f"[PWA WELLNESS] Content length: {request.headers.get('Content-Length', 'Unknown')}")
        
        # Attempt to log raw data for debugging
        try:
            raw_data = request.get_data(as_text=True)
            logger.info(f"[PWA WELLNESS] Raw request data (first 500 chars): {raw_data[:500]}")
        except Exception as e:
            logger.error(f"[PWA WELLNESS] Could not log raw data: {str(e)}")
        
        # Special handling for possible POST encoding issues
        if request.content_type and 'application/x-www-form-urlencoded' in request.content_type:
            logger.info("[PWA WELLNESS] Form data is application/x-www-form-urlencoded")
        elif request.content_type and 'multipart/form-data' in request.content_type:
            logger.info("[PWA WELLNESS] Form data is multipart/form-data")
        elif request.content_type and 'application/json' in request.content_type:
            logger.info("[PWA WELLNESS] Data appears to be JSON despite the endpoint")
            # Try to handle as JSON but continue with form processing as well
            try:
                json_data = request.get_json(silent=True)
                if json_data:
                    logger.info(f"[PWA WELLNESS] Successfully parsed JSON data")
                    
                    # Force into form-like structure
                    logger.info("[PWA WELLNESS] Converting JSON to form data format")
                    from werkzeug.datastructures import MultiDict
                    request.form = MultiDict(json_data)
                    logger.info(f"[PWA WELLNESS] Converted JSON to form data: {list(request.form.keys())}")
            except Exception as e:
                logger.error(f"[PWA WELLNESS] Error handling JSON data: {str(e)}")
        
        # Log all form fields for complete diagnostics 
        form_data = dict(request.form)
        if form_data:
            logger.info(f"[PWA WELLNESS] Form data keys: {list(form_data.keys())}")
            
            # Redact CSRF token for security but log its presence
            if 'csrf_token' in form_data:
                token_length = len(form_data['csrf_token'])
                logger.info(f"[PWA WELLNESS] CSRF token present (length: {token_length})")
                # Make a safe copy of form data for logging
                safe_form_data = {k: v if k != 'csrf_token' else '***REDACTED***' for k, v in form_data.items()}
                logger.info(f"[PWA WELLNESS] Form data: {safe_form_data}")
            else:
                logger.warning("[PWA WELLNESS] No CSRF token found in form data")
                logger.info(f"[PWA WELLNESS] Form data: {form_data}")
            
            # Check if is_pwa field is present and set correctly
            if 'is_pwa' in form_data:
                logger.info(f"[PWA WELLNESS] is_pwa field value: {form_data['is_pwa']}")
            else:
                # Add is_pwa field if missing since we know this is a PWA request
                logger.warning("[PWA WELLNESS] is_pwa field missing from form data - adding it")
                form_data['is_pwa'] = 'true'
                from werkzeug.datastructures import MultiDict
                request.form = MultiDict(form_data)
        else:
            logger.warning("[PWA WELLNESS] Form data is empty! Checking if data was sent as JSON...")
            
            # Check if data was mistakenly sent as JSON
            if request.is_json:
                logger.warning("[PWA WELLNESS] Data was sent as JSON instead of form data")
                
                try:
                    json_data = request.get_json(silent=True)
                    if json_data:
                        logger.info(f"[PWA WELLNESS] JSON data keys: {list(json_data.keys())}")
                        # Make a safe copy of JSON data for logging
                        safe_json_data = {k: v if k != 'csrf_token' else '***REDACTED***' for k, v in json_data.items()}
                        logger.info(f"[PWA WELLNESS] JSON data: {safe_json_data}")
                        
                        # Convert JSON to form data format
                        from werkzeug.datastructures import MultiDict
                        request.form = MultiDict(json_data)
                        logger.info(f"[PWA WELLNESS] Converted JSON to form data: {list(request.form.keys())}")
                        
                        # Ensure is_pwa is set
                        if 'is_pwa' not in json_data:
                            request.form.add('is_pwa', 'true')
                            logger.info("[PWA WELLNESS] Added is_pwa=true to form data")
                    else:
                        logger.error("[PWA WELLNESS] Failed to parse JSON data")
                        
                        # Create empty form data with minimal required fields
                        from werkzeug.datastructures import MultiDict
                        request.form = MultiDict({
                            'is_pwa': 'true',
                            'mood': 'neutral',
                            'notes': 'Created via PWA companion app with minimal data'
                        })
                        logger.info("[PWA WELLNESS] Created minimal form data due to parsing failure")
                except Exception as json_err:
                    logger.error(f"[PWA WELLNESS] Error parsing JSON: {str(json_err)}")
                    
                    # Create empty form data with minimal required fields as fallback
                    from werkzeug.datastructures import MultiDict
                    request.form = MultiDict({
                        'is_pwa': 'true',
                        'mood': 'neutral',
                        'notes': 'Created via PWA companion app (JSON parse error)'
                    })
                    logger.info("[PWA WELLNESS] Created minimal form data due to JSON error")
        
        # Set default values for all fields
        energy_level = 5
        physical_comfort = 5
        sleep_quality = 5
        breathing_quality = 5
        physical_tension = 5
        stress_level = 5
        focus_level = 5
        mood = request.form.get('mood', 'neutral')
        exercise_minutes = None
        water_glasses = None
        weather_condition = request.form.get('weather_condition', '')
        location_type = request.form.get('location_type', '')
        notes = request.form.get('notes', '')
        
        # Process each field individually with safe conversion
        # Energy level
        if request.form.get('energy_level'):
            try:
                energy_level = int(request.form.get('energy_level'))
            except:
                pass
        
        # Physical comfort
        if request.form.get('physical_comfort'):
            try:
                physical_comfort = int(request.form.get('physical_comfort'))
            except:
                pass
        
        # Sleep quality
        if request.form.get('sleep_quality'):
            try:
                sleep_quality = int(request.form.get('sleep_quality'))
            except:
                pass
        
        # Breathing quality
        if request.form.get('breathing_quality'):
            try:
                breathing_quality = int(request.form.get('breathing_quality'))
            except:
                pass
        
        # Physical tension
        if request.form.get('physical_tension'):
            try:
                physical_tension = int(request.form.get('physical_tension'))
            except:
                pass
        
        # Stress level
        if request.form.get('stress_level'):
            try:
                stress_level = int(request.form.get('stress_level'))
            except:
                pass
        
        # Focus level
        if request.form.get('focus_level'):
            try:
                focus_level = int(request.form.get('focus_level'))
            except:
                pass
        
        # Exercise minutes (optional)
        if request.form.get('exercise_minutes'):
            try:
                exercise_minutes = int(request.form.get('exercise_minutes'))
            except:
                pass
        
        # Water glasses (optional)
        if request.form.get('water_glasses'):
            try:
                water_glasses = int(request.form.get('water_glasses'))
            except:
                pass
                
        logger.info(f"[PWA WELLNESS] Processed values: energy={energy_level}, comfort={physical_comfort}, " + 
                   f"sleep={sleep_quality}, exercise={exercise_minutes}, water={water_glasses}")
        
        # Create and save the wellness check-in with additional debugging
        logger.info(f"[PWA WELLNESS] Creating check-in with values: user_id={current_user.id}, energy={energy_level}, comfort={physical_comfort}, sleep={sleep_quality}, breathing={breathing_quality}, tension={physical_tension}, stress={stress_level}, focus={focus_level}, mood={mood}, exercise={exercise_minutes}, water={water_glasses}")
        
        try:
            # Create the database object
            check_in = ManualWellnessCheckIn(
                user_id=current_user.id,
                energy_level=energy_level,
                physical_comfort=physical_comfort,
                sleep_quality=sleep_quality,
                breathing_quality=breathing_quality,
                physical_tension=physical_tension,
                stress_level=stress_level,
                mood=mood,
                focus_level=focus_level,
                exercise_minutes=exercise_minutes,
                water_glasses=water_glasses,
                weather_condition=weather_condition,
                location_type=location_type,
                notes=notes
            )
            
            # Add to session and flush to get ID (without committing yet)
            db.session.add(check_in)
            db.session.flush()
            logger.info(f"[PWA WELLNESS] Object created with ID: {check_in.id}")
            
            # Now commit to save permanently
            db.session.commit()
            logger.info(f"[PWA WELLNESS] Successfully saved check-in with ID: {check_in.id}")
            
            # Start recommendation generation in background
            from threading import Thread
            
            # Create a copy of the user ID for use in the background thread
            user_id = current_user.id
            
            def generate_recommendations_async():
                # Import Flask app directly from main module
                from main import app
                
                # Create an application context for the background thread
                with app.app_context():
                    try:
                        # Create database session specific to this thread
                        engine = RecommendationEngine(user_id)
                        recommendations = engine.generate_context_aware_recommendations(count=3)
                        logger.info(f"[PWA WELLNESS] Asynchronously generated {len(recommendations)} recommendations for user {user_id}")
                    except Exception as e:
                        logger.error(f"[PWA WELLNESS] Error generating recommendations asynchronously: {str(e)}")
            
            # Start the recommendation generation in a background thread
            Thread(target=generate_recommendations_async).start()
            
            # Redirect back to self-care index page on success
            return redirect(url_for('self_care.index'))
            
        except Exception as e:
            # Log detailed information about the error
            import traceback
            logger.error(f"[PWA WELLNESS] Database error while saving check-in: {str(e)}")
            logger.error(f"[PWA WELLNESS] Error traceback: {traceback.format_exc()}")
            
            # Roll back the transaction
            db.session.rollback()
            
            # Show error page with details
            return render_template(
                'self-care/wellness_check_in.html',
                title="Wellness Check-In Error",
                error_message=f"There was a database error saving your check-in: {str(e)}. Please try again."
            )
    
    except Exception as e:
        db.session.rollback()
        # Add detailed logging for troubleshooting
        import traceback
        logger.error(f"[PWA WELLNESS] Error saving check-in: {str(e)}")
        logger.error(f"[PWA WELLNESS] Traceback: {traceback.format_exc()}")
        
        return render_template(
            'self-care/wellness_check_in.html',
            title="Wellness Check-In",
            error_message="There was an error saving your check-in. Please try again."
        )
        
        # For mobile compatibility, skip CSRF validation for API requests
        # This allows both desktop and mobile submissions to work
        logger.info("[WELLNESS API] Skipping CSRF validation for mobile compatibility")
        
        # Check if the request is coming from a PWA
        is_pwa = request.json.get('is_pwa', False)
        logger.info(f"[WELLNESS API] Request from PWA: {is_pwa}")
        
        # Extract all the data directly from request.json
        data = request.json
        logger.info(f"[WELLNESS API] Processing data: {data}")
        
        # SIMPLIFIED: Just use the data directly for creating the check-in
        # Default values are set in the model itself
        energy_level = 5
        physical_comfort = 5
        sleep_quality = 5
        breathing_quality = 5
        physical_tension = 5
        stress_level = 5
        focus_level = 5
        mood = data.get('mood', 'neutral')
        exercise_minutes = None
        water_glasses = None
        
        # Safely convert string values to integers
        try:
            if data.get('energy_level') and data.get('energy_level').strip():
                energy_level = int(data.get('energy_level'))
        except:
            pass
            
        try:
            if data.get('physical_comfort') and data.get('physical_comfort').strip():
                physical_comfort = int(data.get('physical_comfort'))
        except:
            pass
            
        try:
            if data.get('sleep_quality') and data.get('sleep_quality').strip():
                sleep_quality = int(data.get('sleep_quality'))
        except:
            pass
            
        try:
            if data.get('breathing_quality') and data.get('breathing_quality').strip():
                breathing_quality = int(data.get('breathing_quality'))
        except:
            pass
            
        try:
            if data.get('physical_tension') and data.get('physical_tension').strip():
                physical_tension = int(data.get('physical_tension'))
        except:
            pass
            
        try:
            if data.get('stress_level') and data.get('stress_level').strip():
                stress_level = int(data.get('stress_level'))
        except:
            pass
            
        try:
            if data.get('focus_level') and data.get('focus_level').strip():
                focus_level = int(data.get('focus_level'))
        except:
            pass
            
        try:
            if data.get('exercise_minutes') and data.get('exercise_minutes').strip():
                exercise_minutes = int(data.get('exercise_minutes'))
        except:
            pass
            
        try:
            if data.get('water_glasses') and data.get('water_glasses').strip():
                water_glasses = int(data.get('water_glasses'))
        except:
            pass
        
        # Log detailed information about what we're trying to save
        logger.info(f"[WELLNESS API] Creating check-in with values: user_id={current_user.id}, energy={energy_level}, comfort={physical_comfort}, sleep={sleep_quality}, breathing={breathing_quality}, tension={physical_tension}, stress={stress_level}, focus={focus_level}, mood={mood}, exercise={exercise_minutes}, water={water_glasses}")
        
        # Create and save the wellness check-in with proper error handling
        try:
            check_in = ManualWellnessCheckIn(
                user_id=current_user.id,
                energy_level=energy_level,
                physical_comfort=physical_comfort,
                sleep_quality=sleep_quality,
                breathing_quality=breathing_quality,
                physical_tension=physical_tension,
                stress_level=stress_level,
                mood=data.get('mood', 'neutral'),
                focus_level=focus_level,
                exercise_minutes=exercise_minutes,
                water_glasses=water_glasses,
                weather_condition=data.get('weather_condition'),
                location_type=data.get('location_type'),
                notes=data.get('notes')
            )
            
            # Add to session and flush to get ID (without committing yet)
            db.session.add(check_in)
            db.session.flush()
            logger.info(f"[WELLNESS API] Object created with ID: {check_in.id}")
            
            # Now commit to save permanently
            db.session.commit()
            logger.info(f"[WELLNESS API] Successfully saved check-in to database with ID: {check_in.id}")
        except Exception as e:
            # Log detailed database error
            import traceback
            logger.error(f"[WELLNESS API] Database error while saving check-in: {str(e)}")
            logger.error(f"[WELLNESS API] Error traceback: {traceback.format_exc()}")
            db.session.rollback()
            raise  # Re-raise to be caught by outer exception handler
        
        # Start recommendation generation in background for API calls too
        from threading import Thread
        
        # Create a copy of the user ID for use in the background thread
        user_id = current_user.id
        
        def generate_api_recommendations_async():
            # Import Flask app directly from main module
            from main import app
            
            # Create an application context for the background thread
            with app.app_context():
                try:
                    # Create database session specific to this thread
                    engine = RecommendationEngine(user_id)
                    recommendations = engine.generate_context_aware_recommendations(count=3)
                    logger.info(f"Asynchronously generated {len(recommendations)} recommendations from API for user {user_id}")
                except Exception as e:
                    logger.error(f"Error generating recommendations asynchronously from API: {str(e)}")
        
        # Start the recommendation generation in a background thread
        Thread(target=generate_api_recommendations_async).start()
        
        return jsonify({
            'status': 'success',
            'message': 'Wellness check-in recorded successfully. Your recommendations are being updated.',
            'check_in_id': check_in.id
        })
        
    except Exception as e:
        db.session.rollback()
        # Add detailed debugging information
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"API Error saving wellness check-in: {str(e)}")
        logger.error(f"Detailed error trace: {error_details}")
        
        # For debugging, show more details about the request
        try:
            if request.is_json:
                raw_data = request.get_json()
                logger.error(f"Raw input data causing error: {raw_data}")
        except:
            pass
        
        return jsonify({
            'status': 'error',
            'message': 'There was an error saving your wellness check-in. Please try again or contact support.'
        }), 400


@self_care_bp.route('/api/wellness-check-in/history', methods=['GET'])
@login_required
def wellness_check_in_history_api():
    """API endpoint to get wellness check-in history"""
    try:
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 30, type=int)
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        check_ins = ManualWellnessCheckIn.query.filter(
            ManualWellnessCheckIn.user_id == current_user.id,
            ManualWellnessCheckIn.recorded_at >= cutoff_date
        ).order_by(desc(ManualWellnessCheckIn.recorded_at)).limit(limit).all()
        
        return jsonify({
            'status': 'success',
            'check_ins': [check_in.to_dict() for check_in in check_ins]
        })
        
    except Exception as e:
        logger.error(f"API Error retrieving wellness check-in history: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400