"""Data models and helper representations for MongoDB collections."""
from datetime import datetime
from flask_login import UserMixin
from bson import ObjectId
from app.extensions import get_db, bcrypt

class User(UserMixin):
    """User representation for Flask-Login backed by MongoDB."""

    def __init__(self, user_doc):
        self.doc = user_doc or {}
        self.id = str(user_doc.get("_id")) if user_doc and "_id" in user_doc else None
        self.email = user_doc.get("email", "")
        self.full_name = user_doc.get("full_name", "")
        self.role = user_doc.get("role", "candidate")  # 'candidate' or 'recruiter'
        self.account_status = user_doc.get("account_status", "active")
        self.created_at = user_doc.get("created_at")

    @property
    def is_recruiter(self):
        return self.role == "recruiter"

    @property
    def is_candidate(self):
        return self.role == "candidate"

    @staticmethod
    def get_by_id(user_id):
        if not user_id:
            return None
        db = get_db()
        try:
            doc = db.users.find_one({"_id": ObjectId(user_id)})
            if not doc or doc.get("account_status", "active") != "active":
                return None
            return User(doc)
        except Exception:
            return None

    @staticmethod
    def get_by_email(email):
        if not email:
            return None
        db = get_db()
        doc = db.users.find_one({"email": email.strip().lower()})
        return User(doc) if doc else None

    @staticmethod
    def create(full_name, email, password, role="candidate"):
        db = get_db()
        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        now = datetime.utcnow()
        doc = {
            "full_name": full_name.strip(),
            "email": email.strip().lower(),
            "password_hash": password_hash,
            "role": role if role in ["candidate", "recruiter"] else "candidate",
            "account_status": "active",
            "created_at": now,
            "updated_at": now,
        }
        result = db.users.insert_one(doc)
        doc["_id"] = result.inserted_id
        return User(doc)

    def check_password(self, password):
        stored_hash = self.doc.get("password_hash", "")
        if not stored_hash:
            return False
        return bcrypt.check_password_hash(stored_hash, password)


class CandidateProfileModel:
    """Helper for candidate_profiles collection."""

    @staticmethod
    def get_by_user_id(user_id):
        db = get_db()
        return db.candidate_profiles.find_one({"user_id": str(user_id)})

    @staticmethod
    def upsert(user_id, data):
        db = get_db()
        now = datetime.utcnow()
        update_fields = {
            "user_id": str(user_id),
            "updated_at": now,
        }
        for field in [
            "github_url", "linkedin_url", "resume_storage_name",
            "resume_original_name", "resume_text", "target_role",
            "experience_level", "preferred_duration"
        ]:
            if field in data:
                update_fields[field] = data[field]

        return db.candidate_profiles.update_one(
            {"user_id": str(user_id)},
            {"$set": update_fields, "$setOnInsert": {"created_at": now}},
            upsert=True
        )

    @staticmethod
    def calculate_completion(profile_doc):
        """Calculates profile completion percentage and readiness checklist."""
        if not profile_doc:
            return {
                "percentage": 0,
                "has_resume": False,
                "has_github": False,
                "has_role": False,
                "is_ready_for_interview": False
            }

        has_resume = bool(profile_doc.get("resume_text"))
        has_github = bool(profile_doc.get("github_url"))
        has_role = bool(profile_doc.get("target_role"))

        score = 0
        if has_resume: score += 40
        if has_github: score += 40
        if has_role: score += 20

        return {
            "percentage": score,
            "has_resume": has_resume,
            "has_github": has_github,
            "has_role": has_role,
            "is_ready_for_interview": (has_resume and has_github and has_role)
        }
