import unittest

from rolefit_platform.scraper_agent import summarize_pull


class ScraperAgentTest(unittest.TestCase):
    def test_summarize_pull_counts_and_sorts(self):
        added, skipped_count, error_count = summarize_pull({
            "A": {
                "added": [
                    {"company": "A", "role": "Low", "score": 61},
                    {"company": "A", "role": "High", "score": 92},
                ],
                "skipped": [{"reason": "duplicate"}],
            },
            "B": {"error": "timeout", "added": [], "skipped": [{"reason": "bad fit"}]},
        })

        self.assertEqual([item["role"] for item in added], ["High", "Low"])
        self.assertEqual(skipped_count, 2)
        self.assertEqual(error_count, 1)


if __name__ == "__main__":
    unittest.main()
