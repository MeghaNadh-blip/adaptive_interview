"""Flask extensions and explicit database initialization."""
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from pymongo import MongoClient

login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()
_mongo_client = None
_db = None


def init_db(app):
    """Initialize MongoDB; tests use an isolated mongomock database."""
    global _mongo_client, _db
    db_name = app.config.get("MONGO_DB_NAME", "adaptive_interview_db")
    if app.config.get("TESTING"):
        try:
            import mongomock
        except ImportError as exc:
            raise RuntimeError("Install mongomock to run the test suite.") from exc
        _mongo_client = mongomock.MongoClient()
        _db = _mongo_client[db_name]
    else:
        mongo_uri = app.config.get("MONGO_URI")
        if not mongo_uri or "replace_with" in mongo_uri:
            raise RuntimeError("MONGO_URI is missing. Copy .env.example to .env and configure MongoDB Atlas.")
        _mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
        _db = _mongo_client[db_name]
        try:
            _mongo_client.admin.command("ping")
        except Exception as exc:
            _mongo_client.close()
            _mongo_client = None
            _db = None
            raise RuntimeError("Could not connect to MongoDB. Check MONGO_URI and network access.") from exc

    _db.users.create_index("email", unique=True)
    _db.candidate_profiles.create_index("user_id", unique=True)
    _db.interview_sessions.create_index("candidate_id")
    _db.questions.create_index([("session_id", 1), ("sequence_number", 1)])
    _db.answers.create_index([("session_id", 1), ("question_id", 1)], unique=True)
    _db.evaluations.create_index([("session_id", 1), ("question_id", 1)], unique=True)
    _db.integrity_events.create_index("session_id")
    _db.competency_results.create_index("session_id")
    _db.interview_reports.create_index("session_id", unique=True)
    return _db


def get_db():
    """Return the currently configured database instance."""
    return _db
