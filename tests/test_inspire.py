import unittest

from ml_physics_crawler.inspire import build_inspire_query, parse_inspire
from ml_physics_crawler.models import CrawlConfig


SAMPLE_INSPIRE = {
    "hits": {
        "hits": [
            {
                "metadata": {
                    "titles": [{"title": "Graph Neural Networks for Event Reconstruction at the LHC"}],
                    "abstracts": [{"value": "We study machine learning for particle physics event reconstruction."}],
                    "authors": [{"full_name": "Alice Wang"}, {"full_name": "Bob Li"}],
                    "dois": [{"value": "10.1234/example"}],
                    "arxiv_eprints": [{"value": "2501.00001"}],
                    "inspire_categories": [{"term": "hep-ex"}],
                    "earliest_date": "2025-01-01",
                    "publication_info": [{"journal_title": "Example Journal"}],
                },
                "links": {"json": "https://inspirehep.net/api/literature/12345"},
            }
        ]
    }
}


class InspireTests(unittest.TestCase):
    def test_build_inspire_query_uses_topcite(self) -> None:
        query = build_inspire_query(CrawlConfig(source="inspire", inspire_query="hep-ex", inspire_topcite=100))
        self.assertEqual(query, "(hep-ex) and topcite 100+")

    def test_parse_inspire_extracts_expected_fields(self) -> None:
        records = parse_inspire(SAMPLE_INSPIRE, CrawlConfig(source="inspire", recall_mode="balanced"))
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.source, "INSPIRE")
        self.assertEqual(record.title, "Graph Neural Networks for Event Reconstruction at the LHC")
        self.assertEqual(record.authors, ["Alice Wang", "Bob Li"])
        self.assertEqual(record.doi, "10.1234/example")
        self.assertEqual(record.arxiv_id, "2501.00001")
        self.assertEqual(record.article_url, "https://doi.org/10.1234/example")
        self.assertEqual(record.pdf_url, "https://arxiv.org/pdf/2501.00001.pdf")
        self.assertEqual(record.theme, "hybrid")


if __name__ == "__main__":
    unittest.main()
