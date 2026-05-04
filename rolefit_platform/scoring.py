import re

from rolefit_platform.profile import TARGET_PROFILE
from rolefit_platform.location import location_fit
from rolefit_platform.text_utils import count_matches


CATEGORIES = [
    ("backend/platform/cloud", 18, [
        "backend", "platform", "cloud", "infrastructure", "api", "service", "microservice",
        "compute", "storage", "networking", "control plane", "data plane", "distributed",
    ]),
    ("distributed systems or infrastructure", 16, [
        "distributed systems", "scale", "high availability", "fault tolerant", "latency",
        "reliability", "orchestration", "scheduler", "multi-tenant", "fleet",
    ]),
    ("Python/Java usage", 10, ["python", "java", "go", "sql"]),
    ("Kubernetes/cloud/API/IaC", 14, [
        "kubernetes", "k8s", "docker", "terraform", "cloud", "grpc", "rest", "api",
        "infrastructure as code", "iac", "linux",
    ]),
    ("testing/automation/reliability/release", 14, [
        "ci/cd", "continuous integration", "deployment", "release", "build", "test automation",
        "validation", "pipeline", "sre", "observability", "monitoring", "alerting",
    ]),
    ("security/compliance/data pipelines", 8, [
        "security", "compliance", "vulnerability", "data pipeline", "metrics", "telemetry",
        "governance", "audit",
    ]),
    ("infrastructure cloud platform work", 10, [
        "gpu", "accelerated computing", "ai infrastructure", "ml infrastructure", "cluster",
        "kubernetes", "provisioning", "infrastructure lifecycle", "cloud platform", "apis",
    ]),
    ("real SWE signal", 10, [
        "software engineer", "software development", "design", "build", "coding", "systems",
        "production", "code review", "architecture",
    ]),
]

NEGATIVE_TERMS = [
    "help desk", "desktop support", "customer support", "technical support", "on-call only",
    "ticket queue", "manual qa", "qa analyst", "frontend", "front-end", "react native",
    "ios", "android", "mobile", "embedded", "firmware", "data scientist", "ml researcher",
    "internship", "new grad only", "principal", "staff engineer", "senior staff",
]

LOW_SIGNAL_COMPANIES = [
    "revature", "dice", "tek systems", "teksystems", "collabera", "synergisticit",
    "jobot", "cybercoders",
]


def extract_years(text):
    lower = text.lower()
    years = []
    for match in re.finditer(r"(\d+)\+?\s*(?:years|yrs|yoe)", lower):
        years.append(int(match.group(1)))
    return years


def company_score(company):
    if not company:
        return 4, "unknown company"
    lower = company.lower()
    primary = [name.lower() for name in TARGET_PROFILE["primary_companies"]]
    equivalent = [name.lower() for name in TARGET_PROFILE["equivalent_companies"]]
    avoid = [name.lower() for name in TARGET_PROFILE["avoid_companies"]]
    if lower in avoid:
        return -12, "explicitly avoided company"
    if lower in primary:
        return 10, "configured high-signal company"
    if lower in equivalent:
        return 8, "high-signal AI/cloud infrastructure company"
    if any(name in lower for name in LOW_SIGNAL_COMPANIES):
        return -8, "low staffing-firm signal"
    return 4, "neutral/unknown company signal"


def level_fit(text):
    lower = text.lower()
    years = extract_years(text)
    if any(term in lower for term in ["principal", "staff engineer", "senior staff", "distinguished", "sr. ", "sr "]):
        return -18, "senior/staff/principal mismatch"
    if any(term in lower for term in ["internship", "new grad only", "student internship"]):
        return -12, "intern/new-grad-only signal"
    if years and min(years) >= 4:
        return -16, "requires 4+ years"
    if years and min(years) <= 2:
        return 10, "explicit 0-2 year fit"
    if any(term in lower for term in ["software engineer ii", "engineer ii", "l2", "early career"]):
        return 8, "likely early-career fit"
    if any(term in lower for term in ["software engineer i", "engineer i", "entry level"]):
        return 7, "likely early-career fit"
    if "senior" in lower or "sr. " in lower or "sr " in lower:
        return -8, "senior wording without clear flexibility"
    return 4, "level not explicit"


def score_job(text, company=None):
    details = []
    total = 0
    max_points = sum(item[1] for item in CATEGORIES) + 20
    for name, weight, terms in CATEGORIES:
        matches = count_matches(text, terms)
        ratio = min(len(matches) / 4.0, 1.0)
        points = round(weight * ratio)
        total += points
        details.append({"category": name, "points": points, "max": weight, "matches": matches[:8]})

    level_points, level_reason = level_fit(text)
    company_points, company_reason = company_score(company)
    location = location_fit(text)
    negative_matches = count_matches(text, NEGATIVE_TERMS)
    penalty = min(len(negative_matches) * 5, 25) + location["penalty"]

    total += level_points + company_points - penalty
    score = max(0, min(100, round((total / max_points) * 100)))

    if score >= 82:
        confidence = "high"
    elif score >= 62:
        confidence = "medium"
    else:
        confidence = "low"

    explanation = [
        "Role score reflects backend/platform/cloud, infra automation, level fit, company signal, and SWE-vs-support signal.",
        "Level: " + level_reason,
        "Company: " + company_reason,
        "Location: " + location["reason"],
    ]
    if negative_matches:
        explanation.append("Penalties: " + ", ".join(negative_matches[:8]))
    strengths = []
    for item in details:
        if item["points"] >= item["max"] * 0.5 and item["matches"]:
            strengths.append(item["category"] + " (" + ", ".join(item["matches"][:4]) + ")")
    if strengths:
        explanation.append("Strong signals: " + "; ".join(strengths))

    return {
        "score": score,
        "confidence": confidence,
        "explanation": " ".join(explanation),
        "details": details,
        "level_points": level_points,
        "company_points": company_points,
        "penalty": penalty,
        "negative_matches": negative_matches,
        "location": location,
    }
