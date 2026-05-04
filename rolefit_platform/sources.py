import json
import re
import urllib.parse
import urllib.request
import html

from rolefit_platform.auto_tailor import auto_tailor_job
from rolefit_platform.classifier import classify_job
from rolefit_platform.location import NON_US_SIGNALS, US_SIGNALS, has_signal, location_fit
from rolefit_platform.storage import add_job, find_existing_job
from rolefit_platform.text_utils import normalize


DEFAULT_GREENHOUSE_BOARDS = {
    "Anthropic": "anthropic",
    "CoreWeave": "coreweave",
    "Databricks": "databricks",
    "Datadog": "datadog",
    "Elastic": "elastic",
    "Grafana Labs": "grafanalabs",
    "MongoDB": "mongodb",
    "Stripe": "stripe",
    "Cloudflare": "cloudflare",
}

US_LOCATION_DISPLAY = [
    ("austin", "Austin, TX"),
    ("atlanta", "Atlanta, GA"),
    ("denver", "Denver, CO"),
    ("washington", "Washington, DC"),
    ("san francisco", "San Francisco, CA"),
    ("san jose", "San Jose, CA"),
    ("santa clara", "Santa Clara, CA"),
    ("sunnyvale", "Sunnyvale, CA"),
    ("mountain view", "Mountain View, CA"),
    ("menlo park", "Menlo Park, CA"),
    ("palo alto", "Palo Alto, CA"),
    ("seattle", "Seattle, WA"),
    ("redmond", "Redmond, WA"),
    ("new york", "New York, NY"),
]


SAVED_SEARCH_LINKS = []


ROLE_FILTER = [
    "software engineer", "backend", "platform", "infrastructure", "cloud", "distributed",
    "reliability", "sre", "developer infrastructure", "build", "release", "deployment",
    "kubernetes", "ai infrastructure", "compute",
]

TITLE_FILTER = [
    "software engineer", "backend engineer", "platform engineer", "infrastructure engineer",
    "cloud engineer", "site reliability", "sre", "reliability engineer", "build engineer",
    "release engineer", "developer infrastructure", "systems engineer", "distributed systems",
]

TITLE_AVOID = ["senior", "sr.", "sr ", "staff", "principal", "intern", "new grad", "graduate", "lead", "manager"]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rolefit-platform/0.1"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def strip_html(value):
    unescaped = html.unescape(value or "")
    return normalize(re.sub(r"<[^>]+>", " ", unescaped))


def display_location(title, location, text):
    title_lower = (title or "").lower()
    location_lower = (location or "").lower()
    text_lower = (text or "").lower()
    if "remote" in title_lower and any(term in title_lower for term in ["usa", "united states", "us remote"]):
        return "USA (Remote)"
    if "remote" in text_lower and any(term in text_lower for term in ["united states time zones", "usa time zones", "applicants from usa"]):
        return "USA (Remote)"
    if has_signal(location_lower, US_SIGNALS) and has_signal(location_lower, NON_US_SIGNALS):
        found = []
        for marker, label in US_LOCATION_DISPLAY:
            if marker in location_lower and label not in found:
                found.append(label)
        if found:
            return ", ".join(found)
    return location


def greenhouse_jobs(board, company, limit=25):
    url = "https://boards-api.greenhouse.io/v1/boards/" + urllib.parse.quote(board) + "/jobs?content=true"
    data = fetch_json(url)
    jobs = []
    for item in data.get("jobs", []):
        title = item.get("title") or ""
        location = ", ".join(location.get("name", "") for location in item.get("offices", []) if location.get("name"))
        departments = ", ".join(dept.get("name", "") for dept in item.get("departments", []) if dept.get("name"))
        content = strip_html(item.get("content") or "")
        text = normalize(" ".join([title, company, location, departments, content]))
        title_blob = (title + " " + departments).lower()
        if any(term in title_blob for term in TITLE_AVOID):
            continue
        if not location_fit(title)["ok"]:
            continue
        if location and not location_fit(location)["ok"]:
            continue
        if not any(term in title_blob for term in TITLE_FILTER):
            continue
        if not any(term in text.lower() for term in ROLE_FILTER):
            continue
        if not location_fit(text)["ok"]:
            continue
        jobs.append({
            "company": company,
            "role": title,
            "location": display_location(title, location, text),
            "link": item.get("absolute_url"),
            "description": text,
            "notes": "Pulled from Greenhouse board: " + board,
        })
        if len(jobs) >= limit:
            break
    return jobs


def lever_jobs(slug, company, limit=25):
    url = "https://api.lever.co/v0/postings/" + urllib.parse.quote(slug) + "?mode=json"
    data = fetch_json(url)
    jobs = []
    for item in data:
        title = item.get("text") or ""
        location = (item.get("categories") or {}).get("location", "")
        team = (item.get("categories") or {}).get("team", "")
        content = " ".join(section.get("content", "") for section in item.get("lists", []))
        text = normalize(" ".join([title, company, location, team, strip_html(content), item.get("descriptionPlain", "")]))
        title_blob = (title + " " + team).lower()
        if any(term in title_blob for term in TITLE_AVOID):
            continue
        if not location_fit(title)["ok"]:
            continue
        if location and not location_fit(location)["ok"]:
            continue
        if not any(term in title_blob for term in TITLE_FILTER):
            continue
        if not any(term in text.lower() for term in ROLE_FILTER):
            continue
        if not location_fit(text)["ok"]:
            continue
        jobs.append({
            "company": company,
            "role": title,
            "location": display_location(title, location, text),
            "link": item.get("hostedUrl"),
            "description": text,
            "notes": "Pulled from Lever slug: " + slug,
        })
        if len(jobs) >= limit:
            break
    return jobs


def score_and_store(db_path, jobs):
    added = []
    skipped = []
    for job in jobs:
        existing = find_existing_job(db_path, job.get("company"), job.get("role"), job.get("link"))
        if existing:
            skipped.append({"reason": "duplicate", "id": existing["id"], "role": job.get("role")})
            continue
        classified = classify_job(job.get("description", ""), job.get("company"))
        if classified["decision"] == "Skip":
            skipped.append({"reason": classified["reasoning"], "role": job.get("role")})
            continue
        job["score"] = classified["score"]["score"]
        job["infrastructure_alignment_score"] = classified["alignment"]["similarity_score"]
        job["apply_decision"] = classified["decision"]
        job["status"] = "pulled"
        job["notes"] = (job.get("notes") or "") + " | " + classified["reasoning"]
        job_id = add_job(db_path, job)
        auto_tailor_job(db_path, job_id)
        added.append({
            "id": job_id,
            "company": job.get("company"),
            "role": job.get("role"),
            "score": job["score"],
            "infrastructure_alignment_score": job["infrastructure_alignment_score"],
            "apply_decision": job["apply_decision"],
        })
    return {"added": added, "skipped": skipped}


def pull_greenhouse(db_path, board, company, limit=25):
    if not company:
        for known_company, known_board in DEFAULT_GREENHOUSE_BOARDS.items():
            if known_board == board:
                company = known_company
                break
    return score_and_store(db_path, greenhouse_jobs(board, company, limit))


def pull_lever(db_path, slug, company, limit=25):
    return score_and_store(db_path, lever_jobs(slug, company, limit))


def pull_defaults(db_path, limit_per_company=20):
    results = {}
    for company, board in DEFAULT_GREENHOUSE_BOARDS.items():
        try:
            results[company] = pull_greenhouse(db_path, board, company, limit_per_company)
        except Exception as exc:
            results[company] = {"error": str(exc), "added": [], "skipped": []}
    return results
