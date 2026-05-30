import html
import json
import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime

from rolefit_platform.auto_tailor import DEFAULT_RESUME_PATH, auto_tailor_job, auto_tailor_jobs
from rolefit_platform.classifier import classify_job
from rolefit_platform.maintenance import cleanup_locations
from rolefit_platform.prep import interview_prep
from rolefit_platform.outreach import outreach_message
from rolefit_platform.resume import tailor_resume
from rolefit_platform.resume_export import DEFAULT_OUTPUT_DIR, export_finished_resumes
from rolefit_platform.resume_match import load_resume_text, resume_match, top_resume_matches
from rolefit_platform.scraper_agent import recent_agent_runs, run_scraper_once
from rolefit_platform.sources import DEFAULT_APPLE_SEARCHES, DEFAULT_ASHBY_BOARDS, DEFAULT_EIGHTFOLD_SITES, DEFAULT_GREENHOUSE_BOARDS, DEFAULT_LEVER_SLUGS, DEFAULT_WORKDAY_SITES, GUARDED_SOURCES, SAVED_SEARCH_LINKS, pull_apple, pull_ashby, pull_defaults, pull_greenhouse, pull_lever, pull_workday
from rolefit_platform.storage import add_interview, add_job, export_jobs, get_job, get_tailored_resume, list_interviews, list_jobs, stats, update_interview, update_status
from rolefit_platform.text_utils import load_text_from_url


def esc(value):
    return html.escape(str(value or ""))


def status_options(current):
    statuses = ["saved", "pulled", "contact requested", "applied", "interview", "offer", "rejected", "skipped"]
    current_value = current or "saved"
    parts = []
    for status in statuses:
        selected = " selected" if status == current_value else ""
        parts.append("<option value=\"" + esc(status) + "\"" + selected + ">" + esc(status) + "</option>")
    return "".join(parts)


def ensure_db_dir(path):
    directory = os.path.dirname(os.path.abspath(os.path.expanduser(path)))
    if directory and not os.path.exists(directory):
        os.makedirs(directory)


TECH_KEYWORDS = [
    "Python", "Java", "Go", "C++", "Kubernetes", "Docker", "Terraform", "Linux",
    "AWS", "Azure", "GCP", "PostgreSQL", "Kafka", "Spark", "CI/CD", "PyTest",
    "REST", "GraphQL", "SQL", "Redis", "Datadog", "Prometheus",
]

SPECIALTY_KEYWORDS = [
    ("AI Infra", ["ai infrastructure", "ml infrastructure", "gpu", "model", "inference", "data pipeline"]),
    ("Backend", ["backend", "api", "microservice", "service", "java", "python", "go"]),
    ("Platform", ["platform", "infrastructure", "cloud", "kubernetes", "developer infrastructure"]),
    ("Reliability", ["sre", "reliability", "observability", "monitoring", "incident", "on-call"]),
    ("Release", ["release", "deployment", "ci/cd", "build", "validation", "test automation"]),
    ("Security", ["security", "compliance", "vulnerability", "secure coding"]),
]


def row_text(row):
    return " ".join([row.get("role") or "", row.get("company") or "", row.get("location") or "", row.get("description") or "", row.get("notes") or ""])


def display_date(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.isdigit() and len(raw) >= 10:
        try:
            return datetime.fromtimestamp(int(raw[:10])).strftime("%b %-d, %Y")
        except Exception:
            return raw
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%b %-d, %Y")
    except Exception:
        pass
    for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(raw, fmt).strftime("%b %-d, %Y")
        except Exception:
            pass
    return raw.replace("Posted ", "")


def posted_label(row):
    if row.get("posted_at"):
        return "Posted " + display_date(row.get("posted_at"))
    return "Added " + display_date(row.get("created_at"))


def detect_level(row):
    text = row_text(row).lower()
    role = (row.get("role") or "").lower()
    if any(term in role for term in ["staff", "principal"]):
        return "Staff+"
    if any(term in role for term in ["senior", "sr."]):
        return "Senior"
    if any(term in text for term in ["new grad", "university graduate", "entry level", "0 years"]):
        return "Entry"
    if any(term in text for term in ["1+ years", "2 years", "software engineer ii", "engineer ii", "mid level", "mid-level"]):
        return "Mid"
    return "Any"


def detect_specialty(row):
    text = row_text(row).lower()
    hits = []
    for label, terms in SPECIALTY_KEYWORDS:
        if any(term in text for term in terms):
            hits.append(label)
    return hits[:3] or ["Software"]


def detect_tech(row):
    text = row_text(row).lower()
    hits = []
    aliases = {"C++": ["c++", "c/c++"], "CI/CD": ["ci/cd", "cicd"], "GCP": ["gcp", "google cloud"], "REST": ["rest api", "restful"]}
    for tech in TECH_KEYWORDS:
        checks = aliases.get(tech, [tech.lower()])
        if any(item in text for item in checks):
            hits.append(tech)
    return hits[:8]


def detect_salary(row):
    text = row_text(row)
    match = None
    for pattern in [r"\$[0-9]{2,3}k\s*-\s*\$[0-9]{2,3}k", r"\$[0-9,]{5,}\s*-\s*\$[0-9,]{5,}"]:
        match = re_search(pattern, text)
        if match:
            break
    return match or "Salary not listed"


def re_search(pattern, text):
    import re
    found = re.search(pattern, text or "", re.I)
    return found.group(0) if found else None


def compact_summary(row):
    text = row.get("description") or row.get("notes") or ""
    text = " ".join(str(text).split())
    sentences = [item.strip() for item in text.split(".") if item.strip()]
    for sentence in sentences:
        if 80 <= len(sentence) <= 220 and not sentence.lower().startswith(("the application", "job posting", "message to applicants")):
            return sentence[:240]
    return text[:240] + ("..." if len(text) > 240 else "")


def filter_jobs(rows, params):
    query = ((params.get("q") or [""])[0]).strip().lower()
    location = ((params.get("location") or [""])[0]).strip().lower()
    level = ((params.get("level") or [""])[0]).strip()
    specialty = ((params.get("specialty") or [""])[0]).strip()
    tech = ((params.get("tech") or [""])[0]).strip().lower()
    status = ((params.get("status") or [""])[0]).strip()
    min_score_raw = ((params.get("min_score") or [""])[0]).strip()
    min_score = int(min_score_raw) if min_score_raw.isdigit() else 0
    filtered = []
    for row in rows:
        text = row_text(row).lower()
        if query and query not in text:
            continue
        if location and location not in (row.get("location") or "").lower() and location not in text:
            continue
        if level and level != "Any" and detect_level(row) != level:
            continue
        if specialty and specialty not in detect_specialty(row):
            continue
        if tech and tech not in [item.lower() for item in detect_tech(row)]:
            continue
        if status and row.get("status") != status:
            continue
        if (row.get("score") or 0) < min_score:
            continue
        filtered.append(row)
    return filtered


def layout(title, body):
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>""" + esc(title) + """</title>
  <style>
    :root { color-scheme: dark; --ink:#e6edf3; --muted:#8b98a9; --line:#243244; --bg:#0b1118; --panel:#111a24; --soft:#172333; --accent:#38bdf8; --accent2:#2dd4bf; --good:#4ade80; --warn:#fbbf24; --bad:#fb7185; }
    * { box-sizing:border-box; }
    body { margin:0; font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:linear-gradient(180deg,#101827 0,#0b1118 340px); }
    header { position:sticky; top:0; z-index:3; background:rgba(11,17,24,.92); border-bottom:1px solid var(--line); backdrop-filter:blur(10px); }
    nav { max-width:1180px; margin:0 auto; padding:12px 18px; display:flex; align-items:center; gap:14px; }
    nav a { color:var(--ink); text-decoration:none; font-weight:650; }
    nav .brand { margin-right:auto; font-size:17px; }
    main { max-width:1320px; margin:0 auto; padding:18px; }
    .hero { display:grid; grid-template-columns:1fr auto; gap:16px; align-items:end; margin-bottom:16px; }
    .hero h1 { font-size:28px; margin-bottom:4px; }
    .grid { display:grid; grid-template-columns:minmax(0,1.3fr) minmax(340px,.7fr); gap:16px; align-items:start; }
    .three { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
    .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px; }
    .stat, .panel, .job { background:rgba(17,26,36,.96); border:1px solid var(--line); border-radius:8px; }
    .stat { padding:12px; box-shadow:0 12px 30px rgba(0,0,0,.16); }
    .stat b { display:block; font-size:22px; }
    .panel { padding:14px; margin-bottom:16px; }
    h1, h2, h3 { margin:0 0 10px; letter-spacing:0; }
    h1 { font-size:22px; }
    h2 { font-size:16px; }
    label { display:block; font-weight:650; margin:10px 0 4px; }
    input, textarea, select { width:100%; border:1px solid var(--line); border-radius:6px; padding:9px 10px; font:inherit; background:#0d1621; color:var(--ink); }
    textarea { min-height:150px; resize:vertical; }
    button, .button { border:0; border-radius:6px; background:var(--accent); color:#fff; padding:9px 12px; font-weight:700; cursor:pointer; text-decoration:none; display:inline-block; }
    .secondary { background:#334155; }
    .ghost { background:#1d2a3a; color:var(--ink); }
    .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
    .muted { color:var(--muted); }
    .job { padding:14px; margin-bottom:10px; box-shadow:0 10px 24px rgba(0,0,0,.14); }
    .job:hover { border-color:#365778; box-shadow:0 14px 30px rgba(0,0,0,.22); }
    .job-title { font-weight:760; font-size:16px; color:var(--ink); text-decoration:none; }
    .pill { display:inline-flex; align-items:center; min-height:24px; padding:2px 8px; border-radius:999px; background:#1c2a3a; margin:4px 4px 0 0; font-size:12px; font-weight:650; }
    .tag { background:#0f2e2b; color:#5eead4; }
    .verified { color:var(--good); font-weight:760; }
    .feed-shell { display:grid; grid-template-columns:280px minmax(0,1fr); gap:16px; align-items:start; }
    .filters { position:sticky; top:64px; }
    .feed-head { display:flex; justify-content:space-between; gap:12px; align-items:end; margin-bottom:12px; }
    .feed-list { display:grid; gap:10px; }
    .job-top { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; align-items:start; }
    .company-mark { width:38px; height:38px; border-radius:8px; display:inline-grid; place-items:center; background:linear-gradient(135deg,#1769aa,#18a999); color:white; font-weight:800; }
    .job-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
    .empty { padding:28px; text-align:center; }
    .stage { border-left:4px solid var(--accent); }
    .stage h2 { display:flex; justify-content:space-between; gap:8px; align-items:center; }
    .stage-count { color:var(--muted); font-size:12px; }
    .agent-card { background:linear-gradient(135deg,#102337,#0f2e2b); border-color:#24465f; }
    .status-board { display:grid; grid-template-columns:repeat(6, minmax(160px,1fr)); gap:10px; margin-bottom:16px; }
    .status-col { background:rgba(17,26,36,.82); border:1px solid var(--line); border-radius:8px; padding:10px; min-height:120px; }
    .status-col.drag-over { border-color:var(--accent); box-shadow:0 0 0 2px rgba(56,189,248,.22) inset; }
    .status-col h2 { display:flex; justify-content:space-between; gap:8px; font-size:14px; }
    .mini-job { display:block; padding:8px; margin-top:8px; border-radius:6px; background:#0d1621; color:var(--ink); text-decoration:none; border:1px solid #1e2c3c; cursor:grab; }
    .mini-job:active { cursor:grabbing; }
    .mini-job.dragging { opacity:.55; }
    .mini-job span { display:block; font-size:12px; color:var(--muted); margin-top:2px; }
    .agent-log { max-height:220px; overflow:auto; }
    .split { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .score { color:var(--good); }
    .warn { color:var(--warn); }
    .bad { color:var(--bad); }
    pre { white-space:pre-wrap; background:#0d1621; border:1px solid var(--line); border-radius:8px; padding:12px; overflow:auto; }
    ul { margin-top:6px; padding-left:20px; }
    @media (max-width: 900px) { .grid, .stats, .three, .hero, .split, .feed-shell, .job-top, .status-board { grid-template-columns:1fr; } nav { overflow:auto; } .filters { position:static; } }
  </style>
</head>
<body>
  <header><nav>
    <a class="brand" href="/">rolefit-platform</a>
    <a href="/">Jobs</a>
    <a href="/status">Status</a>
    <a href="/add">Add</a>
    <a href="/pull">Pull</a>
    <a href="/agent">Agent</a>
    <a href="/matches">Resume Matches</a>
    <a href="/interviews">Interviews</a>
    <a href="/export">Export</a>
  </nav></header>
  <main>""" + body + """</main>
  <script>
    let draggedJob = null;
    document.addEventListener("dragstart", event => {
      const card = event.target.closest("[data-job-id]");
      if (!card) return;
      draggedJob = card;
      card.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", card.dataset.jobId);
    });
    document.addEventListener("dragend", () => {
      document.querySelectorAll(".dragging").forEach(item => item.classList.remove("dragging"));
      document.querySelectorAll(".drag-over").forEach(item => item.classList.remove("drag-over"));
      draggedJob = null;
    });
    document.addEventListener("dragover", event => {
      const column = event.target.closest(".status-col");
      if (!column || !draggedJob) return;
      event.preventDefault();
      column.classList.add("drag-over");
    });
    document.addEventListener("dragleave", event => {
      const column = event.target.closest(".status-col");
      if (column && !column.contains(event.relatedTarget)) column.classList.remove("drag-over");
    });
    document.addEventListener("drop", async event => {
      const column = event.target.closest(".status-col");
      if (!column || !draggedJob) return;
      event.preventDefault();
      column.classList.remove("drag-over");
      const body = new URLSearchParams({ job_id: draggedJob.dataset.jobId, status: column.dataset.status });
      const response = await fetch("/drag-status", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body });
      if (response.ok) {
        const empty = column.querySelector(".empty-status");
        if (empty) empty.remove();
        column.appendChild(draggedJob);
        draggedJob.dataset.status = column.dataset.status;
        window.location.reload();
      }
    });
  </script>
</body>
</html>"""


class App(BaseHTTPRequestHandler):
    db_path = None

    def send_html(self, body, title="rolefit-platform", status=200):
        raw = layout(title, body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def redirect(self, path):
        self.send_response(303)
        self.send_header("Location", path)
        self.end_headers()

    def form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return {key: values[-1] for key, values in urllib.parse.parse_qs(raw).items()}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/":
            self.dashboard(params)
        elif path == "/add":
            self.add_page(params)
        elif path == "/pull":
            self.pull_page(params)
        elif path == "/agent":
            self.agent_page(params)
        elif path == "/status":
            self.status_page(params)
        elif path == "/matches":
            self.matches_page(params)
        elif path == "/interviews":
            self.interviews_page(params)
        elif path == "/job":
            self.job_page(params)
        elif path == "/export":
            output = os.path.abspath("job_tracker_export.csv")
            export_jobs(self.db_path, output)
            self.send_html("<div class='panel'><h1>Exported</h1><p>Wrote CSV to <code>" + esc(output) + "</code>.</p><p><a class='button' href='/'>Back to dashboard</a></p></div>")
        elif path == "/export-resumes":
            result = export_finished_resumes(self.db_path, DEFAULT_OUTPUT_DIR, int((params.get("limit") or ["25"])[0]))
            links = "".join("<li><code>" + esc(item["path"]) + "</code></li>" for item in result["exported"])
            self.send_html("<div class='panel'><h1>Finished Resumes Exported</h1><p>Wrote " + str(result["count"]) + " DOCX files to <code>" + esc(result["output_dir"]) + "</code>.</p><ul>" + links + "</ul><p><a class='button' href='/matches'>Back to matches</a></p></div>")
        else:
            self.send_html("<div class='panel'><h1>Not found</h1></div>", status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        data = self.form()
        if parsed.path == "/add-text":
            self.add_from_text(data)
        elif parsed.path == "/add-url":
            self.add_from_url(data)
        elif parsed.path == "/update-status":
            update_status(self.db_path, int(data.get("job_id")), data.get("status"), data.get("notes"), data.get("contact"))
            self.redirect("/job?id=" + urllib.parse.quote(data.get("job_id", "")))
        elif parsed.path == "/drag-status":
            ok = update_status(self.db_path, int(data.get("job_id")), data.get("status"))
            raw = json.dumps({"updated": bool(ok)}).encode("utf-8")
            self.send_response(200 if ok else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif parsed.path == "/add-interview":
            self.add_interview(data)
        elif parsed.path == "/update-interview":
            update_interview(
                self.db_path,
                int(data.get("interview_id")),
                stage=data.get("stage"),
                scheduled_at=data.get("scheduled_at"),
                timezone=data.get("timezone"),
                format=data.get("format"),
                contact=data.get("contact"),
                status=data.get("status"),
                prep_focus=data.get("prep_focus"),
                notes=data.get("notes"),
            )
            self.redirect("/interviews")
        elif parsed.path == "/pull-defaults":
            pull_defaults(self.db_path, int(data.get("limit") or "50"))
            self.redirect("/?pulled=1")
        elif parsed.path == "/agent-run":
            run_scraper_once(self.db_path, int(data.get("limit") or "50"), DEFAULT_RESUME_PATH)
            self.redirect("/agent?ran=1")
        elif parsed.path == "/pull-greenhouse":
            pull_greenhouse(self.db_path, data.get("board", ""), data.get("company", ""), int(data.get("limit") or "20"))
            self.redirect("/?pulled=1")
        elif parsed.path == "/pull-lever":
            pull_lever(self.db_path, data.get("slug", ""), data.get("company", ""), int(data.get("limit") or "20"))
            self.redirect("/?pulled=1")
        elif parsed.path == "/pull-workday":
            pull_workday(
                self.db_path,
                data.get("base_url", "") or "https://nvidia.wd5.myworkdayjobs.com",
                data.get("tenant", "") or "nvidia",
                data.get("site", ""),
                data.get("company", ""),
                int(data.get("limit") or "20"),
                data.get("search_text", "") or "broad",
            )
            self.redirect("/?pulled=1")
        elif parsed.path == "/pull-ashby":
            pull_ashby(self.db_path, data.get("board", ""), data.get("company", ""), int(data.get("limit") or "20"))
            self.redirect("/?pulled=1")
        elif parsed.path == "/pull-apple":
            pull_apple(self.db_path, data.get("url", ""), data.get("company", "") or "Apple", int(data.get("limit") or "20"))
            self.redirect("/?pulled=1")
        elif parsed.path == "/cleanup-locations":
            cleanup_locations(self.db_path)
            self.redirect("/?cleaned=1")
        elif parsed.path == "/auto-tailor":
            auto_tailor_jobs(self.db_path, DEFAULT_RESUME_PATH, True)
            self.redirect("/matches?tailored=1")
        else:
            self.send_html("<div class='panel'><h1>Not found</h1></div>", status=404)

    def add_from_text(self, data):
        text = data.get("description", "")
        company = data.get("company", "")
        scoring_text = " ".join([data.get("role", ""), company, data.get("location", ""), text])
        classified = classify_job(scoring_text, company)
        job = {
            "company": company,
            "role": data.get("role", ""),
            "location": data.get("location", ""),
            "link": data.get("link", ""),
            "description": text,
            "score": classified["score"]["score"],
            "infrastructure_alignment_score": classified["alignment"]["similarity_score"],
            "apply_decision": classified["decision"],
            "contact": data.get("contact", ""),
            "status": data.get("status", "saved"),
            "posted_at": data.get("posted_at", ""),
            "source": "Manual",
            "notes": data.get("notes", "") + " " + classified["reasoning"],
        }
        job_id = add_job(self.db_path, job)
        auto_tailor_job(self.db_path, job_id)
        self.redirect("/job?id=" + str(job_id))

    def add_interview(self, data):
        job_id = int(data.get("job_id")) if data.get("job_id") else None
        interview_id = add_interview(self.db_path, {
            "job_id": job_id,
            "company": data.get("company"),
            "role": data.get("role"),
            "stage": data.get("stage") or "phone screen",
            "scheduled_at": data.get("scheduled_at"),
            "timezone": data.get("timezone") or "America/Chicago",
            "format": data.get("format") or "phone",
            "contact": data.get("contact"),
            "status": data.get("status") or "scheduled",
            "prep_focus": data.get("prep_focus"),
            "notes": data.get("notes"),
        })
        if data.get("from_job") and job_id:
            self.redirect("/job?id=" + str(job_id))
        else:
            self.redirect("/interviews?added=" + str(interview_id))

    def add_from_url(self, data):
        text = load_text_from_url(data.get("url", ""))
        data["description"] = text
        data["link"] = data.get("url", "")
        self.add_from_text(data)

    def dashboard(self, params):
        rows = list_jobs(self.db_path, 250)
        filtered_rows = filter_jobs(rows, params)
        interviews = list_interviews(self.db_path, 5, "scheduled")
        runs = recent_agent_runs(self.db_path, 3)
        summary = stats(self.db_path)
        pulled = "<div class='panel'><b>Pull complete.</b> New jobs were scored and deduped.</div>" if params.get("pulled") else ""
        cleaned = "<div class='panel'><b>Cleanup complete.</b> Non-US restricted jobs are now hidden as skipped.</div>" if params.get("cleaned") else ""
        body = pulled + cleaned + """
<section class="hero">
  <div>
    <h1>Browse Scored Engineering Roles</h1>
    <p class="muted">Verified ATS ingestion, deterministic filters, resume match scoring, tailoring automation, and tracker actions in one local workflow.</p>
  </div>
  <form method="post" action="/agent-run" class="row">
    <input name="limit" value="50" style="max-width:80px">
    <button>Refresh jobs</button>
  </form>
</section>
<div class="stats">
  <div class="stat"><span class="muted">Tracked</span><b>""" + str(summary["total"]) + """</b></div>
  <div class="stat"><span class="muted">75+ score</span><b>""" + str(summary["top_fit"]) + """</b></div>
  <div class="stat"><span class="muted">Applied</span><b>""" + str(summary["by_status"].get("applied", 0)) + """</b></div>
  <div class="stat"><span class="muted">Scheduled</span><b>""" + str(summary["scheduled_interviews"]) + """</b></div>
</div>
""" + self.status_board_html(rows) + """
<div class="feed-shell">
  <aside class="panel filters">
    <h2>Filters</h2>
    <form method="get" action="/">
      <label>Search</label><input name="q" value=\"""" + esc((params.get("q") or [""])[0]) + """\" placeholder="backend, kubernetes, ci/cd">
      <label>Location</label><input name="location" value=\"""" + esc((params.get("location") or [""])[0]) + """\" placeholder="United States, Austin, Remote">
      <label>Minimum score</label><select name="min_score">
        """ + self.option_html(["", "55", "65", "75", "85"], (params.get("min_score") or [""])[0], "Any") + """
      </select>
      <label>Level</label><select name="level">
        """ + self.option_html(["", "Entry", "Mid", "Senior", "Staff+"], (params.get("level") or [""])[0], "Any") + """
      </select>
      <label>Specialty</label><select name="specialty">
        """ + self.option_html(["", "Backend", "Platform", "AI Infra", "Reliability", "Release", "Security"], (params.get("specialty") or [""])[0], "Any") + """
      </select>
      <label>Tech Stack</label><select name="tech">
        """ + self.option_html(["", "Python", "Java", "Go", "C++", "Kubernetes", "Docker", "Linux", "CI/CD", "PyTest"], (params.get("tech") or [""])[0], "Any") + """
      </select>
      <label>Status</label><select name="status">
        """ + self.option_html(["", "saved", "pulled", "contact requested", "applied", "interview", "offer", "rejected", "skipped"], (params.get("status") or [""])[0], "Any") + """
      </select>
      <p><button>Apply filters</button></p>
      <p><a class="button ghost" href="/">Reset</a></p>
    </form>
    <hr>
    <h2>Agent</h2>
    """ + self.agent_status_html(runs) + """
    <p><a class="button ghost" href="/agent">Sources</a></p>
  </aside>
  <section>
    <div class="feed-head">
      <div>
        <h2>""" + str(len(filtered_rows)) + """ Matching Jobs</h2>
        <p class="muted">Direct-from-source postings, ranked by role fit and filtered for US or eligible remote work.</p>
      </div>
      <div class="row">
        <a class="button" href="/add">Add URL</a>
        <a class="button secondary" href="/pull">Pull feeds</a>
        <a class="button ghost" href="/matches">Resume matches</a>
      </div>
    </div>
    <div class="feed-list">
      """ + self.job_feed_html(filtered_rows[:80]) + """
    </div>
  </section>
</div>"""
        self.send_html(body)

    def status_board_html(self, rows):
        columns = [
            ("saved", "Saved"),
            ("pulled", "New"),
            ("contact requested", "Contact"),
            ("applied", "Applied"),
            ("interview", "Interviewing"),
            ("offer", "Offer"),
            ("rejected", "Rejected"),
        ]
        parts = ["<section class='status-board'>"]
        for status, label in columns:
            selected = [row for row in rows if row.get("status") == status][:4]
            parts.append("<div class='status-col' data-status='" + esc(status) + "'><h2>" + esc(label) + "<span class='stage-count'>" + str(len([row for row in rows if row.get("status") == status])) + "</span></h2>")
            if selected:
                for row in selected:
                    parts.append("<a class='mini-job' draggable='true' data-job-id='" + str(row.get("id")) + "' href='/job?id=" + str(row.get("id")) + "'>" + esc(row.get("company")) + " · " + esc(row.get("role")) + "<span>" + esc(posted_label(row)) + " · Fit " + str(row.get("score") or 0) + "</span></a>")
            else:
                parts.append("<p class='muted empty-status'>Empty</p>")
            parts.append("</div>")
        parts.append("</section>")
        return "".join(parts)

    def status_page(self, params):
        rows = list_jobs(self.db_path, 500)
        interviews = list_interviews(self.db_path, 50)
        body = """
<section class="hero">
  <div>
    <h1>Application Status</h1>
    <p class="muted">A quick board for saved roles, contacts, applications, interviews, offers, and rejections.</p>
  </div>
  <a class="button" href="/">Back to job feed</a>
</section>
""" + self.status_board_html(rows) + """
<div class="grid">
  <section class="panel">
    <h2>Interview Rounds</h2>
    """ + self.interviews_compact_html(interviews) + """
  </section>
  <aside class="panel">
    <h2>Status Shortcuts</h2>
    <p class="muted">Open any job card to update status, contact, notes, or add an interview round.</p>
    <p><a class="button ghost" href="/interviews">Open interview tracker</a></p>
  </aside>
</div>"""
        self.send_html(body, "Application Status")

    def option_html(self, values, current, blank_label):
        parts = []
        for value in values:
            label = blank_label if value == "" else value
            selected = " selected" if value == current else ""
            parts.append("<option value=\"" + esc(value) + "\"" + selected + ">" + esc(label) + "</option>")
        return "".join(parts)

    def jobs_html(self, rows):
        if not rows:
            return "<div class='panel'><h2>No jobs yet</h2><p>Add one manually or pull public feeds.</p></div>"
        parts = []
        for row in rows:
            score_class = "score" if (row.get("score") or 0) >= 75 else "warn" if (row.get("score") or 0) >= 55 else "bad"
            match = resume_match(" ".join([row.get("role") or "", row.get("company") or "", row.get("location") or "", row.get("description") or ""]))
            parts.append("""
<article class="job">
  <div class="row"><a class="job-title" href="/job?id=""" + str(row["id"]) + """">""" + esc(row["role"] or "Untitled role") + """</a></div>
  <div class="muted">""" + esc(row["company"]) + """ · """ + esc(row["location"]) + """</div>
  <span class="pill """ + score_class + """">Score """ + str(row.get("score") or 0) + """</span>
  <span class="pill">Resume """ + str(match["resume_match_score"]) + """</span>
  <span class="pill">Infra """ + str(row.get("infrastructure_alignment_score") or 0) + """</span>
  <span class="pill">""" + esc(row.get("apply_decision")) + """</span>
  <span class="pill">""" + esc(row.get("status")) + """</span>
</article>""")
        return "\n".join(parts)

    def job_feed_html(self, rows):
        if not rows:
            return "<div class='panel empty'><h2>No matching jobs</h2><p class='muted'>Relax the filters or run the scraper agent.</p></div>"
        parts = []
        for row in rows:
            match = resume_match(row_text(row))
            score = row.get("score") or 0
            score_class = "score" if score >= 75 else "warn" if score >= 55 else "bad"
            tech = detect_tech(row)
            specialty = detect_specialty(row)
            company = row.get("company") or "?"
            initials = "".join([part[:1] for part in company.split()[:2]]).upper() or "?"
            apply = "<a class='button ghost' href='" + esc(row.get("link")) + "' target='_blank'>Apply</a>" if row.get("link") else ""
            parts.append("""
<article class="job">
  <div class="job-top">
    <div class="row" style="align-items:flex-start">
      <span class="company-mark">""" + esc(initials) + """</span>
      <div>
        <a class="job-title" href="/job?id=""" + str(row["id"]) + """">""" + esc(row.get("role") or "Untitled role") + """</a>
        <div class="muted">""" + esc(company) + """ · """ + esc(row.get("location")) + """ · """ + esc(posted_label(row)) + """ <span class="verified">""" + esc(row.get("source") or "verified source") + """</span></div>
      </div>
    </div>
    <div>
      <span class="pill """ + score_class + """">Fit """ + str(score) + """</span>
      <span class="pill">Resume """ + str(match["resume_match_score"]) + """</span>
    </div>
  </div>
  <p>""" + esc(compact_summary(row)) + """</p>
  <div>
    <span class="pill">""" + esc(detect_level(row)) + """</span>
    <span class="pill">""" + esc(detect_salary(row)) + """</span>
    <span class="pill">Added """ + esc(display_date(row.get("created_at"))) + """</span>
    <span class="pill">""" + esc(row.get("apply_decision")) + """</span>
    <span class="pill">""" + esc(row.get("status")) + """</span>
    """ + "".join("<span class='pill tag'>" + esc(item) + "</span>" for item in specialty) + """
    """ + "".join("<span class='pill'>" + esc(item) + "</span>" for item in tech[:5]) + """
  </div>
  <div class="job-actions">
    <a class="button" href="/job?id=""" + str(row["id"]) + """">Review</a>
    """ + apply + """
    <a class="button ghost" href="/export-resumes?limit=25">Export resumes</a>
  </div>
</article>""")
        return "".join(parts)

    def pipeline_html(self, rows):
        groups = [
            ("New high-fit", lambda row: row.get("status") in ["pulled", "saved"] and (row.get("score") or 0) >= 75),
            ("Contact / apply", lambda row: row.get("status") in ["contact requested", "applied"]),
            ("Interviewing", lambda row: row.get("status") == "interview"),
        ]
        parts = []
        for title, predicate in groups:
            selected = [row for row in rows if predicate(row)][:8]
            parts.append("<section class='panel stage'><h2>" + esc(title) + "<span class='stage-count'>" + str(len(selected)) + "</span></h2>")
            parts.append(self.jobs_html(selected) if selected else "<p class='muted'>Nothing here yet.</p>")
            parts.append("</section>")
        return "".join(parts)

    def agent_status_html(self, runs):
        if not runs:
            return "<p class='muted'>No agent runs yet.</p>"
        latest = runs[0]
        return """
<p><b>Last run:</b> """ + esc(latest.get("finished_at") or latest.get("started_at")) + """</p>
<span class="pill">""" + esc(latest.get("status")) + """</span>
<span class="pill">Added """ + str(latest.get("added_count") or 0) + """</span>
<span class="pill">Skipped """ + str(latest.get("skipped_count") or 0) + """</span>
<span class="pill">Errors """ + str(latest.get("error_count") or 0) + """</span>"""

    def next_action_html(self, rows, interviews):
        if interviews:
            item = interviews[0]
            return "<p><b>Prep:</b> " + esc(item.get("company")) + " " + esc(item.get("stage")) + " at " + esc(item.get("scheduled_at")) + "</p><p><a class='button ghost' href='/interviews'>Open prep notes</a></p>"
        for row in rows:
            if row.get("status") in ["pulled", "saved"] and (row.get("score") or 0) >= 75:
                return "<p><b>Review:</b> " + esc(row.get("company")) + " · " + esc(row.get("role")) + "</p><p><a class='button ghost' href='/job?id=" + str(row.get("id")) + "'>Open role</a></p>"
        return "<p class='muted'>Run the scraper agent or add a target role.</p>"

    def interviews_compact_html(self, rows):
        if not rows:
            return "<p class='muted'>No scheduled interviews yet.</p>"
        parts = []
        for row in rows:
            parts.append("""
<article class="job">
  <div class="job-title">""" + esc(row.get("company")) + """ · """ + esc(row.get("stage")) + """</div>
  <div class="muted">""" + esc(row.get("scheduled_at")) + """ """ + esc(row.get("timezone")) + """ · """ + esc(row.get("format")) + """</div>
  <span class="pill">""" + esc(row.get("role")) + """</span>
  <span class="pill">""" + esc(row.get("status")) + """</span>
</article>""")
        return "".join(parts)

    def add_page(self, params):
        body = """
<div class="grid">
<section class="panel">
  <h1>Paste a Job</h1>
  <form method="post" action="/add-text">
    <label>Company</label><input name="company" placeholder="Cloud Platform Co.">
    <label>Role</label><input name="role" placeholder="Software Engineer II, Cloud Platform">
    <label>Location</label><input name="location" placeholder="Santa Clara, CA / Remote">
    <label>Link</label><input name="link" placeholder="https://...">
    <label>Posted date</label><input name="posted_at" placeholder="May 30, 2026 / Posted 3 Days Ago">
    <label>Description</label><textarea name="description" placeholder="Paste the job description here"></textarea>
    <label>Contact</label><input name="contact" placeholder="Recruiter or hiring contact">
    <label>Notes</label><input name="notes" placeholder="Ask for team guidance first">
    <input type="hidden" name="status" value="saved">
    <p><button>Score and save</button></p>
  </form>
</section>
<aside class="panel">
  <h1>Add by URL</h1>
  <form method="post" action="/add-url">
    <label>Company</label><input name="company" placeholder="Google">
    <label>Role</label><input name="role" placeholder="Backend Software Engineer">
    <label>Location</label><input name="location">
    <label>URL</label><input name="url" placeholder="https://...">
    <p><button>Fetch, score, save</button></p>
  </form>
</aside>
</div>"""
        self.send_html(body, "Add job")

    def pull_page(self, params):
        default_options = "".join("<option value='" + esc(board) + "'>" + esc(company) + " (" + esc(board) + ")</option>" for company, board in DEFAULT_GREENHOUSE_BOARDS.items())
        body = """
<div class="grid">
<section class="panel">
  <h1>One-click Pull</h1>
  <p class="muted">Pulls public Greenhouse, Lever, Eightfold, Workday CXS, Ashby, and Apple careers search sources. Jobs are scored, deduped, filtered, and auto-tailored.</p>
  <p class="muted">Non-US onsite roles and country-restricted non-US remote roles are filtered out unless the posting explicitly includes US eligibility.</p>
  <form method="post" action="/pull-defaults">
    <label>Limit per company</label><input name="limit" value="50">
    <p><button>Pull default public feeds</button></p>
  </form>
</section>
<aside class="panel">
  <h1>Custom ATS Pull</h1>
  <form method="post" action="/pull-greenhouse">
    <label>Known Greenhouse board</label><select name="board">""" + default_options + """</select>
    <label>Company name</label><input name="company" placeholder="Databricks">
    <label>Limit</label><input name="limit" value="20">
    <p><button>Pull Greenhouse</button></p>
  </form>
  <hr>
  <form method="post" action="/pull-lever">
    <label>Lever slug</label><input name="slug" placeholder="company-slug">
    <label>Company name</label><input name="company" placeholder="Company">
    <label>Limit</label><input name="limit" value="20">
    <p><button class="secondary">Pull Lever</button></p>
  </form>
  <hr>
  <form method="post" action="/pull-workday">
    <label>Workday base URL</label><input name="base_url" value="https://nvidia.wd5.myworkdayjobs.com">
    <label>Tenant</label><input name="tenant" value="nvidia">
    <label>Site</label><input name="site" value="NVIDIAExternalCareerSite">
    <label>Company name</label><input name="company" value="NVIDIA">
    <label>Search text</label><input name="search_text" value="software engineer">
    <label>Limit</label><input name="limit" value="20">
    <p><button class="secondary">Pull Workday</button></p>
  </form>
  <hr>
  <form method="post" action="/pull-ashby">
    <label>Ashby board</label><input name="board" value="openai">
    <label>Company name</label><input name="company" value="OpenAI">
    <label>Limit</label><input name="limit" value="20">
    <p><button class="secondary">Pull Ashby</button></p>
  </form>
  <hr>
  <form method="post" action="/pull-apple">
    <label>Apple careers search URL</label><input name="url" value="https://jobs.apple.com/en-us/search?sort=relevance&amp;search=software%20engineer&amp;location=united-states-USA">
    <label>Company name</label><input name="company" value="Apple">
    <label>Limit</label><input name="limit" value="20">
    <p><button class="secondary">Pull Apple</button></p>
  </form>
</aside>
</div>"""
        self.send_html(body, "Pull jobs")

    def agent_page(self, params):
        runs = recent_agent_runs(self.db_path, 10)
        ran = "<div class='panel'><b>Agent run complete.</b> New roles were scored, deduped, filtered, and auto-tailored.</div>" if params.get("ran") else ""
        rows = []
        for run in runs:
            added = (run.get("summary") or {}).get("added") or []
            rows.append("""
<article class="job">
  <div class="row"><span class="job-title">Run #""" + str(run.get("id")) + """</span><span class="pill">""" + esc(run.get("status")) + """</span></div>
  <div class="muted">""" + esc(run.get("finished_at") or run.get("started_at")) + """ · limit """ + str(run.get("limit_per_company") or "") + """ per company</div>
  <span class="pill score">Added """ + str(run.get("added_count") or 0) + """</span>
  <span class="pill">Skipped """ + str(run.get("skipped_count") or 0) + """</span>
  <span class="pill">Errors """ + str(run.get("error_count") or 0) + """</span>
  <ul>""" + "".join("<li>" + esc(item.get("company")) + " · " + esc(item.get("role")) + " · " + str(item.get("score")) + "</li>" for item in added[:5]) + """</ul>
</article>""")
        body = ran + """
<section class="hero">
  <div>
    <h1>Scraper Agent</h1>
    <p class="muted">Runs public ATS pulls, filters for US/remote eligibility, scores roles, dedupes, auto-tailors resumes, and records every run.</p>
  </div>
  <form method="post" action="/agent-run" class="row">
    <input name="limit" value="50" style="max-width:80px">
    <button>Run now</button>
  </form>
</section>
<div class="grid">
<section>
  <div class="panel agent-card">
    <h2>Routine Mode</h2>
    <p>For routine scraping, run this in a terminal and leave it open:</p>
    <pre>python3 -m rolefit_platform scrape-agent --interval-minutes 360 --limit 50</pre>
    <p class="muted">Use <code>--cycles 1</code> for one scheduled pass or <code>--once</code> for an immediate run. The UI reads the same run history.</p>
  </div>
  <div class="panel">
    <h2>Run History</h2>
    <div class="agent-log">""" + ("".join(rows) if rows else "<p class='muted'>No runs yet.</p>") + """</div>
  </div>
</section>
<aside>
  <div class="panel">
    <h2>Sources</h2>
""" + "".join("<p><b>" + esc(company) + "</b> · Greenhouse board <code>" + esc(board) + "</code></p>" for company, board in DEFAULT_GREENHOUSE_BOARDS.items()) + """
""" + "".join("<p><b>" + esc(company) + "</b> · Lever slug <code>" + esc(slug) + "</code></p>" for company, slug in DEFAULT_LEVER_SLUGS.items()) + """
""" + "".join("<p><b>" + esc(company) + "</b> · Eightfold page</p>" for company, url in DEFAULT_EIGHTFOLD_SITES.items()) + """
""" + "".join("<p><b>" + esc(company) + "</b> · Workday CXS site <code>" + esc(config["site"]) + "</code></p>" for company, config in DEFAULT_WORKDAY_SITES.items()) + """
""" + "".join("<p><b>" + esc(company) + "</b> · Ashby board <code>" + esc(board) + "</code></p>" for company, board in DEFAULT_ASHBY_BOARDS.items()) + """
""" + "".join("<p><b>" + esc(company) + "</b> · Apple careers HTML search</p>" for company, url in DEFAULT_APPLE_SEARCHES.items()) + """
""" + "".join("<p><b>" + esc(company) + "</b> · Guarded source<br><span class='muted'>" + esc(reason) + "</span></p>" for company, reason in GUARDED_SOURCES.items()) + """
  </div>
  <div class="panel">
    <h2>Guardrails</h2>
    <p class="muted">Skips senior/staff roles, internships, weak support roles, non-US restricted roles, and duplicate postings. Adds tailoring snapshots automatically for new matches.</p>
  </div>
</aside>
</div>"""
        self.send_html(body, "Scraper Agent")

    def matches_page(self, params):
        resume_path = (params.get("resume") or [DEFAULT_RESUME_PATH])[0]
        limit = int((params.get("limit") or ["8"])[0])
        resume = load_resume_text(resume_path)
        rows = top_resume_matches(self.db_path, resume, limit)
        tailored_notice = "<div class='panel'><b>Tailoring complete.</b> Missing tailored resumes were generated from the default resume.</div>" if params.get("tailored") else ""
        cards = []
        for row in rows:
            cards.append("""
<article class="job">
  <div class="row"><a class="job-title" href="/job?id=""" + str(row["id"]) + """">""" + esc(row["role"]) + """</a></div>
  <div class="muted">""" + esc(row["company"]) + """ · """ + esc(row["location"]) + """</div>
  <span class="pill score">Priority """ + str(row["combined_priority_score"]) + """</span>
  <span class="pill">Role """ + str(row["role_score"]) + """</span>
  <span class="pill">Resume """ + str(row["resume_match_score"]) + """</span>
  <span class="pill">""" + esc(row["readiness"]) + """</span>
  <p><b>Position as:</b> """ + esc(row["position_as"]) + """</p>
  <p><b>Covered:</b> """ + esc(", ".join(row["covered_keywords"][:12])) + """</p>
  <p><b>Missing:</b> """ + esc(", ".join(row["missing_keywords"][:12])) + """</p>
  <h3>Auto-Tailored Bullets</h3>
  <ul>""" + "".join("<li>" + esc(item) + "</li>" for item in row["rewritten_bullets"][:5]) + """</ul>
</article>""")
        body = tailored_notice + """
<div class="panel">
  <h1>Resume Matches</h1>
  <p class="muted">Ranks visible jobs by role score plus how well your current resume already covers the job requirements. New jobs are auto-tailored from the default resume.</p>
  <form method="get" action="/matches" class="row">
    <input name="resume" value=\"""" + esc(resume_path) + """\">
    <input name="limit" value=\"""" + str(limit) + """\" style="max-width:90px">
    <button>Refresh matches</button>
  </form>
  <form method="post" action="/auto-tailor" class="row">
    <button class="secondary">Generate missing tailored resumes</button>
  </form>
  <p><a class="button" href="/export-resumes?limit=""" + str(limit) + """">Export finished DOCX resumes</a></p>
</div>
""" + ("\n".join(cards) if cards else "<div class='panel'>No visible jobs to match yet.</div>")
        self.send_html(body, "Resume Matches")

    def interviews_page(self, params):
        rows = list_interviews(self.db_path, 50)
        added = "<div class='panel'><b>Interview saved.</b></div>" if params.get("added") else ""
        cards = []
        for row in rows:
            link = ""
            if row.get("job_id"):
                link = " <a class='button ghost' href='/job?id=" + str(row.get("job_id")) + "'>Open job</a>"
            cards.append("""
<article class="job">
  <div class="row"><span class="job-title">""" + esc(row.get("company")) + """ · """ + esc(row.get("stage")) + """</span>""" + link + """</div>
  <div class="muted">""" + esc(row.get("role")) + """</div>
  <span class="pill score">""" + esc(row.get("scheduled_at")) + """</span>
  <span class="pill">""" + esc(row.get("timezone")) + """</span>
  <span class="pill">""" + esc(row.get("format")) + """</span>
  <span class="pill">""" + esc(row.get("status")) + """</span>
  <p><b>Contact:</b> """ + esc(row.get("contact")) + """</p>
  <p><b>Prep focus:</b> """ + esc(row.get("prep_focus")) + """</p>
  <form method="post" action="/update-interview" class="row">
    <input type="hidden" name="interview_id" value=\"""" + str(row.get("id")) + """\">
    <select name="status" style="max-width:160px">
      <option value="scheduled" """ + ("selected" if row.get("status") == "scheduled" else "") + """>scheduled</option>
      <option value="completed" """ + ("selected" if row.get("status") == "completed" else "") + """>completed</option>
      <option value="rescheduled" """ + ("selected" if row.get("status") == "rescheduled" else "") + """>rescheduled</option>
      <option value="cancelled" """ + ("selected" if row.get("status") == "cancelled" else "") + """>cancelled</option>
    </select>
    <input name="notes" value=\"""" + esc(row.get("notes")) + """\" placeholder="Notes" style="min-width:260px; flex:1">
    <button>Save</button>
  </form>
</article>""")
        body = added + """
<div class="grid">
<section>
  <div class="panel">
    <h1>Interview Tracker</h1>
    <p class="muted">Track each interview as a scheduled event with stage, time, contact, format, prep focus, and outcome notes.</p>
  </div>
""" + ("\n".join(cards) if cards else "<div class='panel'>No interviews yet.</div>") + """
</section>
<aside class="panel">
  <h1>Add Interview</h1>
  <form method="post" action="/add-interview">
    <label>Company</label><input name="company" placeholder="Cloud Platform Co.">
    <label>Role</label><input name="role" placeholder="Systems Engineer II">
    <label>Stage</label><input name="stage" value="phone screen">
    <label>Scheduled at</label><input name="scheduled_at" type="datetime-local">
    <label>Timezone</label><input name="timezone" value="America/Chicago">
    <label>Format</label><input name="format" value="phone">
    <label>Contact</label><input name="contact" placeholder="Recruiter or interviewer">
    <label>Prep focus</label><input name="prep_focus" placeholder="Recruiter screen, role story, compensation, timeline">
    <label>Notes</label><textarea name="notes"></textarea>
    <input type="hidden" name="status" value="scheduled">
    <p><button>Add interview</button></p>
  </form>
</aside>
</div>"""
        self.send_html(body, "Interviews")

    def job_page(self, params):
        job_id = int((params.get("id") or ["0"])[0])
        job = get_job(self.db_path, job_id)
        if not job:
            self.send_html("<div class='panel'><h1>Job not found</h1></div>", status=404)
            return
        scoring_text = " ".join([
            job.get("role") or "",
            job.get("company") or "",
            job.get("location") or "",
            job.get("description") or "",
        ])
        classified = classify_job(scoring_text, job.get("company"))
        tailored = get_tailored_resume(self.db_path, job_id)
        if not tailored:
            tailored = auto_tailor_job(self.db_path, job_id)
        match = resume_match(scoring_text)
        prep = interview_prep(scoring_text)
        message = outreach_message("recruiter", job.get("company"), job.get("role"), "Hi")
        body = """
<div class="grid">
<section>
  <div class="panel">
    <h1>""" + esc(job.get("role")) + """</h1>
    <p class="muted">""" + esc(job.get("company")) + """ · """ + esc(job.get("location")) + """</p>
    <p><span class="pill score">Score """ + str(job.get("score") or 0) + """</span><span class="pill">Infra """ + str(job.get("infrastructure_alignment_score") or 0) + """</span><span class="pill">""" + esc(job.get("apply_decision")) + """</span><span class="pill">""" + esc(job.get("status")) + """</span><span class="pill">""" + esc(posted_label(job)) + """</span><span class="pill">Source """ + esc(job.get("source") or "manual") + """</span></p>
    <p>""" + ("<a class='button ghost' target='_blank' href='" + esc(job.get("link")) + "'>Open posting</a>" if job.get("link") else "") + """</p>
    <h2>Decision Reasoning</h2><p>""" + esc(classified["reasoning"]) + """</p>
    <h2>Current Resume Match</h2><p><b>""" + str(match["resume_match_score"]) + """/100</b> · """ + esc(match["readiness"]) + """</p>
    <p><b>Covered:</b> """ + esc(", ".join(match["covered_keywords"][:12])) + """</p>
    <p><b>Missing:</b> """ + esc(", ".join(match["missing_keywords"][:12])) + """</p>
    <h2>Infrastructure Alignment</h2><p>""" + esc(classified["alignment"]["reasoning"]) + """</p>
  </div>
  <div class="panel">
    <h2>Tailored Resume Bullets</h2>
    <ul>""" + "".join("<li>" + esc(item) + "</li>" for item in tailored["rewritten_bullets"]) + """</ul>
    <p><b>Position as:</b> """ + esc(tailored["position_as"]) + """</p>
    <p><b>Keywords:</b> """ + esc(", ".join(tailored["keywords_to_inject"])) + """</p>
    <p><b>Emphasize:</b> """ + esc(", ".join(tailored["oracle_work_to_emphasize"])) + """</p>
  </div>
  <div class="panel">
    <h2>Interview Prep</h2>
    <p><b>DSA:</b> """ + esc(", ".join(prep["likely_dsa_topics"])) + """</p>
    <p><b>System design:</b> """ + esc(", ".join(prep["system_design_topics"])) + """</p>
    <p><b>Cloud/platform:</b> """ + esc(", ".join(prep["cloud_platform_concepts"])) + """</p>
  </div>
</section>
<aside>
  <div class="panel">
    <h2>Update Status</h2>
    <form method="post" action="/update-status">
      <input type="hidden" name="job_id" value=\"""" + str(job_id) + """\">
      <label>Status</label><select name="status">
        """ + status_options(job.get("status")) + """
      </select>
      <label>Contact</label><input name="contact" value=\"""" + esc(job.get("contact")) + """\">
      <label>Notes</label><textarea name="notes">""" + esc(job.get("notes")) + """</textarea>
      <p><button>Update</button></p>
    </form>
  </div>
  <div class="panel">
    <h2>Add Interview</h2>
    <form method="post" action="/add-interview">
      <input type="hidden" name="job_id" value=\"""" + str(job_id) + """\">
      <input type="hidden" name="from_job" value="1">
      <label>Stage</label><input name="stage" value="phone screen">
      <label>Scheduled at</label><input name="scheduled_at" type="datetime-local">
      <label>Timezone</label><input name="timezone" value="America/Chicago">
      <label>Format</label><input name="format" value="phone">
      <label>Contact</label><input name="contact" value=\"""" + esc(job.get("contact")) + """\">
      <label>Prep focus</label><input name="prep_focus" placeholder="Recruiter screen, project story, role fit">
      <label>Notes</label><textarea name="notes"></textarea>
      <input type="hidden" name="status" value="scheduled">
      <p><button>Add interview</button></p>
    </form>
  </div>
  <div class="panel">
    <h2>Contact Message</h2>
    <pre>""" + esc(message) + """</pre>
  </div>
</aside>
</div>"""
        self.send_html(body, esc(job.get("role") or "Job"))


def serve(db_path, host="127.0.0.1", port=8765, open_browser=True):
    ensure_db_dir(db_path)
    App.db_path = db_path
    server = ThreadingHTTPServer((host, port), App)
    url = "http://" + host + ":" + str(port)
    if open_browser:
        webbrowser.open(url)
    print("rolefit-platform UI running at " + url)
    print("Press Ctrl+C to stop.")
    server.serve_forever()
