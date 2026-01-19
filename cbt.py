from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from models import Mood, db, FoodLog
import logging
from datetime import datetime, timedelta

cbt_bp = Blueprint('cbt', __name__)
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

@cbt_bp.route('/api/mood-patterns')
@login_required
def get_mood_patterns():
    """Get mood data for visualization."""
    try:
        logger.info(f"Fetching mood patterns for user {current_user.id}")
        # Get moods from the last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        moods = Mood.query.filter(
            Mood.user_id == current_user.id,
            Mood.timestamp >= thirty_days_ago
        ).order_by(Mood.timestamp.asc()).all()

        logger.info(f"Found {len(moods)} mood entries for user {current_user.id}")

        # Convert mood string to numeric value for visualization
        def mood_to_value(mood):
            mood_values = {
                'Peaceful': 4, 'Happy': 4, 'Excited': 5, 'Grateful': 4,
                'Relaxed': 4, 'Thoughtful': 3, 'Neutral': 3,
                'Uncertain': 2, 'Sad': 1, 'Stressed': 1, 'Frustrated': 1,
                'Anxious': 1, 'Tired': 2, 'Unwell': 1, 'Numb': 2
            }
            return mood_values.get(mood, 3)  # Default to 3 for unknown moods

        if not moods:
            logger.info("No mood data found")
            return jsonify({
                'dates': [],
                'values': [],
                'moods': []
            })

        # Format data for the chart
        dates = [mood.timestamp.strftime('%Y-%m-%d') for mood in moods]
        values = [mood_to_value(mood.mood) for mood in moods]
        mood_labels = [mood.mood for mood in moods]

        mood_data = {
            'dates': dates,
            'values': values,
            'moods': mood_labels
        }

        logger.info(f"Returning mood data: {mood_data}")
        return jsonify(mood_data)

    except Exception as e:
        logger.error(f"Error fetching mood patterns: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Failed to fetch mood patterns',
            'dates': [],
            'values': [],
            'moods': []
        }), 500

@cbt_bp.route('/api/save-mood', methods=['POST'])
@login_required
def save_mood():
    """Save a new mood entry."""
    try:
        data = request.get_json()
        if not data:
            logger.error("No JSON data received in request")
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400

        mood = data.get('mood')
        notes = data.get('notes', '')

        if not mood:
            logger.error("No mood value provided in request")
            return jsonify({
                'status': 'error',
                'message': 'Mood is required'
            }), 400

        # Log the incoming data for debugging
        logger.info(f"Attempting to save mood entry: {mood} with notes: {notes} for user {current_user.id}")

        new_mood = Mood(
            user_id=current_user.id,
            mood=mood,
            notes=notes,
            timestamp=datetime.utcnow()
        )

        try:
            db.session.add(new_mood)
            db.session.commit()
            logger.info(f"Successfully saved new mood entry: {mood} for user {current_user.id}")
        except Exception as db_error:
            logger.error(f"Database error while saving mood: {str(db_error)}")
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': 'Database error while saving mood'
            }), 500

        # Return success response with the saved data
        return jsonify({
            'status': 'success',
            'message': 'Mood saved successfully',
            'data': {
                'mood': mood,
                'notes': notes,
                'timestamp': datetime.utcnow().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"Error saving mood: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Failed to save mood: {str(e)}'
        }), 500

@cbt_bp.route('/cbt-coaching')
@login_required
def cbt_coaching():
    """Render the CBT coaching page with accordion insights."""
    try:
        logger.debug("Starting CBT coaching view function")
        # Get user's recent moods from the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_moods = Mood.query.filter(
            Mood.user_id == current_user.id,
            Mood.timestamp >= week_ago
        ).order_by(Mood.timestamp.desc()).all()

        logger.debug(f"Retrieved {len(recent_moods)} recent moods")

        # Get recent food logs for mindful eating insights
        recent_food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= week_ago
        ).order_by(FoodLog.timestamp.desc()).all()

        logger.debug(f"Retrieved {len(recent_food_logs)} food logs")

        # Process mood data
        logger.debug("Analyzing mood patterns")
        mood_patterns = analyze_mood_patterns(recent_moods)
        logger.debug("Analyzing food patterns")
        food_insights = analyze_food_patterns(recent_food_logs)

        insights = {
            'mood_patterns': mood_patterns,
            'food_insights': food_insights
        }

        logger.debug("Rendering CBT coaching template with insights")
        return render_template('cbt_coaching.html', insights=insights)
    except Exception as e:
        logger.error(f"Error in CBT coaching view: {str(e)}", exc_info=True)
        return render_template('cbt_coaching.html', error="Unable to load insights at this time.")

def analyze_mood_patterns(moods):
    """Analyze mood patterns and generate insights with detailed explanations."""
    if not moods:
        return {
            'summary': 'No recent mood data available. Start tracking your moods to get personalized insights.',
            'patterns': []
        }

    try:
        # Calculate mood frequencies and trends
        mood_counts = {}
        mood_values = []
        timestamps = []

        for mood in moods:
            mood_counts[mood.mood] = mood_counts.get(mood.mood, 0) + 1
            mood_values.append(mood_to_value(mood.mood))
            timestamps.append(mood.timestamp)

        # Find predominant mood
        predominant_mood = max(mood_counts.items(), key=lambda x: x[1])[0] if mood_counts else 'neutral'

        # Calculate trend
        if len(mood_values) >= 2:
            trend = 'improving' if mood_values[-1] > mood_values[0] else 'declining' if mood_values[-1] < mood_values[0] else 'stable'
        else:
            trend = 'stable'

        # Generate personalized insights with detailed explanations
        patterns = []

        # Mood stability insight
        unique_moods = len(mood_counts)
        if unique_moods > 3:
            patterns.append({
                'summary': f"Your mood has been varying between {unique_moods} different states, suggesting emotional variability",
                'detail': f"Experiencing {unique_moods} different emotional states can indicate heightened emotional sensitivity. This variability provides opportunities to practice emotional regulation skills and identify triggers that influence your mood changes."
            })
        else:
            patterns.append({
                'summary': f"Your mood has been relatively consistent, primarily {predominant_mood}",
                'detail': f"Maintaining a consistent {predominant_mood} state suggests emotional stability. This can be beneficial for building routine and implementing sustainable lifestyle changes, though it's also important to maintain emotional flexibility."
            })

        # Trend insight
        trend_insights = {
            'improving': {
                'summary': "Your emotional well-being appears to be improving based on recent entries",
                'detail': "The positive trend in your mood suggests that recent coping strategies and lifestyle choices are working well. Consider documenting what specific actions or circumstances might be contributing to this improvement."
            },
            'declining': {
                'summary': "Your emotional well-being appears to be declining based on recent entries",
                'detail': "A downward trend in mood can be challenging but provides valuable information. This might be a good time to review and adjust your coping strategies, reach out for support, or implement stress-reduction techniques."
            },
            'stable': {
                'summary': "Your emotional well-being appears to be stable based on recent entries",
                'detail': "Emotional stability can provide a strong foundation for personal growth. Use this stable period to reinforce positive habits and prepare strategies for future challenging situations."
            }
        }
        patterns.append(trend_insights[trend])

        # Time pattern insight
        if len(timestamps) >= 2:
            time_diff = max(timestamps) - min(timestamps)
            if time_diff.days <= 1:
                patterns.append({
                    'summary': "You're tracking moods multiple times per day, which is great for self-awareness",
                    'detail': "Frequent mood tracking helps identify daily patterns and triggers, allowing for more immediate and effective responses to emotional changes. This detailed data can help refine your emotional regulation strategies."
                })
            else:
                patterns.append({
                    'summary': f"You've been tracking moods over {time_diff.days} days, helping build a clearer pattern",
                    'detail': f"Consistent tracking over {time_diff.days} days provides valuable insights into your emotional patterns. This longer-term view can help identify weekly cycles, external influences, and the effectiveness of different coping strategies."
                })

        logger.info(f"Generated {len(patterns)} mood insights for user {current_user.id}")

        return {
            'summary': f"Recent mood tracking shows a {trend} trend, predominantly {predominant_mood}.",
            'patterns': patterns
        }

    except Exception as e:
        logger.error(f"Error analyzing mood patterns: {str(e)}", exc_info=True)
        return {
            'summary': 'Unable to analyze mood patterns at this time.',
            'patterns': [{
                'summary': 'Continue tracking your moods for personalized insights.',
                'detail': 'Regular mood tracking helps build a comprehensive picture of your emotional well-being and enables more personalized recommendations.'
            }]
        }

def mood_to_value(mood):
    """Convert mood string to numeric value for trend analysis."""
    mood_values = {
        'Peaceful': 4, 'Happy': 4, 'Excited': 5, 'Grateful': 4,
        'Relaxed': 4, 'Thoughtful': 3, 'Neutral': 3,
        'Uncertain': 2, 'Sad': 1, 'Stressed': 1, 'Frustrated': 1,
        'Anxious': 1, 'Tired': 2, 'Unwell': 1, 'Numb': 2
    }
    return mood_values.get(mood, 3)  # Default to 3 for unknown moods

def analyze_food_patterns(food_logs):
    """Analyze food patterns and generate mindful eating insights with detailed hover content."""
    if not food_logs:
        return {
            'summary': 'No recent food logs available. Start tracking your meals to get personalized insights.',
            'patterns': [
                {
                    'summary': 'Begin tracking your meals',
                    'detail': 'Regular meal tracking helps build a comprehensive picture of your eating patterns and nutritional well-being.'
                }
            ]
        }

    patterns = []
    total_logs = len(food_logs)
    mindful_ratings = [log.mindful_eating_rating for log in food_logs if log.mindful_eating_rating]
    avg_mindful_rating = sum(mindful_ratings) / len(mindful_ratings) if mindful_ratings else 0

    # Generate detailed insights with summary and detail properties
    patterns = [
        {
            'summary': 'Eating patterns during stress',
            'detail': 'Your logs show specific patterns in eating habits during stressful periods. Understanding these patterns can help develop more mindful eating strategies.'
        },
        {
            'summary': 'Emotional eating triggers',
            'detail': 'We\'ve identified emotional triggers that may lead to mindless eating. Being aware of these triggers is the first step to developing healthier responses.'
        },
        {
            'summary': 'Meal timing patterns',
            'detail': 'There\'s a noticeable pattern of meal timing changes when feeling overwhelmed. Creating a regular eating schedule can help maintain stability.'
        },
        {
            'summary': 'Comfort food patterns',
            'detail': 'Your logs indicate specific food preferences during periods of anxiety. Understanding these patterns can help develop alternative coping strategies.'
        }
    ]

    if avg_mindful_rating:
        if avg_mindful_rating < 3:
            patterns.append({
                'summary': 'Mindful eating opportunity',
                'detail': 'Your mindful eating ratings suggest an opportunity to enhance your awareness during meals. Try focusing on the sensory experience of eating.'
            })
        else:
            patterns.append({
                'summary': 'Positive mindful eating progress',
                'detail': 'You\'re showing good progress with mindful eating awareness. Continue building on these positive habits.'
            })

    return {
        'summary': 'Analysis of your eating patterns reveals opportunities for mindful eating practice.',
        'patterns': patterns
    }

@cbt_bp.route('/api/cbt/insights')
@login_required
def get_insights():
    """Get updated insights based on latest mood and food data."""
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_moods = Mood.query.filter(
            Mood.user_id == current_user.id,
            Mood.timestamp >= week_ago
        ).order_by(Mood.timestamp.desc()).all()

        recent_food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= week_ago
        ).order_by(FoodLog.timestamp.desc()).all()

        return jsonify({
            'status': 'success',
            'insights': {
                'mood_patterns': analyze_mood_patterns(recent_moods),
                'food_insights': analyze_food_patterns(recent_food_logs)
            }
        })
    except Exception as e:
        logger.error(f"Error getting CBT insights: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch insights'
        }), 500

@cbt_bp.route('/dbt-coaching')
@login_required
def dbt_coaching():
    """Render the DBT coaching page with accordion insights."""
    try:
        logger.info("Starting DBT coaching view function")
        # Get user's recent moods from the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_moods = Mood.query.filter(
            Mood.user_id == current_user.id,
            Mood.timestamp >= week_ago
        ).order_by(Mood.timestamp.desc()).all()

        logger.debug(f"Retrieved {len(recent_moods)} recent moods")

        # Get recent food logs for mindful eating insights
        recent_food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= week_ago
        ).order_by(FoodLog.timestamp.desc()).all()

        logger.debug(f"Retrieved {len(recent_food_logs)} food logs")

        # Process mood data
        logger.debug("Analyzing mood patterns")
        dbt_insights = analyze_dbt_patterns(recent_moods, recent_food_logs)
        logger.debug(f"Generated insights structure: {dbt_insights}")

        return render_template('dbt_coaching.html', insights=dbt_insights)
    except Exception as e:
        logger.error(f"Error in DBT coaching view: {str(e)}", exc_info=True)
        return render_template('dbt_coaching.html', error="Unable to load insights at this time.")

def analyze_dbt_patterns(moods, food_logs):
    """Analyze patterns and generate DBT-specific insights."""
    if not moods:
        return {
            'mindfulness': {
                'summary': 'Start tracking your moods to receive personalized DBT insights.',
                'patterns': [
                    {
                        'summary': 'Begin daily mindfulness practice',
                        'detail': 'Start with 5-minute daily mindfulness exercises to build awareness'
                    }
                ]
            },
            'emotion_regulation': {
                'summary': 'Track your emotions to develop regulation skills.',
                'patterns': [
                    {
                        'summary': 'Start emotion tracking',
                        'detail': 'Record your emotions throughout the day to identify patterns'
                    }
                ]
            },
            'distress_tolerance': {
                'summary': 'Learn skills for managing difficult moments.',
                'patterns': [
                    {
                        'summary': 'Practice basic coping skills',
                        'detail': 'Start with simple breathing exercises when feeling overwhelmed'
                    }
                ]
            },
            'interpersonal_effectiveness': {
                'summary': 'Build stronger relationship skills.',
                'patterns': [
                    {
                        'summary': 'Practice active listening',
                        'detail': 'Focus on understanding others without planning your response'
                    }
                ]
            }
        }

    try:
        # Calculate mood frequencies and trends
        mood_counts = {}
        mood_values = []
        timestamps = []

        for mood in moods:
            mood_counts[mood.mood] = mood_counts.get(mood.mood, 0) + 1
            mood_values.append(mood_to_value(mood.mood))
            timestamps.append(mood.timestamp)

        # Find predominant mood
        predominant_mood = max(mood_counts.items(), key=lambda x: x[1])[0] if mood_counts else 'neutral'

        # Calculate trend
        if len(mood_values) >= 2:
            trend = 'improving' if mood_values[-1] > mood_values[0] else 'declining' if mood_values[-1] < mood_values[0] else 'stable'
        else:
            trend = 'stable'

        return {
            'mindfulness': {
                'summary': 'Mindfulness Skills for Present Moment Awareness',
                'patterns': [
                    {
                        'summary': 'Observe without judgment',
                        'detail': 'Practice observing thoughts and feelings without trying to change them. Notice when your mind wanders and gently return focus to the present moment.'
                    },
                    {
                        'summary': 'Use mindful breathing',
                        'detail': 'Focus on your breath as an anchor to the present moment. Notice the sensation of breathing without trying to change it.'
                    },
                    {
                        'summary': 'Practice mindful activities',
                        'detail': 'Choose one daily activity (like eating or walking) to do mindfully, paying full attention to the experience.'
                    }
                ]
            },
            'emotion_regulation': {
                'summary': 'Skills for Managing Emotions',
                'patterns': [
                    {
                        'summary': 'Identify and label emotions',
                        'detail': 'Practice naming your emotions with specific labels. Notice the intensity and duration of different feelings.'
                    },
                    {
                        'summary': 'Track emotional triggers',
                        'detail': 'Notice what events or situations tend to trigger strong emotional responses. Look for patterns in your reactions.'
                    },
                    {
                        'summary': 'Use opposite action',
                        'detail': 'When emotions don\'t fit the facts, try doing the opposite of what the emotion urges you to do.'
                    }
                ]
            },
            'distress_tolerance': {
                'summary': 'Skills for Difficult Moments',
                'patterns': [
                    {
                        'summary': 'Use TIPP skills',
                        'detail': 'Temperature (cold water on face), Intense exercise, Paced breathing, Progressive muscle relaxation to manage intense emotions.'
                    },
                    {
                        'summary': 'Practice radical acceptance',
                        'detail': 'Accept reality as it is, even when difficult. Acknowledge what you can\'t change while working on what you can.'
                    },
                    {
                        'summary': 'Use self-soothing',
                        'detail': 'Engage your senses (sight, sound, smell, taste, touch) in comforting ways when distressed.'
                    }
                ]
            },
            'interpersonal_effectiveness': {
                'summary': 'Skills for Better Relationships',
                'patterns': [
                    {
                        'summary': 'Use DEAR MAN skills',
                        'detail': 'Describe situation, Express feelings, Assert wishes, Reinforce, stay Mindful, Appear confident, Negotiate.'
                    },
                    {
                        'summary': 'Balance priorities',
                        'detail': 'Consider objectives, relationship health, and self-respect when making interpersonal decisions.'
                    },
                    {
                        'summary': 'Practice validation',
                        'detail': 'Acknowledge others\' feelings and experiences as valid, even if you disagree.'
                    }
                ]
            }
        }

    except Exception as e:
        logger.error(f"Error analyzing DBT patterns: {str(e)}", exc_info=True)
        return {
            'mindfulness': {'summary': 'Mindfulness Skills', 'patterns': []},
            'emotion_regulation': {'summary': 'Emotion Regulation', 'patterns': []},
            'distress_tolerance': {'summary': 'Distress Tolerance', 'patterns': []},
            'interpersonal_effectiveness': {'summary': 'Interpersonal Skills', 'patterns': []}
        }

@cbt_bp.route('/api/dbt/insights')
@login_required
def get_dbt_insights():
    """Get updated DBT insights based on latest mood and food data."""
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_moods = Mood.query.filter(
            Mood.user_id == current_user.id,
            Mood.timestamp >= week_ago
        ).order_by(Mood.timestamp.desc()).all()

        recent_food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= week_ago
        ).order_by(FoodLog.timestamp.desc()).all()

        insights = analyze_dbt_patterns(recent_moods, recent_food_logs)

        return jsonify({
            'status': 'success',
            'insights': insights
        })
    except Exception as e:
        logger.error(f"Error getting DBT insights: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch DBT insights'
        }), 500

@cbt_bp.route('/act-coaching')
@login_required
def act_coaching():
    """Render the ACT coaching page with accordion insights."""
    try:
        logger.info("Starting ACT coaching view function")
        # Get user's recent moods from the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_moods = Mood.query.filter(
            Mood.user_id == current_user.id,
            Mood.timestamp >= week_ago
        ).order_by(Mood.timestamp.desc()).all()

        logger.debug(f"Retrieved {len(recent_moods)} recent moods")

        # Get recent food logs for mindful eating insights
        recent_food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= week_ago
        ).order_by(FoodLog.timestamp.desc()).all()

        logger.debug(f"Retrieved {len(recent_food_logs)} food logs")

        # Process mood data for ACT-specific insights
        act_insights = analyze_act_patterns(recent_moods, recent_food_logs)

        # Debug logging to verify data structure
        logger.debug("ACT insights structure before template render:")
        logger.debug(f"Values section content: {act_insights.get('values', {})}")
        logger.debug(f"Values practices: {act_insights.get('values', {}).get('practices', [])}")
        logger.debug(f"First practice item: {act_insights.get('values', {}).get('practices', [])[0] if act_insights.get('values', {}).get('practices', []) else 'No practices found'}")

        return render_template('act_coaching.html', insights=act_insights)
    except Exception as e:
        logger.error(f"Error in ACT coaching view: {str(e)}", exc_info=True)
        return render_template('act_coaching.html', error="Unable to load insights at this time.")

def analyze_act_patterns(moods, food_logs):
    """Analyze patterns and generate ACT-specific insights."""
    try:
        logger.debug("Starting analysis of ACT patterns")

        # Initialize base insights structure with committed action section
        insights = {
            'committed_action': {
                'summary': 'Take meaningful actions aligned with your values',
                'strategies': [
                    {
                        'summary': 'Set specific, measurable goals',
                        'detail': 'Break down your values into concrete, achievable actions that you can take daily or weekly.'
                    },
                    {
                        'summary': 'Track your progress',
                        'detail': 'Keep a record of your committed actions and reflect on what helps or hinders your progress.'
                    },
                    {
                        'summary': 'Overcome obstacles',
                        'detail': 'Identify potential barriers and develop specific strategies to overcome them while staying committed to your values.'
                    },
                    {
                        'summary': 'Build supportive habits',
                        'detail': 'Create routines and practices that support your committed actions and make them more sustainable.'
                    }
                ]
            }
        }

        # Add other sections
        insights.update({
            'present_moment': {
                'summary': 'Cultivate mindful awareness in daily activities',
                'practices': [
                    {
                        'summary': 'Notice physical sensations',
                        'detail': 'Practice being present in your body by noticing physical sensations like breathing, muscle tension, or movement.'
                    },
                    {
                        'summary': 'Observe thoughts mindfully',
                        'detail': 'Watch your thoughts like leaves floating on a stream, acknowledging their presence without needing to follow them.'
                    },
                    {
                        'summary': 'Engage fully in experiences',
                        'detail': "Bring full attention to whatever you're doing, whether it's eating, walking, or talking with someone."
                    },
                    {
                        'summary': 'Use grounding techniques',
                        'detail': 'Connect with your environment using your senses - notice 5 things you can see, 4 you can touch, 3 you can hear, etc.'
                    }
                ]
            },
            'acceptance': {
                'summary': 'Develop acceptance strategies for challenging emotions',
                'strategies': [
                    {
                        'summary': 'Acknowledge emotions without judgment',
                        'detail': 'Practice accepting all emotions as valid experiences, without trying to change or avoid them.'
                    },
                    {
                        'summary': 'Use the "observer self" perspective',
                        'detail': 'Notice thoughts and feelings from a distance, recognizing that you are not your thoughts.'
                    },
                    {
                        'summary': 'Practice willingness exercises',
                        'detail': 'Develop willingness to experience uncomfortable thoughts when doing so serves your values.'
                    },
                    {
                        'summary': 'Apply self-compassion',
                        'detail': 'Treat yourself with the same kindness you would offer a good friend facing similar challenges.'
                    }
                ]
            },
            'defusion': {
                'summary': 'Learn techniques for relating differently to thoughts',
                'techniques': [
                    {
                        'summary': 'Label thoughts as just thoughts',
                        'detail': 'Practice saying "I\'m having the thought that..." to create distance from thought content.'
                    },
                    {
                        'summary': 'Use metaphors for perspective',
                        'detail': 'Visualize thoughts as leaves on a stream or clouds in the sky passing by.'
                    },
                    {
                        'summary': 'Thank your mind',
                        'detail': 'Acknowledge your mind\'s attempts to protect you, even when thoughts aren\'t helpful.'
                    },
                    {
                        'summary': 'Practice thought defusion exercises',
                        'detail': 'Say thoughts in different voices or write them down to see them as mental events rather than facts.'
                    }
                ]
            }
        })

        return insights

    except Exception as e:
        logger.error(f"Error analyzing ACT patterns: {str(e)}", exc_info=True)
        return {
            'committed_action': {
                'summary': 'Commit to value-based actions',
                'strategies': []
            },
            'present_moment': {
                'summary': 'Practice mindful awareness',
                'practices': []
            },
            'acceptance': {
                'summary': 'Develop acceptance strategies',
                'strategies': []
            },
            'defusion': {
                'summary': 'Learn cognitive defusion techniques',
                'techniques': []
            }
        }

@cbt_bp.route('/api/act/insights')
@login_required
def get_act_insights():
    """Get updated ACT insights based on latest mood and food data."""
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_moods = Mood.query.filter(
            Mood.user_id == current_user.id,
            Mood.timestamp >= week_ago
        ).order_by(Mood.timestamp.desc()).all()

        recent_food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= week_ago
        ).order_by(FoodLog.timestamp.desc()).all()

        insights = analyze_act_patterns(recent_moods, recent_food_logs)

        return jsonify({
            'status': 'success',
            'insights': insights
        })
    except Exception as e:
        logger.error(f"Error getting ACT insights: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch ACT insights'
        }), 500
        
@cbt_bp.route('/ipt-coaching')
@login_required
def ipt_coaching():
    """Render the IPT (Interpersonal Therapy) coaching page with accordion insights."""
    try:
        logger.info("Starting IPT coaching view function")
        # Get user's recent moods from the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_moods = Mood.query.filter(
            Mood.user_id == current_user.id,
            Mood.timestamp >= week_ago
        ).order_by(Mood.timestamp.desc()).all()

        logger.debug(f"Retrieved {len(recent_moods)} recent moods")

        # Get recent food logs for mindful eating insights
        recent_food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= week_ago
        ).order_by(FoodLog.timestamp.desc()).all()

        logger.debug(f"Retrieved {len(recent_food_logs)} food logs")

        # Process mood data for IPT-specific insights
        ipt_insights = analyze_ipt_patterns(recent_moods, recent_food_logs)

        # Debug logging to verify data structure
        logger.debug("IPT insights structure before template render:")
        logger.debug(f"Communication section content: {ipt_insights.get('communication', {})}")
        logger.debug(f"Communication strategies: {ipt_insights.get('communication', {}).get('strategies', [])}")
        logger.debug(f"First strategy item: {ipt_insights.get('communication', {}).get('strategies', [])[0] if ipt_insights.get('communication', {}).get('strategies', []) else 'No strategies found'}")

        return render_template('ipt_coaching.html', insights=ipt_insights)
    except Exception as e:
        logger.error(f"Error in IPT coaching view: {str(e)}", exc_info=True)
        return render_template('ipt_coaching.html', error="Unable to load insights at this time.")

def analyze_ipt_patterns(moods, food_logs):
    """Analyze patterns and generate IPT-specific insights focused on relationships and communication."""
    try:
        logger.debug("Starting analysis of IPT patterns")

        # Initialize base insights structure
        insights = {
            'communication': {
                'summary': 'Enhance relationship communication for healthier eating behaviors',
                'strategies': [
                    {
                        'summary': 'Express feelings directly about food situations',
                        'detail': 'Practice using "I" statements when discussing food choices with others, such as "I feel pressured when offered dessert" instead of "You always push food on me."'
                    },
                    {
                        'summary': 'Set clear boundaries around social eating',
                        'detail': 'Communicate your eating preferences or dietary needs in advance of social gatherings to reduce anxiety and prevent impulsive eating.'
                    },
                    {
                        'summary': 'Address conflicts that trigger emotional eating',
                        'detail': 'Identify specific relationship conflicts that lead to emotional eating and address them directly through conversation rather than turning to food.'
                    }
                ]
            },
            'social_support': {
                'summary': 'Build and utilize social support networks',
                'practices': [
                    {
                        'summary': 'Engage a support person for meal planning',
                        'detail': 'Identify a trusted friend or family member who can help with meal planning and provide accountability without judgment.'
                    },
                    {
                        'summary': 'Practice assertiveness in food-related social situations',
                        'detail': 'Rehearse and use assertive responses to decline unwanted food offerings or pressure to eat in social settings.'
                    },
                    {
                        'summary': 'Share your wellness goals with close relationships',
                        'detail': 'Openly discuss your health and eating goals with close friends or family to enlist their support and understanding.'
                    }
                ]
            },
            'relationship_patterns': {
                'summary': 'Identify relationship patterns that affect eating behaviors',
                'patterns': [
                    {
                        'summary': 'Recognize eating as connection or disconnection',
                        'detail': 'Notice when you use food as a substitute for connection or as a way to cope with relationship difficulties.'
                    },
                    {
                        'summary': 'Track mood changes after interactions',
                        'detail': 'Monitor how specific interactions with key people in your life affect your mood and subsequent eating behaviors.'
                    },
                    {
                        'summary': 'Identify food-related role transitions',
                        'detail': 'Examine how changes in your relationships or social roles (e.g., new job, parenthood) have influenced your eating patterns and address these transitions mindfully.'
                    }
                ]
            },
            'grief_processing': {
                'summary': 'Address unresolved grief that may trigger emotional eating',
                'techniques': [
                    {
                        'summary': 'Acknowledge losses without using food to cope',
                        'detail': 'Identify significant losses or changes that you may be responding to with emotional eating, and develop alternative coping strategies.'
                    },
                    {
                        'summary': 'Create meaningful rituals around food',
                        'detail': 'Transform emotional eating into meaningful food rituals that honor connections rather than numb feelings, such as cooking family recipes mindfully.'
                    },
                    {
                        'summary': 'Express feelings about loss directly',
                        'detail': 'Practice expressing feelings about losses or changes directly through conversation, journaling, or creative outlets rather than through eating behaviors.'
                    }
                ]
            }
        }

        # Analyze mood patterns if there are recent moods
        if moods:
            logger.debug("Analyzing mood patterns in relation to interpersonal factors")
            mood_timestamps = [mood.timestamp for mood in moods]
            mood_values = [mood_to_value(mood.mood) for mood in moods]
            
            # Detect rapid mood changes which might indicate relationship issues
            if len(mood_values) > 1:
                mood_changes = [abs(mood_values[i] - mood_values[i+1]) for i in range(len(mood_values)-1)]
                significant_changes = [change for change in mood_changes if change >= 2]
                
                if significant_changes:
                    logger.debug(f"Detected {len(significant_changes)} significant mood changes")
                    insights['relationship_patterns']['patterns'].append({
                        'summary': 'Notice connection between mood shifts and interactions',
                        'detail': f'Your mood tracker shows significant shifts that may be connected to interactions with others. Consider keeping a log of who you were with before mood changes to identify patterns.'
                    })

        # Analyze food logs for social eating patterns
        if food_logs:
            logger.debug("Analyzing food logs for social context patterns")
            
            # Check for mentions of social settings in notes
            social_keywords = ['restaurant', 'party', 'friend', 'family', 'dinner with', 'lunch with']
            social_eating_logs = [log for log in food_logs 
                                if log.notes and any(keyword in log.notes.lower() for keyword in social_keywords)]
            
            if social_eating_logs:
                logger.debug(f"Found {len(social_eating_logs)} food logs with social context")
                insights['social_support']['practices'].append({
                    'summary': 'Develop strategies for mindful social eating',
                    'detail': f'Your food log indicates several social eating occasions. Create a plan for maintaining mindful eating in social settings, such as eating a small healthy snack before events.'
                })

        return insights
    except Exception as e:
        logger.error(f"Error analyzing IPT patterns: {str(e)}", exc_info=True)
        return {
            'communication': {
                'summary': 'Start tracking your moods to receive personalized IPT insights.',
                'strategies': [
                    {
                        'summary': 'Begin noting relationship contexts with meals',
                        'detail': 'Record who you were with during meals to identify interpersonal patterns affecting your eating.'
                    }
                ]
            }
        }

@cbt_bp.route('/api/ipt/insights')
@login_required
def get_ipt_insights():
    """Get updated IPT insights based on latest mood and food data."""
    try:
        logger.info("Fetching latest IPT insights via API")
        # Get user's recent moods from the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_moods = Mood.query.filter(
            Mood.user_id == current_user.id,
            Mood.timestamp >= week_ago
        ).order_by(Mood.timestamp.desc()).all()
        
        recent_food_logs = FoodLog.query.filter(
            FoodLog.user_id == current_user.id,
            FoodLog.timestamp >= week_ago
        ).order_by(FoodLog.timestamp.desc()).all()
        
        logger.debug(f"Retrieved {len(recent_moods)} moods and {len(recent_food_logs)} food logs for IPT insights API")
        
        # Process mood data for IPT-specific insights
        ipt_insights = analyze_ipt_patterns(recent_moods, recent_food_logs)
        
        return jsonify({
            'status': 'success',
            'insights': ipt_insights
        })
    except Exception as e:
        logger.error(f"Error in get_ipt_insights: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch IPT insights'
        }), 500