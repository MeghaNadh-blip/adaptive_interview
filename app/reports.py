"""Reports detail and export routes."""
from bson import ObjectId
from flask import Blueprint, render_template, abort, send_file, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from io import BytesIO
from datetime import datetime
from app.extensions import get_db
from app.services.report_service import ReportService
from app.services.question_service import QuestionService
from app.services.ai_service import AIService

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

@reports_bp.route("/<session_id>")
@login_required
def detail(session_id):
    db = get_db()
    if not ObjectId.is_valid(session_id):
        abort(404)
    session = db.interview_sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        abort(404)

    # Ownership / authorization check
    if session["candidate_id"] != current_user.id and not current_user.is_recruiter:
        abort(403)

    report = ReportService.generate_or_get_report(session_id)
    questions = QuestionService.get_session_questions(session_id)
    answers = list(db.answers.find({"session_id": str(session_id)}))
    evaluations = list(db.evaluations.find({"session_id": str(session_id)}))
    integrity_events = list(db.integrity_events.find({"session_id": str(session_id)}))

    # Older evaluation documents may predate evaluation_status, or may have been
    # saved without a usable score. Count those as retryable too, not just rows
    # explicitly marked "unavailable".
    evaluations_by_question = {str(e.get("question_id")): e for e in evaluations}
    retryable_evaluations = 0
    for answer in answers:
        evaluation = evaluations_by_question.get(str(answer.get("question_id")))
        is_scored = (
            evaluation is not None
            and evaluation.get("evaluation_status", "completed") == "completed"
            and isinstance(evaluation.get("weighted_score"), (int, float))
            and not isinstance(evaluation.get("weighted_score"), bool)
        )
        if not is_scored:
            retryable_evaluations += 1
    recruiter_reviews = list(db.recruiter_reviews.find({"session_id": str(session_id)}))

    ans_map = {str(a["question_id"]): a for a in answers}
    eval_map = {str(e["question_id"]): e for e in evaluations}

    qa_details = []
    for q in questions:
        qid = str(q["_id"])
        qa_details.append({
            "question": q,
            "answer": ans_map.get(qid),
            "evaluation": eval_map.get(qid)
        })

    return render_template(
        "report_detail.html",
        session=session,
        report=report,
        qa_details=qa_details,
        integrity_events=integrity_events,
        recruiter_reviews=recruiter_reviews,
        retryable_evaluations=retryable_evaluations
    )


@reports_bp.route("/<session_id>/retry-evaluations", methods=["POST"])
@login_required
def retry_evaluations(session_id):
    """Retry every saved answer without a valid completed evaluation.

    This intentionally handles legacy records that lack evaluation_status and
    answers whose evaluation document was never created, as well as explicit
    "unavailable" evaluations.
    """
    db = get_db()
    if not ObjectId.is_valid(session_id):
        abort(404)
    session = db.interview_sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        abort(404)
    if session["candidate_id"] != current_user.id and not current_user.is_recruiter:
        abort(403)

    answers = list(db.answers.find({"session_id": str(session_id)}))
    attempted = 0
    succeeded = 0
    skipped = 0

    for answer in answers:
        question_id = str(answer.get("question_id", ""))
        if not ObjectId.is_valid(question_id):
            skipped += 1
            continue
        question = db.questions.find_one({"_id": ObjectId(question_id)})
        if not question:
            skipped += 1
            continue

        old_eval = db.evaluations.find_one({
            "session_id": str(session_id), "question_id": question_id
        })
        old_score = old_eval.get("weighted_score") if old_eval else None
        old_status = old_eval.get("evaluation_status", "completed") if old_eval else "missing"
        already_scored = (
            old_eval is not None
            and old_status == "completed"
            and isinstance(old_score, (int, float))
            and not isinstance(old_score, bool)
        )
        if already_scored:
            continue

        attempted += 1
        try:
            result = AIService.evaluate_answer(
                question_text=question.get("question_text", ""),
                competency=question.get("competency", "Engineering"),
                assessment_criteria=question.get("assessment_criteria", []),
                answer_text=answer.get("answer_text", ""),
                time_limit=question.get("time_limit_seconds", 120),
                duration_seconds=answer.get("duration_seconds", 0),
            )
        except Exception as exc:
            # Avoid logging candidate answers, prompts, API keys, or provider payloads.
            current_app.logger.error(
                "Evaluation retry failed for session %s question %s (%s).",
                str(session_id)[:8], question_id[:8], type(exc).__name__
            )
            continue

        update = {
            "session_id": str(session_id),
            "question_id": question_id,
            "answer_id": str(answer["_id"]),
            "rubric_scores": result.get("rubric_scores", {}),
            "weighted_score": result.get("weighted_score"),
            "evidence": result.get("evidence", {}),
            "feedback": result.get("feedback", ""),
            "uncertainty": result.get("uncertainty", "high"),
            "human_review_required": result.get("human_review_required", True),
            "evaluation_status": result.get("evaluation_status", "unavailable"),
            "rubric_version": old_eval.get("rubric_version", "v1.2-five-dimension") if old_eval else "v1.2-five-dimension",
            "evaluated_at": datetime.utcnow(),
        }
        if old_eval:
            db.evaluations.update_one({"_id": old_eval["_id"]}, {"$set": update})
        else:
            db.evaluations.insert_one(update)

        if update["evaluation_status"] == "completed" and isinstance(update["weighted_score"], (int, float)) and not isinstance(update["weighted_score"], bool):
            succeeded += 1

    # Reports are cached, so rebuild the snapshot after any retry attempt.
    if attempted:
        db.interview_reports.delete_one({"session_id": str(session_id)})

    if succeeded and succeeded == attempted:
        flash(f"Successfully completed all {succeeded} retryable evaluation(s). The report has been refreshed.", "success")
    elif succeeded:
        flash(
            f"Completed {succeeded} of {attempted} retryable evaluation(s). The report has been refreshed; remaining evaluations still need another retry or human review.",
            "warning"
        )
    elif attempted:
        flash(
            f"Tried {attempted} evaluation(s), but none completed. Check the Flask terminal for the sanitized provider error and verify your AI provider, API key, and model before retrying.",
            "warning"
        )
    else:
        flash("No retryable saved answers were found. If a question is still unavailable, refresh the report and check the saved answer record.", "info")
    return redirect(url_for("reports.detail", session_id=session_id))

@reports_bp.route("/<session_id>/export-pdf")
@login_required
def export_pdf(session_id):
    db = get_db()
    if not ObjectId.is_valid(session_id):
        abort(404)
    session = db.interview_sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        abort(404)

    if session["candidate_id"] != current_user.id and not current_user.is_recruiter:
        abort(403)

    report = ReportService.generate_or_get_report(session_id)
    pdf_bytes = ReportService.generate_pdf_bytes(report)

    if not pdf_bytes:
        flash("PDF generator requires reportlab. You can print the report directly from your browser.", "info")
        return redirect(url_for("reports.detail", session_id=session_id))

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Interview_Report_{session.get('target_role','Role').replace(' ','_')}_{session_id[:8]}.pdf"
    )
