import os
import tempfile
import unittest

from rolefit_platform.resume import tailor_resume
from rolefit_platform.resume_export import export_job_resume
from rolefit_platform.storage import add_job, save_tailored_resume


AI_PLATFORM_TEXT = """
Software Engineer IC2. Designs, develops, and deploys AI/ML systems for customer
interaction scenarios. Integrates LLMs, Retrieval-Augmented Generation, and
advanced analytics into customer service workflows. Ensures high reliability,
scalability, and responsible AI practices. Troubleshoots live site issues,
optimizes AI-driven workflows, and works with engineering teams. Requires Python
or Java, cloud infrastructure, REST/gRPC APIs, debugging, and test automation.
"""


class ResumeTailoringTest(unittest.TestCase):
    def test_ai_release_ops_is_professional_experience_for_ai_platform_roles(self):
        result = tailor_resume(AI_PLATFORM_TEXT)
        bullets = result["rewritten_bullets"]
        joined = " ".join(bullets).lower()

        self.assertIn("ai-assisted release-operations system", joined)
        self.assertIn("ai-assisted", joined)
        self.assertIn("human approval boundaries", joined)
        self.assertNotIn("side project", joined)
        self.assertNotIn("helper scripts", joined)
        self.assertNotIn("shepherd", joined)
        self.assertNotIn("bgp", joined)
        self.assertTrue(any("200+ test suites" in item for item in bullets))

        project_names = [project["name"] for project in result["projects"]]
        self.assertEqual(project_names, [
            "RoleFit Platform",
            "Computer Vision For Autonomous Driving",
            "Scheme Interpreter",
        ])

    def test_single_job_export_writes_only_requested_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = os.path.join(directory, "jobs.sqlite3")
            output_dir = os.path.join(directory, "exports")
            first_id = add_job(db_path, {"company": "First Co", "role": "Backend Engineer I", "status": "saved"})
            second_id = add_job(db_path, {"company": "Second Co", "role": "Platform Engineer I", "status": "saved"})
            for job_id in [first_id, second_id]:
                save_tailored_resume(db_path, job_id, {
                    "resume_source": "saved snapshot",
                    "resume_match_score": 70,
                    "readiness": "Strong",
                    "position_as": "Backend engineer",
                    "rewritten_bullets": ["Built reliable production systems"],
                    "projects": [],
                    "keywords_to_inject": [],
                    "experience_to_emphasize": [],
                    "gaps_in_fit": [],
                    "covered_keywords": [],
                    "missing_keywords": [],
                })

            result = export_job_resume(db_path, first_id, output_dir)
            files = [name for name in os.listdir(output_dir) if name.endswith(".docx")]

            self.assertEqual(result["job_id"], first_id)
            self.assertEqual(len(files), 1)
            self.assertIn("First_Co", files[0])
            self.assertNotIn("Second_Co", files[0])


if __name__ == "__main__":
    unittest.main()
