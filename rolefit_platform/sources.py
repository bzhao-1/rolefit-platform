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

DEFAULT_LEVER_SLUGS = {
    "Palantir": "palantir",
}

DEFAULT_EIGHTFOLD_SITES = {
    "Netflix": "https://explore.jobs.netflix.net/careers",
}

DEFAULT_WORKDAY_SITES = {
    "NVIDIA": {
        "base_url": "https://nvidia.wd5.myworkdayjobs.com",
        "tenant": "nvidia",
        "site": "NVIDIAExternalCareerSite",
        "search_text": "software engineer",
    },
}

DEFAULT_ASHBY_BOARDS = {
    "OpenAI": "openai",
}

DEFAULT_APPLE_SEARCHES = {
    "Apple": "https://jobs.apple.com/en-us/search?sort=relevance&search=software%20engineer&location=united-states-USA",
}

GUARDED_SOURCES = {
    "Google": "Careers search exposes dynamic result markup; use saved search/manual link until a stable parser is enabled.",
    "Meta": "Careers search is heavily dynamic; keep as manual link unless browser automation is enabled.",
    "Microsoft AI": "Careers search endpoint details are unstable; keep as manual link for now.",
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


SAVED_SEARCH_LINKS = [
    ("NVIDIA", "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"),
    ("Google", "https://www.google.com/about/careers/applications/jobs/results/"),
    ("Apple", "https://jobs.apple.com/en-us/search"),
    ("Meta", "https://www.metacareers.com/jobs/"),
    ("Netflix", "https://explore.jobs.netflix.net/careers"),
    ("OpenAI", "https://openai.com/careers/search/"),
    ("Microsoft AI", "https://jobs.careers.microsoft.com/global/en/search"),
    ("Palantir", "https://www.palantir.com/careers/"),
]


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

TITLE_AVOID = [
    "senior", "sr.", "sr ", "staff", "principal", "intern", "new grad",
    "graduate", "lead", "manager", "software engineer 4", "software engineer 5",
    "software engineering 4", "software engineering 5", "engineer in test",
    "embedded", "firmware",
]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rolefit-platform/0.1"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def post_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"User-Agent": "Mozilla/5.0 rolefit-platform/0.1", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 rolefit-platform/0.1"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", "ignore")


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


def job_passes(title, company, location, text, extra_title=""):
    title_blob = normalize(" ".join([title or "", extra_title or ""])).lower()
    full_text = normalize(" ".join([title or "", company or "", location or "", text or ""]))
    if any(term in title_blob for term in TITLE_AVOID):
        return False
    if not location_fit(title or "")["ok"]:
        return False
    if location and not location_fit(location)["ok"]:
        return False
    if not any(term in title_blob for term in TITLE_FILTER):
        return False
    if not any(term in full_text.lower() for term in ROLE_FILTER):
        return False
    if not location_fit(full_text)["ok"]:
        return False
    return True


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
        if not job_passes(title, company, location, text, departments):
            continue
        jobs.append({
            "company": company,
            "role": title,
            "location": display_location(title, location, text),
            "link": item.get("absolute_url"),
            "description": text,
            "posted_at": item.get("updated_at"),
            "source": "Greenhouse",
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
        if not job_passes(title, company, location, text, team):
            continue
        jobs.append({
            "company": company,
            "role": title,
            "location": display_location(title, location, text),
            "link": item.get("hostedUrl"),
            "description": text,
            "posted_at": str(item.get("createdAt") or ""),
            "source": "Lever",
            "notes": "Pulled from Lever slug: " + slug,
        })
        if len(jobs) >= limit:
            break
    return jobs


def extract_eightfold_objects(page):
    decoded = html.unescape(page or "")
    objects = []
    for match in re.finditer(r'\{[^{}]*"canonicalPositionUrl"\s*:\s*"[^"]+"[^{}]*\}', decoded):
        raw = match.group(0)
        try:
            objects.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return objects


def eightfold_jobs(url, company, limit=25):
    page = fetch_text(url)
    jobs = []
    seen = set()
    for item in extract_eightfold_objects(page):
        title = item.get("posting_name") or item.get("name") or ""
        locations = item.get("locations") or [item.get("location") or ""]
        location = ", ".join(location for location in locations if location)
        description = strip_html(item.get("job_description") or "")
        link = item.get("canonicalPositionUrl")
        if not title or not link or link in seen:
            continue
        seen.add(link)
        text = normalize(" ".join([title, company, location, item.get("department") or "", description]))
        if not job_passes(title, company, location, text):
            continue
        jobs.append({
            "company": company,
            "role": title,
            "location": display_location(title, location, text),
            "link": link,
            "description": text,
            "posted_at": item.get("posted_date") or item.get("date_posted") or item.get("posted_on"),
            "source": "Eightfold",
            "notes": "Pulled from Eightfold careers page: " + url,
        })
        if len(jobs) >= limit:
            break
    return jobs


def workday_detail(base_url, tenant, site, external_path):
    url = base_url.rstrip("/") + "/wday/cxs/" + urllib.parse.quote(tenant) + "/" + urllib.parse.quote(site) + external_path
    return fetch_json(url)


def workday_jobs(base_url, tenant, site, company, search_text="software engineer", limit=25):
    endpoint = base_url.rstrip("/") + "/wday/cxs/" + urllib.parse.quote(tenant) + "/" + urllib.parse.quote(site) + "/jobs"
    payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": search_text}
    data = post_json(endpoint, payload)
    jobs = []
    seen = set()
    for item in data.get("jobPostings", []):
        title = item.get("title") or ""
        external_path = item.get("externalPath") or ""
        if not title or not external_path or external_path in seen:
            continue
        seen.add(external_path)
        info = {}
        try:
            info = (workday_detail(base_url, tenant, site, external_path).get("jobPostingInfo") or {})
        except Exception:
            info = {}
        title = info.get("title") or title
        locations = []
        if info.get("location"):
            locations.append(info.get("location"))
        for location in info.get("additionalLocations") or []:
            if location:
                locations.append(location)
        if not locations and item.get("locationsText"):
            locations.append(item.get("locationsText"))
        location = ", ".join(locations)
        description = strip_html(info.get("jobDescription") or "")
        text = normalize(" ".join([title, company, location, item.get("postedOn") or "", description]))
        if not job_passes(title, company, location, text):
            continue
        link = info.get("externalUrl") or (base_url.rstrip("/") + "/" + urllib.parse.quote(site) + external_path)
        jobs.append({
            "company": company,
            "role": title,
            "location": display_location(title, location, text),
            "link": link,
            "description": text,
            "posted_at": info.get("postedOn") or item.get("postedOn"),
            "source": "Workday",
            "notes": "Pulled from Workday CXS site: " + site,
        })
        if len(jobs) >= limit:
            break
    return jobs


def ashby_jobs(board, company, limit=25):
    url = "https://api.ashbyhq.com/posting-api/job-board/" + urllib.parse.quote(board)
    data = fetch_json(url)
    jobs = []
    for item in data.get("jobs", []):
        title = item.get("title") or ""
        location = item.get("location") or ""
        secondary = ", ".join(loc.get("location", "") for loc in item.get("secondaryLocations", []) if loc.get("location"))
        if secondary:
            location = ", ".join(value for value in [location, secondary] if value)
        description = strip_html(item.get("descriptionHtml") or "")
        text = normalize(" ".join([title, company, location, item.get("department") or "", item.get("team") or "", description]))
        if not job_passes(title, company, location, text):
            continue
        jobs.append({
            "company": company,
            "role": title,
            "location": display_location(title, location, text),
            "link": item.get("jobUrl"),
            "description": text,
            "posted_at": item.get("publishedAt"),
            "source": "Ashby",
            "notes": "Pulled from Ashby board: " + board,
        })
        if len(jobs) >= limit:
            break
    return jobs


def extract_apple_cards(page):
    decoded = html.unescape(page or "")
    pattern = re.compile(
        r'<a class="link-inline[^"]*"[^>]*aria-label="([^"]+)" href="([^"]+)"[^>]*>(.*?)</a>'
        r'.*?<span[^>]*team-name[^>]*>(.*?)</span>'
        r'.*?<span[^>]*job-posted-date[^>]*>(.*?)</span>'
        r'.*?<span[^>]*search-store-name-container[^>]*>(.*?)</span>',
        re.S,
    )
    cards = []
    for match in pattern.finditer(decoded):
        aria_title, href, inner_title, team, posted, location = match.groups()
        title = strip_html(inner_title) or strip_html(aria_title)
        cards.append({
            "title": title,
            "href": href,
            "team": strip_html(team),
            "posted": strip_html(posted),
            "location": strip_html(location),
        })
    return cards


def apple_jobs(search_url, company="Apple", limit=25):
    page = fetch_text(search_url)
    jobs = []
    seen = set()
    for item in extract_apple_cards(page):
        link = urllib.parse.urljoin("https://jobs.apple.com", item.get("href") or "")
        if not item.get("title") or not link or link in seen:
            continue
        seen.add(link)
        title = item.get("title")
        location = item.get("location")
        text = normalize(" ".join([title, company, location, item.get("team") or "", item.get("posted") or ""]))
        if not job_passes(title, company, location, text, item.get("team")):
            continue
        jobs.append({
            "company": company,
            "role": title,
            "location": display_location(title, location, text),
            "link": link,
            "description": text,
            "posted_at": item.get("posted"),
            "source": "Apple Careers",
            "notes": "Pulled from Apple careers search: " + search_url,
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


def pull_eightfold(db_path, url, company, limit=25):
    return score_and_store(db_path, eightfold_jobs(url, company, limit))


def pull_workday(db_path, base_url, tenant, site, company, limit=25, search_text="software engineer"):
    return score_and_store(db_path, workday_jobs(base_url, tenant, site, company, search_text, limit))


def pull_ashby(db_path, board, company, limit=25):
    return score_and_store(db_path, ashby_jobs(board, company, limit))


def pull_apple(db_path, search_url, company="Apple", limit=25):
    return score_and_store(db_path, apple_jobs(search_url, company, limit))


def pull_defaults(db_path, limit_per_company=20):
    results = {}
    for company, board in DEFAULT_GREENHOUSE_BOARDS.items():
        try:
            results[company] = pull_greenhouse(db_path, board, company, limit_per_company)
        except Exception as exc:
            results[company] = {"error": str(exc), "added": [], "skipped": []}
    for company, slug in DEFAULT_LEVER_SLUGS.items():
        try:
            results[company] = pull_lever(db_path, slug, company, limit_per_company)
        except Exception as exc:
            results[company] = {"error": str(exc), "added": [], "skipped": []}
    for company, url in DEFAULT_EIGHTFOLD_SITES.items():
        try:
            results[company] = pull_eightfold(db_path, url, company, limit_per_company)
        except Exception as exc:
            results[company] = {"error": str(exc), "added": [], "skipped": []}
    for company, config in DEFAULT_WORKDAY_SITES.items():
        try:
            results[company] = pull_workday(
                db_path,
                config["base_url"],
                config["tenant"],
                config["site"],
                company,
                limit_per_company,
                config.get("search_text", "software engineer"),
            )
        except Exception as exc:
            results[company] = {"error": str(exc), "added": [], "skipped": []}
    for company, board in DEFAULT_ASHBY_BOARDS.items():
        try:
            results[company] = pull_ashby(db_path, board, company, limit_per_company)
        except Exception as exc:
            results[company] = {"error": str(exc), "added": [], "skipped": []}
    for company, url in DEFAULT_APPLE_SEARCHES.items():
        try:
            results[company] = pull_apple(db_path, url, company, limit_per_company)
        except Exception as exc:
            results[company] = {"error": str(exc), "added": [], "skipped": []}
    for company, reason in GUARDED_SOURCES.items():
        results.setdefault(company, {"error": reason, "added": [], "skipped": []})
    return results
