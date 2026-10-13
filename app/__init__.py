"""Flask Application Factory for Adaptive Interview Intelligence."""
import os
from flask import Flask, render_template
from dotenv import load_dotenv

from app.extensions import login_manager, bcrypt, csrf, init_db
from app.models import User

load_dotenv()

def create_app(test_config=None):
    """Construct and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # Configuration defaults
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        MONGO_URI=os.environ.get("MONGO_URI"),
        MONGO_DB_NAME=os.environ.get("MONGO_DB_NAME", "adaptive_interview_db"),
        GEMINI_API_KEY=os.environ.get("GEMINI_API_KEY"),
        GROQ_API_KEY=os.environ.get("GROQ_API_KEY"),
        AI_PROVIDER=os.environ.get("AI_PROVIDER", "auto"),
        AI_MODEL=os.environ.get("AI_MODEL", "gemini-2.5-flash"),
        GEMINI_MODEL=os.environ.get("GEMINI_MODEL", os.environ.get("AI_MODEL", "gemini-2.5-flash")),
        GROQ_MODEL=os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b"),
        GITHUB_TOKEN=os.environ.get("GITHUB_TOKEN"),
        MAX_RESUME_MB=int(os.environ.get("MAX_RESUME_MB", 5)),
        UPLOAD_FOLDER=os.path.join(app.root_path, "..", "instance", "private_resumes"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        MAX_CONTENT_LENGTH=int(os.environ.get("MAX_CONTENT_LENGTH", str(5 * 1024 * 1024 + 256 * 1024))),
        PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
    )

    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY") or str(app.config.get("SECRET_KEY")).startswith("replace_with"):
        raise RuntimeError("SECRET_KEY is missing. Set a strong random value in your .env file.")
    if not app.config.get("TESTING") and len(str(app.config["SECRET_KEY"])) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters outside tests.")

    # Initialize extensions
    bcrypt.init_app(app)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(user_id)

    # Initialize MongoDB connection
    with app.app_context():
        init_db(app)

    # Register Blueprints
    from app.routes.main import main_bp
    from app.auth import auth_bp
    from app.profile import profile_bp
    from app.interview import interview_bp
    from app.integrity import integrity_bp
    from app.reports import reports_bp
    from app.recruiter import recruiter_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(interview_bp)
    app.register_blueprint(integrity_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(recruiter_bp)

    # Error Handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, title="Access Forbidden",
                               message="You do not have permission to view this resource."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, title="Page Not Found",
                               message="The requested resource could not be found."), 404

    @app.errorhandler(413)
    def request_too_large(e):
        return render_template("error.html", code=413, title="File Too Large",
                               message="Uploaded resume exceeds maximum allowed size (5MB)."), 413

    @app.errorhandler(500)
    def internal_error(e):
        return render_template("error.html", code=500, title="Server Error",
                               message="An unexpected server error occurred. Please try again later."), 500

    return app

