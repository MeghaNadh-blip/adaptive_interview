"""Question plan creation, persistence, and adaptive sequencing service."""
from datetime import datetime
from bson import ObjectId
from app.extensions import get_db
from app.services.ai_service import AIService

class QuestionService:

    @staticmethod
    def create_interview_plan(session_id, user_id, target_role, job_description, competencies, resume_text, github_summary, question_count=10, time_limit=120):
        """Generates questions using AI service and persists them to MongoDB questions collection."""
        db = get_db()
        raw_questions = AIService.generate_question_plan(
            target_role=target_role,
            job_description=job_description,
            competencies=competencies,
            resume_text=resume_text,
            github_summary=github_summary,
            question_count=question_count,
            time_limit=time_limit
        )

        persisted_questions = []
        now = datetime.utcnow()

        for idx, q in enumerate(raw_questions):
            doc = {
                "session_id": str(session_id),
                "sequence_number": idx + 1,
                "question_text": q.get("question_text"),
                "competency": q.get("competency", "Core Engineering"),
                "difficulty": q.get("difficulty", "medium"),
                "question_type": q.get("question_type", "role_technical"),
                "evidence_reference": q.get("evidence_reference", "Role Requirement"),
                "relevance_reason": q.get("relevance_reason", "Core competency verification"),
                "assessment_criteria": q.get("assessment_criteria", ["Demonstrates core knowledge"]),
                "time_limit_seconds": int(q.get("time_limit_seconds", time_limit)),
                "is_followup": False,
                "created_at": now
            }
            res = db.questions.insert_one(doc)
            doc["_id"] = res.inserted_id
            persisted_questions.append(doc)

        return persisted_questions

    @staticmethod
    def get_session_questions(session_id):
        """Fetch all questions for a given session sorted by sequence number."""
        db = get_db()
        return list(db.questions.find({"session_id": str(session_id)}).sort("sequence_number", 1))

    @staticmethod
    def get_question_by_id(question_id):
        """Fetch question document by ID."""
        db = get_db()
        try:
            return db.questions.find_one({"_id": ObjectId(question_id)})
        except Exception:
            return None
    @staticmethod
    def insert_adaptive_followup(session_id, current_question, followup, time_limit=120):
        """Insert a validated follow-up immediately after its parent question."""
        if not isinstance(followup, dict) or not isinstance(followup.get("question_text"), str):
            return None
        text = followup["question_text"].strip()
        if not text or len(text) > 2000:
            return None
        db = get_db()
        current_sequence = int(current_question.get("sequence_number", 1))
        # Move later questions forward, then insert the follow-up in the next slot.
        later = list(db.questions.find({
            "session_id": str(session_id),
            "sequence_number": {"$gt": current_sequence}
        }).sort("sequence_number", -1))
        for question in later:
            db.questions.update_one(
                {"_id": question["_id"]},
                {"$set": {"sequence_number": int(question["sequence_number"]) + 1}}
            )
        try:
            followup_time_limit = int(followup.get("time_limit_seconds", time_limit))
        except (TypeError, ValueError):
            followup_time_limit = int(time_limit)
        doc = {
            "session_id": str(session_id),
            "sequence_number": current_sequence + 1,
            "question_text": text,
            "competency": str(followup.get("competency") or current_question.get("competency") or "Role competency")[:160],
            "difficulty": followup.get("difficulty") if followup.get("difficulty") in {"easy", "medium", "hard"} else "medium",
            "question_type": "adaptive_followup",
            "evidence_reference": "Previous interview answer and evaluation",
            "relevance_reason": str(followup.get("adaptation_reason") or "Follow-up selected based on the previous answer.")[:500],
            "assessment_criteria": [str(x)[:200] for x in followup.get("assessment_criteria", [])[:8] if isinstance(x, str)] if isinstance(followup.get("assessment_criteria", []), list) else [],
            "time_limit_seconds": max(30, min(followup_time_limit, 300)),
            "is_followup": True,
            "parent_question_id": str(current_question.get("_id")),
            "created_at": datetime.utcnow()
        }
        result = db.questions.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

