import unittest

from rolefit_platform.sources import extract_apple_cards, extract_eightfold_objects


class SourceParsingTest(unittest.TestCase):
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
