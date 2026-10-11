"""Integrity event API route for browser telemetry recording."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.integrity_service import IntegrityService
from app.extensions import get_db
from bson import ObjectId

integrity_bp = Blueprint("integrity", __name__, url_prefix="/integrity")

@integrity_bp.route("/log-event", methods=["POST"])
@login_required
def log_event():
    """Receives JSON events from browser client during active interview."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    event_type = data.get("event_type", "visibility_hidden")
    context = data.get("context", "")
    question_id = data.get("question_id")

    if not isinstance(session_id, str) or not ObjectId.is_valid(session_id):
        return jsonify({"status": "error", "message": "Invalid session_id"}), 400
    allowed_events = {"visibility_hidden", "fullscreen_exited", "window_blur", "navigation_attempt", "rapid_duplicate_submission", "session_anomaly"}
    if event_type not in allowed_events:
        return jsonify({"status": "error", "message": "Unsupported event type"}), 400
    if not isinstance(context, str):
        context = ""
    context = context[:300]
    if question_id is not None and (not isinstance(question_id, str) or not ObjectId.is_valid(question_id)):
        return jsonify({"status": "error", "message": "Invalid question_id"}), 400

    db = get_db()
    session = db.interview_sessions.find_one({"_id": ObjectId(session_id)})
    if not session or session.get("candidate_id") != current_user.id or session.get("status") != "in_progress":
        return jsonify({"status": "forbidden", "message": "Unauthorized or inactive session"}), 403

    event_doc = IntegrityService.log_event(
        session_id=session_id,
        candidate_id=current_user.id,
        event_type=event_type,
        context=context,
        question_id=question_id
    )

    return jsonify({
        "status": "success",
        "event_id": str(event_doc["_id"]),
        "recorded_at": event_doc["recorded_at"].isoformat()
    })
