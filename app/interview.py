"""Interview setup, live room, answer evaluation, and completion flow."""
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.extensions import get_db
from app.utils.security import candidate_required
from app.models import CandidateProfileModel
from app.services.question_service import QuestionService
from app.services.evaluation_service import EvaluationService
from app.services.report_service import ReportService
from app.services.ai_service import AIService

interview_bp = Blueprint("interview", __name__, url_prefix="/interview")

@interview_bp.route("/setup", methods=["GET", "POST"])
@login_required
@candidate_required
def setup():
    db = get_db()
    profile = CandidateProfileModel.get_by_user_id(current_user.id) or {}
    completion = CandidateProfileModel.calculate_completion(profile)

    if not completion["is_ready_for_interview"]:
        flash("Please complete your profile (upload resume and add GitHub URL) before starting an interview.", "warning")
        return redirect(url_for("profile.candidate_profile"))

    if request.method == "POST":
        target_role = request.form.get("target_role", "").strip() or profile.get("target_role", "Software Engineer")
        job_description = request.form.get("job_description", "").strip()
        difficulty = request.form.get("difficulty", "adaptive")
        try:
            question_count = int(request.form.get("question_count", 5))
            time_limit = int(request.form.get("time_limit", 120))
        except (TypeError, ValueError):
            flash("Choose a valid question count and time limit.", "danger")
            return render_template("interview_setup.html", profile=profile), 400
        if question_count not in {3, 5, 10} or time_limit not in {60, 120, 180}:
            flash("Choose one of the supported question counts and time limits.", "danger")
            return render_template("interview_setup.html", profile=profile), 400
        if not target_role or len(target_role) > 120:
            flash("Enter a target role of at most 120 characters.", "danger")
            return render_template("interview_setup.html", profile=profile), 400
        job_description = job_description[:12000]
        raw_competencies = request.form.get("competencies", "").strip()[:1500]

        if raw_competencies:
            competencies = [c.strip() for c in raw_competencies.split(",") if c.strip()]
        else:
            competencies = [
                f"{target_role} Architecture",
                "Database Design & Indexing",
                "Testing & Reliability",
                "System Concurrency"
            ]

        now = datetime.utcnow()
        # Save Job Requirements document
        job_req_doc = {
            "user_id": current_user.id,
            "target_role": target_role,
            "job_description": job_description or f"Senior engineering position focusing on {target_role} development.",
            "required_competencies": competencies,
            "preferred_competencies": ["Performance Tuning", "Distributed Systems"],
            "difficulty": difficulty,
            "question_count": question_count,
            "time_limit_per_question": time_limit,
            "created_at": now
        }
        jr_res = db.job_requirements.insert_one(job_req_doc)
        job_req_id = str(jr_res.inserted_id)

        # Create Interview Session
        session_doc = {
            "candidate_id": current_user.id,
            "candidate_name": current_user.full_name,
            "job_requirement_id": job_req_id,
            "target_role": target_role,
            "status": "in_progress",
            "configuration": {
                "total_questions": question_count,
                "time_limit_per_question": time_limit,
                "difficulty": difficulty
            },
            "current_question_index": 0,
            "started_at": now,
            "rubric_version": "v1.2-five-dimension",
            "created_at": now
        }
        s_res = db.interview_sessions.insert_one(session_doc)
        session_id = str(s_res.inserted_id)

        # Generate initial interview question plan
        resume_ev = db.evidence_sources.find_one({"user_id": current_user.id, "source_type": "resume"}) or {}
        github_ev = db.evidence_sources.find_one({"user_id": current_user.id, "source_type": "github"}) or {}

        QuestionService.create_interview_plan(
            session_id=session_id,
            user_id=current_user.id,
            target_role=target_role,
            job_description=job_req_doc["job_description"],
            competencies=competencies,
            resume_text=profile.get("resume_text", ""),
            github_summary=github_ev.get("source_summary", ""),
            question_count=question_count,
            time_limit=time_limit
        )

        return redirect(url_for("interview.room", session_id=session_id))

    return render_template("interview_setup.html", profile=profile)

@interview_bp.route("/<session_id>/room")
@login_required
def room(session_id):
    db = get_db()
    if not ObjectId.is_valid(session_id):
        abort(404)
    session = db.interview_sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        abort(404)

    # Ownership check
    if session["candidate_id"] != current_user.id and not current_user.is_recruiter:
        abort(403)

    if session["status"] == "completed":
        return redirect(url_for("interview.result", session_id=session_id))

    questions = QuestionService.get_session_questions(session_id)
    if not questions:
        flash("No questions found for this session.", "danger")
        return redirect(url_for("main.dashboard"))

    curr_idx = session.get("current_question_index", 0)
    if curr_idx >= len(questions):
        # Mark completed
        db.interview_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"status": "completed", "completed_at": datetime.utcnow()}}
        )
        ReportService.generate_or_get_report(session_id)
        return redirect(url_for("interview.result", session_id=session_id))

    current_question = questions[curr_idx]
    total_questions = len(questions)

    # Check if answer was already submitted for this question
    existing_answer = db.answers.find_one({
        "session_id": str(session_id),
        "question_id": str(current_question["_id"])
    })

    return render_template(
        "interview_room.html",
        session=session,
        current_question=current_question,
        question_index=curr_idx + 1,
        total_questions=total_questions,
        existing_answer=existing_answer
    )

@interview_bp.route("/<session_id>/submit-answer", methods=["POST"])
@login_required
@candidate_required
def submit_answer(session_id):
    db = get_db()
    if not ObjectId.is_valid(session_id):
        abort(404)
    session = db.interview_sessions.find_one({"_id": ObjectId(session_id)})
    if not session or session["candidate_id"] != current_user.id:
        abort(404)

    if session["status"] == "completed":
        return redirect(url_for("interview.result", session_id=session_id))

    question_id = request.form.get("question_id", "")
    answer_text = request.form.get("answer_text", "").strip()
    try:
        duration_seconds = int(request.form.get("duration_seconds", 0))
    except (TypeError, ValueError):
        flash("Invalid answer timing data. Please submit your answer again.", "danger")
        return redirect(url_for("interview.room", session_id=session_id))
    if not ObjectId.is_valid(question_id):
        abort(400)
    if len(answer_text) > 12000:
        flash("Your answer is too long. Please keep it under 12,000 characters.", "danger")
        return redirect(url_for("interview.room", session_id=session_id))
    duration_seconds = max(0, min(duration_seconds, 3600))
    is_timeout = request.form.get("is_timeout") == "true"
    question = db.questions.find_one({"_id": ObjectId(question_id), "session_id": str(session_id)})
    if not question:
        abort(400)
    expected_question = QuestionService.get_session_questions(session_id)
    idx = session.get("current_question_index", 0)
    if idx >= len(expected_question) or str(expected_question[idx].get("_id")) != question_id:
        flash("This question is no longer active. Refresh the interview page.", "warning")
        return redirect(url_for("interview.room", session_id=session_id))

    try:
        ans_doc, eval_doc = EvaluationService.evaluate_and_store_answer(
            session_id=session_id,
            question_id=question_id,
            candidate_id=current_user.id,
            answer_text=answer_text,
            duration_seconds=duration_seconds,
            timeout_status=is_timeout
        )

        # Generate at most two answer-dependent follow-ups per session. If AI is
        # unavailable, do not present a generic question as an adaptive one.
        current_question = question
        followups_added = int(session.get("adaptive_followups_added", 0))
        if (followups_added < 2 and not current_question.get("is_followup")
                and eval_doc and eval_doc.get("evaluation_status", "completed") == "completed"):
            later_questions = QuestionService.get_session_questions(session_id)
            remaining_competencies = [q.get("competency", "") for q in later_questions
                                      if q.get("sequence_number", 0) > current_question.get("sequence_number", 0)]
            followup = AIService.generate_adaptive_followup(
                target_role=session.get("target_role", "Software Engineer"),
                prev_question=current_question.get("question_text", ""),
                prev_answer=answer_text,
                prev_eval=eval_doc,
                remaining_competencies=remaining_competencies
            )
            if followup:
                inserted = QuestionService.insert_adaptive_followup(
                    session_id, current_question, followup,
                    time_limit=session.get("configuration", {}).get("time_limit_per_question", 120)
                )
                if inserted:
                    followups_added += 1
                    db.interview_sessions.update_one(
                        {"_id": ObjectId(session_id)},
                        {"$set": {"adaptive_followups_added": followups_added}}
                    )

        curr_idx = session.get("current_question_index", 0)
        new_idx = curr_idx + 1
        questions = QuestionService.get_session_questions(session_id)
        db.interview_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {
                "current_question_index": new_idx,
                "configuration.total_questions": len(questions)
            }}
        )

        if new_idx >= len(questions):
            db.interview_sessions.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {"status": "completed", "completed_at": datetime.utcnow()}}
            )
            # Synthesize final report
            ReportService.generate_or_get_report(session_id)
            flash("Interview completed successfully! Here is your explainable performance report.", "success")
            return redirect(url_for("interview.result", session_id=session_id))

        return redirect(url_for("interview.room", session_id=session_id))

    except Exception as e:
        flash(f"Error evaluating answer: {str(e)}", "danger")
        return redirect(url_for("interview.room", session_id=session_id))

@interview_bp.route("/<session_id>/result")
@login_required
def result(session_id):
    db = get_db()
    if not ObjectId.is_valid(session_id):
        abort(404)
    session = db.interview_sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        abort(404)

    # Ownership check
    if session["candidate_id"] != current_user.id and not current_user.is_recruiter:
        abort(403)

    report = ReportService.generate_or_get_report(session_id)
    questions = QuestionService.get_session_questions(session_id)
    answers = list(db.answers.find({"session_id": str(session_id)}))
    evaluations = list(db.evaluations.find({"session_id": str(session_id)}))
    integrity_events = list(db.integrity_events.find({"session_id": str(session_id)}))

    q_map = {str(q["_id"]): q for q in questions}
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
        "interview_result.html",
        session=session,
        report=report,
        qa_details=qa_details,
        integrity_events=integrity_events
    )
