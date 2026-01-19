import logging
import sqlalchemy
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from models import (
    db, FastingProgram, FastingSession, FastingCheckIn,
    get_local_time, format_timestamp
)

logger = logging.getLogger(__name__)
fasting_bp = Blueprint('fasting', __name__)

@fasting_bp.route('/api/fasting/programs')
@login_required
def get_fasting_programs():
    """Get list of available extended fasting programs"""
    try:
        # Only get extended fasting programs
        programs = FastingProgram.query.filter_by(type='extended').all()

        logger.info(f"[FASTING] Found {len(programs)} extended fasting programs")

        program_list = [{
            'id': p.id,
            'name': p.name,
            'duration_days': p.duration_days,
            'description': p.description,
            'benefits': p.benefits,
            'instructions': p.instructions
        } for p in programs]

        logger.info(f"[FASTING] Returning programs: {[p['name'] for p in program_list]}")

        return jsonify({
            'status': 'success',
            'programs': program_list
        })
    except Exception as e:
        logger.error(f"[FASTING] Error fetching fasting programs: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
@fasting_bp.route('/api/fasting/intermittent/programs')
@login_required
def get_intermittent_fasting_programs():
    """Get list of available intermittent fasting programs"""
    try:
        # Only get intermittent fasting programs
        programs = FastingProgram.query.filter_by(type='intermittent').all()

        logger.info(f"[FASTING] Found {len(programs)} intermittent fasting programs")

        program_list = [{
            'id': p.id,
            'name': p.name,
            'duration_hours': int(p.name.split('-')[0]),  # Extract hours from name (e.g., "16-Hour Fast")
            'description': p.description,
            'benefits': p.benefits,
            'instructions': p.instructions
        } for p in programs]

        logger.info(f"[FASTING] Returning intermittent programs: {[p['name'] for p in program_list]}")

        return jsonify({
            'status': 'success',
            'programs': program_list
        })
    except Exception as e:
        logger.error(f"[FASTING] Error fetching intermittent fasting programs: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
@fasting_bp.route('/api/fasting/intermittent/start', methods=['POST'])
@login_required
def start_intermittent_fasting():
    """Start a new intermittent fasting session"""
    try:
        data = request.get_json()
        logger.info(f"[FASTING] Received request to start intermittent fasting session with data: {data}")

        if not data or 'program_id' not in data:
            logger.error("[FASTING] Missing program_id in request")
            return jsonify({'status': 'error', 'message': 'Program ID required'}), 400

        # Get the program and verify it exists
        program = FastingProgram.query.get(data['program_id'])
        if not program:
            logger.error(f"[FASTING] Invalid program ID: {data['program_id']}")
            return jsonify({'status': 'error', 'message': 'Invalid program ID'}), 404
            
        # Verify it's an intermittent fasting program
        if program.type != 'intermittent':
            logger.error(f"[FASTING] Not an intermittent fasting program: {program.type}")
            return jsonify({'status': 'error', 'message': 'Not an intermittent fasting program'}), 400

        # Cancel any existing active intermittent fasting sessions
        active_sessions = FastingSession.query.join(FastingProgram).filter(
            FastingSession.user_id == current_user.id,
            FastingSession.status == 'active',
            FastingProgram.type == 'intermittent'
        ).all()

        current_time = get_local_time()
        for session in active_sessions:
            session.status = 'cancelled'
            session.end_date = current_time
            logger.info(f"[FASTING] Cancelled existing intermittent session {session.id}")

        # Create new session with explicit program relationship and start time
        new_session = FastingSession(
            user_id=current_user.id,
            program_id=program.id,
            start_date=current_time,
            status='active'
        )

        db.session.add(new_session)

        try:
            db.session.commit()
            logger.info(f"[FASTING] Started new intermittent fasting session {new_session.id} with program {program.name}")
        except Exception as e:
            logger.error(f"[FASTING] Database error while creating session: {e}")
            db.session.rollback()
            raise

        # Get duration in hours
        duration_hours = int(program.name.split('-')[0])
        
        # Calculate end time
        end_time = current_time + timedelta(hours=duration_hours)

        return jsonify({
            'status': 'success',
            'session_id': new_session.id,
            'message': 'Intermittent fasting session started successfully',
            'program': {
                'name': program.name,
                'duration_hours': duration_hours,
                'start_time': current_time.isoformat(),
                'end_time': end_time.isoformat(),
                'description': program.description,
                'benefits': program.benefits,
                'instructions': program.instructions
            }
        })

    except Exception as e:
        logger.error(f"[FASTING] Error starting intermittent fasting session: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@fasting_bp.route('/api/fasting/start', methods=['POST'])
@login_required
def start_fasting_session():
    """Start a new extended fasting session"""
    try:
        data = request.get_json()
        logger.info(f"[FASTING] Received request to start fasting session with data: {data}")

        if not data or 'program_id' not in data:
            logger.error("[FASTING] Missing program_id in request")
            return jsonify({'status': 'error', 'message': 'Program ID required'}), 400

        # Get the program and verify it exists
        program = FastingProgram.query.get(data['program_id'])
        if not program:
            logger.error(f"[FASTING] Invalid program ID: {data['program_id']}")
            return jsonify({'status': 'error', 'message': 'Invalid program ID'}), 404
            
        # Verify it's an extended fasting program
        if program.type != 'extended':
            logger.error(f"[FASTING] Not an extended fasting program: {program.type}")
            return jsonify({'status': 'error', 'message': 'Not an extended fasting program'}), 400

        # Cancel any existing active sessions
        active_sessions = FastingSession.query.join(FastingProgram).filter(
            FastingSession.user_id == current_user.id,
            FastingSession.status == 'active',
            FastingProgram.type == 'extended'
        ).all()

        current_time = get_local_time()
        for session in active_sessions:
            session.status = 'cancelled'
            session.end_date = current_time
            logger.info(f"[FASTING] Cancelled existing session {session.id}")

        # Create new session with explicit program relationship and start time
        new_session = FastingSession(
            user_id=current_user.id,
            program_id=program.id,
            start_date=current_time,
            status='active'
        )

        db.session.add(new_session)

        try:
            db.session.commit()
            logger.info(f"[FASTING] Started new fasting session {new_session.id} with program {program.name}")
        except Exception as e:
            logger.error(f"[FASTING] Database error while creating session: {e}")
            db.session.rollback()
            raise

        return jsonify({
            'status': 'success',
            'session_id': new_session.id,
            'message': 'Extended fasting session started successfully',
            'program': {
                'name': program.name,
                'duration_days': program.duration_days,
                'current_day': 1,  # Always start at day 1
                'total_days': program.duration_days,
                'display_day': f"Day 1 of {program.duration_days}"
            }
        })

    except Exception as e:
        logger.error(f"[FASTING] Error starting fasting session: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@fasting_bp.route('/api/fasting/active')
@login_required
def get_active_session():
    """Get the current active extended fasting session with program details and check-ins"""
    try:
        logger.info(f"[FASTING] Checking active extended fasting session for user {current_user.id}")

        # Get active extended fasting session with program details
        session = FastingSession.query\
            .join(FastingProgram)\
            .filter(
                FastingSession.user_id == current_user.id,
                FastingSession.status == 'active',
                FastingProgram.type == 'extended'
            ).first()

        if not session:
            logger.info(f"[FASTING] No active extended fasting session found for user {current_user.id}")
            return jsonify({
                'status': 'success',
                'has_active_session': False
            })

        # Verify program association
        program = session.program
        if not program:
            logger.error(f"[FASTING] No program found for session {session.id}")
            return jsonify({'status': 'error', 'message': 'Program not found'}), 500

        # Get check-ins for this session
        check_ins = FastingCheckIn.query\
            .filter_by(session_id=session.id)\
            .order_by(FastingCheckIn.day_number)\
            .all()

        # Get current day using the improved calculation logic
        current_day = session.get_current_day()
        total_days = program.duration_days
        display_day = f"Day {current_day} of {total_days}"
        
        # Check if the current day has a check-in
        todays_checkin = None
        checkin_done_today = False
        
        for ci in check_ins:
            if ci.day_number == current_day:
                todays_checkin = ci
                checkin_done_today = True
                break
        
        logger.info(f"[FASTING] Returning active extended fasting session {session.id}: {display_day}, check-in done: {checkin_done_today}")
        
        return jsonify({
            'status': 'success',
            'has_active_session': True,
            'checkin_today': checkin_done_today,  # Add this flag to indicate if today's check-in is done
            'session': {
                'id': session.id,
                'start_time': session.start_date.isoformat() if session.start_date else None,
                'program': {
                    'name': program.name,
                    'duration_days': total_days,
                    'description': program.description,
                    'benefits': program.benefits,
                    'instructions': program.instructions
                },
                'current_day': current_day,
                'total_days': total_days,
                'display_day': display_day,
                'check_ins': [{
                    'day_number': ci.day_number,
                    'mood': ci.mood,
                    'energy_level': ci.energy_level,
                    'weight': ci.weight,
                    'symptoms': ci.symptoms,
                    'notes': ci.notes,
                    'check_in_time': ci.check_in_time.isoformat() if ci.check_in_time else None
                } for ci in check_ins]
            }
        })
        
    except Exception as e:
        logger.error(f"[FASTING] Error fetching active extended fasting session: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500
@fasting_bp.route('/api/fasting/intermittent/active')
@login_required
def get_active_intermittent_session():
    """Get the current active intermittent fasting session with program details"""
    try:
        logger.info(f"[FASTING] Checking active intermittent fasting session for user {current_user.id}")

        # Get active intermittent fasting session with program details
        session = FastingSession.query\
            .join(FastingProgram)\
            .filter(
                FastingSession.user_id == current_user.id,
                FastingSession.status == 'active',
                FastingProgram.type == 'intermittent'
            ).first()

        if not session:
            logger.info(f"[FASTING] No active intermittent fasting session found for user {current_user.id}")
            return jsonify({
                'status': 'success',
                'has_active_session': False
            })

        # Verify program association
        program = session.program
        if not program:
            logger.error(f"[FASTING] No program found for intermittent session {session.id}")
            return jsonify({'status': 'error', 'message': 'Program not found'}), 500

        # Calculate elapsed time and progress
        current_time = get_local_time()
        start_time = session.start_date
        elapsed_seconds = (current_time - start_time).total_seconds()
        elapsed_hours = round(elapsed_seconds / 3600, 1)  # Convert to hours
        
        # Get target hours from program name (e.g., "16-Hour Fast")
        target_hours = int(program.name.split('-')[0])
        progress_percent = min(100, round((elapsed_hours / target_hours) * 100, 1))
        
        # Calculate end time
        end_time = start_time + timedelta(hours=target_hours)
        
        # Check if fast is completed
        is_completed = current_time >= end_time
        
        logger.info(f"[FASTING] Returning active intermittent fasting session {session.id}: {elapsed_hours}/{target_hours} hours ({progress_percent}%), completed: {is_completed}")
        
        # Get duration in hours from program name
        duration_hours = int(program.name.split('-')[0])
        
        # Calculate elapsed time and remaining time
        remaining_hours = max(0, duration_hours - elapsed_hours)
        
        return jsonify({
            'status': 'success',
            'has_active_session': True,
            'checkin_today': is_completed,  # For intermittent fasting, completion is equivalent to check-in
            'session': {
                'id': session.id,
                'start_date': session.start_date.isoformat() if session.start_date else None,
                'start_time': session.start_date.isoformat() if session.start_date else None,
                'end_time': end_time.isoformat(),
                'elapsed_hours': round(elapsed_hours, 1),
                'remaining_hours': round(remaining_hours, 1),
                'duration_hours': duration_hours,
                'progress_percent': round(progress_percent, 1),
                'is_completed': is_completed,
                'program': {
                    'id': program.id,
                    'name': program.name,
                    'description': program.description,
                    'benefits': program.benefits,
                    'instructions': program.instructions
                }
            }
        })

    except Exception as e:
        logger.error(f"[FASTING] Error fetching active intermittent fasting session: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@fasting_bp.route('/api/fasting/history')
@login_required
def get_fasting_history():
    """Get user's fasting history for the current active session"""
    try:
        logger.info(f"[FASTING] Getting history for user {current_user.id}")

        # Get active session with program details
        session = FastingSession.query\
            .join(FastingProgram)\
            .filter(
                FastingSession.user_id == current_user.id,
                FastingSession.status == 'active'
            ).order_by(FastingSession.id.desc()).first()  # Get the most recent active session

        if not session:
            logger.info(f"[FASTING] No active session found for user {current_user.id}")
            return jsonify({
                'status': 'success',
                'check_ins': []
            })

        # Get check-ins for this session ordered by day number
        check_ins = FastingCheckIn.query\
            .filter_by(session_id=session.id)\
            .order_by(FastingCheckIn.day_number)\
            .all()

        logger.info(f"[FASTING] Found {len(check_ins)} check-ins for session {session.id}")

        check_in_data = [{
            'day_number': ci.day_number,
            'mood': ci.mood,
            'energy_level': ci.energy_level,
            'weight': ci.weight,
            'symptoms': ci.symptoms,
            'notes': ci.notes,
            'check_in_time': ci.check_in_time.isoformat() if ci.check_in_time else None,
            'completed': True
        } for ci in check_ins]

        logger.info(f"[FASTING] Sending check-in data: {check_in_data}")

        # Get actual current day using the method from the model
        current_day = session.get_current_day()
        
        # Check if the current day has a check-in
        checkin_done_today = False
        for ci in check_ins:
            if ci.day_number == current_day:
                checkin_done_today = True
                break
        
        logger.info(f"[FASTING] History endpoint: current day: {current_day}, check-in done today: {checkin_done_today}")
        
        return jsonify({
            'status': 'success',
            'check_ins': check_in_data,
            'checkin_today': checkin_done_today,
            'program': {
                'name': session.program.name,
                'duration_days': session.program.duration_days,
                'current_day': current_day,
                'total_days': session.program.duration_days,
                'display_day': f"Day {current_day} of {session.program.duration_days}"
            }
        })

    except Exception as e:
        logger.error(f"[FASTING] Error fetching history: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@fasting_bp.route('/api/fasting/checkin', methods=['POST'])
@login_required
def daily_checkin():
    """Record a daily check-in for a fasting session with improved transaction handling"""
    try:
        data = request.get_json()
        if not data:
            logger.error("[FASTING] No data received in check-in request")
            return jsonify({'status': 'error', 'message': 'No check-in data provided'}), 400

        logger.info(f"[FASTING] Processing check-in data: {data}")

        # Get active session with program details in a new transaction
        session = FastingSession.query\
            .join(FastingProgram)\
            .filter(
                FastingSession.user_id == current_user.id,
                FastingSession.status == 'active'
            ).with_for_update().first()

        if not session:
            logger.error(f"[FASTING] No active fasting session found for user {current_user.id}")
            return jsonify({'status': 'error', 'message': 'No active fasting session found'}), 400

        # Calculate current day using improved method with timezone handling
        current_day = session.get_current_day()
        logger.info(f"[FASTING] Processing check-in for session {session.id}, day {current_day}")

        # Validate required fields
        required_fields = ['mood', 'energy_level']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'status': 'error', 'message': f'Missing required fields: {", ".join(missing_fields)}'}), 400

        try:
            # Start a new transaction for check-in
            db.session.begin_nested()

            # Check for existing check-in
            existing_checkin = FastingCheckIn.query\
                .filter_by(session_id=session.id, day_number=current_day)\
                .first()

            if existing_checkin:
                logger.info(f"[FASTING] Check-in already exists for day {current_day}")
                db.session.rollback()

                # Get history in a separate transaction
                check_in_history = get_session_history(session.id)

                return jsonify({
                    'status': 'success',
                    'message': f'Day {current_day} already completed',
                    'history': check_in_history,
                    'day_completed': current_day,
                    'total_days': session.program.duration_days,
                    'next_day': current_day + 1 if current_day < session.program.duration_days else None
                })

            # Create new check-in
            check_in = FastingCheckIn(
                session_id=session.id,
                day_number=current_day,
                check_in_time=get_local_time(),
                completed=True,
                mood=data.get('mood'),
                energy_level=data.get('energy_level'),
                weight=data.get('weight'),
                symptoms=data.get('symptoms', []),
                notes=data.get('notes', '')
            )

            db.session.add(check_in)

            # Update session status if this is the last day
            if current_day >= session.program.duration_days:
                session.status = 'completed'
                session.end_date = get_local_time()

            # Commit the nested transaction
            db.session.commit()
            logger.info(f"[FASTING] Successfully saved check-in for day {current_day}")

            # Get updated history in a separate transaction
            check_in_history = get_session_history(session.id)
            logger.info(f"[FASTING] Retrieved {len(check_in_history)} check-ins for history")

            response_data = {
                'status': 'success',
                'message': f'Day {current_day} completed successfully',
                'check_in': {
                    'day_number': check_in.day_number,
                    'mood': check_in.mood,
                    'energy_level': check_in.energy_level,
                    'weight': check_in.weight,
                    'symptoms': check_in.symptoms,
                    'notes': check_in.notes,
                    'check_in_time': check_in.check_in_time.isoformat(),
                    'completed': True
                },
                'day_completed': current_day,
                'total_days': session.program.duration_days,
                'next_day': current_day + 1 if current_day < session.program.duration_days else None,
                'history': check_in_history,
                'program': {
                    'name': session.program.name,
                    'duration_days': session.program.duration_days,
                    'current_day': current_day,
                    'total_days': session.program.duration_days,
                    'display_day': f"Day {current_day} of {session.program.duration_days}"
                }
            }

            logger.info(f"[FASTING] Returning successful response with {len(check_in_history)} history entries")
            return jsonify(response_data)

        except SQLAlchemyError as e:
            logger.error(f"[FASTING] Database error while recording check-in: {e}")
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    except Exception as e:
        logger.error(f"[FASTING] Error recording check-in: {str(e)}", exc_info=True)
        if db.session.is_active:
            db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@fasting_bp.route('/api/fasting/end', methods=['POST'])
@login_required
def end_fasting_session():
    """End the current extended fasting session"""
    try:
        session = FastingSession.query.join(FastingProgram).filter(
            FastingSession.user_id == current_user.id,
            FastingSession.status == 'active',
            FastingProgram.type == 'extended'
        ).first()

        if not session:
            return jsonify({'status': 'error', 'message': 'No active extended fasting session found'}), 404

        logger.info(f"Ending extended fasting session {session.id} for user {current_user.id}")

        current_time = get_local_time()
        session.status = 'completed'
        session.end_date = current_time
        db.session.commit()

        duration = str(session.end_date - session.start_date).split('.')[0]

        return jsonify({
            'status': 'success',
            'message': 'Extended fasting session ended successfully',
            'session': {
                'id': session.id,
                'start_date': session.start_date.strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': session.end_date.strftime('%Y-%m-%d %H:%M:%S'),
                'duration': duration
            }
        })

    except Exception as e:
        logger.error(f"Error ending extended fasting session: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
@fasting_bp.route('/api/fasting/intermittent/end', methods=['POST'])
@login_required
def end_intermittent_fasting_session():
    """End the current intermittent fasting session"""
    try:
        session = FastingSession.query.join(FastingProgram).filter(
            FastingSession.user_id == current_user.id,
            FastingSession.status == 'active',
            FastingProgram.type == 'intermittent'
        ).first()

        if not session:
            return jsonify({'status': 'error', 'message': 'No active intermittent fasting session found'}), 404

        logger.info(f"Ending intermittent fasting session {session.id} for user {current_user.id}")

        current_time = get_local_time()
        session.status = 'completed'
        session.end_date = current_time
        
        # Calculate total fasting duration
        fasting_duration = current_time - session.start_date
        hours_fasted = round(fasting_duration.total_seconds() / 3600, 1)
        
        # Get target duration from program name
        target_hours = int(session.program.name.split('-')[0])
        completion_percent = min(100, round((hours_fasted / target_hours) * 100, 1))
        
        # Add feedback to session
        session.notes = f"Completed {hours_fasted} hours of {target_hours}-hour fast ({completion_percent}%)"
        
        db.session.commit()

        duration_str = str(fasting_duration).split('.')[0]

        return jsonify({
            'status': 'success',
            'message': 'Intermittent fasting session ended successfully',
            'session': {
                'id': session.id,
                'start_date': session.start_date.strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': session.end_date.strftime('%Y-%m-%d %H:%M:%S'),
                'duration': duration_str,
                'hours_fasted': hours_fasted,
                'target_hours': target_hours,
                'completion_percent': completion_percent
            }
        })

    except Exception as e:
        logger.error(f"Error ending intermittent fasting session: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@fasting_bp.route('/api/fasting/reset', methods=['POST'])
@login_required
def reset_fasting_session():
    """Reset active extended fasting sessions - improved version with single-click functionality"""
    try:
        logger.info(f"[FASTING] Resetting active extended fasting sessions for user {current_user.id}")

        # Get all active extended fasting sessions for the user
        active_sessions = FastingSession.query.join(FastingProgram).filter(
            FastingSession.user_id == current_user.id,
            FastingSession.status == 'active',
            FastingProgram.type == 'extended'
        ).all()

        current_time = get_local_time()
        for session in active_sessions:
            session.status = 'cancelled'
            session.end_date = current_time
            logger.info(f"[FASTING] Cancelling extended fasting session {session.id}")

        try:
            db.session.commit()
            logger.info(f"[FASTING] Successfully reset {len(active_sessions)} active extended fasting sessions")
        except SQLAlchemyError as e:
            logger.error(f"[FASTING] Database error while resetting extended fasting sessions: {e}")
            db.session.rollback()
            raise

        return jsonify({
            'status': 'success',
            'message': 'Extended fasting session reset successfully',
            'reset_count': len(active_sessions)
        })

    except Exception as e:
        logger.error(f"[FASTING] Error resetting extended fasting sessions: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
@fasting_bp.route('/api/fasting/intermittent/reset', methods=['POST'])
@login_required
def reset_intermittent_fasting_session():
    """Reset active intermittent fasting sessions"""
    try:
        logger.info(f"[FASTING] Resetting active intermittent fasting sessions for user {current_user.id}")

        # Get all active intermittent fasting sessions for the user
        active_sessions = FastingSession.query.join(FastingProgram).filter(
            FastingSession.user_id == current_user.id,
            FastingSession.status == 'active',
            FastingProgram.type == 'intermittent'
        ).all()

        current_time = get_local_time()
        for session in active_sessions:
            session.status = 'cancelled'
            session.end_date = current_time
            
            # Calculate fasting duration
            fasting_duration = current_time - session.start_date
            hours_fasted = round(fasting_duration.total_seconds() / 3600, 1)
            
            # Get target duration from program name
            target_hours = int(session.program.name.split('-')[0])
            completion_percent = min(100, round((hours_fasted / target_hours) * 100, 1))
            
            # Add feedback to session
            session.notes = f"Cancelled after {hours_fasted} hours of {target_hours}-hour fast ({completion_percent}%)"
            
            logger.info(f"[FASTING] Cancelling intermittent fasting session {session.id}")

        try:
            db.session.commit()
            logger.info(f"[FASTING] Successfully reset {len(active_sessions)} active intermittent fasting sessions")
        except SQLAlchemyError as e:
            logger.error(f"[FASTING] Database error while resetting intermittent fasting sessions: {e}")
            db.session.rollback()
            raise

        return jsonify({
            'status': 'success',
            'message': 'Intermittent fasting session reset successfully',
            'reset_count': len(active_sessions)
        })

    except Exception as e:
        logger.error(f"[FASTING] Error resetting intermittent fasting sessions: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@fasting_bp.route('/fasting')
@login_required
def fasting_index():
    """Main fasting programs page"""
    logger.info(f"User {current_user.id} accessing main fasting page")
    return render_template('fasting/index.html')

@fasting_bp.route('/fasting/history')
@login_required
def view_fasting_history():
    """View page for fasting history"""
    logger.info(f"User {current_user.id} accessing fasting history page")
    return render_template('fasting/history.html')

@fasting_bp.route('/api/fasting/programs/<int:program_id>')
@login_required
def get_program_details(program_id):
    """Get details for a specific program by ID"""
    try:
        program = FastingProgram.query.get(program_id)
        if not program:
            return jsonify({'status': 'error', 'message': 'Program not found'}), 404
        return jsonify({
            'status': 'success',
            'program': {
                'id': program.id,
                'name': program.name,
                'duration_days': program.duration_days,
                'description': program.description,
                'benefits': program.benefits,
                'instructions': program.instructions
            }
        })
    except Exception as e:
        logger.error(f"Error fetching program details: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

def init_default_programs():
    """Initialize default extended fasting programs if they don't exist"""
    try:
        logger.info("[FASTING] Checking for existing extended fasting programs...")

        existing_count = FastingProgram.query.filter_by(type='extended').count()
        logger.info(f"[FASTING] Found {existing_count} existing programs")

        # Only initialize if no programs exist
        if existing_count == 0:
            logger.info("[FASTING] Initializing default extended fasting programs...")

            # Add extended fasting programs
            extended_programs = [
                {
                    'name': '3-Day Reset',
                    'duration_days': 3,
                    'type': 'extended',
                    'description': 'Three day water fast',
                    'benefits': 'Deep autophagy, immune system reset',
                    'instructions': 'Water, tea and electrolytes only'
                },
                {
                    'name': '5-Day Longevity Fast',
                    'duration_days': 5,
                    'type': 'extended',
                    'description': 'Five day fasting for longevity',
                    'benefits': 'Enhanced cellular repair, longevity',
                    'instructions': 'Water and electrolytes only'
                },
                {
                    'name': '7-Day Transformation',
                    'duration_days': 7,
                    'type': 'extended',
                    'description': 'Seven day deep healing fast',
                    'benefits': 'Maximum autophagy, immune system reset',
                    'instructions': 'Water and electrolytes only'
                }
            ]

            # Reset all programs to ensure consistent state
            FastingProgram.query.filter_by(type='extended').delete()

            for program_data in extended_programs:
                program = FastingProgram(**program_data)
                db.session.add(program)
                logger.info(f"[FASTING] Added program: {program_data['name']} ({program_data['duration_days']} days)")

            db.session.commit()
            logger.info("[FASTING] Successfully initialized all extended fasting programs")

            # Verify programs were created
            created_programs = FastingProgram.query.filter_by(type='extended').all()
            logger.info(f"[FASTING] Verified {len(created_programs)} programs created successfully")
            for prog in created_programs:
                logger.info(f"[FASTING] Program available: {prog.name} (ID: {prog.id})")

        # Check for intermittent fasting programs
        intermittent_count = FastingProgram.query.filter_by(type='intermittent').count()
        logger.info(f"[FASTING] Found {intermittent_count} existing intermittent fasting programs")

        # Initialize intermittent fasting programs if they don't exist
        if intermittent_count == 0:
            logger.info("[FASTING] Initializing default intermittent fasting programs...")

            # Add intermittent fasting programs
            intermittent_programs = [
                {
                    'name': '16-Hour Fast',
                    'duration_days': 1,  # These are daily programs
                    'type': 'intermittent',
                    'description': '16-hour fasting window with 8-hour eating window',
                    'benefits': 'Enhanced fat burning, improved metabolic health, convenient daily schedule',
                    'instructions': 'Fast for 16 hours (including sleep time), eat during an 8-hour window'
                },
                {
                    'name': '18-Hour Fast',
                    'duration_days': 1,
                    'type': 'intermittent',
                    'description': '18-hour fasting window with 6-hour eating window',
                    'benefits': 'Deeper autophagy, improved insulin sensitivity, reduced inflammation',
                    'instructions': 'Fast for 18 hours, eat during a 6-hour window'
                },
                {
                    'name': '20-Hour Fast',
                    'duration_days': 1,
                    'type': 'intermittent',
                    'description': '20-hour fasting window with 4-hour eating window',
                    'benefits': 'Significant autophagy, enhanced fat adaptation, cellular rejuvenation',
                    'instructions': 'Fast for 20 hours, eat during a 4-hour window'
                }
            ]

            for program_data in intermittent_programs:
                program = FastingProgram(**program_data)
                db.session.add(program)
                logger.info(f"[FASTING] Added intermittent program: {program_data['name']} ({program_data['duration_days']} days)")

            db.session.commit()
            logger.info("[FASTING] Successfully initialized all intermittent fasting programs")

            # Verify programs were created
            created_intermittent = FastingProgram.query.filter_by(type='intermittent').all()
            logger.info(f"[FASTING] Verified {len(created_intermittent)} intermittent programs created successfully")

    except Exception as e:
        logger.error(f"[FASTING] Error initializing default programs: {str(e)}", exc_info=True)
        db.session.rollback()

# Initialize programs when blueprint is registered
init_default_programs()

def get_session_history(session_id):
    """Get check-in history for a session in a separate transaction"""
    try:
        # Query all check-ins for the session
        check_ins = FastingCheckIn.query\
            .filter_by(session_id=session_id)\
            .order_by(FastingCheckIn.day_number)\
            .all()

        # Format check-ins for response
        history = [{
            'day_number': ci.day_number,
            'mood': ci.mood,
            'energy_level': ci.energy_level,
            'weight': ci.weight,
            'symptoms': ci.symptoms,
            'notes': ci.notes,
            'check_in_time': ci.check_in_time.isoformat() if ci.check_in_time else None,
            'completed': True
        } for ci in check_ins]

        logger.info(f"[FASTING] Retrieved history for session {session_id}: {len(history)} entries")
        return history
    except Exception as e:
        logger.error(f"[FASTING] Error retrieving session history: {e}")
        return []