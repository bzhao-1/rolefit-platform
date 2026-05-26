import html
import json
import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from rolefit_platform.auto_tailor import DEFAULT_RESUME_PATH, auto_tailor_job, auto_tailor_jobs
from rolefit_platform.classifier import classify_job
from rolefit_platform.maintenance import cleanup_locations
from rolefit_platform.prep import interview_prep
from rolefit_platform.outreach import outreach_message
from rolefit_platform.resume import tailor_resume
from rolefit_platform.resume_export import DEFAULT_OUTPUT_DIR, export_finished_resumes
from rolefit_platform.resume_match import load_resume_text, resume_match, top_resume_matches
from rolefit_platform.scraper_agent import recent_agent_runs, run_scraper_once
from rolefit_platform.sources import DEFAULT_GREENHOUSE_BOARDS, SAVED_SEARCH_LINKS, pull_defaults, pull_greenhouse, pull_lever
from rolefit_platform.storage import add_interview, add_job, export_jobs, get_job, get_tailored_resume, list_interviews, list_jobs, stats, update_interview, update_status
from rolefit_platform.text_utils import load_text_from_url


def esc(value):
    return html.escape(str(value or ""))


def status_options(current):
    statuses = ["saved", "pulled", "referral requested", "applied", "interview", "offer", "rejected", "skipped"]
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


def layout(title, body):
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>""" + esc(title) + """</title>
  <style>
    :root { color-scheme: light; --ink:#18212f; --muted:#647183; --line:#d8e0ea; --bg:#f4f7fb; --panel:#ffffff; --soft:#eef6f4; --accent:#0f766e; --accent2:#1d4ed8; --good:#0a7a37; --warn:#9a5b00; --bad:#b42318; }
    * { box-sizing:border-box; }
    body { margin:0; font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:linear-gradient(180deg,#f8fbff 0,#f4f7fb 220px); }
    header { position:sticky; top:0; z-index:1; background:rgba(255,255,255,.94); border-bottom:1px solid var(--line); backdrop-filter:blur(8px); }
    nav { max-width:1180px; margin:0 auto; padding:12px 18px; display:flex; align-items:center; gap:14px; }
    nav a { color:var(--ink); text-decoration:none; font-weight:650; }
    nav .brand { margin-right:auto; font-size:17px; }
    main { max-width:1280px; margin:0 auto; padding:18px; }
    .hero { display:grid; grid-template-columns:1fr auto; gap:16px; align-items:end; margin-bottom:16px; }
    .hero h1 { font-size:28px; margin-bottom:4px; }
    .grid { display:grid; grid-template-columns:minmax(0,1.3fr) minmax(340px,.7fr); gap:16px; align-items:start; }
    .three { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
    .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px; }
    .stat, .panel, .job { background:var(--panel); border:1px solid var(--line); border-radius:8px; }
    .stat { padding:12px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
    .stat b { display:block; font-size:22px; }
    .panel { padding:14px; margin-bottom:16px; }
    h1, h2, h3 { margin:0 0 10px; letter-spacing:0; }
    h1 { font-size:22px; }
    h2 { font-size:16px; }
    label { display:block; font-weight:650; margin:10px 0 4px; }
    input, textarea, select { width:100%; border:1px solid var(--line); border-radius:6px; padding:9px 10px; font:inherit; background:#fff; color:var(--ink); }
    textarea { min-height:150px; resize:vertical; }
    button, .button { border:0; border-radius:6px; background:var(--accent); color:#fff; padding:9px 12px; font-weight:700; cursor:pointer; text-decoration:none; display:inline-block; }
    .secondary { background:#334155; }
    .ghost { background:#eef3f7; color:var(--ink); }
    .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
    .muted { color:var(--muted); }
    .job { padding:12px; margin-bottom:10px; }
    .job-title { font-weight:750; font-size:15px; color:var(--ink); text-decoration:none; }
    .pill { display:inline-flex; align-items:center; min-height:24px; padding:2px 8px; border-radius:999px; background:#eef3f7; margin:4px 4px 0 0; font-size:12px; font-weight:650; }
    .stage { border-left:4px solid var(--accent); }
    .stage h2 { display:flex; justify-content:space-between; gap:8px; align-items:center; }
    .stage-count { color:var(--muted); font-size:12px; }
    .agent-card { background:linear-gradient(135deg,#eaf7f4,#eef4ff); border-color:#c9ddd8; }
    .agent-log { max-height:220px; overflow:auto; }
    .split { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .score { color:var(--good); }
    .warn { color:var(--warn); }
    .bad { color:var(--bad); }
    pre { white-space:pre-wrap; background:#f1f5f9; border:1px solid var(--line); border-radius:8px; padding:12px; overflow:auto; }
    ul { margin-top:6px; padding-left:20px; }
    @media (max-width: 900px) { .grid, .stats, .three, .hero, .split { grid-template-columns:1fr; } nav { overflow:auto; } }
  </style>
</head>
<body>
  <header><nav>
    <a class="brand" href="/">rolefit-platform</a>
    <a href="/">Dashboard</a>
    <a href="/add">Add</a>
    <a href="/pull">Pull</a>
    <a href="/agent">Agent</a>
    <a href="/matches">Resume Matches</a>
    <a href="/interviews">Interviews</a>
    <a href="/export">Export</a>
  </nav></header>
  <main>""" + body + """</main>
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
            pull_defaults(self.db_path, int(data.get("limit") or "12"))
            self.redirect("/?pulled=1")
        elif parsed.path == "/agent-run":
            run_scraper_once(self.db_path, int(data.get("limit") or "12"), DEFAULT_RESUME_PATH)
            self.redirect("/agent?ran=1")
        elif parsed.path == "/pull-greenhouse":
            pull_greenhouse(self.db_path, data.get("board", ""), data.get("company", ""), int(data.get("limit") or "20"))
            self.redirect("/?pulled=1")
        elif parsed.path == "/pull-lever":
            pull_lever(self.db_path, data.get("slug", ""), data.get("company", ""), int(data.get("limit") or "20"))
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
        rows = list_jobs(self.db_path, 80)
        interviews = list_interviews(self.db_path, 5, "scheduled")
        runs = recent_agent_runs(self.db_path, 3)
        summary = stats(self.db_path)
        pulled = "<div class='panel'><b>Pull complete.</b> New jobs were scored and deduped.</div>" if params.get("pulled") else ""
        cleaned = "<div class='panel'><b>Cleanup complete.</b> Non-US restricted jobs are now hidden as skipped.</div>" if params.get("cleaned") else ""
        body = pulled + cleaned + """
<section class="hero">
  <div>
    <h1>Job Search Cockpit</h1>
    <p class="muted">Agent-assisted sourcing, scoring, resume tailoring, interviews, and follow-through in one local workflow.</p>
  </div>
  <form method="post" action="/agent-run" class="row">
    <input name="limit" value="12" style="max-width:80px">
    <button>Run scraper agent</button>
  </form>
</section>
<div class="stats">
  <div class="stat"><span class="muted">Tracked</span><b>""" + str(summary["total"]) + """</b></div>
  <div class="stat"><span class="muted">75+ score</span><b>""" + str(summary["top_fit"]) + """</b></div>
  <div class="stat"><span class="muted">Applied</span><b>""" + str(summary["by_status"].get("applied", 0)) + """</b></div>
  <div class="stat"><span class="muted">Scheduled</span><b>""" + str(summary["scheduled_interviews"]) + """</b></div>
</div>
<div class="three">
  <div class="panel agent-card">
    <h2>Agent</h2>
    """ + self.agent_status_html(runs) + """
    <p><a class="button ghost" href="/agent">Tune sources</a></p>
  </div>
  <div class="panel">
    <h2>Next Best Action</h2>
    """ + self.next_action_html(rows, interviews) + """
  </div>
  <div class="panel">
    <h2>Upcoming</h2>
    """ + self.interviews_compact_html(interviews) + """
  </div>
</div>
<div class="grid">
<section>
  <div class="panel row">
    <a class="button" href="/add">Add job</a>
    <a class="button secondary" href="/pull">Pull public feeds</a>
    <a class="button ghost" href="/interviews">Interviews</a>
    <a class="button ghost" href="/export">Export CSV</a>
    <a class="button ghost" href="/export-resumes">Export resumes</a>
  </div>
""" + self.pipeline_html(rows) + """
</section>
<aside>
  <div class="panel">
    <h2>Fast Workflow</h2>
    <p class="muted">Review the agent discoveries, move strong matches to referral or applied, then prep from the job page. Location rule: US roles and global/anywhere remote only.</p>
    <div class="row">
      <a class="button" href="/matches">Resume matches</a>
      <a class="button ghost" href="/interviews">Interview tracker</a>
      <a class="button ghost" href="/export-resumes">Export resumes</a>
    </div>
  </div>
  <div class="panel">
    <h2>Manual Search Links</h2>
    <p class="muted">These companies use more guarded career sites, so open them and paste URLs back here.</p>
""" + "".join("<p><a href='" + esc(url) + "' target='_blank'>" + esc(company) + "</a></p>" for company, url in SAVED_SEARCH_LINKS) + """
  </div>
</aside>
</div>"""
        self.send_html(body)

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

    def pipeline_html(self, rows):
        groups = [
            ("New high-fit", lambda row: row.get("status") in ["pulled", "saved"] and (row.get("score") or 0) >= 75),
            ("Referral / apply", lambda row: row.get("status") in ["referral requested", "applied"]),
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
    <label>Company</label><input name="company" placeholder="Example Cloud Co.">
    <label>Role</label><input name="role" placeholder="Software Engineer II, Cloud Platform">
    <label>Location</label><input name="location" placeholder="Santa Clara, CA / Remote">
    <label>Link</label><input name="link" placeholder="https://...">
    <label>Description</label><textarea name="description" placeholder="Paste the job description here"></textarea>
    <label>Referral contact</label><input name="contact" placeholder="Platform team contact">
    <label>Notes</label><input name="notes" placeholder="Ask for team guidance first">
    <input type="hidden" name="status" value="saved">
    <p><button>Score and save</button></p>
  </form>
</section>
<aside class="panel">
  <h1>Add by URL</h1>
  <form method="post" action="/add-url">
    <label>Company</label><input name="company" placeholder="Example Platform Co.">
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
  <p class="muted">Pulls public Greenhouse boards for Anthropic, CoreWeave, Databricks, Datadog, Elastic, Grafana Labs, MongoDB, Stripe, and Cloudflare. Jobs are scored and deduped.</p>
  <p class="muted">Non-US onsite roles and country-restricted non-US remote roles are filtered out unless the posting explicitly includes US eligibility.</p>
  <form method="post" action="/pull-defaults">
    <label>Limit per company</label><input name="limit" value="12">
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
    <input name="limit" value="12" style="max-width:80px">
    <button>Run now</button>
  </form>
</section>
<div class="grid">
<section>
  <div class="panel agent-card">
    <h2>Routine Mode</h2>
    <p>For routine scraping, run this in a terminal and leave it open:</p>
    <pre>python3 -m rolefit_platform scrape-agent --interval-minutes 360 --limit 12</pre>
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
    <label>Company</label><input name="company" placeholder="Example Cloud Co.">
    <label>Role</label><input name="role" placeholder="Software Engineer II">
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
    <p><span class="pill score">Score """ + str(job.get("score") or 0) + """</span><span class="pill">Infra """ + str(job.get("infrastructure_alignment_score") or 0) + """</span><span class="pill">""" + esc(job.get("apply_decision")) + """</span><span class="pill">""" + esc(job.get("status")) + """</span></p>
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
    <p><b>Emphasize:</b> """ + esc(", ".join(tailored["experience_to_emphasize"])) + """</p>
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
      <label>Referral contact</label><input name="contact" value=\"""" + esc(job.get("contact")) + """\">
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
    <h2>Referral Message</h2>
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
