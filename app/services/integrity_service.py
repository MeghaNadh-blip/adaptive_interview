"""Transparent interview integrity event tracking and reviewer annotation service."""
from datetime import datetime
from bson import ObjectId
from app.extensions import get_db

class IntegrityService:

    EVENT_DESCRIPTIONS = {
        "visibility_hidden": "Candidate switched window/tab or minimized browser during interview.",
        "fullscreen_exited": "Interview room fullscreen view was exited.",
        "window_blur": "Browser window lost focus.",
        "navigation_attempt": "Candidate attempted to leave interview room URL.",
        "rapid_duplicate_submission": "Multiple rapid submission attempts detected in sub-second interval.",
        "session_anomaly": "Unusual state transition or timing variance detected."
    }

    @classmethod
    def log_event(cls, session_id, candidate_id, event_type, context=None, question_id=None):
        """
        Records an integrity event transparently.
        Never infers guilt or terminates automatically.
        """
        db = get_db()
        now = datetime.utcnow()

        event_doc = {
            "session_id": str(session_id),
            "candidate_id": str(candidate_id),
            "event_type": event_type,
            "question_id": str(question_id) if question_id else None,
            "context": context or cls.EVENT_DESCRIPTIONS.get(event_type, "Browser state change recorded."),
            "review_status": "unverified",
            "reviewer_notes": "",
            "recorded_at": now
        }
        res = db.integrity_events.insert_one(event_doc)
        event_doc["_id"] = res.inserted_id
        return event_doc

    @classmethod
    def get_session_events(cls, session_id):
        """Fetch all integrity events for a specific interview session."""
        db = get_db()
        return list(db.integrity_events.find({"session_id": str(session_id)}).sort("recorded_at", 1))

    @classmethod
    def add_reviewer_note(cls, event_id, reviewer_notes, status="reviewed"):
        """Recruiter updates an integrity event with human review findings."""
        db = get_db()
        return db.integrity_events.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {
                "reviewer_notes": reviewer_notes.strip(),
                "review_status": status,
                "reviewed_at": datetime.utcnow()
            }}
        )
