import os
import tempfile
import unittest

from rolefit_platform.storage import add_interview, add_job, get_job, list_interviews, stats, update_interview


class InterviewStorageTest(unittest.TestCase):
    def test_interview_tracks_event_and_updates_job_status(self):
        handle, db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(handle)
        try:
            job_id = add_job(db_path, {
                "company": "Example Cloud Co.",
                "role": "Software Engineer II",
                "location": "US",
                "description": "Phone screening for infrastructure role",
                "score": 70,
                "infrastructure_alignment_score": 55,
                "apply_decision": "Review selectively",
                "status": "applied",
            })
            interview_id = add_interview(db_path, {
                "job_id": job_id,
                "stage": "phone screen",
                "scheduled_at": "2026-05-08T16:00",
                "timezone": "America/Chicago",
                "format": "phone",
                "status": "scheduled",
                "prep_focus": "Recruiter screen and role story",
            })

            interviews = list_interviews(db_path)
            self.assertEqual(interviews[0]["id"], interview_id)
            self.assertEqual(interviews[0]["company"], "Example Cloud Co.")
            self.assertEqual(interviews[0]["stage"], "phone screen")
            self.assertEqual(get_job(db_path, job_id)["status"], "interview")
            self.assertEqual(stats(db_path)["scheduled_interviews"], 1)

            self.assertTrue(update_interview(db_path, interview_id, status="completed"))
            self.assertEqual(list_interviews(db_path)[0]["status"], "completed")
        finally:
            os.remove(db_path)


if __name__ == "__main__":
    unittest.main()
