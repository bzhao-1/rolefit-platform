# RoleFit Platform

RoleFit Platform is a local Python system for ingesting ATS job feeds, scoring software engineering roles, tracking opportunities in SQLite, and automating resume match/tailoring workflows through both a CLI and a browser-based local dashboard.

The project is intentionally offline-first. It uses deterministic scoring, standard-library HTTP/HTML handling, and SQLite storage, with no paid APIs or hosted services required. The modules are separated so richer scraping, ranking models, or LLM summarization can be added later without replacing the core pipeline.

## Core Capabilities

- Pull public Greenhouse, Lever, Eightfold, Workday CXS, Ashby, and HTML search postings, normalize descriptions, dedupe saved roles, and filter location eligibility.
- Run an agent-style scraper loop for routine public ATS ingestion, scoring, cleanup, and tailoring without manual button-clicking.
- Score postings from 0-100 for backend, platform, cloud infrastructure, distributed systems, reliability, automation, and production ownership signals.
- Classify roles as `High priority`, `Review selectively`, or `Skip` using deterministic stack, level, location, and role-quality checks.
- Detect infrastructure alignment across cloud platform systems, GPU/AI infrastructure, orchestration, APIs, reliability, and SRE collaboration.
- Store job records, scores, status, notes, contacts, and generated tailoring snapshots in SQLite.
- Compare a resume against job requirements and rank tracked jobs by combined role score plus resume match score.
- Generate tailored resume bullets, keyword lists, positioning guidance, gap analysis, project selections, and finished DOCX resumes.
- Prefer production-grade framing for platform and release-operations work, including AI-assisted triage systems with explicit human approval boundaries.
- Track interview events with stage, scheduled time, format, contact, prep focus, status, and notes.
- Provide a dependency-free local dashboard for ingestion, scoring, tracking, matching, tailoring, status updates, and CSV export.

## Setup

```bash
cd rolefit-platform
python3 -m rolefit_platform --help
```

Optional shell alias:

```bash
alias rolefit-platform='python3 -m rolefit_platform'
```

The default SQLite database is:

```bash
~/.rolefit-platform/jobs.sqlite3
```

You can override it with `--db` before any command:

```bash
python3 -m rolefit_platform --db ./jobs.sqlite3 list-top
```

## Local Dashboard

Start the browser UI:

```bash
python3 -m rolefit_platform serve
```

Or double-click:

```text
launch.command
```

The dashboard runs locally at:

```text
http://127.0.0.1:8765
```

From the dashboard you can paste a job description, add a posting URL, pull public ATS feeds, inspect scored roles, update tracker status, review resume match results, generate missing tailoring snapshots, export CSV data, and export finished DOCX resumes.

## Example Commands

Pull default public ATS feeds:

```bash
python3 -m rolefit_platform pull-jobs --limit 12
```

Default ingestion includes representative public ATS adapters for Greenhouse, Lever, Eightfold, Workday CXS, Ashby, and a public careers HTML search parser. Dynamic or guarded careers pages can still be saved manually through the dashboard or `add-job`.

Run the scraper agent once:

```bash
python3 -m rolefit_platform scrape-agent --once --limit 12
```

Run the scraper agent routinely every 6 hours:

```bash
python3 -m rolefit_platform scrape-agent --interval-minutes 360 --limit 12
```

Show recent scraper-agent runs:

```bash
python3 -m rolefit_platform scrape-agent --recent
```

Pull a specific public Greenhouse board:

```bash
python3 -m rolefit_platform pull-jobs \
  --greenhouse-board grafanalabs \
  --company "Grafana Labs" \
  --limit 20
```

Pull a Workday CXS source:

```bash
python3 -m rolefit_platform pull-jobs \
  --workday-site ExampleExternalCareerSite \
  --company "Example Systems" \
  --limit 20
```

Pull an Ashby source:

```bash
python3 -m rolefit_platform pull-jobs \
  --ashby-board example \
  --company "Example AI" \
  --limit 20
```

Pull a public careers HTML search page:

```bash
python3 -m rolefit_platform pull-jobs \
  --apple-url "https://jobs.example.com/search?search=software%20engineer&location=united-states" \
  --company "Example Devices" \
  --limit 20
```

Score a pasted posting:

```bash
python3 -m rolefit_platform score-job \
  --company "Example Cloud Co." \
  --text "Software Engineer II, Cloud Platform Infrastructure. Python, Java, Kubernetes, APIs, distributed systems, CI/CD, reliability, 1+ years."
```

Classify a posting from a text file:

```bash
python3 -m rolefit_platform classify-job \
  --company "Example Cloud Co." \
  --file examples/cloud_platform_job.txt
```

Add a posting to the tracker:

```bash
python3 -m rolefit_platform add-job \
  --company "Example Cloud Co." \
  --role "Software Engineer II, Cloud Platform Infrastructure" \
  --location "Austin, TX / Remote" \
  --url "https://example.com/job" \
  --file examples/cloud_platform_job.txt \
  --contact "platform team source" \
  --notes "Verify ownership of infrastructure APIs and release automation."
```

Score resume fit for a saved posting:

```bash
python3 -m rolefit_platform resume-match --job-id 1
```

Rank tracked postings by role score plus resume match:

```bash
python3 -m rolefit_platform tailor-top --limit 5
```

Generate saved tailoring snapshots:

```bash
python3 -m rolefit_platform auto-tailor --missing-only
```

Export finished DOCX resumes for matched postings:

```bash
python3 -m rolefit_platform export-resumes --output-dir generated_resumes --limit 25
```

Add an interview event:

```bash
python3 -m rolefit_platform add-interview \
  --company "Example Cloud Co." \
  --role "Software Engineer II" \
  --stage "phone screen" \
  --scheduled-at "2026-05-08T16:00" \
  --timezone "America/Chicago" \
  --format "phone"
```

List scheduled interviews:

```bash
python3 -m rolefit_platform list-interviews --status scheduled
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

Export tracker data:

```bash
python3 -m rolefit_platform export --output job_tracker_export.csv
```

## Scoring Model

The deterministic scorer rewards:

- backend, platform, cloud, and infrastructure relevance
- distributed systems, reliability, orchestration, and multi-tenant systems
- Python, Java, Go, SQL, APIs, Linux, Docker, Terraform, and Kubernetes
- CI/CD, deployment automation, validation, release gates, testing, and observability
- security, compliance, vulnerability automation, telemetry, and data pipelines
- infrastructure lifecycle work, GPU/AI infrastructure, and SRE/developer collaboration
- clear software engineering ownership and early-career level fit

It penalizes:

- non-US onsite roles unless explicitly remote or US-eligible
- senior/staff/principal mismatch
- roles requiring 4+ years when evaluating early-career fit
- frontend-heavy, mobile-only, embedded/firmware, data scientist, ML researcher, support/IT, internship, and new-grad-only signals
- low-signal staffing-firm postings

## Architecture

```text
rolefit_platform/
  alignment.py      infrastructure alignment detector
  auto_tailor.py    saved tailoring generation
  classifier.py     deterministic high-priority/review/skip logic
  cli.py            argparse CLI
  location.py       US/remote location eligibility checks
  maintenance.py    tracker cleanup utilities
  outreach.py       concise outreach-note generator
  prep.py           interview prep mapper
  profile.py        anonymized sample profile and resume context
  resume.py         resume tailoring engine
  resume_export.py  DOCX resume exporter
  resume_match.py   resume/job match scoring and ranking
  scraper_agent.py  routine ATS scraping, scoring, dedupe, cleanup, and auto-tailoring
  scoring.py        0-100 scoring engine
  sources.py        ATS/feed ingestion adapters
  storage.py        SQLite tracker and CSV export
  text_utils.py     URL/text loading helpers
  web.py            dependency-free local browser UI
examples/
  cloud_platform_job.txt
tests/
  test_resume_tailoring.py
launch.command      macOS double-click launcher
```

## Portfolio Notes

This is a backend/platform project, not a marketing site. The technical emphasis is deterministic ranking, ATS ingestion, SQLite-backed workflow state, local-first tooling, modular scoring logic, and document generation automation.

## Maintainer Notes

Before releasing changes, run:

```bash
python3 -m compileall rolefit_platform
python3 -m unittest discover -s tests
rg -n "PRIVATE_COMPANY|PRIVATE_NAME|PRIVATE_EMAIL|PRIVATE_PATH|active-search-framing" .
```
