import argparse
import json
import os

from rolefit_platform.auto_tailor import DEFAULT_RESUME_PATH, auto_tailor_job, auto_tailor_jobs
from rolefit_platform.alignment import infrastructure_alignment
from rolefit_platform.classifier import classify_job
from rolefit_platform.maintenance import cleanup_locations
from rolefit_platform.prep import interview_prep
from rolefit_platform.outreach import outreach_message
from rolefit_platform.resume import tailor_resume
from rolefit_platform.resume_export import DEFAULT_OUTPUT_DIR, export_finished_resumes
from rolefit_platform.resume_match import load_resume_text, resume_match, top_resume_matches
from rolefit_platform.scoring import score_job
from rolefit_platform.sources import pull_defaults, pull_greenhouse, pull_lever
from rolefit_platform.storage import add_job, export_jobs, get_job, list_top, update_status
from rolefit_platform.text_utils import load_job_text
from rolefit_platform.web import serve


DEFAULT_DB = os.path.expanduser("~/.rolefit-platform/jobs.sqlite3")


def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def ensure_db_dir(path):
    directory = os.path.dirname(os.path.abspath(os.path.expanduser(path)))
    if directory and not os.path.exists(directory):
        os.makedirs(directory)


def resolve_text(args):
    if getattr(args, "job_id", None):
        job = get_job(args.db, args.job_id)
        if not job:
            raise SystemExit("No job found with id " + str(args.job_id))
        text = " ".join([
            job.get("role") or "",
            job.get("company") or "",
            job.get("location") or "",
            job.get("description") or "",
        ])
        return text, job
    text = load_job_text(args)
    if not text:
        raise SystemExit("Provide --text, --file, --url, or --job-id.")
    return text, None


def command_add_job(args):
    ensure_db_dir(args.db)
    text = load_job_text(args)
    if not text:
        raise SystemExit("add-job requires --text, --file, or --url.")
    scoring_text = " ".join([args.role or "", args.company or "", args.location or "", text])
    classified = classify_job(scoring_text, args.company)
    job = {
        "company": args.company,
        "role": args.role,
        "location": args.location,
        "link": args.url or args.link,
        "description": text,
        "score": classified["score"]["score"],
        "infrastructure_alignment_score": classified["alignment"]["similarity_score"],
        "apply_decision": classified["decision"],
        "contact": args.contact,
        "status": args.status,
        "notes": args.notes,
    }
    job_id = add_job(args.db, job)
    auto_tailor_job(args.db, job_id)
    print_json({
        "id": job_id,
        "score": job["score"],
        "infrastructure_alignment_score": job["infrastructure_alignment_score"],
        "apply_decision": job["apply_decision"],
        "reasoning": classified["reasoning"],
    })


def command_score_job(args):
    text, job = resolve_text(args)
    company = args.company or (job or {}).get("company")
    print_json(score_job(text, company))


def command_classify_job(args):
    text, job = resolve_text(args)
    company = args.company or (job or {}).get("company")
    print_json(classify_job(text, company))


def command_tailor_resume(args):
    text, job = resolve_text(args)
    resume = load_resume_text(args.resume) if getattr(args, "resume", None) else None
    print_json(tailor_resume(text, resume))


def command_resume_match(args):
    text, job = resolve_text(args)
    resume = load_resume_text(args.resume)
    print_json(resume_match(text, resume))


def command_tailor_top(args):
    ensure_db_dir(args.db)
    resume = load_resume_text(args.resume)
    print_json(top_resume_matches(args.db, resume, args.limit))


def command_generate_review(args):
    print(outreach_message(args.kind, args.company, args.role, args.contact))


def command_prep_interview(args):
    text, job = resolve_text(args)
    print_json(interview_prep(text))


def command_list_top(args):
    ensure_db_dir(args.db)
    rows = list_top(args.db, args.limit)
    print_json(rows)


def command_update_status(args):
    ensure_db_dir(args.db)
    ok = update_status(args.db, args.job_id, args.status, args.notes, args.contact)
    if not ok:
        raise SystemExit("No job found with id " + str(args.job_id))
    print_json({"id": args.job_id, "status": args.status, "updated": True})


def command_export(args):
    ensure_db_dir(args.db)
    output = export_jobs(args.db, args.output)
    print_json({"exported_to": output})


def command_pull_jobs(args):
    ensure_db_dir(args.db)
    if args.greenhouse_board:
        result = pull_greenhouse(args.db, args.greenhouse_board, args.company, args.limit)
    elif args.lever_slug:
        result = pull_lever(args.db, args.lever_slug, args.company, args.limit)
    else:
        result = pull_defaults(args.db, args.limit)
    print_json(result)


def command_cleanup_locations(args):
    ensure_db_dir(args.db)
    print_json(cleanup_locations(args.db))


def command_auto_tailor(args):
    ensure_db_dir(args.db)
    print_json(auto_tailor_jobs(args.db, args.resume, args.missing_only, args.limit))


def command_export_resumes(args):
    ensure_db_dir(args.db)
    print_json(export_finished_resumes(args.db, args.output_dir, args.limit))


def command_serve(args):
    ensure_db_dir(args.db)
    serve(args.db, args.host, args.port, not args.no_browser)


def add_text_inputs(parser):
    parser.add_argument("--url")
    parser.add_argument("--text")
    parser.add_argument("--file")
    parser.add_argument("--job-id", type=int)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="rolefit-platform",
        description="Local ATS ingestion, role scoring, resume matching, and tracking system.",
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite tracker path")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add-job", help="Add and score a job from text, file, or URL")
    add_text_inputs(add)
    add.add_argument("--company")
    add.add_argument("--role")
    add.add_argument("--location")
    add.add_argument("--link")
    add.add_argument("--contact")
    add.add_argument("--status", default="saved")
    add.add_argument("--notes")
    add.set_defaults(func=command_add_job)

    score = sub.add_parser("score-job", help="Score a job posting")
    add_text_inputs(score)
    score.add_argument("--company")
    score.set_defaults(func=command_score_job)

    classify = sub.add_parser("classify-job", help="Classify apply decision")
    add_text_inputs(classify)
    classify.add_argument("--company")
    classify.set_defaults(func=command_classify_job)

    tailor = sub.add_parser("tailor-resume", help="Generate tailored bullets and keywords")
    add_text_inputs(tailor)
    tailor.add_argument("--resume", help="Path to current resume PDF or text file")
    tailor.set_defaults(func=command_tailor_resume)

    match = sub.add_parser("resume-match", help="Score how well the current resume matches a job")
    add_text_inputs(match)
    match.add_argument("--resume", default=DEFAULT_RESUME_PATH)
    match.set_defaults(func=command_resume_match)

    tailor_top = sub.add_parser("tailor-top", help="Auto-tailor the highest resume-matching tracked jobs")
    tailor_top.add_argument("--resume", default=DEFAULT_RESUME_PATH)
    tailor_top.add_argument("--limit", type=int, default=5)
    tailor_top.set_defaults(func=command_tailor_top)

    review = sub.add_parser("generate-outreach", help="Generate a concise outreach note")
    review.add_argument("--kind", choices=["infrastructure", "connection", "team", "recruiter", "network"], default="recruiter")
    review.add_argument("--company")
    review.add_argument("--role")
    review.add_argument("--contact")
    review.set_defaults(func=command_generate_review)

    prep = sub.add_parser("prep-interview", help="Map likely interview prep")
    add_text_inputs(prep)
    prep.set_defaults(func=command_prep_interview)

    top = sub.add_parser("list-top", help="List highest-scoring tracked jobs")
    top.add_argument("--limit", type=int, default=10)
    top.set_defaults(func=command_list_top)

    update = sub.add_parser("update-status", help="Update application status")
    update.add_argument("job_id", type=int)
    update.add_argument("--status", required=True)
    update.add_argument("--notes")
    update.add_argument("--contact")
    update.set_defaults(func=command_update_status)

    export = sub.add_parser("export", help="Export tracker to CSV")
    export.add_argument("--output", default="job_tracker_export.csv")
    export.set_defaults(func=command_export)

    pull = sub.add_parser("pull-jobs", help="Pull public ATS feeds, score, dedupe, and save")
    pull.add_argument("--greenhouse-board")
    pull.add_argument("--lever-slug")
    pull.add_argument("--company")
    pull.add_argument("--limit", type=int, default=12)
    pull.set_defaults(func=command_pull_jobs)

    cleanup = sub.add_parser("cleanup-locations", help="Rescore saved jobs and hide non-US restricted roles")
    cleanup.set_defaults(func=command_cleanup_locations)

    auto_tailor = sub.add_parser("auto-tailor", help="Generate saved tailored resumes for tracked jobs")
    auto_tailor.add_argument("--resume", default=DEFAULT_RESUME_PATH)
    auto_tailor.add_argument("--limit", type=int, default=500)
    auto_tailor.add_argument("--missing-only", action="store_true")
    auto_tailor.set_defaults(func=command_auto_tailor)

    export_resumes = sub.add_parser("export-resumes", help="Export finished DOCX resumes for matched jobs")
    export_resumes.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    export_resumes.add_argument("--limit", type=int, default=25)
    export_resumes.set_defaults(func=command_export_resumes)

    web = sub.add_parser("serve", help="Launch the local browser UI")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--no-browser", action="store_true")
    web.set_defaults(func=command_serve)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.db = os.path.expanduser(args.db)
    args.func(args)


if __name__ == "__main__":
    main()
