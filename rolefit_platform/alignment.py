from rolefit_platform.text_utils import count_matches


INFRASTRUCTURE_SIGNALS = {
    "cloud platform systems": ["cloud platform", "control plane", "data plane", "compute", "storage", "networking", "infrastructure lifecycle"],
    "AI infrastructure / GPU infra": ["gpu", "ai infrastructure", "ml infrastructure", "accelerated computing", "training", "inference", "cluster"],
    "distributed systems at scale": ["distributed systems", "scale", "multi-tenant", "high availability", "fault tolerant", "scheduler", "fleet"],
    "Kubernetes / orchestration": ["kubernetes", "k8s", "orchestration", "containers", "docker", "helm"],
    "APIs for infrastructure automation": ["api", "grpc", "rest", "automation", "provisioning", "terraform", "iac"],
    "SRE + dev collaboration": ["sre", "reliability", "observability", "monitoring", "incident", "deployment", "ci/cd"],
}


def infrastructure_alignment(text):
    category_results = []
    total = 0
    max_total = len(INFRASTRUCTURE_SIGNALS) * 2
    for category, terms in INFRASTRUCTURE_SIGNALS.items():
        matches = count_matches(text, terms)
        points = min(len(matches), 2)
        total += points
        category_results.append({"category": category, "matches": matches, "points": points})
    score = round((total / max_total) * 100)
    aligned = score >= 55
    reasoning_parts = []
    for item in category_results:
        if item["matches"]:
            reasoning_parts.append(item["category"] + ": " + ", ".join(item["matches"][:5]))
    if not reasoning_parts:
        reasoning_parts.append("No strong cloud platform, orchestration, GPU/AI infra, API automation, or reliability signals found.")
    return {
        "infrastructure_aligned": aligned,
        "similarity_score": score,
        "reasoning": " | ".join(reasoning_parts),
        "details": category_results,
    }
