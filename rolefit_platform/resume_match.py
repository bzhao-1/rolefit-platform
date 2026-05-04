import re

from rolefit_platform.profile import BASE_RESUME
from rolefit_platform.resume import tailor_resume
from rolefit_platform.storage import list_jobs
from rolefit_platform.text_utils import count_matches, normalize, words


MATCH_GROUPS = [
    ("languages", 18, ["python", "java", "go", "sql", "c++", "rust", "typescript"]),
    ("backend/platform", 18, ["backend", "platform", "cloud", "infrastructure", "api", "service", "distributed systems"]),
    ("cloud/devops", 16, ["kubernetes", "docker", "terraform", "linux", "ci/cd", "deployment", "release", "build"]),
    ("reliability/testing", 16, ["validation", "testing", "automation", "observability", "monitoring", "alerting", "reliability"]),
    ("data/security", 14, ["data pipeline", "metrics", "telemetry", "security", "compliance", "vulnerability", "postgresql"]),
    ("scale/production", 18, ["production", "scale", "fleet", "multi-tenant", "high availability", "latency", "performance"]),
]


def load_resume_text(path=None):
    if not path:
        return BASE_RESUME
    lower = path.lower()
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return BASE_RESUME
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def likely_job_requirements(job_text):
    candidates = []
    for group, weight, terms in MATCH_GROUPS:
        candidates.extend(terms)
    extra = [
        "grpc", "rest", "microservices", "prometheus", "grafana", "kafka", "flink",
        "spark", "clickhouse", "postgres", "aws", "gcp", "azure", "gpu",
        "ai infrastructure", "ml infrastructure", "control plane", "data plane",
    ]
    candidates.extend(extra)
    found = count_matches(job_text, candidates)
    return list(dict.fromkeys(found))


def resume_match(job_text, resume_text=None):
    resume = resume_text or BASE_RESUME
    total = 0
    possible = 0
    details = []
    for group, weight, terms in MATCH_GROUPS:
        job_terms = count_matches(job_text, terms)
        if not job_terms:
            continue
        resume_terms = count_matches(resume, job_terms)
        possible += weight
        ratio = len(resume_terms) / max(len(job_terms), 1)
        points = round(weight * min(ratio, 1.0))
        total += points
        missing = [term for term in job_terms if term not in resume_terms]
        details.append({
            "group": group,
            "points": points,
            "max": weight,
            "covered": resume_terms,
            "missing": missing,
        })

    requirements = likely_job_requirements(job_text)
    covered = count_matches(resume, requirements)
    missing = [term for term in requirements if term not in covered]
    score = round((total / possible) * 100) if possible else 50

    if score >= 80:
        readiness = "strong current-resume match"
    elif score >= 65:
        readiness = "good match with light tailoring"
    elif score >= 50:
        readiness = "possible match, needs careful tailoring"
    else:
        readiness = "weak current-resume match"

    return {
        "resume_match_score": max(0, min(100, score)),
        "readiness": readiness,
        "covered_keywords": covered[:20],
        "missing_keywords": missing[:20],
        "details": details,
    }


def job_text(job):
    return " ".join([
        job.get("role") or "",
        job.get("company") or "",
        job.get("location") or "",
        job.get("description") or "",
    ])


def top_resume_matches(db_path, resume_text=None, limit=5):
    resume = resume_text or BASE_RESUME
    rows = list_jobs(db_path, 300)
    ranked = []
    for job in rows:
        text = job_text(job)
        match = resume_match(text, resume)
        combined = round((job.get("score") or 0) * 0.55 + match["resume_match_score"] * 0.45)
        tailored = tailor_resume(text, resume)
        ranked.append({
            "id": job.get("id"),
            "company": job.get("company"),
            "role": job.get("role"),
            "location": job.get("location"),
            "link": job.get("link"),
            "role_score": job.get("score"),
            "infrastructure_alignment_score": job.get("infrastructure_alignment_score"),
            "resume_match_score": match["resume_match_score"],
            "combined_priority_score": combined,
            "apply_decision": job.get("apply_decision"),
            "readiness": match["readiness"],
            "covered_keywords": match["covered_keywords"],
            "missing_keywords": match["missing_keywords"],
            "position_as": tailored["position_as"],
            "rewritten_bullets": tailored["rewritten_bullets"],
            "keywords_to_inject": tailored["keywords_to_inject"],
            "gaps_in_fit": tailored["gaps_in_fit"],
        })
    ranked.sort(key=lambda item: (item["combined_priority_score"], item["role_score"] or 0), reverse=True)
    return ranked[:limit]
