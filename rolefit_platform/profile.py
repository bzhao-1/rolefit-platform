TARGET_PROFILE = {
    "name": "Sample Candidate",
    "current_role": "Software Engineer, Cloud Infrastructure",
    "experience": "early-career software engineer",
    "education": "graduate computer science coursework",
    "target_roles": [
        "Software Engineer I",
        "Software Engineer II",
        "Cloud Platform Software Engineer",
        "Developer Infrastructure Engineer",
        "Reliability Engineer",
        "SRE",
        "AI Infrastructure Software Engineer",
        "Forward Deployed Software Engineer",
        "Release Engineer",
        "Build Systems Engineer",
    ],
    "primary_companies": [],
    "equivalent_companies": [
        "Databricks",
        "Snowflake",
        "Stripe",
        "Cloudflare",
        "Datadog",
        "CoreWeave",
        "Microsoft AI",
        "OpenAI",
        "Anthropic",
        "Palantir",
        "MongoDB",
        "Confluent",
        "GitHub",
        "HashiCorp",
        "IBM",
        "DigitalOcean",
        "Elastic",
        "Grafana Labs",
    ],
    "avoid_companies": [],
    "avoid_roles": [
        "senior",
        "staff",
        "principal",
        "frontend",
        "front-end",
        "mobile",
        "ios",
        "android",
        "embedded",
        "firmware",
        "data scientist",
        "ml researcher",
        "internship",
        "new grad",
        "help desk",
        "support engineer",
        "it support",
    ],
    "strengths": [
        "Python",
        "Java",
        "distributed systems",
        "cloud infrastructure",
        "deployment automation",
        "validation pipelines",
        "hypervisor image validation",
        "CI/CD",
        "release gating",
        "testing automation",
        "security tooling",
        "compliance tooling",
        "data pipelines",
        "observability",
    ],
}


BASE_RESUME = """Sample Candidate
sample@example.com | portfolio.example.com | linkedin.com/in/sample | github.com/sample

Technical Skills:
Languages: Python, Java, C++, SQL, Go
Infrastructure & Cloud: public cloud, Docker, Terraform, Linux
Testing & Automation: PyTest, CI/CD, Canary Testing
Data & Observability: Metric pipelines, Alerting, MQL, PostgreSQL

Cloud Infrastructure Platform, Software Engineer, Austin, TX, 2025 - Present
- Owned hypervisor image validation testing for the OL9 migration, validating image readiness and mitigating rollout risk during the transition from OL8.
- Rebuilt and delivered Check-in Gate as a Service (CIGaaS), enabling functional test execution for multiple internal repositories against a stable 200+ test golden suite.
- Built an end-to-end production security data pipeline ingesting, normalizing, correlating, and visualizing fleet-wide hypervisor vulnerability signals across 10k+ hypervisors and 100k+ VMs per month, with reporting used by security and leadership teams.
- Automated triage and remediation workflows for hundreds of security tickets per month, reducing manual investigation time and enabling fleet-wide pattern analysis.
- Designed and implemented a long-running VM testing stage that operates on already-running VMs, expanding coverage beyond launch-based validation.
- Expanded dataplane and endurance coverage by integrating long-running validation into CI workflows, enabling detection of stability and regression issues missed by launch-based tests.

Cloud Storage Platform, Software Engineer Intern, Seattle, WA, Summer 2024
- Designed and deployed a metrics pipeline ingesting 50+ tenant-level object storage replication and copy-service signals for network and latency analysis.
- Authored 50+ MQL-based monitors to isolate replication and networking issues, reducing fault localization time by about 40%.

Infrastructure Reliability Team, Software Engineer Intern, Austin, TX, Summer 2023
- Built a real-time PSU fault detection system, reducing mean detection time by about 60% and enabling live repair services.
- Verified fault scenarios across 3+ hardware generations, supporting migration to non-terminating VM repair models.

Education:
University of Texas at Austin, Master of Science in Computer Science, starting August 2026
Carleton College, Bachelor of Arts in Computer Science, Mathematics & Finance concentration, GPA 3.72, graduated 2025
"""
