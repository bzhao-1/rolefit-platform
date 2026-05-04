from rolefit_platform.classifier import classify_job
from rolefit_platform.location import location_fit
from rolefit_platform.sources import display_location
from rolefit_platform.storage import connect


def combined_text(job):
    return " ".join([
        job.get("role") or "",
        job.get("company") or "",
        job.get("location") or "",
        job.get("description") or "",
    ])


def cleanup_locations(db_path):
    conn = connect(db_path)
    rows = conn.execute("select * from jobs").fetchall()
    cleaned = []
    rescored = []
    for row in rows:
        job = dict(row)
        text = combined_text(job)
        location = location_fit(text)
        title_location = location_fit(job.get("role") or "")
        field_location = location_fit(job.get("location") or "")
        classified = classify_job(text, job.get("company"))
        notes = job.get("notes") or ""
        location_ok = location["ok"] and title_location["ok"] and field_location["ok"]
        cleanup_reason = field_location["reason"]
        if not title_location["ok"]:
            cleanup_reason = title_location["reason"]
        elif not location["ok"]:
            cleanup_reason = location["reason"]
        if not location_ok and "Location cleanup:" not in notes:
            notes = (notes + " | Location cleanup: " + cleanup_reason).strip()
        status = job.get("status")
        if not location_ok:
            status = "skipped"
            cleaned.append({"id": job["id"], "role": job.get("role"), "reason": cleanup_reason})
        elif classified["decision"] == "Skip":
            status = "skipped"
            cleaned.append({"id": job["id"], "role": job.get("role"), "reason": classified["reasoning"]})
        display = display_location(job.get("role"), job.get("location"), text)
        rescored.append(job["id"])
        conn.execute(
            """
            update jobs
            set score = ?,
                infrastructure_alignment_score = ?,
                apply_decision = ?,
                location = ?,
                status = ?,
                notes = ?,
                updated_at = current_timestamp
            where id = ?
            """,
            (
                classified["score"]["score"],
                classified["alignment"]["similarity_score"],
                classified["decision"],
                display,
                status,
                notes,
                job["id"],
            ),
        )
    conn.commit()
    conn.close()
    return {"rescored": len(rescored), "hidden_non_us": cleaned}
