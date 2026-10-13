"""Automated unit tests for Question sequencing and Interview lifecycle."""
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

def test_question_plan_generation_fallback(app, monkeypatch):
    """Test deterministic question generation when API key is not live."""
    monkeypatch.setattr(AIService, "_call_gemini_json", staticmethod(lambda *args, **kwargs: None))
    with app.app_context():
        questions = AIService.generate_question_plan(
            target_role="Python Backend Developer",
            job_description="FastAPI, PostgreSQL, Redis",
            competencies=["Async I/O", "Indexing", "Caching"],
            resume_text="Worked on async worker queues and PostgreSQL.",
            github_summary="Repositories with python scripts.",
            question_count=5,
            time_limit=120
        )

        assert len(questions) == 5
        for idx, q in enumerate(questions):
            assert q["sequence_number"] == idx + 1
            assert "question_text" in q
            assert "competency" in q
            assert q["time_limit_seconds"] == 120

def test_question_plan_replaces_unverified_resume_claims(app, monkeypatch):
    """AI-generated questions must not attribute an unsupported project or employer to a candidate."""
    generated = [
        {
            "sequence_number": 1,
            "question_text": "In your VignanAI project, how would you handle concurrency?",
            "competency": "System Concurrency",
            "difficulty": "medium",
            "question_type": "resume_specific",
            "evidence_reference": "VignanAI project",
            "relevance_reason": "Project-specific question",
            "assessment_criteria": ["Concurrency"],
        },
        {
            "sequence_number": 2,
            "question_text": "During your internship at nference Labs, how did you use pytest?",
            "competency": "Testing",
            "difficulty": "medium",
            "question_type": "resume_specific",
            "evidence_reference": "nference Labs",
            "relevance_reason": "Internship-specific question",
            "assessment_criteria": ["Testing"],
        },
        {
            "sequence_number": 3,
            "question_text": "Explain how to choose a compound database index.",
            "competency": "Database Indexing",
            "difficulty": "medium",
            "question_type": "role_technical",
            "evidence_reference": "Role requirement",
            "relevance_reason": "Tests indexing knowledge",
            "assessment_criteria": ["Index selection"],
        },
    ]
    monkeypatch.setattr(AIService, "_call_gemini_json", staticmethod(lambda *args, **kwargs: generated))
    with app.app_context():
        questions = AIService.generate_question_plan(
            target_role="Python Intern",
            job_description="Python and databases",
            competencies=["System Concurrency", "Testing", "Database Indexing"],
            resume_text="Student with Python coursework and database assignments.",
            github_summary="",
            question_count=3,
            time_limit=120,
        )
    assert len(questions) == 3
    assert "VignanAI" not in questions[0]["question_text"]
    assert "nference Labs" not in questions[1]["question_text"]
    assert "For the Python Intern role" in questions[0]["question_text"]
    assert "compound database index" in questions[2]["question_text"] or "Database Indexing" in questions[2]["question_text"]


def test_question_plan_rewrites_unsupported_experience_and_implementation_claims(app, monkeypatch):
    """Questions must not invent internship history or claim an unverified implementation."""
    generated = [
        {
            "sequence_number": 1,
            "question_text": "During your internship you assisted in debugging and testing backend application issues. What testing strategies did you use?",
            "competency": "Testing & Code Quality",
            "difficulty": "medium",
            "question_type": "resume_specific",
            "evidence_reference": "Internship",
            "relevance_reason": "Tests internship experience",
            "assessment_criteria": ["Unit testing", "CI"],
        },
        {
            "sequence_number": 2,
            "question_text": "In the VFSTR Academic AI Platform you designed secure authentication. Explain how you would secure its REST API.",
            "competency": "API Security",
            "difficulty": "medium",
            "question_type": "resume_specific",
            "evidence_reference": "VFSTR Academic AI Platform",
            "relevance_reason": "Tests implementation experience",
            "assessment_criteria": ["Authentication", "Rate limiting"],
        },
    ]
    monkeypatch.setattr(AIService, "_call_gemini_json", staticmethod(lambda *args, **kwargs: generated))
    with app.app_context():
        questions = AIService.generate_question_plan(
            target_role="Python Intern",
            job_description="Python REST APIs and testing",
            competencies=["Testing & Code Quality", "API Security"],
            resume_text="Student project work using Python, Flask, MongoDB, and Gemini API.",
            github_summary="",
            question_count=2,
            time_limit=120,
        )
    assert len(questions) == 2
    assert "During your internship" not in questions[0]["question_text"]
    assert "you designed secure authentication" not in questions[1]["question_text"]
    assert all("For the Python Intern role" in q["question_text"] for q in questions)


def test_fallback_questions_match_their_competency_and_avoid_unsupported_experience(app, monkeypatch):
    monkeypatch.setattr(AIService, "_call_gemini_json", staticmethod(lambda *args, **kwargs: None))
    competencies = ["Python Concurrency", "Testing & Code Quality", "Database Indexing", "Distributed Systems"]
    with app.app_context():
        questions = AIService.generate_question_plan(
            target_role="intern",
            job_description="Python, testing, databases, distributed systems",
            competencies=competencies,
            resume_text="Student coursework only.",
            github_summary="",
            question_count=8,
            time_limit=120,
        )
    assert len(questions) == 8
    for question in questions:
        assert question["competency"] in competencies
        assert question["competency"].casefold() in question["question_text"].casefold()
        assert "a intern" not in question["question_text"].casefold()
        assert "during your internship" not in question["question_text"].casefold()
