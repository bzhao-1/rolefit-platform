from rolefit_platform.profile import BASE_RESUME
from rolefit_platform.text_utils import count_matches


EXPERIENCE_THEMES = {
    "deployment systems": ["deployment", "release", "ci/cd", "pipeline", "validation", "gate", "canary"],
    "cloud infrastructure": ["cloud", "compute", "infrastructure", "hypervisor", "vm", "fleet", "linux"],
    "security/compliance": ["security", "compliance", "vulnerability", "audit", "risk"],
    "observability/data": ["metrics", "observability", "monitoring", "alerting", "telemetry", "data pipeline"],
    "distributed systems": ["distributed", "scale", "multi-tenant", "reliability", "latency"],
    "API/platform": ["api", "platform", "service", "automation", "orchestration", "kubernetes"],
}


def infer_positioning(text):
    platform = len(count_matches(text, ["platform", "infrastructure", "kubernetes", "cloud", "api", "provisioning"]))
    backend = len(count_matches(text, ["backend", "java", "python", "service", "distributed", "api"]))
    sre = len(count_matches(text, ["sre", "reliability", "observability", "incident", "monitoring", "on-call"]))
    if platform >= backend and platform >= sre:
        return "platform / cloud infrastructure"
    if sre > backend:
        return "software-heavy reliability / infrastructure"
    return "backend distributed systems"


def choose_experience_work(text):
    results = []
    for theme, terms in EXPERIENCE_THEMES.items():
        matches = count_matches(text, terms)
        if matches:
            results.append((theme, len(matches), matches))
    results.sort(key=lambda item: item[1], reverse=True)
    return results[:4]


def keywords_to_inject(text):
    candidates = [
        "Python", "Java", "distributed systems", "cloud infrastructure", "Kubernetes",
        "CI/CD", "deployment automation", "release gating", "validation pipelines",
        "observability", "monitoring", "security automation", "data pipelines",
        "Linux", "Terraform", "APIs", "reliability", "production systems",
    ]
    return count_matches(text, candidates)


def tailored_bullets(text, resume_text=None):
    positioning = infer_positioning(text)
    themes = [item[0] for item in choose_experience_work(text)]
    bullets = []

    if "deployment systems" in themes or "platform" in positioning:
        bullets.append("Built and operated deployment validation and release-gating systems that executed stable 200+ test suites across internal repositories, improving confidence for production infrastructure changes.")
    if "cloud infrastructure" in themes or "distributed systems" in themes:
        bullets.append("Owned hypervisor image validation for cloud platform migrations, validating fleet readiness and reducing rollout risk across production VM infrastructure.")
    if "security/compliance" in themes:
        bullets.append("Delivered a production security data pipeline that ingested, normalized, correlated, and visualized vulnerability signals across 10k+ hypervisors and 100k+ VMs per month.")
    if "observability/data" in themes:
        bullets.append("Designed metrics and monitoring pipelines for cloud infrastructure services, including 50+ tenant-level replication signals and 50+ MQL monitors that reduced fault localization time by about 40%.")
    if "API/platform" in themes:
        bullets.append("Automated infrastructure testing and remediation workflows in Python/Java-oriented cloud services, reducing manual triage across recurring fleet issues.")

    fallback = [
        "Expanded dataplane and endurance coverage by integrating long-running VM validation into CI workflows, catching stability regressions missed by launch-only tests.",
        "Built production automation for cloud infrastructure teams spanning validation, observability, security reporting, and release-readiness workflows.",
        "Verified infrastructure behavior across hardware and VM lifecycle scenarios, supporting safer cloud compute repair and migration models.",
    ]
    for item in fallback:
        if len(bullets) >= 5:
            break
        bullets.append(item)
    return bullets[:5]


def tailor_resume(text, resume_text=None):
    resume = resume_text or BASE_RESUME
    themes = choose_experience_work(text)
    gaps = []
    if not count_matches(resume, ["kubernetes", "k8s"]):
        gaps.append("Kubernetes is not currently prominent in the base resume; only include it if you have hands-on examples or coursework/project proof.")
    if count_matches(text, ["gpu", "cuda", "ai infrastructure", "ml infrastructure"]) and not count_matches(resume, ["gpu", "cuda", "ml infrastructure"]):
        gaps.append("AI/GPU infrastructure terms appear in the role but are not strongly supported by the current resume evidence.")
    if count_matches(text, ["go"]) and "Go" not in resume:
        gaps.append("Go appears in the role; base resume lists Go but needs project or production evidence if emphasized.")
    if not gaps:
        gaps.append("No major gap detected; keep claims grounded in production systems and measurable impact.")

    return {
        "position_as": infer_positioning(text),
        "rewritten_bullets": tailored_bullets(text, resume),
        "keywords_to_inject": keywords_to_inject(text),
        "experience_to_emphasize": [item[0] for item in themes],
        "gaps_in_fit": gaps,
    }
