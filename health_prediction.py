from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
import logging
import os
import re
from gtts import gTTS
import tempfile
import threading
from pathlib import Path
from ai_client import generate_health_insight, get_health_chat_response

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

health_prediction_bp = Blueprint('health_prediction', __name__)

def clean_text_for_speech(text):
    """Clean text for speech synthesis by removing special characters and formatting"""
    # Remove markdown formatting
    text = re.sub(r'\*\*?(.*?)\*\*?', r'\1', text)

    # Simplify punctuation for flow
    text = re.sub(r'[!?]', '.', text)

    # Convert list items to flowing speech
    text = re.sub(r'^\s*[-•*]\s*', ', ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s*', ', ', text, flags=re.MULTILINE)

    # Paragraph structure optimization
    text = re.sub(r'\n{2,}', '. ', text)
    text = re.sub(r'\n', ' ', text)

    # Remove parenthetical content
    text = re.sub(r'\([^)]*\)', '', text)

    # Clean up double spaces and trailing/leading whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text

@health_prediction_bp.route('/api/text-to-speech', methods=['POST'])
@login_required
def text_to_speech():
    """Convert text to speech using Google Text-to-Speech with optimized settings"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "No text provided"}), 400

        # Clean the text for speech synthesis
        text = clean_text_for_speech(data['text'])

        # Create a temporary directory if it doesn't exist
        temp_dir = Path(tempfile.gettempdir()) / "health_prediction_audio"
        temp_dir.mkdir(exist_ok=True)

        # Generate a unique temporary file path
        temp_file = temp_dir / f"speech_{threading.get_ident()}.mp3"

        # Generate speech with optimized settings
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(str(temp_file))

        return send_file(
            str(temp_file),
            mimetype="audio/mpeg",
            as_attachment=True,
            download_name="response.mp3"
        )
    except Exception as e:
        logger.error(f"Error in text-to-speech conversion: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Failed to convert text to speech"
        }), 500

@health_prediction_bp.route('/health-prediction')
@login_required
def index():
    return render_template('health_prediction/index.html')

@health_prediction_bp.route('/api/health-chat', methods=['POST'])
@login_required
def chat():
    """Handle health prediction chat messages and generate responses."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        user_message = data.get('message')
        chat_history = data.get('history', [])

        if not user_message:
            return jsonify({"success": False, "error": "No message provided"}), 400

        # Log request details
        logger.debug(f"Processing health chat request - Message: {user_message}")
        logger.debug(f"Chat history length: {len(chat_history)}")

        try:
            # Use the new AI client to get the response
            ai_response = get_health_chat_response(user_message, chat_history)
            logger.debug("Successfully received response from GPT-4o-mini")

            return jsonify({
                "success": True,
                "response": ai_response
            })

        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"AI API error: {error_type} - {str(e)}")
            return jsonify({
                "success": False,
                "error": "Failed to get response from AI service"
            }), 500

    except Exception as e:
        logger.error(f"Error in health prediction chat: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred"
        }), 500