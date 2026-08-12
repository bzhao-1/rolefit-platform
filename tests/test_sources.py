import unittest

from rolefit_platform.sources import extract_apple_cards, extract_eightfold_objects
from rolefit_platform.web import App


class SourceParsingTest(unittest.TestCase):
    def test_home_job_card_has_one_click_stages_and_single_export(self):
        handler = type("Handler", (), {"path": "/?status=pulled"})()
        card = App.job_feed_html(handler, [{
            "id": 42,
            "company": "ExampleCo",
            "role": "Backend Engineer I",
            "location": "Austin, TX",
            "description": "Backend Java cloud APIs production systems",
            "score": 70,
            "status": "saved",
        }])
        self.assertEqual(card.count("action='/quick-status'"), 6)
        self.assertIn("value='contact requested'", card)
        self.assertIn("value='interview'", card)
        self.assertIn("value='offer'", card)
        self.assertIn("/export-resume?job_id=42", card)
        self.assertNotIn("/export-resumes?limit=25", card)
        self.assertIn("/?status=pulled", card)

    def test_extract_eightfold_objects_from_html_entities(self):
        html = """
        {&#34;id&#34;: 1, &#34;posting_name&#34;: &#34;Software Engineer&#34;,
        &#34;canonicalPositionUrl&#34;: &#34;https://example.com/job/1&#34;}
        """
        jobs = extract_eightfold_objects(html)
        self.assertEqual(jobs[0]["posting_name"], "Software Engineer")
        self.assertEqual(jobs[0]["canonicalPositionUrl"], "https://example.com/job/1")

    def test_extract_apple_cards(self):
        html = """
        <a class="link-inline" aria-label="Software Engineer" href="/en-us/details/1/software-engineer">Software Engineer</a>
        <span class="team-name">Cloud Infrastructure</span>
        <span class="job-posted-date">May 25, 2026</span>
        <span class="search-store-name-container">Austin, Texas, United States</span>
        """
        jobs = extract_apple_cards(html)
        self.assertEqual(jobs[0]["title"], "Software Engineer")
        self.assertEqual(jobs[0]["team"], "Cloud Infrastructure")
        self.assertEqual(jobs[0]["location"], "Austin, Texas, United States")


if __name__ == "__main__":
    unittest.main()
