from rolefit_platform.resume import tailor_resume
from rolefit_platform.resume_match import load_resume_text, resume_match
from rolefit_platform.storage import get_job, list_jobs, list_missing_tailoring_jobs, save_tailored_resume


DEFAULT_RESUME_PATH = None


def job_text(job):
    return " ".join([
        job.get("role") or "",
        job.get("company") or "",
        job.get("location") or "",
        job.get("description") or "",
    ])


def build_tailored_resume(job, resume_text=None, resume_source=None):
    resume = resume_text or load_resume_text(DEFAULT_RESUME_PATH)
    text = job_text(job)
    tailored = tailor_resume(text, resume)
    match = resume_match(text, resume)
    return {
        "resume_source": resume_source or "built-in sample resume",
        "resume_match_score": match["resume_match_score"],
        "readiness": match["readiness"],
        "position_as": tailored["position_as"],
        "rewritten_bullets": tailored["rewritten_bullets"],
        "keywords_to_inject": tailored["keywords_to_inject"],
        "experience_to_emphasize": tailored.get("experience_to_emphasize") or [],
        "gaps_in_fit": tailored["gaps_in_fit"],
        "covered_keywords": match["covered_keywords"],
        "missing_keywords": match["missing_keywords"],
    }


def auto_tailor_job(db_path, job_id, resume_path=None):
    job = get_job(db_path, job_id)
    if not job:
        return None
    source = resume_path or DEFAULT_RESUME_PATH
    resume = load_resume_text(source)
    tailored = build_tailored_resume(job, resume, source)
    save_tailored_resume(db_path, job_id, tailored)
    return tailored


def auto_tailor_jobs(db_path, resume_path=None, missing_only=False, limit=500):
    source = resume_path or DEFAULT_RESUME_PATH
    resume = load_resume_text(source)
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
