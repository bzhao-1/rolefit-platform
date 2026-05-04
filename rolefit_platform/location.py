import re


US_SIGNALS = [
    "united states", "usa", "u.s.", "us remote", "remote us", "remote - us",
    "california", "ca", "washington", "wa", "texas", "tx", "new york", "ny",
    "austin", "seattle", "santa clara", "sunnyvale", "mountain view", "menlo park",
    "redmond", "san francisco", "san jose", "palo alto", "remote, usa", "usa remote",
]

NON_US_SIGNALS = [
    "canada", "toronto", "vancouver", "montreal", "waterloo", "uk", "united kingdom",
    "london", "ireland", "dublin", "germany", "berlin", "munich", "france", "paris",
    "spain", "madrid", "barcelona", "portugal", "lisbon", "denmark", "aarhus",
    "copenhagen", "mexico", "mexico city",
    "netherlands", "amsterdam", "singapore", "india", "bengaluru", "bangalore",
    "hyderabad", "japan", "tokyo", "china", "beijing", "shanghai", "australia",
]

GLOBAL_REMOTE_SIGNALS = [
    "anywhere", "worldwide", "global remote", "remote globally", "distributed globally",
]


def is_remote(text):
    lower = (text or "").lower()
    return any(term in lower for term in [
        "remote", "work from home", "work remotely", "distributed team", "remote-first",
        "remote first", "anywhere",
    ])


def has_signal(lower, signals):
    for signal in signals:
        if len(signal) <= 3 and signal.replace(".", "").isalpha():
            if re.search(r"\b" + re.escape(signal) + r"\b", lower):
                return True
        elif signal in lower:
            return True
    return False


def location_fit(text):
    lower = (text or "").lower()
    remote = is_remote(lower)
    us = has_signal(lower, US_SIGNALS)
    non_us = has_signal(lower, NON_US_SIGNALS)
    global_remote = any(term in lower for term in GLOBAL_REMOTE_SIGNALS)
    if remote:
        if us:
            return {
                "ok": True,
                "category": "us_remote",
                "reason": "remote role includes US eligibility",
                "penalty": 0,
            }
        if non_us and not global_remote:
            return {
                "ok": False,
                "category": "non_us_remote_restricted",
                "reason": "remote role appears restricted to a non-US location",
                "penalty": 35,
            }
        return {
            "ok": True,
            "category": "remote_global_or_unclear",
            "reason": "remote role without a non-US restriction",
            "penalty": 0,
        }
    if us:
        return {
            "ok": True,
            "category": "us",
            "reason": "US-based role",
            "penalty": 0,
        }
    if non_us:
        return {
            "ok": False,
            "category": "non_us_onsite",
            "reason": "non-US role without remote signal",
            "penalty": 35,
        }
    return {
        "ok": True,
        "category": "unknown",
        "reason": "location unclear; verify US or remote before applying",
        "penalty": 5,
    }
