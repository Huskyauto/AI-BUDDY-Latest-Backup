from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, MeditationChallenge, MeditationSession, ChallengeMessage
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
from sqlalchemy import text

challenges_bp = Blueprint('challenges', __name__)
logger = logging.getLogger(__name__)

@challenges_bp.route('/meditation-challenges')
@login_required
def list_challenges():
    """Display meditation challenges page"""
    try:
        # Get challenges and include user's meditation sessions
        now = datetime.now(ZoneInfo('UTC'))
        today = now.date()

        # Get today's meditation sessions for the user
        today_sessions = MeditationSession.query.filter(
            MeditationSession.user_id == current_user.id,
            db.func.date(MeditationSession.start_time) == today
        ).all()

        # Get all challenges where user is a participant
        user_challenges = MeditationChallenge.query\
            .filter(MeditationChallenge.participants.contains(current_user))\
            .all()

        # Get other available challenges
        other_challenges = MeditationChallenge.query\
            .filter(~MeditationChallenge.participants.contains(current_user))\
            .all()

        active_challenges = []
        upcoming_challenges = []
        completed_challenges = []

        # First add user's participated challenges
        for challenge in user_challenges:
            if challenge.end_date.date() < today:
                completed_challenges.append(challenge)
            elif challenge.start_date.date() <= today <= challenge.end_date.date():
                active_challenges.append(challenge)
            elif challenge.start_date.date() > today:
                upcoming_challenges.append(challenge)

        # Then add other available challenges
        for challenge in other_challenges:
            if challenge.end_date.date() < today:
                completed_challenges.append(challenge)
            elif challenge.start_date.date() <= today <= challenge.end_date.date():
                active_challenges.append(challenge)
            elif challenge.start_date.date() > today:
                upcoming_challenges.append(challenge)

        # Check if user is admin to show reset functionality
        is_admin = current_user.email == 'huskyauto@gmail.com'
        
        return render_template('meditation_challenges.html',
                             active_challenges=active_challenges,
                             upcoming_challenges=upcoming_challenges,
                             completed_challenges=completed_challenges,
                             today_sessions=today_sessions,
                             is_admin=is_admin)

    except Exception as e:
        logger.error(f"Error listing challenges: {e}", exc_info=True)
        is_admin = current_user.email == 'huskyauto@gmail.com'
        return render_template('meditation_challenges.html', error="Error loading challenges", is_admin=is_admin)

@challenges_bp.route('/join-challenge/<int:challenge_id>', methods=['POST'])
@login_required
def join_challenge(challenge_id):
    """Join a meditation challenge"""
    try:
        logger.info(f"Attempting to join challenge {challenge_id} for user {current_user.id}")
        challenge = MeditationChallenge.query.get_or_404(challenge_id)

        if not challenge.can_join(current_user):
            logger.warning(f"User {current_user.id} cannot join challenge {challenge_id}")
            return jsonify({
                'status': 'error',
                'message': 'Unable to join this challenge'
            }), 400

        if current_user not in challenge.participants:
            challenge.participants.append(current_user)
            challenge.current_participants += 1
            db.session.commit()
            logger.info(f"User {current_user.id} successfully joined challenge {challenge_id}")

        return jsonify({
            'status': 'success',
            'message': 'Successfully joined the challenge'
        })

    except Exception as e:
        logger.error(f"Error joining challenge: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@challenges_bp.route('/create-challenge', methods=['GET', 'POST'])
@login_required
def create_challenge():
    """Create a new meditation challenge"""
    try:
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            goal_minutes = int(request.form.get('goal_minutes', 0))
            max_participants = int(request.form.get('max_participants', 10))

            if not all([name, description, start_date_str, end_date_str, goal_minutes]):
                flash('All fields are required', 'danger')
                return render_template('create_challenge.html')

            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').replace(tzinfo=ZoneInfo('UTC'))
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(tzinfo=ZoneInfo('UTC'))
                end_date = end_date.replace(hour=23, minute=59, second=59)  # End of day
            except ValueError:
                flash('Invalid date format', 'danger')
                return render_template('create_challenge.html')

            # Validate dates
            if start_date.date() < datetime.now(ZoneInfo('UTC')).date():
                flash('Start date cannot be in the past', 'danger')
                return render_template('create_challenge.html')

            if end_date <= start_date:
                flash('End date must be after start date', 'danger')
                return render_template('create_challenge.html')

            # Create the challenge
            challenge = MeditationChallenge(
                name=name,
                description=description,
                start_date=start_date,
                end_date=end_date,
                duration_requirement=goal_minutes,
                frequency_requirement=7,  # Default to daily
                max_participants=max_participants,
                current_participants=1,  # Creator joins automatically
                created_by=current_user.id,
                challenge_type='group',
                is_public=True
            )
            # Note: status is calculated automatically as a property based on dates

            # Add creator as first participant
            challenge.participants.append(current_user)

            db.session.add(challenge)
            db.session.commit()

            # Add welcome message
            welcome_message = ChallengeMessage(
                challenge_id=challenge.id,
                user_id=current_user.id,
                message=f"Welcome to the {name} challenge! Let's achieve our meditation goals together."
                # timestamp uses default=get_local_time in the model
            )
            db.session.add(welcome_message)
            db.session.commit()

            logger.info(f"User {current_user.id} created new challenge {challenge.id}: {name}")
            flash('Challenge created successfully!', 'success')
            return redirect(url_for('challenges.list_challenges'))

        # Pass today's date to the template for date input min values
        today = datetime.now(ZoneInfo('UTC')).strftime('%Y-%m-%d')
        return render_template('challenges/create_challenge.html', today=today)

    except Exception as e:
        logger.error(f"Error creating challenge: {e}", exc_info=True)
        flash('An error occurred while creating the challenge', 'danger')
        # Include today's date even in error case
        today = datetime.now(ZoneInfo('UTC')).strftime('%Y-%m-%d')
        return render_template('challenges/create_challenge.html', today=today)

@challenges_bp.route('/reset-challenges', methods=['POST'])
@login_required
def reset_challenges():
    """Reset all meditation challenges - admin only"""
    try:
        # Check if user is admin
        if current_user.email != 'huskyauto@gmail.com':
            flash('Unauthorized access', 'danger')
            return redirect(url_for('challenges.list_challenges'))
        
        # Get all challenges
        challenges = MeditationChallenge.query.all()
        challenge_ids = [challenge.id for challenge in challenges]
        
        # Delete all challenge messages first (due to foreign key constraints)
        ChallengeMessage.query.filter(ChallengeMessage.challenge_id.in_(challenge_ids)).delete(synchronize_session=False)
        
        # Clear the challenge_participants association table
        db.session.execute(text("DELETE FROM challenge_participants"))
        
        # Delete all challenges
        MeditationChallenge.query.delete()
        
        db.session.commit()
        logger.info(f"Admin user {current_user.id} reset all meditation challenges")
        flash('All meditation challenges have been reset successfully', 'success')
        
        return redirect(url_for('challenges.list_challenges'))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting challenges: {e}", exc_info=True)
        flash('An error occurred while resetting challenges', 'danger')
        return redirect(url_for('challenges.list_challenges'))

@challenges_bp.route('/edit-challenge/<int:challenge_id>', methods=['GET', 'POST'])
@login_required
def edit_challenge(challenge_id):
    """Edit an existing meditation challenge"""
    try:
        challenge = MeditationChallenge.query.get_or_404(challenge_id)

        # Only the creator can edit
        if challenge.created_by != current_user.id:
            flash('You do not have permission to edit this challenge', 'danger')
            return redirect(url_for('challenges.list_challenges'))

        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            end_date_str = request.form.get('end_date')
            goal_minutes = int(request.form.get('goal_minutes', 0))

            if not all([name, description, end_date_str, goal_minutes]):
                flash('All fields are required', 'danger')
                return render_template('challenges/edit_challenge.html', challenge=challenge)

            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(tzinfo=ZoneInfo('UTC'))
                end_date = end_date.replace(hour=23, minute=59, second=59)  # End of day
            except ValueError:
                flash('Invalid date format', 'danger')
                return render_template('challenges/edit_challenge.html', challenge=challenge)

            # Cannot edit start date after challenge has been created
            # Validate end date is after start date and not in the past
            if end_date <= challenge.start_date:
                flash('End date must be after start date', 'danger')
                return render_template('challenges/edit_challenge.html', challenge=challenge)

            # Update challenge
            challenge.name = name
            challenge.description = description
            challenge.end_date = end_date
            challenge.duration_requirement = goal_minutes

            db.session.commit()
            logger.info(f"User {current_user.id} updated challenge {challenge.id}")
            flash('Challenge updated successfully!', 'success')
            return redirect(url_for('challenges.list_challenges'))

        return render_template('challenges/edit_challenge.html', challenge=challenge)

    except Exception as e:
        logger.error(f"Error editing challenge: {e}", exc_info=True)
        flash('An error occurred while editing the challenge', 'danger')
        return redirect(url_for('challenges.list_challenges'))