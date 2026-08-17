from datetime import datetime


NEXT_ACTIONS = ("SUBMIT", "SEEK_REFERRAL", "REVIEW_JD", "WAIT", "FOLLOW_UP", "NONE")
QUEUE_PRIORITIES = ("VERY HIGH", "HIGH", "MEDIUM", "LOW", "NONE")

NEXT_ACTION_ORDER = {
    "SUBMIT": 0,
    "SEEK_REFERRAL": 1,
    "REVIEW_JD": 2,
    "FOLLOW_UP": 3,
    "WAIT": 4,
    "NONE": 5,
}

QUEUE_PRIORITY_ORDER = {
    "VERY HIGH": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "NONE": 4,
}

QUEUE_GROUPS = (
    ("apply", "Apply Now", {"SUBMIT", "REVIEW_JD"}),
    ("referral", "Referral First", {"SEEK_REFERRAL"}),
    ("waiting", "Waiting", {"WAIT", "FOLLOW_UP"}),
    ("skip", "Skip", {"NONE"}),
)


def normalize_next_action(value):
    raw = str(value or "").strip().upper().replace(" ", "_")
    return raw if raw in NEXT_ACTIONS else None


def normalize_queue_priority(value):
    raw = str(value or "").strip().upper().replace("_", " ")
    return raw if raw in QUEUE_PRIORITIES else None


def _posted_at_key(value):
    raw = str(value or "").strip()
    if not raw:
        return (1, 0)
    try:
        return (0, -datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp())
    except (OverflowError, ValueError):
        return (1, 0)


def action_queue_sort_key(job):
    """Order explicitly queued jobs without changing the global recommendation order."""
    action = normalize_next_action(job.get("next_action")) or "NONE"
    priority = normalize_queue_priority(job.get("queue_priority")) or "NONE"
    return (
        NEXT_ACTION_ORDER[action],
        _posted_at_key(job.get("posted_at")),
        QUEUE_PRIORITY_ORDER[priority],
        -(job.get("score") or 0),
        str(job.get("company") or "").lower(),
        str(job.get("role") or "").lower(),
        str(job.get("id") or ""),
    )


def action_queue_rows(rows):
    queued = [row for row in rows if normalize_next_action(row.get("next_action"))]
    return sorted(queued, key=action_queue_sort_key)


def action_queue_group(action):
    normalized = normalize_next_action(action)
    for key, _label, actions in QUEUE_GROUPS:
        if normalized in actions:
            return key
    return None
