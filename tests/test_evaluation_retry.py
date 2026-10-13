"""Regression tests for retrying unavailable and legacy answer evaluations."""
from bson import ObjectId
import pytest

from app import create_app
from app.extensions import get_db
from app.models import User
from app.services.ai_service import AIService


@pytest.fixture
def app():
    return create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "MONGO_URI": "mongodb://localhost:27017/test_db",
        "MONGO_DB_NAME": "test_db",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-for-tests",
    })


def _completed_result():
    return {
        "rubric_scores": {
            "technical_correctness": 4,
            "depth_of_understanding": 4,
            "reasoning_problem_solving": 4,
            "relevance": 5,
            "explanation_clarity": 5,
        },
        "weighted_score": 88,
        "evidence": {
            "what_was_correct": ["Identified the main technical trade-off."],
            "what_was_incomplete_or_incorrect": ["Could explain failure handling in more detail."],
            "suggested_improvement": "Discuss edge cases and validation.",
        },
        "feedback": "Good answer with a clear improvement opportunity.",
        "uncertainty": "moderate",
        "human_review_required": False,
        "evaluation_status": "completed",
    }


@pytest.mark.parametrize("legacy_evaluation", [True, False])
def test_retry_handles_legacy_or_missing_evaluation(app, monkeypatch, legacy_evaluation):
    """A retry must include old rows without status and answers with no evaluation row."""
    monkeypatch.setattr(AIService, "evaluate_answer", staticmethod(lambda **kwargs: _completed_result()))
    client = app.test_client()

    with app.app_context():
        db = get_db()
        user = User.create("Retry Candidate", "retry-candidate@example.com", "securepassword123")
        session_id = ObjectId()
        question_id = ObjectId()
        answer_id = ObjectId()

        db.interview_sessions.insert_one({
            "_id": session_id,
            "candidate_id": user.id,
            "target_role": "Python Intern",
        })
        db.questions.insert_one({
            "_id": question_id,
            "session_id": str(session_id),
            "sequence_number": 1,
            "question_text": "How would you handle an unavailable AI provider?",
            "competency": "Reliability",
            "assessment_criteria": ["Retry", "Error handling"],
            "time_limit_seconds": 120,
        })
        db.answers.insert_one({
            "_id": answer_id,
            "session_id": str(session_id),
            "question_id": str(question_id),
            "candidate_id": user.id,
            "answer_text": "I would retry safely and show an explicit error.",
            "duration_seconds": 45,
        })
        if legacy_evaluation:
            # Simulate a previous app version: no evaluation_status and no score.
            db.evaluations.insert_one({
                "session_id": str(session_id),
                "question_id": str(question_id),
                "answer_id": str(answer_id),
                "weighted_score": None,
                "evidence": {},
            })

        with client.session_transaction() as flask_session:
            flask_session["_user_id"] = user.id
            flask_session["_fresh"] = True

        response = client.post(f"/reports/{session_id}/retry-evaluations")
        assert response.status_code == 302

        saved = db.evaluations.find_one({
            "session_id": str(session_id),
            "question_id": str(question_id),
        })
        assert saved is not None
        assert saved["evaluation_status"] == "completed"
        assert saved["weighted_score"] == 88
        assert saved["answer_id"] == str(answer_id)
