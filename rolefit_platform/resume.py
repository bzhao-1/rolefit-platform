from rolefit_platform.profile import BASE_RESUME
from rolefit_platform.text_utils import count_matches


EXPERIENCE_THEMES = {
    "deployment systems": ["deployment", "release", "ci/cd", "pipeline", "validation", "gate", "canary"],
    "cloud infrastructure": ["cloud", "compute", "infrastructure", "hypervisor", "vm", "fleet", "linux"],
    "security/compliance": ["security", "compliance", "vulnerability", "audit", "risk"],
    "observability/data": ["metrics", "observability", "monitoring", "alerting", "telemetry", "data pipeline"],
    "distributed systems": ["distributed", "scale", "multi-tenant", "reliability", "latency"],
    "API/platform": ["api", "platform", "service", "automation", "orchestration", "kubernetes"],
    "ai/customer systems": ["ai", "ml", "llm", "rag", "nlp", "chatbot", "voice agent", "sentiment", "customer", "crm"],
    "frontend/web": ["frontend", "front-end", "react", "angular", "typescript", "javascript", "web application", "accessibility"],
    "ai-assisted release operations": [
        "copilot", "genai", "ai-assisted", "release triage", "incident triage",
        "human in the loop", "deterministic guardrails", "release engineering",
        "devops", "sre", "developer productivity",
    ],
}


AI_RELEASE_OPS_TAGS = [
    "ai_assisted_tooling", "genai", "platform_engineering",
    "cloud_infrastructure", "release_engineering", "devops", "sre",
    "observability", "ci_cd", "production_automation",
    "deployment_validation", "reliability", "human_in_the_loop",
    "deterministic_guardrails", "developer_productivity",
    "incident_triage", "release_triage",
]


SOURCE_FACTS = [
    {
        "id": "ai_assisted_release_operations",
        "role": "Cloud Infrastructure Platform, Software Engineer",
        "workstream": "AI-assisted release operations",
        "kind": "professional_experience",
        "tags": AI_RELEASE_OPS_TAGS,
        "summary": (
            "AI-assisted release-operations system for cloud infrastructure rollouts "
            "that centralizes validation state, release orchestration status, capacity "
            "health, test failures, curated failure memory, and remediation guidance."
        ),
        "guardrail": "AI-assisted and human-reviewed, not autonomous for production-facing actions.",
    },
]


WEAK_FRAMING = {
    "team-only tooling": "platform engineering system",
    "team dashboard": "observability system",
    "one-off scripts": "production automation",
    "helper scripts": "production automation",
    "helped automate": "automated",
    "supporting engineers": "improving engineering workflows",
    "crud tool": "workflow system",
    "admin tool": "operations system",
    "built a tool for the team": "built a platform engineering system",
}


BULLET_BANK = [
    {
        "id": "ai_release_ops_system",
        "theme": "ai-assisted release operations",
        "source_fact": "ai_assisted_release_operations",
        "tags": AI_RELEASE_OPS_TAGS,
        "terms": [
            "copilot", "ai", "genai", "ai-assisted", "release", "release engineering",
            "release triage", "devops", "pipeline", "ci/cd", "validation",
            "observability", "reliability", "platform", "cloud", "infrastructure",
            "developer productivity",
        ],
        "impact": 3,
        "text": "Built an AI-assisted release-operations system for cloud infrastructure rollouts that centralizes validation state, release orchestration failures, DevOps pipeline status, regional capacity health, test failures, and remediation guidance.",
    },
    {
        "id": "ai_release_safe_actions",
        "theme": "ai-assisted release operations",
        "source_fact": "ai_assisted_release_operations",
        "tags": AI_RELEASE_OPS_TAGS,
        "terms": [
            "ai", "genai", "copilot", "release triage", "incident triage",
            "known failure", "failure", "remediation", "quarantine",
            "host investigation", "safe next action", "deterministic guardrails",
            "human in the loop", "devops", "sre", "reliability",
        ],
        "impact": 2,
        "text": "Integrated live release metadata, curated failure memory, and deterministic guardrails to recommend safe next actions such as targeted regional retries, known-failure handling, quarantine candidates, and host-investigation workflows.",
    },
    {
        "id": "ai_release_safeguards",
        "theme": "ai-assisted release operations",
        "source_fact": "ai_assisted_release_operations",
        "tags": AI_RELEASE_OPS_TAGS,
        "terms": [
            "ai", "genai", "copilot", "ai-assisted", "responsible ai",
            "human approval", "human in the loop", "deterministic guardrails",
            "dependency", "stale image", "latest successful pipeline",
            "production", "release", "safeguard",
        ],
        "impact": 2,
        "text": "Added production safeguards for AI-assisted release actions, including dependency preservation, stale image prevention, latest-successful pipeline selection, and visible human approval boundaries.",
    },
    {
        "id": "ai_release_triage_workflows",
        "theme": "ai-assisted release operations",
        "source_fact": "ai_assisted_release_operations",
        "tags": AI_RELEASE_OPS_TAGS,
        "terms": [
            "release triage", "pipeline failure", "execution target", "pool health",
            "recurring failure", "known remediation", "production image validation",
            "observability", "sre", "devops", "reliability", "ci/cd",
            "deployment validation",
        ],
        "impact": 2,
        "text": "Developed AI-assisted release triage workflows that analyze pipeline failures, execution target status, regional capacity health, recurring failure patterns, and known remediation paths for production image validation.",
    },
    {
        "id": "regional_retry_automation",
        "theme": "ai-assisted release operations",
        "source_fact": "ai_assisted_release_operations",
        "tags": AI_RELEASE_OPS_TAGS,
        "terms": [
            "release automation", "targeted regional retry", "regional retry",
            "predecessor dependency", "stale image", "rollout recovery",
            "devops", "release engineering", "cloud infrastructure", "platform",
            "ci/cd",
        ],
        "impact": 2,
        "text": "Built release automation capabilities for targeted regional retry creation while preserving release dependency ordering and preventing stale image selection during rollout recovery.",
    },
    {
        "id": "release_gates",
        "theme": "deployment systems",
        "terms": ["deployment", "release", "ci/cd", "validation", "test automation", "unit", "integration", "e2e", "quality"],
        "impact": 3,
        "required_for": ["service", "test automation", "production", "reliability", "cloud", "api"],
        "text": "Built and operated deployment validation and release-gating systems that ran stable 200+ test suites across service repositories, improving confidence for production service changes.",
    },
    {
        "id": "hypervisor_validation",
        "theme": "cloud infrastructure",
        "terms": ["cloud", "infrastructure", "compute", "vm", "hypervisor", "linux", "reliability", "migration", "scale"],
        "impact": 2,
        "text": "Owned hypervisor image validation for cloud platform migrations, validating fleet readiness and reducing rollout risk across production VM infrastructure.",
    },
    {
        "id": "security_pipeline",
        "theme": "security/compliance",
        "terms": ["security", "compliance", "vulnerability", "responsible ai", "risk", "governance", "audit"],
        "impact": 3,
        "required_for": ["security", "responsible ai", "production", "scale", "cloud"],
        "text": "Delivered a production security data pipeline that ingested, normalized, correlated, and visualized vulnerability signals across 10k+ hypervisors and 100k+ VMs per month.",
    },
    {
        "id": "security_triage",
        "theme": "security/compliance",
        "terms": ["security", "automation", "triage", "workflow", "live site", "troubleshoot", "incident"],
        "impact": 3,
        "required_for": ["security", "automation", "workflow", "live site", "troubleshoot"],
        "text": "Automated triage and remediation workflows for hundreds of recurring fleet security findings per month, reducing manual investigation time and improving production risk analysis.",
    },
    {
        "id": "observability",
        "theme": "observability/data",
        "terms": ["observability", "monitoring", "metrics", "telemetry", "performance", "customer outcomes", "model performance", "alerting"],
        "impact": 1,
        "text": "Built observability and reporting workflows for cloud infrastructure validation and fleet security systems, turning production signals into actionable release and reliability decisions.",
    },
    {
        "id": "long_running_tests",
        "theme": "deployment systems",
        "terms": ["test automation", "unit", "integration", "e2e", "debugging", "validation", "reliability", "quality"],
        "impact": 2,
        "required_for": ["test automation", "debugging", "reliability", "production"],
        "text": "Designed a long-running VM validation stage for already-running instances, expanding test coverage beyond launch flows and catching stability regressions before production rollout.",
    },
    {
        "id": "api_automation",
        "theme": "API/platform",
        "terms": ["api", "rest", "grpc", "service", "automation", "workflow", "program managers", "cross-functional"],
        "impact": 1,
        "text": "Built Python/Java-oriented platform automation spanning validation, observability, release readiness, and recurring fleet issue remediation.",
    },
    {
        "id": "distributed_reliability",
        "theme": "distributed systems",
        "terms": ["distributed", "scale", "scalability", "reliability", "live site", "customer", "availability", "performance"],
        "impact": 1,
        "text": "Improved reliability coverage for distributed cloud infrastructure by integrating fleet-level validation, monitoring, and release-readiness checks into production-adjacent workflows.",
    },
    {
        "id": "cross_functional",
        "theme": "distributed systems",
        "terms": ["collaborates", "cross-functional", "program managers", "data scientists", "researchers", "engineering teams", "customer-centric"],
        "impact": 0,
        "text": "Partnered with service owners, security stakeholders, and release teams to translate ambiguous infrastructure risks into measurable validation, monitoring, and remediation workflows.",
    },
]


PROJECT_BANK = [
    {
        "id": "rolefit_platform",
        "terms": [
            "backend", "platform", "cloud", "infrastructure", "api", "service",
            "automation", "workflow", "sqlite", "ats", "resume", "tailoring",
            "scoring", "ranking", "dashboard", "python", "data pipeline",
            "tracking", "developer tools", "productivity", "ci/cd", "reliability",
            "observability", "llm", "rag", "ai", "web application",
        ],
        "name": "RoleFit Platform",
        "label": "Personal Project",
        "date": "May 2026",
        "always_include": True,
        "bullets": [
            "Built a local Python system for ATS job-feed ingestion, deterministic role scoring, SQLite-backed tracking, and browser-based workflow automation",
            "Implemented resume matching and tailoring pipelines that rank postings by role fit, surface covered/missing keywords, and export formatted DOCX resumes",
        ],
    },
    {
        "id": "cv_ai",
        "terms": ["ai", "ml", "model", "llm", "rag", "nlp", "sentiment", "computer vision", "customer outcomes"],
        "baseline": 1,
        "name": "Computer Vision For Autonomous Driving",
        "label": "Undergraduate Thesis",
        "date": "Sep 2024 - Mar 2025",
        "bullets": [
            "Generated 1M+ multimodal simulation samples using CARLA with custom weather, vehicle density, and sensor configurations",
            "Trained and evaluated HRNetV2 semantic segmentation models under domain shift conditions",
            "Improved robustness using domain adaptation, recovering up to 95% mIoU, and reduced fog-induced performance drops by ~35%",
        ],
    },
    {
        "id": "scheme_systems",
        "terms": [
            "compiler", "runtime", "programming languages", "systems", "debugging",
            "data structures", "algorithms", "backend", "distributed systems",
            "service", "api", "java", "python", "coding", "software engineering",
        ],
        "baseline": 2,
        "name": "Scheme Interpreter",
        "label": "Personal Project",
        "date": "Dec 2023",
        "bullets": [
            "Built a complete interpreter supporting primitives and continuations",
            "Reinforced compiler, runtime, and systems-level design fundamentals",
        ],
    },
]


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
        "Linux", "Terraform", "APIs", "REST", "gRPC", "reliability", "production systems",
        "LLMs", "RAG", "NLP", "test automation", "React", "TypeScript", "responsible AI",
        "AI-assisted tooling", "GenAI", "release engineering", "release triage",
        "DevOps", "SRE", "production automation", "deployment validation",
        "human-in-the-loop", "deterministic guardrails", "developer productivity",
        "incident triage",
    ]
    return count_matches(text, candidates)


def score_bullet(text, bullet):
    matches = count_matches(text, bullet["terms"])
    theme_matches = count_matches(text, EXPERIENCE_THEMES.get(bullet["theme"], []))
    tag_matches = count_matches(text, [tag.replace("_", " ") for tag in bullet.get("tags") or []])
    required_matches = count_matches(text, bullet.get("required_for") or [])
    return len(matches) * 3 + len(theme_matches) + len(tag_matches) * 2 + len(required_matches) * 2 + bullet.get("impact", 0) * 2


def strengthen_platform_framing(text):
    result = text
    lower = result.lower()
    for weak, strong in WEAK_FRAMING.items():
        if weak in lower:
            result = result.replace(weak, strong).replace(weak.title(), strong)
            lower = result.lower()
    return result


def is_ai_release_ops_bullet(bullet):
    return bullet.get("source_fact") == "ai_assisted_release_operations"


def quantified_bullet(bullet):
    return bullet.get("impact", 0) >= 2 and not is_ai_release_ops_bullet(bullet)


def add_selected(selected, seen, bullet):
    if bullet["id"] in seen:
        return False
    selected.append(bullet)
    seen.add(bullet["id"])
    return True


def ai_release_ops_target_count(text):
    ai_terms = [
        "ai", "genai", "llm", "rag", "copilot", "agentic", "developer productivity",
        "ai-assisted", "responsible ai",
    ]
    cloud_terms = ["cloud infrastructure", "platform", "cloud platform", "infrastructure", "api", "service"]
    release_terms = [
        "sre", "devops", "release", "release engineering", "observability",
        "ci/cd", "deployment", "incident", "live site",
    ]
    if count_matches(text, ai_terms):
        return 3
    if count_matches(text, release_terms):
        return 4
    if count_matches(text, cloud_terms):
        return 3
    return 2


def tailored_bullets(text, resume_text=None):
    ranked = []
    for bullet in BULLET_BANK:
        score = score_bullet(text, bullet)
        ranked.append((score, bullet.get("impact", 0), bullet["id"], bullet))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

    selected = []
    seen = set()
    target_ai_release_ops = ai_release_ops_target_count(text)

    for score, impact, bullet_id, bullet in ranked:
        if len([item for item in selected if is_ai_release_ops_bullet(item)]) >= target_ai_release_ops:
            break
        if is_ai_release_ops_bullet(bullet):
            add_selected(selected, seen, bullet)

    for score, impact, bullet_id, bullet in ranked:
        if len([item for item in selected if quantified_bullet(item)]) >= 2:
            break
        if is_ai_release_ops_bullet(bullet) and len([item for item in selected if is_ai_release_ops_bullet(item)]) >= target_ai_release_ops:
            continue
        if quantified_bullet(bullet):
            add_selected(selected, seen, bullet)

    for score, impact, bullet_id, bullet in ranked:
        if score <= 0 and len(selected) >= 4:
            continue
        if is_ai_release_ops_bullet(bullet) and len([item for item in selected if is_ai_release_ops_bullet(item)]) >= target_ai_release_ops:
            continue
        add_selected(selected, seen, bullet)
        if len(selected) == 5:
            break

    selected.sort(key=lambda bullet: score_bullet(text, bullet), reverse=True)
    return [strengthen_platform_framing(bullet["text"]) for bullet in selected[:5]]


def tailored_projects(text):
    return PROJECT_BANK[:3]


def tailor_resume(text, resume_text=None):
    resume = resume_text or BASE_RESUME
    themes = choose_experience_work(text)
    gaps = []
    if not count_matches(resume, ["kubernetes", "k8s"]):
        gaps.append("Kubernetes is not currently prominent in the base resume; only include it if there is hands-on evidence.")
    if count_matches(text, ["gpu", "cuda", "ai infrastructure", "ml infrastructure"]) and not count_matches(resume, ["gpu", "cuda", "ml infrastructure"]):
        gaps.append("AI/GPU infrastructure terms appear in the role but are not strongly supported by the sample resume evidence.")
    if count_matches(text, ["go"]) and "Go" not in resume:
        gaps.append("Go appears in the role; the sample resume lists Go but needs project or production evidence if emphasized.")
    if not gaps:
        gaps.append("No major gap detected; keep claims grounded in production systems and measurable impact.")

    return {
        "position_as": infer_positioning(text),
        "rewritten_bullets": tailored_bullets(text, resume),
        "projects": tailored_projects(text),
        "keywords_to_inject": keywords_to_inject(text),
        "experience_to_emphasize": [item[0] for item in themes],
        "gaps_in_fit": gaps,
    }
