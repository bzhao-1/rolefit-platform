from rolefit_platform.text_utils import count_matches


def interview_prep(text):
    dsa = ["arrays/strings", "hash maps", "trees", "graphs", "BFS/DFS", "heaps/priority queues"]
    if count_matches(text, ["scheduler", "routing", "network", "dependency"]):
        dsa.extend(["topological sort", "shortest paths"])
    if count_matches(text, ["scale", "latency", "stream", "pipeline"]):
        dsa.extend(["sliding window", "binary search", "queues"])

    system_design = [
        "design a deployment validation pipeline",
        "design a CI/CD release gate for cloud services",
        "design fleet-wide metrics ingestion and alerting",
        "design a multi-tenant cloud control-plane API",
    ]
    if count_matches(text, ["kubernetes", "orchestration", "cluster"]):
        system_design.append("design a Kubernetes-based job orchestration platform")
    if count_matches(text, ["gpu", "ai infrastructure", "inference", "training"]):
        system_design.append("design GPU cluster provisioning and health validation")

    behavioral = [
        "ownership of production reliability",
        "debugging ambiguous infrastructure failures",
        "cross-team collaboration with security, release, and service owners",
        "using metrics to prove impact",
        "learning quickly as an early-career engineer",
    ]

    cloud = [
        "Kubernetes primitives and scheduling basics",
        "CI/CD, canarying, rollbacks, and release gates",
        "observability: metrics, logs, traces, SLOs, alert quality",
        "infrastructure scaling, capacity, fault domains, and blast radius",
        "API design for infrastructure automation",
        "security/compliance automation for fleet systems",
    ]

    return {
        "likely_dsa_topics": list(dict.fromkeys(dsa)),
        "system_design_topics": system_design,
        "behavioral_focus": behavioral,
        "cloud_platform_concepts": cloud,
    }
