import time

from rolefit_platform.auto_tailor import DEFAULT_RESUME_PATH, auto_tailor_jobs
from rolefit_platform.maintenance import cleanup_locations
from rolefit_platform.sources import pull_defaults
from rolefit_platform.storage import list_scrape_runs, list_top, save_scrape_run


def summarize_pull(result):
    added = []
    skipped_count = 0
    error_count = 0
    for company, payload in result.items():
        if payload.get("error"):
            error_count += 1
        for item in payload.get("added") or []:
            added.append(item)
        skipped_count += len(payload.get("skipped") or [])
    added.sort(key=lambda item: item.get("score") or 0, reverse=True)
    return added, skipped_count, error_count


def run_scraper_once(db_path, limit_per_company=50, resume_path=None):
    pull_result = pull_defaults(db_path, limit_per_company)
    cleanup = cleanup_locations(db_path)
    tailoring = auto_tailor_jobs(db_path, resume_path or DEFAULT_RESUME_PATH, True, 500)
    added, skipped_count, error_count = summarize_pull(pull_result)
    status = "completed_with_errors" if error_count else "completed"
    run = {
        "status": status,
        "limit_per_company": limit_per_company,
        "added_count": len(added),
        "skipped_count": skipped_count,
        "error_count": error_count,
        "summary": {
            "added": added[:20],
            "cleanup": cleanup,
            "tailored_count": tailoring.get("count", 0),
            "top_jobs": list_top(db_path, 10),
            "sources": pull_result,
        },
    }
    run["id"] = save_scrape_run(db_path, run)
    return run


def run_scraper_loop(db_path, interval_minutes=360, cycles=0, limit_per_company=50, resume_path=None):
    runs = []
    count = 0
    while True:
        runs.append(run_scraper_once(db_path, limit_per_company, resume_path))
        count += 1
        if cycles and count >= cycles:
            break
        time.sleep(max(interval_minutes, 1) * 60)
    return runs


def recent_agent_runs(db_path, limit=10):
    return list_scrape_runs(db_path, limit)
