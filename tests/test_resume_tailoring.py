import os
import tempfile
import unittest
import zipfile

from rolefit_platform.auto_tailor import (
    CANONICAL_EDITABLE_RESUME_PATH,
    CANONICAL_RESUME_FOR_MATCHING,
    DEFAULT_RESUME_PATH,
)
from rolefit_platform.resume import ACTION_VERBS, UNSUPPORTED_KEYWORDS, tailor_resume
from rolefit_platform.resume_export import export_job_resume, validate_ats_docx
from rolefit_platform.storage import add_job


AI_PLATFORM_TEXT = """
Software Engineer IC2. Designs, develops, and deploys AI/ML systems for customer
interaction scenarios. Integrates LLMs, Retrieval-Augmented Generation, and
advanced analytics into customer service workflows. Ensures high reliability,
scalability, and responsible AI practices. Troubleshoots live site issues,
optimizes AI-driven workflows, and works with engineering teams. Requires Python
or Java, cloud infrastructure, REST/gRPC APIs, debugging, and test automation.
"""

BACKEND_TEXT = """
Backend Software Engineer. Build Java and Python services, REST and gRPC APIs,
distributed systems, CI/CD automation, and reliable cloud infrastructure.
"""

SRE_TEXT = """
Site Reliability Engineer. Own observability, monitoring, incident response,
availability, production reliability, Kubernetes, and automated validation.
"""

SECURITY_TEXT = """
Backend Security Engineer. Develop vulnerability data pipelines, automate risk
and compliance workflows, and improve audit coverage for cloud infrastructure.
"""


class ResumeTailoringTest(unittest.TestCase):
    def test_resume_paths_are_unset_by_default(self):
        self.assertIsNone(CANONICAL_RESUME_FOR_MATCHING)
        self.assertIsNone(CANONICAL_EDITABLE_RESUME_PATH)
        self.assertIs(DEFAULT_RESUME_PATH, CANONICAL_RESUME_FOR_MATCHING)

    def test_ai_release_ops_is_professional_experience_for_ai_platform_roles(self):
        result = tailor_resume(AI_PLATFORM_TEXT + " RAG")
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
        self.assertIn("RAG", result["gap_keywords"])
        self.assertIn("gRPC", result["gap_keywords"])
        self.assertNotIn("RAG", result["supported_keywords_to_surface"])

        project_names = [project["name"] for project in result["projects"]]
        self.assertEqual(project_names, [
            "RoleFit Platform",
            "Computer Vision For Autonomous Driving",
            "Scheme Interpreter",
        ])

    def test_bullets_change_by_role_focus_and_do_not_repeat_built(self):
        backend = tailor_resume(BACKEND_TEXT)["rewritten_bullets"]
        sre = tailor_resume(SRE_TEXT)["rewritten_bullets"]
        security = tailor_resume(SECURITY_TEXT)["rewritten_bullets"]

        self.assertNotEqual(backend, sre)
        self.assertNotEqual(sre, security)
        self.assertTrue(any("Python and Java" in bullet for bullet in backend))
        self.assertTrue(any("observability views" in bullet for bullet in sre))
        self.assertTrue(any("vulnerability signals" in bullet for bullet in security))
        self.assertEqual(sum(bullet.lower().startswith("built ") for bullet in backend), 0)
        self.assertEqual(len({bullet.split()[0] for bullet in backend}), len(backend))

    def test_explicit_role_title_controls_primary_tailoring_focus(self):
        mixed = "Cloud platform with security, compliance, risk, monitoring, incidents, and distributed services."
        sre = tailor_resume(mixed, role="Site Reliability Engineer")["rewritten_bullets"]
        security = tailor_resume(mixed, role="Software Engineer, Product Security Data Platforms")["rewritten_bullets"]

        self.assertTrue(any("observability views" in bullet for bullet in sre))
        self.assertTrue(any("vulnerability signals" in bullet for bullet in security))

    def test_every_selected_bullet_has_evidence_and_an_action_verb(self):
        result = tailor_resume(BACKEND_TEXT)
        for record in result["rewritten_bullet_records"]:
            self.assertTrue(record["evidence_id"])
            self.assertTrue(record["source"])
            self.assertTrue(record["fact"])
            self.assertIn(record["text"].split()[0], ACTION_VERBS)
            self.assertIn(record["text"], record["approved_variants"])

    def test_unsupported_keywords_are_never_surfaced(self):
        result = tailor_resume(" ".join(UNSUPPORTED_KEYWORDS))
        self.assertFalse(set(result["supported_keywords_to_surface"]) & set(UNSUPPORTED_KEYWORDS))
        self.assertTrue(set(result["gap_keywords"]) & set(UNSUPPORTED_KEYWORDS))

    def test_export_fails_clearly_without_a_canonical_docx(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = os.path.join(directory, "jobs.sqlite3")
            output_dir = os.path.join(directory, "exports")
            first_id = add_job(db_path, {"company": "First Co", "role": "Backend Engineer I", "status": "saved"})
            with self.assertRaisesRegex(FileNotFoundError, "ROLEFIT_CANONICAL_RESUME"):
                export_job_resume(db_path, first_id, output_dir)

    def test_ats_validation_rejects_layout_that_can_hide_reading_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "unsafe.docx")
            with zipfile.ZipFile(path, "w") as docx:
                docx.writestr("[Content_Types].xml", "<Types/>")
                docx.writestr("word/styles.xml", "<w:styles xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>")
                docx.writestr(
                    "word/document.xml",
                    """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl/></w:body></w:document>""",
                )

            result = validate_ats_docx(path)

            self.assertFalse(result["passed"])
            self.assertIn("contains tables", result["errors"])


if __name__ == "__main__":
    unittest.main()
