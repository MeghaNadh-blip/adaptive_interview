"""Competency mapping and skill-gap intelligence service."""
from datetime import datetime
from bson import ObjectId
from app.extensions import get_db

class SkillGapService:

    @staticmethod
    def compute_competency_map(session_id):
        """
        Calculates status for each role competency based on resume claims,
        GitHub evidence, and actual interview evaluations.
        Persists results to competency_results collection.
        """
        db = get_db()
        session = db.interview_sessions.find_one({"_id": ObjectId(session_id)})
        if not session:
            return []

        job_req = db.job_requirements.find_one({"_id": ObjectId(session.get("job_requirement_id"))})
        required_competencies = job_req.get("required_competencies", []) if job_req else []
        preferred_competencies = job_req.get("preferred_competencies", []) if job_req else []
        all_target_skills = list(dict.fromkeys(required_competencies + preferred_competencies))

        # Fetch evidence sources
        user_id = session.get("candidate_id")
        resume_evidence = db.evidence_sources.find_one({"user_id": user_id, "source_type": "resume"}) or {}
        github_evidence = db.evidence_sources.find_one({"user_id": user_id, "source_type": "github"}) or {}

        resume_skills = [s.lower() for s in resume_evidence.get("extracted_skills", [])]
        github_skills = [s.lower() for s in github_evidence.get("extracted_skills", [])]

        # Fetch session questions and evaluations
        questions = list(db.questions.find({"session_id": str(session_id)}))
        evaluations = list(db.evaluations.find({"session_id": str(session_id)}))

        question_by_id = {str(q["_id"]): q for q in questions}
        eval_by_qid = {str(e["question_id"]): e for e in evaluations}

        results = []
        now = datetime.utcnow()

        for comp in all_target_skills:
            comp_lower = comp.lower()

            # Find matching questions
            matched_qids = []
            matched_scores = []
            for q in questions:
                q_comp = q.get("competency", "").lower()
                if comp_lower in q_comp or q_comp in comp_lower:
                    qid_str = str(q["_id"])
                    matched_qids.append(qid_str)
                    if qid_str in eval_by_qid:
                        evaluation = eval_by_qid[qid_str]
                        score = evaluation.get("weighted_score")
                        if evaluation.get("evaluation_status", "completed") == "completed" and isinstance(score, (int, float)):
                            matched_scores.append(score)

            # Determine sources
            sources = []
            if any(comp_lower in s for s in resume_skills):
                sources.append("Resume Claim")
            if any(comp_lower in s for s in github_skills):
                sources.append("GitHub Repository Artifacts")
            if matched_qids:
                sources.append("Interview Evaluation")

            # Determine Coverage Status
            coverage_status = "Not yet assessed"
            avg_score = None
            uncertainty = "low"
            notes = ""

            if matched_scores:
                avg_score = sum(matched_scores) / len(matched_scores)
                if avg_score >= 70:
                    coverage_status = "Demonstrated in interview"
                    notes = f"Demonstrated high proficiency in interview with average score of {round(avg_score)}%."
                    uncertainty = "low"
                elif avg_score >= 40:
                    coverage_status = "Partially demonstrated"
                    notes = f"Addressed core concepts with moderate score of {round(avg_score)}%."
                    uncertainty = "moderate"
                else:
                    coverage_status = "Insufficient evidence"
                    notes = f"Candidate attempted question but exhibited notable gaps ({round(avg_score)}%)."
                    uncertainty = "moderate"
            elif any(comp_lower in s for s in github_skills):
                coverage_status = "Project evidence found"
                notes = "Corroborated by accessible GitHub public repositories, but not directly tested in this interview."
                uncertainty = "moderate"
            elif any(comp_lower in s for s in resume_skills):
                coverage_status = "Claimed"
                notes = "Claimed on resume; not yet tested in this interview session. (Not assessed is NOT a failure)."
                uncertainty = "high"
            else:
                coverage_status = "Not yet assessed"
                notes = "Required competency for role, but not yet evaluated."
                uncertainty = "high"

            comp_doc = {
                "session_id": str(session_id),
                "competency": comp,
                "required_level": "Core Requirement" if comp in required_competencies else "Preferred",
                "evidence_sources": sources,
                "related_question_ids": matched_qids,
                "related_evaluation_ids": [str(eval_by_qid[qid]["_id"]) for qid in matched_qids if qid in eval_by_qid],
                "coverage_status": coverage_status,
                "score_if_applicable": round(avg_score, 1) if avg_score is not None else None,
                "uncertainty": uncertainty,
                "notes": notes,
                "updated_at": now
            }

            # Upsert into competency_results
            db.competency_results.update_one(
                {"session_id": str(session_id), "competency": comp},
                {"$set": comp_doc},
                upsert=True
            )
            results.append(comp_doc)

        return results
