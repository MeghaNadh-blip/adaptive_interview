"""Authentication routes with candidate-only public registration."""
from urllib.parse import urlsplit

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from pymongo.errors import DuplicateKeyError, PyMongoError
from email_validator import validate_email, EmailNotValidError

from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_next_url(value):
    """Accept only same-origin absolute-path redirects; reject //host and backslashes."""
    if not value or not isinstance(value, str) or "\\" in value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/") or value.startswith("//"):
        return None
    return value


def _dashboard_for(user):
    return redirect(url_for("recruiter.dashboard" if user.is_recruiter else "main.dashboard"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _dashboard_for(current_user)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.get_by_email(email)
        if user and user.account_status == "active" and user.check_password(password):
            login_user(user, remember=False, fresh=True)
            flash(f"Welcome back, {user.full_name}!", "success")
            return redirect(_safe_next_url(request.args.get("next")) or url_for(
                "recruiter.dashboard" if user.is_recruiter else "main.dashboard"
            ))
        flash("Invalid email or password. Please check your credentials.", "danger")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return _dashboard_for(current_user)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        raw_email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or len(full_name) > 100:
            flash("Enter a name between 1 and 100 characters.", "danger")
            return render_template("register.html")
        try:
            email = validate_email(raw_email, check_deliverability=False).normalized.lower()
        except EmailNotValidError:
            flash("Enter a valid email address.", "danger")
            return render_template("register.html")
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        if len(password) < 12 or len(password.encode("utf-8")) > 72:
            flash("Use a password of at least 12 characters and no more than 72 UTF-8 bytes.", "danger")
            return render_template("register.html")

        try:
            # The role is deliberately not accepted from the public request.
            new_user = User.create(full_name=full_name, email=email, password=password, role="candidate")
            login_user(new_user, remember=False, fresh=True)
            flash("Registration successful! Complete your profile to get started.", "success")
            return redirect(url_for("profile.candidate_profile"))
        except DuplicateKeyError:
            flash("An account with this email address already exists.", "warning")
        except (PyMongoError, RuntimeError):
            current_app.logger.exception("Account creation failed")
            flash("We couldn't create your account right now. Please try again later.", "danger")
    return render_template("register.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("main.index"))
