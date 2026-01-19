from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import ChatHistory, db
import logging
from datetime import datetime
import os
from openai import OpenAI

chat_bp = Blueprint('chat', __name__)
logger = logging.getLogger(__name__)

# Initialize OpenAI client with error handling
try:
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.error("OpenAI API key not found in environment variables")
        client = None
    else:
        client = OpenAI(api_key=api_key)
except Exception as e:
    logger.error(f"Error initializing OpenAI client: {str(e)}")
    client = None

WELCOME_MESSAGE = """Welcome to AI-BUDDY! 👋 I'm here to support your wellness journey. 
Feel free to share how you're feeling using the emotion selector above, and let me know how I can help you today. 
I can assist with:
• Emotional support and guidance
• Stress management techniques
• Meditation and mindfulness practices
• General wellness advice
What would you like to focus on?"""

def generate_ai_response(message: str, emotion: str = None) -> str:
    """Generate AI response using gpt-4o-mini."""
    try:
        logger.debug(f"Generating response for message: {message}, emotion: {emotion}")

        if not client:
            logger.error("OpenAI client not properly initialized")
            return "I apologize, but I'm not properly configured at the moment. Please try again in a few moments."

        # Create a context-aware system message
        emotion_context = f"The user is feeling {emotion}. " if emotion else ""
        system_message = (
            "You are an empathetic AI wellness assistant named AI-BUDDY. " +
            "Provide supportive, understanding responses that incorporate CBT principles. " +
            "Keep responses concise but caring. " + emotion_context +
            "Focus on emotional support and practical guidance."
        )

        try:
            # the newest OpenAI model is "gpt-4o-mini" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=150
            )

            if not response.choices:
                logger.error("No response choices received from OpenAI")
                return "I apologize, but I'm having trouble generating a response. Please try again."

            return response.choices[0].message.content.strip()

        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"OpenAI API error: {error_type} - {str(e)}")
            return "I apologize, but I'm having trouble connecting. Please try again in a moment."

    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}", exc_info=True)
        return "I apologize, but I'm having trouble processing your message. Please try again."

@chat_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """Handle chat messages and generate responses."""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'status': 'error',
                'message': 'No message provided'
            }), 400

        message = data.get('message', '').strip()
        emotion = data.get('emotion', 'neutral')

        if not message:
            return jsonify({
                'status': 'error',
                'message': 'Empty message'
            }), 400

        logger.debug(f"Processing chat request - Message: {message}, Emotion: {emotion}")

        # Generate AI response
        ai_response = generate_ai_response(message, emotion)

        # Create chat history entry
        chat_history = ChatHistory(
            user_id=current_user.id,
            message=message,
            response=ai_response,
            emotion=emotion,
            timestamp=datetime.utcnow()
        )

        try:
            db.session.add(chat_history)
            db.session.commit()
            logger.debug(f"Chat history saved - ID: {chat_history.id}")
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            db.session.rollback()
            # Continue with the response even if saving fails
            return jsonify({
                'status': 'success',
                'response': ai_response,
                'warning': 'Response generated but not saved to history'
            })

        return jsonify({
            'status': 'success',
            'response': ai_response
        })

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred. Please try again.'
        }), 500

@chat_bp.route('/history')
@login_required
def get_history():
    """Retrieve chat history for the current user."""
    try:
        logger.debug(f"Fetching chat history for user: {current_user.id}")
        history = ChatHistory.query.filter_by(user_id=current_user.id)\
            .order_by(ChatHistory.timestamp.desc())\
            .limit(6)\
            .all()

        return jsonify([{
            'message': h.message,
            'response': h.response,
            'timestamp': h.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'emotion': h.emotion
        } for h in history])

    except Exception as e:
        logger.error(f"Error fetching chat history: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch chat history'
        }), 500

@chat_bp.route('/')
def index():
    """Render the main chat interface."""
    if current_user.is_authenticated:
        # Create welcome message in chat history if user has no messages
        try:
            has_messages = ChatHistory.query.filter_by(user_id=current_user.id).first() is not None
            if not has_messages:
                welcome_history = ChatHistory(
                    user_id=current_user.id,
                    message="",
                    response=WELCOME_MESSAGE,
                    emotion="neutral",
                    timestamp=datetime.utcnow()
                )
                db.session.add(welcome_history)
                db.session.commit()
                logger.info(f"Welcome message created for user: {current_user.id}")
        except Exception as e:
            logger.error(f"Error creating welcome message: {str(e)}")

        return render_template('chat.html', username=current_user.username)
    return render_template('index.html')