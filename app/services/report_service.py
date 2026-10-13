"""Final explainable report generation, aggregation, and export service."""
from datetime import datetime
from bson import ObjectId
from app.extensions import get_db
from app.services.skill_gap_service import SkillGapService

class ReportService:

    @staticmethod
    def generate_or_get_report(session_id):
        """
        Synthesizes a final explainable report from stored questions, answers,
        evaluations, integrity events, and competency mapping.
        """
        db = get_db()
        existing = db.interview_reports.find_one({"session_id": str(session_id)})
        if existing:
            return existing

        session = db.interview_sessions.find_one({"_id": ObjectId(session_id)})
        if not session:
            return None

        user = db.users.find_one({"_id": ObjectId(session["candidate_id"])})
        candidate_name = user.get("full_name", "Candidate") if user else "Candidate"
        target_role = session.get("target_role", "Software Engineer")

        # Ensure competency map is computed
        comp_results = SkillGapService.compute_competency_map(session_id)

        # Retrieve questions and evaluations
        questions = list(db.questions.find({"session_id": str(session_id)}).sort("sequence_number", 1))
        answers = list(db.answers.find({"session_id": str(session_id)}))
        evaluations = list(db.evaluations.find({"session_id": str(session_id)}))
        integrity_events = list(db.integrity_events.find({"session_id": str(session_id)}))

        # Only completed, numeric AI evaluations contribute to scores. Treat legacy
        # evaluation rows without a status as completed only when they contain a score.
        scored_evaluations = [
            e for e in evaluations
            if e.get("evaluation_status", "completed") == "completed"
            and isinstance(e.get("weighted_score"), (int, float))
            and not isinstance(e.get("weighted_score"), bool)
        ]
        scores = [e["weighted_score"] for e in scored_evaluations]
        overall_score = round(sum(scores) / len(scores), 1) if scores else None
        scored_question_ids = {str(e.get("question_id")) for e in scored_evaluations}
        answered_question_ids = {str(a.get("question_id")) for a in answers}
        evaluations_unavailable = len(answered_question_ids - scored_question_ids)
        score_is_provisional = evaluations_unavailable > 0

        tech_scores = [e.get("rubric_scores", {}).get("technical_correctness") for e in scored_evaluations if isinstance(e.get("rubric_scores", {}).get("technical_correctness"), (int, float))]
        depth_scores = [e.get("rubric_scores", {}).get("depth_of_understanding") for e in scored_evaluations if isinstance(e.get("rubric_scores", {}).get("depth_of_understanding"), (int, float))]
        prob_scores = [e.get("rubric_scores", {}).get("reasoning_problem_solving") for e in scored_evaluations if isinstance(e.get("rubric_scores", {}).get("reasoning_problem_solving"), (int, float))]
        relevance_scores = [e.get("rubric_scores", {}).get("relevance") for e in scored_evaluations if isinstance(e.get("rubric_scores", {}).get("relevance"), (int, float))]
        comm_scores = [e.get("rubric_scores", {}).get("explanation_clarity") for e in scored_evaluations if isinstance(e.get("rubric_scores", {}).get("explanation_clarity"), (int, float))]

        avg_tech = round(sum(tech_scores) / len(tech_scores), 1) if tech_scores else None
        avg_depth = round(sum(depth_scores) / len(depth_scores), 1) if depth_scores else None
        avg_prob = round(sum(prob_scores) / len(prob_scores), 1) if prob_scores else None
        avg_relevance = round(sum(relevance_scores) / len(relevance_scores), 1) if relevance_scores else None
        avg_comm = round(sum(comm_scores) / len(comm_scores), 1) if comm_scores else None

        # Synthesize strengths from evaluations
        strengths = []
        improvements = []
        for e in evaluations:
            for item in e.get("evidence", {}).get("what_was_correct", []):
                if item and item not in strengths and len(strengths) < 4:
                    strengths.append(item)
            for item in e.get("evidence", {}).get("what_was_incomplete_or_incorrect", []):
                if item and item not in improvements and len(improvements) < 4:
                    improvements.append(item)

        if not strengths:
            strengths = ["No verified strengths could be synthesized from the available evaluation evidence."]
        if not improvements:
            improvements = ["No verified improvement areas could be synthesized. Retry unavailable evaluations or arrange human review."]

        # Evidence counts
        demonstrated_count = sum(1 for c in comp_results if c.get("coverage_status") == "Demonstrated in interview")
        artifact_count = sum(1 for c in comp_results if c.get("coverage_status") == "Project evidence found")
        untested_count = sum(1 for c in comp_results if c.get("coverage_status") in ["Not yet assessed", "Claimed"])

        # Structured learning recommendations
        learning_recs = []
        for c in comp_results:
            if c.get("coverage_status") in ["Partially demonstrated", "Insufficient evidence", "Not yet assessed"]:
                learning_recs.append({
                    "skill": c.get("competency"),
                    "action_item": f"Review advanced patterns and practical hands-on benchmarks in {c.get('competency')}.",
                    "resource_type": "Deep-Dive Architecture & Documentation",
                    "priority": "high" if c.get("required_level") == "Core Requirement" else "medium"
                })

        if not learning_recs:
            learning_recs.append({
                "skill": "Systems Scalability",
                "action_item": "Deepen study of distributed consensus and high-throughput messaging guarantees.",
                "resource_type": "Technical Whitepapers",
                "priority": "medium"
            })

        practice_questions = [
            f"How do you design a high-throughput, fault-tolerant worker pipeline for {target_role}?",
            "What strategies do you employ to diagnose and eliminate database lock contention in production?"
        ]

        now = datetime.utcnow()
        report_doc = {
            "session_id": str(session_id),
            "candidate_id": str(session["candidate_id"]),
            "candidate_name": candidate_name,
            "target_role": target_role,
            "report_version": "1.0-explainable",
            "score_summary": {
                "overall_score": overall_score,
                "evaluations_available": len(scored_evaluations),
                "evaluations_unavailable": evaluations_unavailable,
                "questions_answered": len(answers),
                "total_questions": len(questions),
                "score_is_provisional": score_is_provisional,
                "technical_mastery": avg_tech,
                "depth_score": avg_depth,
                "problem_solving": avg_prob,
                "relevance": avg_relevance,
                "communication": avg_comm
            },
            "strengths": strengths,
            "areas_for_improvement": improvements,
            "competency_results": comp_results,
            "evidence_summary": {
                "interview_demonstrated_skills": demonstrated_count,
                "github_artifacts_validated": artifact_count,
                "untested_claims": untested_count
            },
            "integrity_summary": {
                "total_events": len(integrity_events),
                "events": integrity_events
            },
            "limitations": [
                "Evaluation assesses text-based architectural reasoning and technical articulation under timed conditions.",
                "Hands-on live pair programming and soft-skills collaboration were not evaluated in this automated session.",
                "AI evaluations provide structured decision support and must not be used as autonomous hiring determinations."
            ],
            "learning_recommendations": learning_recs[:4],
            "recommended_practice_questions": practice_questions,
            "created_at": now
        }

        db.interview_reports.insert_one(report_doc)
        return report_doc

    @staticmethod
    def generate_pdf_bytes(report_data):
        """Generates a downloadable PDF report using ReportLab if available."""
        try:
            from io import BytesIO
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
            styles = getSampleStyleSheet()

            elements = []
            title_style = ParagraphStyle(
                'TitleStyle',
                parent=styles['Heading1'],
                fontSize=20,
                leading=24,
                textColor=colors.HexColor('#0f172a')
            )
            h2_style = ParagraphStyle(
                'H2Style',
                parent=styles['Heading2'],
                fontSize=14,
                leading=18,
                textColor=colors.HexColor('#1e293b')
            )
            body_style = styles['Normal']

            elements.append(Paragraph("Adaptive Interview Intelligence — Explainable Report", title_style))
            elements.append(Spacer(1, 10))

            meta_text = f"<b>Candidate:</b> {report_data.get('candidate_name')} | <b>Role:</b> {report_data.get('target_role')} | <b>Date:</b> {datetime.utcnow().strftime('%Y-%m-%d')}"
            elements.append(Paragraph(meta_text, body_style))
            elements.append(Spacer(1, 15))

            score_summary = report_data.get("score_summary", {})
            overall = score_summary.get("overall_score")
            overall_label = f"{overall}/100" if isinstance(overall, (int, float)) else "Unavailable — human review needed"
            score_p = Paragraph(f"<b>Overall Rubric Score:</b> {overall_label} | Questions Answered: {score_summary.get('questions_answered')}/{score_summary.get('total_questions')}", h2_style)
            elements.append(score_p)
            elements.append(Spacer(1, 10))

            elements.append(Paragraph("<b>Demonstrated Strengths:</b>", h2_style))
            for s in report_data.get("strengths", []):
                elements.append(Paragraph(f"• {s}", body_style))
            elements.append(Spacer(1, 10))

            elements.append(Paragraph("<b>Competency & Skill Gap Statuses:</b>", h2_style))
            table_data = [["Competency", "Coverage Status", "Score"]]
            for c in report_data.get("competency_results", []):
                table_data.append([
                    c.get("competency", ""),
                    c.get("coverage_status", ""),
                    f"{c.get('score_if_applicable')}%" if c.get("score_if_applicable") else "N/A"
                ])
            t = Table(table_data, colWidths=[240, 200, 80])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0f172a')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('FONTSIZE', (0,0), (-1,-1), 9),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 15))

            elements.append(Paragraph("<b>Assessment Limitations:</b>", h2_style))
            for lim in report_data.get("limitations", []):
                elements.append(Paragraph(f"• {lim}", body_style))

            doc.build(elements)
            buffer.seek(0)
            return buffer.getvalue()
        except Exception as e:
            return None
