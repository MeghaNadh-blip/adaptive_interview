"""Answer evaluation, rubric score calculation, and persistence service."""
from datetime import datetime
from bson import ObjectId
from app.extensions import get_db
from app.services.ai_service import AIService

RUBRIC_VERSION = "v1.2-five-dimension"

class EvaluationService:

    @staticmethod
    def evaluate_and_store_answer(session_id, question_id, candidate_id, answer_text, duration_seconds, timeout_status=False):
        """
        Records the answer, evaluates it against the 5-dimension rubric,
        and saves both answer and evaluation documents.
        """
        db = get_db()
        now = datetime.utcnow()

        # Check for existing answer to prevent duplicate submission
        existing_answer = db.answers.find_one({
            "session_id": str(session_id),
            "question_id": str(question_id)
        })
        if existing_answer:
            return existing_answer, db.evaluations.find_one({"answer_id": str(existing_answer["_id"])})

        # Fetch question details for criteria
        question = db.questions.find_one({"_id": ObjectId(question_id)})
        if not question:
            raise ValueError(f"Question {question_id} not found.")

        # Persist answer document
        answer_doc = {
            "session_id": str(session_id),
            "question_id": str(question_id),
            "candidate_id": str(candidate_id),
            "answer_text": answer_text.strip(),
            "duration_seconds": int(duration_seconds),
            "timeout_status": bool(timeout_status),
            "submission_status": "submitted" if not timeout_status else "auto_submitted",
            "submitted_at": now
        }
        ans_res = db.answers.insert_one(answer_doc)
        answer_id = ans_res.inserted_id
        answer_doc["_id"] = answer_id

        # Evaluate answer with AI service
        eval_result = AIService.evaluate_answer(
            question_text=question["question_text"],
            competency=question.get("competency", "Engineering"),
            assessment_criteria=question.get("assessment_criteria", []),
            answer_text=answer_text,
            time_limit=question.get("time_limit_seconds", 120),
            duration_seconds=duration_seconds
        )

        # Store evaluation document
        eval_doc = {
            "session_id": str(session_id),
            "question_id": str(question_id),
            "answer_id": str(answer_id),
            "rubric_scores": eval_result["rubric_scores"],
            "weighted_score": eval_result["weighted_score"],
            "evidence": eval_result["evidence"],
            "feedback": eval_result["feedback"],
            "uncertainty": eval_result["uncertainty"],
            "human_review_required": eval_result["human_review_required"],
            "evaluation_status": eval_result.get("evaluation_status", "completed"),
            "rubric_version": RUBRIC_VERSION,
            "evaluated_at": now
        }
        eval_res = db.evaluations.insert_one(eval_doc)
        eval_doc["_id"] = eval_res.inserted_id

        return answer_doc, eval_doc
