"""Recruiter Dashboard and Human Decision Recording Module."""
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import get_db
from app.utils.security import recruiter_required

recruiter_bp = Blueprint("recruiter", __name__, url_prefix="/recruiter")

@recruiter_bp.route("/dashboard")
@login_required
@recruiter_required
def dashboard():
    db = get_db()

    # Query completed or active sessions
    sessions = list(db.interview_sessions.find().sort("created_at", -1))
    candidates = list(db.users.find({"role": "candidate"}))
    reports = list(db.interview_reports.find())

    cand_map = {str(c["_id"]): c for c in candidates}
    report_map = {r["session_id"]: r for r in reports}

    session_cards = []
    for s in sessions:
        sid = str(s["_id"])
        cand = cand_map.get(s["candidate_id"], {})
        rep = report_map.get(sid, {})
        integ_events = list(db.integrity_events.find({"session_id": sid}))
        reviews = list(db.recruiter_reviews.find({"session_id": sid}))

        session_cards.append({
            "session": s,
            "candidate": cand,
            "report": rep,
            "integrity_count": len(integ_events),
            "latest_review": reviews[-1] if reviews else None
        })

    # Aggregated metrics
    total_candidates = len(candidates)
    total_interviews = len(sessions)
    completed_interviews = sum(1 for s in sessions if s.get("status") == "completed")

    return render_template(
        "recruiter_dashboard.html",
        session_cards=session_cards,
        total_candidates=total_candidates,
        total_interviews=total_interviews,
        completed_interviews=completed_interviews
    )

@recruiter_bp.route("/record-decision/<session_id>", methods=["POST"])
@login_required
@recruiter_required
def record_decision(session_id):
    db = get_db()
    if not ObjectId.is_valid(session_id):
        abort(404)
    session = db.interview_sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        abort(404)

    review_status = request.form.get("review_status")
    decision_notes = request.form.get("decision_notes", "").strip()

    valid_statuses = [
        "Further interview recommended",
        "Additional evidence required",
        "Human review completed",
        "Decision recorded by recruiter"
    ]
    if review_status not in valid_statuses:
        flash("Invalid decision status selected.", "danger")
        return redirect(url_for("reports.detail", session_id=session_id))

    review_doc = {
        "session_id": str(session_id),
        "recruiter_id": current_user.id,
        "recruiter_name": current_user.full_name,
        "review_status": review_status,
        "decision_notes": decision_notes,
        "reviewed_at": datetime.utcnow()
    }

    db.recruiter_reviews.insert_one(review_doc)
    flash(f"Human decision '{review_status}' recorded successfully.", "success")
    return redirect(url_for("reports.detail", session_id=session_id))
