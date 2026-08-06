import unittest

from rolefit_platform.classifier import classify_job
from rolefit_platform.location import location_fit
from rolefit_platform.scoring import company_score, extract_years, level_fit, score_job


class ScoringAndLocationTest(unittest.TestCase):
    def test_extract_years_accepts_common_job_posting_formats(self):
        self.assertEqual(extract_years("Requires 2+ years or 3 yrs of experience"), [2, 3])

    def test_level_fit_rejects_staff_role(self):
        points, reason = level_fit("Staff Engineer, distributed systems")
        self.assertLess(points, 0)
        self.assertIn("staff", reason)

    def test_company_score_recognizes_configured_infrastructure_company(self):
        points, reason = company_score("Cloudflare")
        self.assertEqual(points, 8)
        self.assertIn("infrastructure", reason)

    def test_remote_role_restricted_outside_us_is_rejected(self):
        result = location_fit("Remote role based in Toronto, Canada")
        self.assertFalse(result["ok"])
        self.assertEqual(result["category"], "non_us_remote_restricted")

    def test_us_remote_role_is_accepted(self):
        result = location_fit("Remote - US; Austin, TX")
        self.assertTrue(result["ok"])
        self.assertEqual(result["category"], "us_remote")

    def test_infrastructure_role_scores_above_frontend_role(self):
        infrastructure = score_job(
            "Software Engineer II building distributed cloud infrastructure, Kubernetes APIs, "
            "deployment automation, observability, and reliability systems. 2+ years. Remote US.",
            "Cloudflare",
        )
        frontend = score_job(
            "Frontend mobile engineer building React Native interfaces. 2+ years. Remote US.",
            "Example Company",
        )
        self.assertGreater(infrastructure["score"], frontend["score"])

    def test_senior_role_is_never_high_priority(self):
        result = classify_job(
            "Senior Staff Software Engineer for distributed cloud infrastructure, Kubernetes, "
            "reliability, APIs, and deployment automation. Remote US.",
            "Cloudflare",
        )
        self.assertEqual(result["decision"], "Skip")


if __name__ == "__main__":
    unittest.main()

