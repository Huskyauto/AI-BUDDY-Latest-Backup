from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
import logging
from models import db, StressLevel, get_local_time

logger = logging.getLogger(__name__)

stress_bp = Blueprint('stress', __name__)

@stress_bp.route('/stress-monitoring')
@login_required
def stress_monitoring():
    """Display stress monitoring dashboard"""
    try:
        if not current_user.can_view_ring_data():
            return render_template('unauthorized.html', 
                                   message=current_user.get_ring_access_message())

        return render_template('stress_monitoring.html')
    except Exception as e:
        logger.error(f"Error accessing stress monitoring: {e}", exc_info=True)
        return render_template('500.html'), 500

@stress_bp.route('/api/stress/log', methods=['POST'])
@login_required
def log_stress():
    """Log a new stress measurement"""
    try:
        data = request.get_json()

        # Create new stress log with local time
        stress_log = StressLevel(
            user_id=current_user.id,
            level=data.get('level'),
            symptoms=data.get('symptoms', []),
            notes=data.get('notes'),
            timestamp=get_local_time()  # Use local time instead of UTC
        )

        db.session.add(stress_log)
        db.session.commit()

        logger.info(f"Stress level logged for user {current_user.id}: {data.get('level')}")

        return jsonify({
            'status': 'success',
            'message': 'Stress level logged successfully',
            'timestamp': stress_log.timestamp.isoformat()
        })

    except Exception as e:
        logger.error(f"Error logging stress level: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@stress_bp.route('/api/stress/history')
@login_required
def get_stress_history():
    """Get stress level history for the current user"""
    try:
        # Get stress logs sorted by local timestamp
        stress_logs = StressLevel.query\
            .filter_by(user_id=current_user.id)\
            .order_by(StressLevel.timestamp.desc())\
            .all()

        return jsonify({
            'status': 'success',
            'history': [log.to_dict() for log in stress_logs]
        })

    except Exception as e:
        logger.error(f"Error retrieving stress history: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500