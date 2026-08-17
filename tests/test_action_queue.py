import os
import tempfile
import unittest

from rolefit_platform.action_queue import action_queue_rows
from rolefit_platform.storage import add_job, get_job, list_action_queue_jobs, update_status
from rolefit_platform.web import App


class ActionQueueTest(unittest.TestCase):
    def test_queue_sort_uses_urgency_then_freshness_priority_and_fit(self):
        rows = [
            {"id": 1, "company": "A", "role": "Submit", "next_action": "SUBMIT", "posted_at": "2026-08-01", "queue_priority": "LOW", "score": 40},
            {"id": 2, "company": "B", "role": "Referral", "next_action": "SEEK_REFERRAL", "posted_at": "2026-08-17", "queue_priority": "VERY HIGH", "score": 90},
            {"id": 3, "company": "C", "role": "Review older", "next_action": "REVIEW_JD", "posted_at": "2026-08-16", "queue_priority": "VERY HIGH", "score": 90},
            {"id": 4, "company": "D", "role": "Review newer", "next_action": "REVIEW_JD", "posted_at": "2026-08-17", "queue_priority": "HIGH", "score": 50},
            {"id": 5, "company": "E", "role": "Review tied high", "next_action": "REVIEW_JD", "posted_at": "2026-08-17", "queue_priority": "HIGH", "score": 70},
            {"id": 6, "company": "F", "role": "Wait", "next_action": "WAIT", "posted_at": "2026-08-17", "queue_priority": "HIGH", "score": 99},
        ]
        self.assertEqual([row["id"] for row in action_queue_rows(rows)], [1, 2, 5, 4, 3, 6])

    def test_queue_fields_persist_and_explicit_skip_remains_visible(self):
        handle, db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(handle)
        try:
            job_id = add_job(db_path, {
                "company": "ExampleCo",
                "role": "Software Engineer I",
                "status": "skipped",
                "next_action": "NONE",
                "queue_priority": "NONE",
            })
            job = get_job(db_path, job_id)
            self.assertEqual(job["next_action"], "NONE")
            self.assertEqual(job["queue_priority"], "NONE")
            self.assertEqual([row["id"] for row in list_action_queue_jobs(db_path)], [job_id])

            update_status(db_path, job_id, "saved", next_action="SUBMIT", queue_priority="HIGH")
            job = get_job(db_path, job_id)
            self.assertEqual((job["next_action"], job["queue_priority"]), ("SUBMIT", "HIGH"))

            update_status(db_path, job_id, "saved", next_action="", queue_priority="")
            job = get_job(db_path, job_id)
            self.assertIsNone(job["next_action"])
            self.assertIsNone(job["queue_priority"])
        finally:
            os.remove(db_path)

    def test_status_page_does_not_render_action_queue(self):
        handle, db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(handle)
        try:
            add_job(db_path, {
                "company": "ExampleCo",
                "role": "Software Engineer I",
                "status": "saved",
                "next_action": "SUBMIT",
                "queue_priority": "HIGH",
            })
            captured = {}
            handler = object.__new__(App)
            handler.db_path = db_path
            handler.send_html = lambda body, title=None: captured.update(body=body, title=title)
            handler.status_page({})
            self.assertIn("Application Status", captured["body"])
            self.assertNotIn("Action Queue", captured["body"])
            self.assertNotIn("Next SUBMIT", captured["body"])
        finally:
            os.remove(db_path)

if __name__ == "__main__":
    unittest.main()
