def outreach_message(kind, company=None, role=None, contact=None):
    company_name = company or "your team"
    role_name = role or "backend/platform software engineering roles"
    name = contact or "Hi"

    templates = {
        "infrastructure": (
            "{name}, I’m evaluating {role_name} at {company_name}. My background is backend/platform "
            "engineering across cloud infrastructure, deployment validation, CI/CD gates, observability, "
            "and production reliability tooling. Would you be open to sharing which teams might value "
            "that background?"
        ),
        "connection": (
            "{name}, I’m mapping backend/platform roles like {role_name} at {company_name}. My recent work "
            "centers on Python/Java services, validation pipelines, release gating, observability, and "
            "security automation for production infrastructure. Could I ask for your read on the best-matching teams?"
        ),
        "team": (
            "{name}, I’m looking at {company_name} infrastructure/platform SWE roles like {role_name}. I work on "
            "production infrastructure systems: hypervisor validation, deployment automation, CI/CD gates, "
            "long-running VM tests, and fleet security pipelines. Could you point me toward teams where this background maps well?"
        ),
        "recruiter": (
            "Hi, I’m a backend/platform software engineer focused on Python/Java services, deployment "
            "validation, CI/CD release gates, observability, and security automation for production cloud "
            "infrastructure. I’m interested in {role_name} at {company_name}. Would you be open to a quick "
            "conversation about whether that background fits the team?"
        ),
        "network": (
            "{name}, I’m researching backend/platform and AI/cloud infrastructure software engineering teams. "
            "If you know anyone at {company_name} or similar engineering teams, could you introduce me for team guidance?"
        ),
    }
    key = (kind or "recruiter").lower()
    return templates.get(key, templates["recruiter"]).format(
        name=name,
        company_name=company_name,
        role_name=role_name,
    )
