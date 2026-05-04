import unittest

from rolefit_platform.resume import tailor_resume


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


if __name__ == "__main__":
    unittest.main()
