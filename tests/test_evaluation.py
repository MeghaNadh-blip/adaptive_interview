"""Automated unit tests for Answer Evaluation and Rubric calculation."""
import pytest
from app import create_app
from app.services.ai_service import AIService

@pytest.fixture
def app():
    return create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "MONGO_URI": "mongodb://localhost:27017/test_db",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-for-tests"
    })

def test_blank_answer_evaluation(app):
    """Test that a blank answer does not crash or generate fake scores."""
    with app.app_context():
        eval_result = AIService.evaluate_answer(
            question_text="How does Redis Redlock function?",
            competency="Distributed Systems",
            assessment_criteria=["Quorum", "Clock drift"],
            answer_text="",
            time_limit=120,
            duration_seconds=120
        )

        assert eval_result["weighted_score"] == 0
        assert eval_result["human_review_required"] is True
        assert eval_result["uncertainty"] == "high"

def test_substantive_answer_without_api_does_not_receive_fake_score(app, monkeypatch):
    """If Gemini is unavailable, the service must not invent a competence score."""
    monkeypatch.setattr(AIService, "_call_gemini_json", staticmethod(lambda *args, **kwargs: None))
    with app.app_context():
        eval_result = AIService.evaluate_answer(
            question_text="How does Redis Redlock function?",
            competency="Distributed Systems",
            assessment_criteria=["Quorum", "Clock drift"],
            answer_text="Redlock uses independent Redis instances and a majority quorum.",
            time_limit=120,
            duration_seconds=65
        )
        assert eval_result["weighted_score"] is None
        assert eval_result["evaluation_status"] == "unavailable"
        assert eval_result["human_review_required"] is True
        assert eval_result["uncertainty"] == "high"


def test_ai_provider_falls_back_to_groq_when_gemini_fails(app, monkeypatch):
    """A transient Gemini failure should not block a configured Groq fallback."""
    monkeypatch.setattr(AIService, "_call_gemini_provider", staticmethod(lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("simulated outage"))))
    monkeypatch.setattr(AIService, "_call_groq_provider", staticmethod(lambda *args, **kwargs: {"ok": True}))
    with app.app_context():
        from flask import current_app
        current_app.config.update({
            "AI_PROVIDER": "auto",
            "GEMINI_API_KEY": "test-gemini-key",
            "GROQ_API_KEY": "test-groq-key",
        })
        result = AIService._call_gemini_json("Return JSON")
    assert result == {"ok": True}


def test_ai_provider_falls_back_when_json_schema_is_invalid(app, monkeypatch):
    """Valid JSON with missing rubric fields should trigger the backup provider."""
    valid_payload = {
        "rubric_scores": {
            "technical_correctness": 4,
            "depth_of_understanding": 4,
            "reasoning_problem_solving": 4,
            "relevance": 4,
            "explanation_clarity": 4,
        }
    }
    calls = []
    monkeypatch.setattr(AIService, "_call_gemini_provider", staticmethod(lambda *args, **kwargs: {"unexpected": "shape"}))
    def groq_result(*args, **kwargs):
        calls.append("groq")
        return valid_payload
    monkeypatch.setattr(AIService, "_call_groq_provider", staticmethod(groq_result))
    with app.app_context():
        from flask import current_app
        current_app.config.update({
            "AI_PROVIDER": "auto",
            "GEMINI_API_KEY": "test-gemini-key",
            "GROQ_API_KEY": "test-groq-key",
        })
        result = AIService._call_gemini_json(
            "Return a rubric object",
            validator=AIService._valid_evaluation_payload,
        )
    assert result == valid_payload
    assert calls == ["groq"]
