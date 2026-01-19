from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from models import db, JournalEntry
from datetime import datetime
import logging
import io
import os
from sqlalchemy.exc import SQLAlchemyError

journal_bp = Blueprint('journal', __name__)
logger = logging.getLogger(__name__)

@journal_bp.route('/journal')
@login_required
def index():
    """Display the journal entries page with optional search functionality."""
    try:
        # Get search parameters
        search_query = request.args.get('search', '')
        mood_filter = request.args.get('mood', '')

        # Start with base query
        query = JournalEntry.query.filter_by(user_id=current_user.id)

        # Apply search filter if provided
        if search_query:
            search_terms = f"%{search_query}%"
            query = query.filter(
                or_(
                    JournalEntry.title.ilike(search_terms),
                    JournalEntry.content.ilike(search_terms)
                )
            )

        # Apply mood filter if provided
        if mood_filter:
            query = query.filter(JournalEntry.mood == mood_filter)

        # Get results ordered by timestamp
        entries = query.order_by(JournalEntry.timestamp.desc()).all()

        return render_template('journal/index.html', entries=entries)
    except Exception as e:
        logger.error(f"Error in journal index: {str(e)}")
        flash('An error occurred while loading journal entries.', 'error')
        return render_template('journal/index.html', entries=[])

@journal_bp.route('/journal/new', methods=['GET', 'POST'])
@login_required
def new_entry():
    """Create a new journal entry."""
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            content = request.form.get('content')
            mood = request.form.get('mood')

            if not title or not content:
                flash('Title and content are required.', 'error')
                return redirect(url_for('journal.new_entry'))

            entry = JournalEntry(
                user_id=current_user.id,
                title=title,
                content=content,
                mood=mood,
                timestamp=datetime.utcnow()
            )

            db.session.add(entry)
            db.session.commit()

            flash('Journal entry created successfully!', 'success')
            return redirect(url_for('journal.index'))

        except SQLAlchemyError as e:
            logger.error(f"Database error creating journal entry: {str(e)}")
            db.session.rollback()
            flash('Error saving journal entry. Please try again.', 'error')
            return redirect(url_for('journal.new_entry'))
        except Exception as e:
            logger.error(f"Error creating journal entry: {str(e)}")
            flash('An unexpected error occurred. Please try again.', 'error')
            return redirect(url_for('journal.new_entry'))

    return render_template('journal/new.html')

@journal_bp.route('/journal/<int:entry_id>')
@login_required
def view_entry(entry_id):
    """View a specific journal entry."""
    try:
        entry = JournalEntry.query.filter_by(
            id=entry_id, 
            user_id=current_user.id
        ).first_or_404()
        return render_template('journal/view.html', entry=entry)
    except Exception as e:
        logger.error(f"Error viewing journal entry {entry_id}: {str(e)}")
        flash('Error loading journal entry.', 'error')
        return redirect(url_for('journal.index'))

@journal_bp.route('/journal/<int:entry_id>/export')
@login_required
def export_entry(entry_id):
    """Export a journal entry as a text file."""
    try:
        entry = JournalEntry.query.filter_by(
            id=entry_id, 
            user_id=current_user.id
        ).first_or_404()

        # Format the content with 12-hour time format
        content = f"""Title: {entry.title}
Date: {entry.timestamp.strftime('%Y-%m-%d %I:%M %p')}
Mood: {entry.mood or 'Not specified'}

{entry.content}
"""
        # Create a BytesIO object
        buffer = io.BytesIO()
        buffer.write(content.encode('utf-8'))
        buffer.seek(0)

        # Generate filename
        safe_title = "".join(x for x in entry.title if x.isalnum() or x in (' ', '-', '_'))
        filename = f"journal_{safe_title}_{entry.timestamp.strftime('%Y%m%d')}.txt"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )

    except Exception as e:
        logger.error(f"Error exporting journal entry {entry_id}: {str(e)}")
        flash('Error exporting journal entry.', 'error')
        return redirect(url_for('journal.view_entry', entry_id=entry_id))