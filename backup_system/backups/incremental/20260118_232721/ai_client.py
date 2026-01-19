import os
import json
import logging
import time
from flask import current_app
from flask_login import current_user
from models import APIUsageLog
from extensions import db

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize OpenAI client (optional)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# the newest OpenAI model is "gpt-4o-mini" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL_NAME = "gpt-4o-mini"

# Initialize client only if API key is available
client = None
if OPENAI_API_KEY:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    logger.warning("OPENAI_API_KEY environment variable is not set! AI features will be disabled.")

def log_api_call(api_name, endpoint, response_time, success=True, status_code=200):
    """Log API call to the database for tracking."""
    try:
        # Determine user_id (use 1 as fallback for admin if no user context)
        user_id = current_user.id if hasattr(current_user, 'id') and not current_user.is_anonymous else 1
        
        logger.info(f"Creating API log entry for {api_name} with user_id={user_id}")
        
        # Create API usage log entry
        log_entry = APIUsageLog()
        log_entry.api_name = api_name
        log_entry.endpoint = endpoint
        log_entry.user_id = user_id
        log_entry.response_time = response_time
        log_entry.success = success
        log_entry.status_code = status_code
        
        # Add to database
        logger.info(f"Adding API log to session: {api_name}, {endpoint}, response_time={response_time:.2f}s")
        db.session.add(log_entry)
        
        try:
            db.session.commit()
            logger.info(f"API call logged successfully: {api_name} - {endpoint} ({response_time:.2f}s)")
        except Exception as commit_error:
            logger.error(f"Failed to commit API log to database: {str(commit_error)}")
            db.session.rollback()
            # Try creating a new session and retrying once more
            try:
                logger.info("Attempting to use a fresh session for logging API call")
                from app import app
                with app.app_context():
                    new_log_entry = APIUsageLog(
                        api_name=api_name,
                        endpoint=endpoint,
                        user_id=user_id,
                        response_time=response_time,
                        success=success,
                        status_code=status_code
                    )
                    db.session.add(new_log_entry)
                    db.session.commit()
                    logger.info(f"API call logged successfully with fresh session: {api_name}")
            except Exception as retry_error:
                logger.error(f"Failed to log API call even with fresh session: {str(retry_error)}")
        
        return True
    except Exception as e:
        logger.error(f"Error logging API call: {str(e)}", exc_info=True)
        # Don't block the application flow if logging fails
        try:
            if db.session.is_active:
                db.session.rollback()
        except:
            pass
        return False

def generate_health_insight(prompt, response_format="text"):
    """
    Generate health insights using gpt-4o-mini model.

    Args:
        prompt (str): The input prompt for generating insights
        response_format (str): Either "text" or "json"

    Returns:
        dict or str: The generated insight
    """
    # Handle case when API key is not available
    if not client:
        error_message = "OpenAI API key not configured"
        logger.warning(f"Cannot generate health insight: {error_message}")
        if response_format == "json":
            return {"error": error_message, "message": "Please configure OpenAI API key to use AI features"}
        return f"AI features are disabled. {error_message}. Please contact the administrator to setup the OpenAI API key."
    
    try:
        messages = [
            {
                "role": "system", 
                "content": "You are an AI health assistant providing evidence-based wellness insights. Format your response in clear sections without using markdown symbols or hashtags. Present your insights in a conversational, easy-to-read format."
            },
            {"role": "user", "content": prompt}
        ]

        kwargs = {
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500
        }

        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        # Start timer for API call
        start_time = time.time()
        success = True
        status_code = 200
        
        try:
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
        except Exception as e:
            success = False
            status_code = getattr(e, 'status_code', 500)
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise
        finally:
            # Calculate response time
            response_time = time.time() - start_time
            
            # Log the API call
            log_api_call(
                api_name="OpenAI",
                endpoint=f"chat/{MODEL_NAME}",
                response_time=response_time,
                success=success,
                status_code=status_code
            )
        
        if response_format == "json":
            return json.loads(content)
        return content

    except Exception as e:
        logger.error(f"Error generating health insight: {e}")
        if response_format == "json":
            return {"error": str(e), "message": "Error generating health insight"}
        return f"An error occurred while generating health insights: {str(e)}"

def analyze_wellness_data(data):
    """
    Analyze wellness data and provide personalized recommendations.

    Args:
        data (dict): Dictionary containing wellness metrics

    Returns:
        dict: Analysis results and recommendations
    """
    try:
        prompt = f"""Analyze the following wellness data and provide actionable recommendations.
        Present your analysis in clear sections without using markdown symbols:

        Data to analyze:
        {json.dumps(data, indent=2)}

        Respond in JSON format with the following structure:
        {{
            "analysis": {{"key_findings": [], "risk_factors": []}},
            "recommendations": [],
            "priority_actions": []
        }}
        """

        return generate_health_insight(prompt, response_format="json")

    except Exception as e:
        logger.error(f"Error analyzing wellness data: {e}")
        raise

def generate_mindful_eating_suggestions(context):
    """
    Generate contextual mindful eating suggestions.

    Args:
        context (dict): Dictionary containing relevant context (location, time, etc.)

    Returns:
        list: List of personalized suggestions
    """
    try:
        prompt = f"""Given the following context, provide personalized mindful eating suggestions.
        Present your suggestions in a clear, readable format without markdown symbols or section headers:

        Context:
        {json.dumps(context, indent=2)}

        Respond in JSON format with an array of suggestions.
        """

        response = generate_health_insight(prompt, response_format="json")
        return response.get("suggestions", [])

    except Exception as e:
        logger.error(f"Error generating mindful eating suggestions: {e}")
        raise

def get_health_chat_response(user_message, chat_history=None):
    """
    Generate a response for the health chat interface.

    Args:
        user_message (str): The user's message
        chat_history (list): Optional list of previous messages

    Returns:
        str: Generated response
    """
    try:
        messages = [
            {
                "role": "system",
                "content": "You are a knowledgeable health assistant providing evidence-based "
                          "information and support. Be empathetic and encouraging while "
                          "maintaining professionalism. Present your responses in clear, "
                          "readable paragraphs without using markdown symbols or section headers."
            }
        ]

        if chat_history:
            messages.extend(chat_history)

        messages.append({"role": "user", "content": user_message})

        return generate_health_insight("\n".join([m["content"] for m in messages]))

    except Exception as e:
        logger.error(f"Error generating chat response: {e}")
        raise

def analyze_health_patterns(data):
    """
    Analyze health patterns and provide insights.

    Args:
        data (dict): Dictionary containing health metrics and patterns

    Returns:
        dict: Analysis and recommendations
    """
    try:
        prompt = f"""Analyze the following health patterns and provide insights.
        Present your analysis in clear sections without using markdown symbols:

        Data to analyze:
        {json.dumps(data, indent=2)}

        Respond in JSON format with:
        {{
            "patterns_identified": [],
            "potential_correlations": [],
            "suggested_improvements": [],
            "lifestyle_recommendations": []
        }}
        """

        return generate_health_insight(prompt, response_format="json")

    except Exception as e:
        logger.error(f"Error analyzing health patterns: {e}")
        raise