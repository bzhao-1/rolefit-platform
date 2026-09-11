import os

from rolefit_platform.profile import BASE_RESUME
from rolefit_platform.resume import tailor_resume
from rolefit_platform.resume_match import load_resume_text, resume_match
from rolefit_platform.storage import get_job, list_jobs, list_missing_tailoring_jobs, save_tailored_resume


CANONICAL_EDITABLE_RESUME_PATH = os.environ.get("ROLEFIT_CANONICAL_RESUME")
CANONICAL_RESUME_FOR_MATCHING = os.environ.get("ROLEFIT_RESUME_FOR_MATCHING") or CANONICAL_EDITABLE_RESUME_PATH
DEFAULT_RESUME_PATH = CANONICAL_RESUME_FOR_MATCHING


def configured_resume(source=None):
    path = source or DEFAULT_RESUME_PATH
    if path:
        return load_resume_text(path), os.path.abspath(os.path.expanduser(path))
    return BASE_RESUME, "built-in sample resume"


def job_text(job):
    return " ".join([
        job.get("role") or "",
        job.get("company") or "",
        job.get("location") or "",
        job.get("description") or "",
    ])


def build_tailored_resume(job, resume_text=None, resume_source=None):
    if resume_text is None:
        resume, resolved_source = configured_resume(resume_source)
    else:
        resume, resolved_source = resume_text, resume_source or "provided resume text"
    text = job_text(job)
    tailored = tailor_resume(text, resume, job.get("role"))
    match = resume_match(text, resume)
    return {
        "resume_source": resolved_source,
        "resume_match_score": match["resume_match_score"],
        "readiness": match["readiness"],
        "position_as": tailored["position_as"],
        "rewritten_bullets": tailored["rewritten_bullets"],
        "rewritten_bullet_records": tailored["rewritten_bullet_records"],
        "projects": tailored.get("projects") or [],
        "keywords_to_inject": tailored["keywords_to_inject"],
        "supported_keywords_to_surface": tailored["supported_keywords_to_surface"],
        "gap_keywords": tailored["gap_keywords"],
        "experience_to_emphasize": tailored.get("experience_to_emphasize") or [],
        "gaps_in_fit": tailored["gaps_in_fit"],
        "covered_keywords": match["covered_keywords"],
        "missing_keywords": match["missing_keywords"],
    }


def auto_tailor_job(db_path, job_id, resume_path=None):
    job = get_job(db_path, job_id)
    if not job:
        return None
    resume, source = configured_resume(resume_path)
    tailored = build_tailored_resume(job, resume, source)
    save_tailored_resume(db_path, job_id, tailored)
    return tailored


def auto_tailor_jobs(db_path, resume_path=None, missing_only=False, limit=500):
    resume, source = configured_resume(resume_path)
    jobs = list_missing_tailoring_jobs(db_path, limit) if missing_only else list_jobs(db_path, limit)
    generated = []
    for job in jobs:
        tailored = build_tailored_resume(job, resume, source)
        save_tailored_resume(db_path, job["id"], tailored)
        generated.append({
            "id": job["id"],
            "company": job.get("company"),
            "role": job.get("role"),
            "resume_match_score": tailored["resume_match_score"],
            "readiness": tailored["readiness"],
        })
    return {"generated": generated, "count": len(generated), "resume_source": source}
