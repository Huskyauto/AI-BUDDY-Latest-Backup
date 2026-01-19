import os
import json
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, Mood, JournalEntry
from datetime import datetime, timedelta
import logging
from openai import OpenAI

dashboard_bp = Blueprint('dashboard', __name__)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def generate_mood_insights_with_ai(moods):
    """Generate AI-powered insights using gpt-4o-mini."""
    try:
        if not moods:
            return None

        # Format mood data for the AI
        mood_data = [{"mood": mood.mood, "timestamp": mood.timestamp.strftime('%H:%M'), "notes": mood.notes} 
                     for mood in moods]

        prompt = {
            "role": "system",
            "content": """You are an empathetic mental health assistant. Based on today's mood entries, 
            provide personalized insights and actionable suggestions. Format your response as JSON with 
            three sections: daily_tip (title, description, affirmation), immediate_actions (list), 
            and long_term_strategies (list). Keep suggestions practical and supportive."""
        }

        # Create the user message with mood data
        user_message = f"Here are today's mood entries: {str(mood_data)}. Please analyze these patterns and provide personalized insights."

        response = openai.chat.completions.create(
            model="gpt-4o-mini",  # Updated to use consistent model across app
            messages=[
                prompt,
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"}
        )

        # Parse the JSON response
        insights = json.loads(response.choices[0].message.content)

        # Convert long-term_strategies to long_term_strategies if needed
        if 'long-term_strategies' in insights:
            insights['long-term_strategies'] = insights.pop('long-term_strategies')

        # Validate the response format
        if not all(key in insights for key in ['daily_tip', 'immediate_actions', 'long-term_strategies']):
            logger.error("Invalid response format from OpenAI")
            return None

        logger.debug(f"Generated insights: {insights}")
        return insights

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding OpenAI response: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error generating AI insights: {str(e)}", exc_info=True)
        return None

@dashboard_bp.route('/dashboard')
@login_required
def index():
    try:
        # Get today's mood data
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        today_moods = Mood.query.filter(
            Mood.user_id == current_user.id,
            Mood.timestamp >= today_start,
            Mood.timestamp <= today_end
        ).order_by(Mood.timestamp.desc()).all()

        # Generate AI insights
        ai_generated_insights = generate_mood_insights_with_ai(today_moods)

        if ai_generated_insights:
            insights = ai_generated_insights
        else:
            # Fallback insights if AI generation fails
            insights = {
                'daily_tip': {
                    'title': 'Start Your Day with Mindfulness',
                    'description': 'Take a moment to check in with yourself and track your mood',
                    'affirmation': 'I am aware of my emotional well-being'
                },
                'immediate_actions': [
                    'Take a moment to reflect on how you feel',
                    'Record your first mood of the day',
                    'Practice deep breathing for 1 minute',
                    'Stay hydrated throughout the day'
                ],
                'long_term_strategies': [
                    'Build a daily mood tracking habit',
                    'Practice regular emotional check-ins',
                    'Develop a consistent mindfulness routine',
                    'Create a supportive daily schedule'
                ]
            }

        logger.debug(f"Generated insights: {insights}")  # Add debug logging

        # Get Google Maps API key from environment
        google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
        if not google_maps_api_key:
            logger.error("Google Maps API key not found in environment variables")

        return render_template('dashboard.html', 
                             insights=insights,
                             google_maps_api_key=google_maps_api_key)
    except Exception as e:
        logger.error(f"Error rendering dashboard: {str(e)}", exc_info=True)
        return render_template('dashboard.html', error="Unable to load insights")

@dashboard_bp.route('/api/save-mood', methods=['POST'])
@login_required
def save_mood():
    try:
        data = request.get_json()
        if not data:
            logger.error("No JSON data received in request")
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400

        mood_value = data.get('mood')
        notes = data.get('notes', '')

        if not mood_value:
            logger.error("No mood value provided in request")
            return jsonify({
                'status': 'error',
                'message': 'Mood is required'
            }), 400

        # Create new mood entry
        new_mood = Mood(
            user_id=current_user.id,
            mood=mood_value,
            notes=notes,
            timestamp=datetime.utcnow()
        )

        db.session.add(new_mood)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Mood saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving mood: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_mood_based_tip(mood):
    """Generate a personalized daily tip based on current mood."""
    tips = {
        'anxious': {
            'title': 'Finding Calm in the Storm',
            'description': 'Practice deep breathing exercises when feeling overwhelmed',
            'affirmation': 'I am safe and capable of handling this moment'
        },
        'stressed': {
            'title': 'Taking a Mindful Break',
            'description': 'Step away from work for a short relaxation pause',
            'affirmation': 'I choose peace over pressure'
        },
        'tired': {
            'title': 'Honoring Your Need for Rest',
            'description': 'Give yourself permission to take breaks and recharge',
            'affirmation': "I listen to my body's needs"
        },
        'neutral': {
            'title': 'Building Positive Momentum',
            'description': 'Set one small achievable goal for today',
            'affirmation': 'I am making progress at my own pace'
        },
        'uncertain': {
            'title': 'Embracing Uncertainty',
            'description': 'Focus on what you can control in this moment',
            'affirmation': 'I can handle whatever comes my way'
        },
        'frustrated': {
            'title': 'Finding Your Center',
            'description': 'Take a step back and reassess the situation',
            'affirmation': 'I can choose how to respond to challenges'
        }
    }

    return tips.get(mood, {
        'title': 'Nurturing Your Well-being',
        'description': 'Practice mindful awareness of your emotions',
        'affirmation': 'I am learning and growing each day'
    })

def get_mood_based_actions(mood, mood_count):
    """Generate immediate action items based on current mood."""
    actions = []

    if mood in ['anxious', 'stressed', 'frustrated']:
        actions.extend([
            'Take 3 deep, calming breaths',
            'Go for a short walk outside',
            'Write down what\'s troubling you'
        ])
    elif mood in ['tired', 'uncertain']:
        actions.extend([
            'Take a 5-minute break',
            'Drink a glass of water',
            'Do some gentle stretching'
        ])
    elif mood == 'neutral':
        actions.extend([
            "Write down three things you're grateful for",
            'Set one small goal for today',
            'Connect with someone supportive'
        ])

    # Add mood tracking suggestion if few entries today
    if mood_count < 3:
        actions.append('Check in with your mood again in a few hours')

    return actions[:4]  # Limit to 4 actions for better focus

def get_mood_based_strategies(mood, today_moods):
    """Generate long-term strategies based on mood patterns."""
    strategies = []

    if len(today_moods) >= 3:
        strategies.append('Continue regular mood tracking throughout the day')
    else:
        strategies.append('Build a habit of checking in with your emotions regularly')

    if mood in ['anxious', 'stressed', 'frustrated']:
        strategies.extend([
            'Develop a personal stress management toolkit',
            'Practice mindfulness meditation daily',
            'Consider scheduling regular exercise'
        ])
    elif mood in ['tired', 'uncertain']:
        strategies.extend([
            'Establish a consistent sleep schedule',
            'Create a morning routine for better energy',
            'Plan regular breaks in your day'
        ])
    else:
        strategies.extend([
            'Maintain your emotional awareness practice',
            'Build on positive coping strategies',
            'Set achievable weekly wellness goals'
        ])

    return strategies[:4]  # Limit to 4 strategies for focus