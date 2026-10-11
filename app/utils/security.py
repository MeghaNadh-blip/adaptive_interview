"""Security helpers, access controls, and filename randomization."""
import uuid
import os
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename

def recruiter_required(f):
    """Decorator to enforce recruiter authorization."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_recruiter:
            flash("Access denied: Recruiter credentials required.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def candidate_required(f):
    """Decorator to enforce candidate authorization."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_candidate:
            flash("Access denied: Candidate account required.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def generate_safe_storage_filename(original_filename):
    """Generate randomized internal storage filename while preserving safe extension."""
    clean_name = secure_filename(original_filename)
    ext = os.path.splitext(clean_name)[1].lower()
    random_id = uuid.uuid4().hex
    return f"resume_{random_id}{ext}"
