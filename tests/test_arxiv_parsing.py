import unittest
from datetime import datetime, timedelta, timezone

from unittest.mock import patch

from ml_physics_crawler.arxiv import crawl_arxiv, is_within_time_window, parse_arxiv
from ml_physics_crawler.models import CrawlConfig


SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2501.00001v1</id>
    <updated>2025-01-01T00:00:00Z</updated>
    <published>2025-01-01T00:00:00Z</published>
    <title>Graph Neural Networks for Particle Physics Event Reconstruction</title>
    <summary>
      We develop a machine learning method for particle physics event reconstruction at the LHC.
    </summary>
    <author><name>Alice Author</name></author>
    <author><name>Bob Author</name></author>
    <link href="http://arxiv.org/abs/2501.00001v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2501.00001v1" rel="related" type="application/pdf"/>
    <arxiv:primary_category term="hep-ex" scheme="http://arxiv.org/schemas/atom"/>
    <category term="hep-ex" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
    <arxiv:doi>10.1234/example-doi</arxiv:doi>
    <arxiv:journal_ref>Example Journal</arxiv:journal_ref>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2501.00002v1</id>
    <updated>2025-01-02T00:00:00Z</updated>
    <published>2025-01-02T00:00:00Z</published>
    <title>Topology of Smooth Manifolds</title>
    <summary>
      We study a classical problem in pure mathematics using geometric analysis.
    </summary>
    <author><name>Carol Author</name></author>
    <arxiv:primary_category term="math-ph" scheme="http://arxiv.org/schemas/atom"/>
    <category term="math-ph" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
"""

EMPTY_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
</feed>
"""


class ArxivParsingTests(unittest.TestCase):
    def test_parse_arxiv_extracts_expected_fields(self) -> None:
        records = parse_arxiv(SAMPLE_FEED, CrawlConfig(recall_mode="balanced"))

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.title, "Graph Neural Networks for Particle Physics Event Reconstruction")
        self.assertEqual(record.authors, ["Alice Author", "Bob Author"])
        self.assertEqual(record.journal, "Example Journal")
        self.assertEqual(record.article_url, "https://doi.org/10.1234/example-doi")
        self.assertEqual(record.pdf_url, "http://arxiv.org/pdf/2501.00001v1")
        self.assertEqual(record.categories, ["cs.LG", "hep-ex"])
        self.assertEqual(record.theme, "hybrid")
        self.assertIn("particle_physics", record.tags)
        self.assertIn("ml_category", record.match_reason)
        self.assertIn("science_category", record.match_reason)

    def test_parse_arxiv_uses_arxiv_url_when_doi_missing(self) -> None:
        feed = SAMPLE_FEED.replace(
            "<arxiv:doi>10.1234/example-doi</arxiv:doi>",
            "",
        ).replace(
            "<arxiv:journal_ref>Example Journal</arxiv:journal_ref>",
            "",
        )

        records = parse_arxiv(feed, CrawlConfig(recall_mode="balanced"))

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.article_url, "http://arxiv.org/abs/2501.00001v1")
        self.assertEqual(record.journal, "arXiv")

    def test_is_within_time_window_days_back(self) -> None:
        recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")

        self.assertTrue(is_within_time_window(recent, 7))
        self.assertFalse(is_within_time_window(old, 7))

    def test_is_within_time_window_since_date(self) -> None:
        recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")

        self.assertTrue(is_within_time_window(recent.replace("+00:00", "Z"), None, recent))
        self.assertFalse(is_within_time_window(old, None, recent))

    def test_parse_arxiv_filters_old_records_when_days_back_set(self) -> None:
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        old = (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")

        feed = (
            SAMPLE_FEED
            .replace("2025-01-01T00:00:00Z", recent, 1)
            .replace("2025-01-01T00:00:00Z", recent, 1)
            .replace("2025-01-02T00:00:00Z", old, 1)
            .replace("2025-01-02T00:00:00Z", old, 1)
        )

        records = parse_arxiv(feed, CrawlConfig(recall_mode="balanced", days_back=7))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].title, "Graph Neural Networks for Particle Physics Event Reconstruction")

    def test_crawl_arxiv_respects_total_results_when_smaller_than_batch_size(self) -> None:
        requested_max_results = []

        def fake_fetch_arxiv_batch(start: int, max_results: int, config: CrawlConfig) -> str:
            requested_max_results.append(max_results)
            return SAMPLE_FEED

        with patch("ml_physics_crawler.arxiv.fetch_arxiv_batch", side_effect=fake_fetch_arxiv_batch):
            records = crawl_arxiv(CrawlConfig(total_results=1, batch_size=100, sleep_seconds=0, recall_mode="balanced"))

        self.assertEqual(requested_max_results, [1])
        self.assertEqual(len(records), 1)

    def test_crawl_arxiv_without_total_limit_continues_until_empty_batch(self) -> None:
        requested_starts = []
        feeds = [SAMPLE_FEED, EMPTY_FEED]

        def fake_fetch_arxiv_batch(start: int, max_results: int, config: CrawlConfig) -> str:
            requested_starts.append((start, max_results))
            return feeds.pop(0)

        with patch("ml_physics_crawler.arxiv.fetch_arxiv_batch", side_effect=fake_fetch_arxiv_batch):
            records = crawl_arxiv(CrawlConfig(total_results=None, batch_size=2, sleep_seconds=0, recall_mode="balanced"))

        self.assertEqual(requested_starts, [(0, 2), (2, 2)])
        self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
