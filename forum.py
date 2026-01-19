from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import ForumPost, ForumReply
from datetime import datetime
import pytz

forum = Blueprint('forum', __name__)

@forum.route('/forum')
@login_required
def index():
    """List all forum posts"""
    category = request.args.get('category', 'all')
    if category != 'all':
        posts = ForumPost.query.filter_by(category=category)\
            .order_by(ForumPost.created_at.desc()).all()
    else:
        posts = ForumPost.query.order_by(ForumPost.created_at.desc()).all()

    # Store timestamps in UTC for client-side conversion
    for post in posts:
        if not post.created_at.tzinfo:
            post.created_at = pytz.UTC.localize(post.created_at)
        if post.updated_at and not post.updated_at.tzinfo:
            post.updated_at = pytz.UTC.localize(post.updated_at)

    return render_template('forum/index.html', 
                         posts=posts,
                         categories=['General Discussion', 'Success Stories', 'Support', 'Tips & Tricks'],
                         current_category=category)

@forum.route('/forum/new', methods=['GET', 'POST'])
@login_required
def new_post():
    """Create a new forum post"""
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category', 'General Discussion')

        if not title or not content:
            flash('Title and content are required.', 'error')
            return redirect(url_for('forum.new_post'))

        # Store in UTC
        utc_now = datetime.now(pytz.UTC)

        post = ForumPost(
            title=title,
            content=content,
            category=category,
            author_id=current_user.id,
            created_at=utc_now,
            updated_at=utc_now
        )

        db.session.add(post)
        db.session.commit()

        flash('Your post has been created!', 'success')
        return redirect(url_for('forum.index'))

    return render_template('forum/new.html')

@forum.route('/forum/post/<int:post_id>')
@login_required
def view_post(post_id):
    """View a specific forum post and its replies"""
    post = ForumPost.query.get_or_404(post_id)

    # Ensure timestamps are UTC for client-side conversion
    if not post.created_at.tzinfo:
        post.created_at = pytz.UTC.localize(post.created_at)
    if post.updated_at and not post.updated_at.tzinfo:
        post.updated_at = pytz.UTC.localize(post.updated_at)

    # Ensure reply timestamps are UTC
    for reply in post.replies:
        if not reply.created_at.tzinfo:
            reply.created_at = pytz.UTC.localize(reply.created_at)
        if reply.updated_at and not reply.updated_at.tzinfo:
            reply.updated_at = pytz.UTC.localize(reply.updated_at)

    return render_template('forum/view.html', post=post)

@forum.route('/forum/post/<int:post_id>/reply', methods=['POST'])
@login_required
def add_reply(post_id):
    """Add a reply to a forum post"""
    post = ForumPost.query.get_or_404(post_id)
    content = request.form.get('content')

    if not content:
        flash('Reply content cannot be empty.', 'error')
        return redirect(url_for('forum.view_post', post_id=post_id))

    # Store in UTC
    utc_now = datetime.now(pytz.UTC)

    reply = ForumReply(
        content=content,
        post_id=post_id,
        author_id=current_user.id,
        created_at=utc_now,
        updated_at=utc_now
    )

    db.session.add(reply)
    db.session.commit()

    flash('Your reply has been added!', 'success')
    return redirect(url_for('forum.view_post', post_id=post_id))

@forum.route('/forum/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    """Like or unlike a post"""
    post = ForumPost.query.get_or_404(post_id)
    post.likes += 1
    db.session.commit()
    return jsonify({'likes': post.likes})

@forum.route('/forum/reply/<int:reply_id>/like', methods=['POST'])
@login_required
def like_reply(reply_id):
    """Like or unlike a reply"""
    reply = ForumReply.query.get_or_404(reply_id)
    reply.likes += 1
    db.session.commit()
    return jsonify({'likes': reply.likes})