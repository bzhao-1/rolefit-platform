from rolefit_platform.alignment import infrastructure_alignment
from rolefit_platform.location import location_fit
from rolefit_platform.profile import TARGET_PROFILE
from rolefit_platform.scoring import score_job
from rolefit_platform.text_utils import count_matches


def classify_job(text, company=None):
    score = score_job(text, company)
    alignment = infrastructure_alignment(text)
    location = location_fit(text)
    lower = text.lower()
    reasons = []

    if company and company.lower() in [name.lower() for name in TARGET_PROFILE["avoid_companies"]]:
        return {"decision": "Skip", "reasoning": "Explicit avoid company.", "score": score, "alignment": alignment}

    if score["negative_matches"]:
        reasons.append("Potential mismatch signals: " + ", ".join(score["negative_matches"][:6]) + ".")
    if not location["ok"]:
        reasons.append("Location mismatch: keep US-eligible roles or global/anywhere remote roles only.")
    elif location["category"] == "unknown":
        reasons.append("Location unclear; verify US or remote before applying.")
    if any(term in lower for term in ["support engineer", "technical support", "customer support", "help desk"]) and "software engineer" not in lower:
        reasons.append("Likely support/IT rather than real SWE.")
    if "frontend" in lower or "front-end" in lower:
        reasons.append("Frontend-heavy signal.")
    if score["level_points"] < 0:
        reasons.append("Level mismatch for 1-2 YOE.")
    if any(term in lower for term in ["senior", "sr. ", "sr ", "staff engineer", "principal"]):
        reasons.append("Avoided senior/staff/principal level signal.")
    if "engineering manager" in lower:
        reasons.append("Management role rather than SWE I/II fit.")

    backend_matches = count_matches(text, ["backend", "platform", "cloud", "infrastructure", "distributed", "api", "kubernetes"])
    if not backend_matches:
        reasons.append("Weak backend/platform signal.")

    if score["score"] >= 82 and alignment["similarity_score"] >= 55 and not reasons:
        decision = "High priority"
        reasons.append("Strong score, infrastructure alignment, and no major mismatch flags.")
    elif score["score"] >= 72 and alignment["similarity_score"] >= 45:
        decision = "High priority"
        reasons.append("Strong enough technical and company/level signal to apply directly.")
    elif score["score"] >= 62:
        decision = "Review selectively"
        reasons.append("Solid role, but a human review should confirm team scope and ownership.")
    elif score["score"] >= 48:
        decision = "Review selectively"
        reasons.append("Possible fit, but prioritize only if team or recruiter confirms backend/platform ownership.")
    else:
        decision = "Skip"
        reasons.append("Low score or too many mismatch signals.")

    if not location["ok"] or score["level_points"] < -10 or len(score["negative_matches"]) >= 3 or any(term in lower for term in ["senior", "sr. ", "sr ", "staff engineer", "principal"]) or "engineering manager" in lower:
        decision = "Skip"

    return {
        "decision": decision,
        "reasoning": " ".join(reasons),
        "score": score,
        "alignment": alignment,
    }
