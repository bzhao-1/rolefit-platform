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
from rolefit_platform.sources import DEFAULT_GREENHOUSE_BOARDS, SAVED_SEARCH_LINKS, pull_defaults, pull_greenhouse, pull_lever
from rolefit_platform.storage import add_interview, add_job, export_jobs, get_job, get_tailored_resume, list_interviews, list_jobs, stats, update_interview, update_status
from rolefit_platform.text_utils import load_text_from_url


def esc(value):
    return html.escape(str(value or ""))


def status_options(current):
    statuses = ["saved", "pulled", "referral requested", "review requested", "applied", "interview", "offer", "rejected", "skipped"]
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
    :root { color-scheme: light; --ink:#172026; --muted:#5c6873; --line:#d9e0e7; --bg:#f6f8fa; --panel:#ffffff; --accent:#0f766e; --good:#0a7a37; --warn:#9a5b00; --bad:#b42318; }
    * { box-sizing:border-box; }
    body { margin:0; font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--bg); }
    header { position:sticky; top:0; z-index:1; background:rgba(255,255,255,.94); border-bottom:1px solid var(--line); backdrop-filter:blur(8px); }
    nav { max-width:1180px; margin:0 auto; padding:12px 18px; display:flex; align-items:center; gap:14px; }
    nav a { color:var(--ink); text-decoration:none; font-weight:650; }
    nav .brand { margin-right:auto; font-size:17px; }
    main { max-width:1180px; margin:0 auto; padding:18px; }
    .grid { display:grid; grid-template-columns:1.05fr .95fr; gap:16px; align-items:start; }
    .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px; }
    .stat, .panel, .job { background:var(--panel); border:1px solid var(--line); border-radius:8px; }
    .stat { padding:12px; }
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
    .job-title { font-weight:750; font-size:15px; }
    .pill { display:inline-flex; align-items:center; min-height:24px; padding:2px 8px; border-radius:999px; background:#eef3f7; margin:4px 4px 0 0; font-size:12px; font-weight:650; }
    .score { color:var(--good); }
    .warn { color:var(--warn); }
    .bad { color:var(--bad); }
    pre { white-space:pre-wrap; background:#f1f5f9; border:1px solid var(--line); border-radius:8px; padding:12px; overflow:auto; }
    ul { margin-top:6px; padding-left:20px; }
    @media (max-width: 820px) { .grid, .stats { grid-template-columns:1fr; } nav { overflow:auto; } }
  </style>
</head>
<body>
  <header><nav>
    <a class="brand" href="/">rolefit-platform</a>
    <a href="/">Dashboard</a>
    <a href="/add">Add</a>
    <a href="/pull">Pull</a>
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
        summary = stats(self.db_path)
        pulled = "<div class='panel'><b>Pull complete.</b> New jobs were scored and deduped.</div>" if params.get("pulled") else ""
        cleaned = "<div class='panel'><b>Cleanup complete.</b> Non-US restricted jobs are now hidden as skipped.</div>" if params.get("cleaned") else ""
        body = pulled + cleaned + """
<div class="stats">
  <div class="stat"><span class="muted">Tracked</span><b>""" + str(summary["total"]) + """</b></div>
  <div class="stat"><span class="muted">75+ score</span><b>""" + str(summary["top_fit"]) + """</b></div>
  <div class="stat"><span class="muted">Applied</span><b>""" + str(summary["by_status"].get("applied", 0)) + """</b></div>
  <div class="stat"><span class="muted">Scheduled</span><b>""" + str(summary["scheduled_interviews"]) + """</b></div>
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
""" + self.jobs_html(rows) + """
</section>
<aside>
  <div class="panel">
    <h2>Upcoming Interviews</h2>
""" + self.interviews_compact_html(interviews) + """
    <p><a class="button ghost" href="/interviews">Open interview tracker</a></p>
  </div>
  <div class="panel">
    <h2>Fast Workflow</h2>
    <p class="muted">Pull feeds or paste a posting, inspect the highest-scored roles, review resume fit, and export structured tracker data. Location rule: show US-eligible roles and global/anywhere remote roles only.</p>
    <form method="post" action="/pull-defaults">
      <label>One-click pull limit per company</label>
      <input name="limit" value="12">
      <p><button>Pull default public feeds</button></p>
    </form>
    <form method="post" action="/cleanup-locations">
      <p><button class="secondary">Clean up old non-US jobs</button></p>
    </form>
    <form method="post" action="/auto-tailor">
      <p><button class="ghost">Generate missing tailored resumes</button></p>
    </form>
  </div>
  <div class="panel">
    <h2>Custom Sources</h2>
    <p class="muted">Add guarded career sites or curated source links in <code>sources.py</code>, then paste selected posting URLs back into the dashboard.</p>
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
    <label>Contact</label><input name="contact" placeholder="Team contact or source">
    <label>Notes</label><input name="notes" placeholder="Ownership, scope, or screening notes">
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
  <h3>Default Projects</h3>
  <p>""" + esc(", ".join(project["name"] for project in row.get("projects") or [])) + """</p>
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
    <label>Prep focus</label><input name="prep_focus" placeholder="Recruiter screen, role story, timeline, compensation">
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
    <p><b>Emphasize:</b> """ + esc(", ".join(tailored.get("experience_to_emphasize") or [])) + """</p>
    <p><b>Projects:</b> """ + esc(", ".join(project["name"] for project in tailored.get("projects") or [])) + """</p>
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
    <h2>Outreach Note</h2>
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
