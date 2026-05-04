import csv
import json
import sqlite3


JOBS_SCHEMA = """
create table if not exists jobs (
    id integer primary key autoincrement,
    company text,
    role text,
    location text,
    link text,
    description text,
    score integer,
    infrastructure_alignment_score integer,
    apply_decision text,
    contact text,
    status text default 'saved',
    notes text,
    created_at text default current_timestamp,
    updated_at text default current_timestamp
);
"""

TAILORING_SCHEMA = """
create table if not exists tailored_resumes (
    job_id integer primary key,
    resume_source text,
    resume_match_score integer,
    readiness text,
    position_as text,
    rewritten_bullets text,
    projects text,
    keywords_to_inject text,
    experience_to_emphasize text,
    gaps_in_fit text,
    covered_keywords text,
    missing_keywords text,
    created_at text default current_timestamp,
    updated_at text default current_timestamp,
    foreign key(job_id) references jobs(id)
);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(JOBS_SCHEMA)
    conn.execute(TAILORING_SCHEMA)
    ensure_column(conn, "tailored_resumes", "projects", "text")
    return conn


def ensure_column(conn, table, column, definition):
    columns = [row["name"] for row in conn.execute("pragma table_info(" + table + ")").fetchall()]
    if column not in columns:
        conn.execute("alter table " + table + " add column " + column + " " + definition)
        conn.commit()


def add_job(db_path, job):
    conn = connect(db_path)
    cur = conn.execute(
        """
        insert into jobs
        (company, role, location, link, description, score, infrastructure_alignment_score, apply_decision, contact, status, notes)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job.get("company"),
            job.get("role"),
            job.get("location"),
            job.get("link"),
            job.get("description"),
            job.get("score"),
            job.get("infrastructure_alignment_score"),
            job.get("apply_decision"),
            job.get("contact"),
            job.get("status", "saved"),
            job.get("notes"),
        ),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def find_existing_job(db_path, company=None, role=None, link=None):
    conn = connect(db_path)
    row = None
    if link:
        row = conn.execute("select * from jobs where link = ? limit 1", (link,)).fetchone()
    if not row and company and role:
        row = conn.execute(
            "select * from jobs where lower(company) = lower(?) and lower(role) = lower(?) limit 1",
            (company, role),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_job(db_path, job_id):
    conn = connect(db_path)
    row = conn.execute("select * from jobs where id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_tailored_resume(db_path, job_id, tailoring):
    conn = connect(db_path)
    conn.execute(
        """
        insert into tailored_resumes
        (job_id, resume_source, resume_match_score, readiness, position_as, rewritten_bullets, projects,
         keywords_to_inject, experience_to_emphasize, gaps_in_fit, covered_keywords, missing_keywords)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(job_id) do update set
            resume_source = excluded.resume_source,
            resume_match_score = excluded.resume_match_score,
            readiness = excluded.readiness,
            position_as = excluded.position_as,
            rewritten_bullets = excluded.rewritten_bullets,
            projects = excluded.projects,
            keywords_to_inject = excluded.keywords_to_inject,
            experience_to_emphasize = excluded.experience_to_emphasize,
            gaps_in_fit = excluded.gaps_in_fit,
            covered_keywords = excluded.covered_keywords,
            missing_keywords = excluded.missing_keywords,
            updated_at = current_timestamp
        """,
        (
            job_id,
            tailoring.get("resume_source"),
            tailoring.get("resume_match_score"),
            tailoring.get("readiness"),
            tailoring.get("position_as"),
            json.dumps(tailoring.get("rewritten_bullets") or []),
            json.dumps(tailoring.get("projects") or []),
            json.dumps(tailoring.get("keywords_to_inject") or []),
            json.dumps(tailoring.get("experience_to_emphasize") or []),
            json.dumps(tailoring.get("gaps_in_fit") or []),
            json.dumps(tailoring.get("covered_keywords") or []),
            json.dumps(tailoring.get("missing_keywords") or []),
        ),
    )
    conn.commit()
    conn.close()


def get_tailored_resume(db_path, job_id):
    conn = connect(db_path)
    row = conn.execute("select * from tailored_resumes where job_id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    for key in ["rewritten_bullets", "projects", "keywords_to_inject", "experience_to_emphasize", "gaps_in_fit", "covered_keywords", "missing_keywords"]:
        try:
            data[key] = json.loads(data.get(key) or "[]")
        except json.JSONDecodeError:
            data[key] = []
    return data


def list_missing_tailoring_jobs(db_path, limit=500):
    conn = connect(db_path)
    rows = conn.execute(
        """
        select jobs.*
        from jobs
        left join tailored_resumes on tailored_resumes.job_id = jobs.id
        where jobs.status != 'skipped' and tailored_resumes.job_id is null
        order by jobs.score desc, jobs.created_at desc
        limit ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_top(db_path, limit=10):
    conn = connect(db_path)
    rows = conn.execute(
        "select * from jobs where status != 'skipped' order by score desc, infrastructure_alignment_score desc, created_at desc limit ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_jobs(db_path, limit=50, status=None):
    conn = connect(db_path)
    if status:
        rows = conn.execute(
            "select * from jobs where status = ? order by score desc, infrastructure_alignment_score desc, created_at desc limit ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "select * from jobs where status != 'skipped' order by score desc, infrastructure_alignment_score desc, created_at desc limit ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def stats(db_path):
    conn = connect(db_path)
    rows = conn.execute("select status, count(*) as count from jobs group by status").fetchall()
    total = conn.execute("select count(*) as count from jobs where status != 'skipped'").fetchone()["count"]
    top = conn.execute("select count(*) as count from jobs where score >= 75 and status != 'skipped'").fetchone()["count"]
    conn.close()
    return {
        "total": total,
        "top_fit": top,
        "by_status": {row["status"]: row["count"] for row in rows},
    }


def update_status(db_path, job_id, status, notes=None, contact=None):
    conn = connect(db_path)
    current = get_job(db_path, job_id)
    if not current:
        conn.close()
        return False
    conn.execute(
        """
        update jobs
        set status = ?,
            notes = coalesce(?, notes),
            contact = coalesce(?, contact),
            updated_at = current_timestamp
        where id = ?
        """,
        (status, notes, contact, job_id),
    )
    conn.commit()
    conn.close()
    return True


def export_jobs(db_path, output_path):
    conn = connect(db_path)
    rows = conn.execute("select * from jobs order by score desc, created_at desc").fetchall()
    conn.close()
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else [
            "id", "company", "role", "location", "link", "description", "score",
            "infrastructure_alignment_score", "apply_decision", "contact", "status",
            "notes", "created_at", "updated_at",
        ])
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return output_path
