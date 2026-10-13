"""Main Blueprint: Landing page and Authoritative Candidate Dashboard."""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import CandidateProfileModel
from app.extensions import get_db

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.is_recruiter:
            return redirect(url_for("recruiter.dashboard"))
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")

@main_bp.route("/about")
def about():
    """Public overview of the five connected platform modules."""
    return render_template("about.html")

@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Authoritative Candidate Dashboard route."""
    if current_user.is_recruiter:
        return redirect(url_for("recruiter.dashboard"))

    db = get_db()
    profile = CandidateProfileModel.get_by_user_id(current_user.id) or {}
    completion = CandidateProfileModel.calculate_completion(profile)

    # Fetch candidate's past interview sessions
    sessions = list(db.interview_sessions.find({"candidate_id": current_user.id}).sort("created_at", -1))
    reports = list(db.interview_reports.find({"candidate_id": current_user.id}))
    report_map = {r["session_id"]: r for r in reports}

    session_items = []
    for s in sessions:
        sid = str(s["_id"])
        session_items.append({
            "session": s,
            "report": report_map.get(sid)
        })

    return render_template(
        "dashboard.html",
        profile=profile,
        completion=completion,
        sessions=session_items
    )
