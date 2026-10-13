"""Candidate Profile Module: resume upload, GitHub verification, and evidence collection."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models import CandidateProfileModel
from app.extensions import get_db
from app.utils.security import candidate_required
from app.utils.validators import validate_github_url, validate_linkedin_url
from app.services.resume_service import ResumeService
from app.services.github_service import GithubService
from app.services.ai_service import AIService

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

@profile_bp.route("/", methods=["GET", "POST"])
@login_required
@candidate_required
def candidate_profile():
    db = get_db()
    profile = CandidateProfileModel.get_by_user_id(current_user.id) or {}
    completion = CandidateProfileModel.calculate_completion(profile)

    if request.method == "POST":
        github_url = request.form.get("github_url", "").strip()
        linkedin_url = request.form.get("linkedin_url", "").strip()
        target_role = request.form.get("target_role", "").strip()
        experience_level = request.form.get("experience_level", "Mid-Level (2-4 Years)")
        preferred_duration = request.form.get("preferred_duration", "15")

        # Validate GitHub URL
        valid_gh, gh_msg = validate_github_url(github_url)
        if not valid_gh:
            flash(gh_msg, "danger")
            return render_template("profile.html", profile=profile, completion=completion)

        # Validate LinkedIn URL (optional)
        valid_li, li_msg = validate_linkedin_url(linkedin_url)
        if not valid_li:
            flash(li_msg, "danger")
            return render_template("profile.html", profile=profile, completion=completion)

        update_data = {
            "github_url": github_url,
            "linkedin_url": linkedin_url,
            "target_role": target_role,
            "experience_level": experience_level,
            "preferred_duration": preferred_duration
        }

        # Check for resume upload
        resume_file = request.files.get("resume_pdf")
        if resume_file and resume_file.filename:
            success, result = ResumeService.save_and_extract_text(resume_file)
            if not success:
                flash(f"Resume Upload Failed: {result}", "danger")
                return render_template("profile.html", profile=profile, completion=completion)

            update_data["resume_storage_name"] = result["storage_name"]
            update_data["resume_original_name"] = result["original_name"]
            update_data["resume_text"] = result["text"]

            # Trigger AI analysis for resume evidence
            try:
                ai_resume_data = AIService.analyze_resume(result["text"])
                db.evidence_sources.update_one(
                    {"user_id": current_user.id, "source_type": "resume"},
                    {"$set": {
                        "user_id": current_user.id,
                        "source_type": "resume",
                        "source_summary": ai_resume_data.get("summary", ""),
                        "extracted_skills": ai_resume_data.get("extracted_skills", []),
                        "evidence_references": ai_resume_data.get("evidence_references", []),
                        "retrieval_status": "verified" if ai_resume_data.get("analysis_status") == "completed" else "unavailable",
                        "retrieved_at": datetime.utcnow()
                    }},
                    upsert=True
                )
            except Exception as e:
                current_app.logger.warning(f"Resume evidence parsing error: {e}")

        # If GitHub URL changed or no github evidence exists, fetch public repositories
        existing_gh_ev = db.evidence_sources.find_one({"user_id": current_user.id, "source_type": "github"})
        if not existing_gh_ev or profile.get("github_url") != github_url:
            gh_data = GithubService.fetch_public_evidence(github_url)
            db.evidence_sources.update_one(
                {"user_id": current_user.id, "source_type": "github"},
                {"$set": {
                    "user_id": current_user.id,
                    "source_type": "github",
                    "source_url": github_url,
                    "source_summary": gh_data.get("summary", ""),
                    "extracted_skills": gh_data.get("extracted_skills", []),
                    "evidence_references": [
                        {"item": f"repo: {r['name']}", "details": f"{r['description']} ({r['language']})", "source": "GitHub Public API"}
                        for r in gh_data.get("repositories", [])
                    ],
                    "retrieval_status": "verified" if gh_data.get("status") == "success" else "parsed",
                    "retrieved_at": datetime.utcnow()
                }},
                upsert=True
            )

        CandidateProfileModel.upsert(current_user.id, update_data)
        # Only remove the old resume after the new profile reference has been saved.
        old_resume = profile.get("resume_storage_name")
        new_resume = update_data.get("resume_storage_name")
        if old_resume and new_resume and old_resume != new_resume:
            ResumeService.delete_file(old_resume)
        flash("Profile updated and evidence gathered successfully!", "success")
        return redirect(url_for("profile.candidate_profile"))

    # Fetch evidence sources to display
    resume_evidence = db.evidence_sources.find_one({"user_id": current_user.id, "source_type": "resume"})
    github_evidence = db.evidence_sources.find_one({"user_id": current_user.id, "source_type": "github"})

    return render_template(
        "profile.html",
        profile=profile,
        completion=completion,
        resume_evidence=resume_evidence,
        github_evidence=github_evidence
    )

@profile_bp.route("/delete-resume", methods=["POST"])
@login_required
@candidate_required
def delete_resume():
    """Safely delete candidate's resume and extracted evidence."""
    db = get_db()
    profile = CandidateProfileModel.get_by_user_id(current_user.id)
    if profile and profile.get("resume_storage_name"):
        ResumeService.delete_file(profile["resume_storage_name"])
        db.candidate_profiles.update_one(
            {"user_id": current_user.id},
            {"$unset": {
                "resume_storage_name": "",
                "resume_original_name": "",
                "resume_text": ""
            }}
        )
        db.evidence_sources.delete_one({"user_id": current_user.id, "source_type": "resume"})
        flash("Resume deleted successfully.", "info")
    return redirect(url_for("profile.candidate_profile"))
