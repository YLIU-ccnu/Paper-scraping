import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from ml_physics_crawler.ai_filter import should_apply_ai_filter
from ml_physics_crawler.bibtex import build_approved_bibtex_filename, export_approved_bibtex
from ml_physics_crawler.cli import (
    build_manifest_filename,
    build_run_manifest,
    build_run_summary,
    resolve_total_limit,
    build_summary_filename,
    resolve_run_plan,
)
from ml_physics_crawler.filtering import classify_record, should_keep_record
from ml_physics_crawler.models import CrawlConfig, PaperRecord, RunPlan
from ml_physics_crawler.mailer import build_email_body, build_email_subject
from ml_physics_crawler.pdf import build_pdf_filename, build_pdf_path, select_approved_records
from ml_physics_crawler.output import build_review_filename, build_theme_filename, flatten_csv_text, sort_records, sort_records_for_review, split_records_by_theme
from ml_physics_crawler.review import apply_review_updates, resolve_review_file
from ml_physics_crawler.scheduler import should_run_scheduled_update
from ml_physics_crawler.zotero import build_record_identity, record_to_zotero_item
from ml_physics_crawler.state import (
    build_records_cache_filename,
    build_run_state_filename,
    load_run_state,
    save_records_cache,
    save_run_state,
)
from ml_physics_crawler.text_utils import matched_keywords


def make_record(title: str, theme: str, ai_score: int | None = None, published: str = "") -> PaperRecord:
    return PaperRecord(
        source="arXiv",
        arxiv_id="2501.00001v1",
        title=title,
        authors=[],
        abstract="",
        journal="arXiv",
        doi="",
        article_url=f"https://example.org/{title}",
        pdf_url="",
        published=published,
        categories=[],
        tags=[],
        theme=theme,
        ai_score=ai_score,
    )


class FilteringTests(unittest.TestCase):
    def test_strict_mode_requires_both_science_and_ml(self) -> None:
        self.assertTrue(should_keep_record(True, True, False, False, "strict"))
        self.assertFalse(should_keep_record(True, False, False, False, "strict"))
        self.assertFalse(should_keep_record(False, True, False, False, "strict"))

    def test_classify_record_ai_methodology(self) -> None:
        keep, match_reason, tags, theme = classify_record(
            "A transformer foundation model for representation learning and diffusion",
            ["cs.LG"],
            "broad",
        )
        self.assertTrue(keep)
        self.assertEqual(theme, "ai_methodology")
        self.assertIn("ml_category", match_reason)
        self.assertIn("ai_for_science_or_method", tags)

    def test_classify_record_hybrid(self) -> None:
        keep, match_reason, tags, theme = classify_record(
            "Graph neural network for particle physics event reconstruction at the LHC",
            ["hep-ex", "cs.LG"],
            "balanced",
        )
        self.assertTrue(keep)
        self.assertEqual(theme, "hybrid")
        self.assertIn("science_category", match_reason)
        self.assertIn("ml_category", match_reason)
        self.assertIn("particle_physics", tags)

    def test_classify_record_science_application(self) -> None:
        keep, _, tags, theme = classify_record(
            "Quantum chemistry simulation for materials science and molecular dynamics",
            ["physics.chem-ph"],
            "broad",
        )
        self.assertTrue(keep)
        self.assertEqual(theme, "science_application")
        self.assertIn("science_application", tags)

    def test_should_apply_ai_filter_borderline_only(self) -> None:
        record = make_record("hybrid-paper", "hybrid")
        record.match_reason = "science_category; ml_category"
        self.assertFalse(should_apply_ai_filter(record, CrawlConfig(enable_ai_filter=True, ai_filter_scope="borderline")))

        borderline = make_record("science-paper", "science_application")
        borderline.match_reason = "science_keywords=materials science"
        self.assertTrue(should_apply_ai_filter(borderline, CrawlConfig(enable_ai_filter=True, ai_filter_scope="borderline")))

    def test_matched_keywords_avoids_short_substring_false_positives(self) -> None:
        text = "Neutrinos from all past core-collapse supernovae could be observed."
        self.assertEqual(matched_keywords(text, ["vae", "ai", "gan"]), [])

    def test_build_email_body_contains_expected_fields(self) -> None:
        record = make_record("Graph Neural Networks for Event Reconstruction", "hybrid", published="2026-04-12")
        record.authors = ["Alice", "Bob"]
        record.abstract = "We study graph neural networks for event reconstruction."
        record.pdf_url = "https://arxiv.org/pdf/2501.00001.pdf"
        config = CrawlConfig(source="arxiv", mail_subject_prefix="Paper update")

        body = build_email_body([record], config, "Run summary:\n- total records: 1")

        self.assertIn("theme: hybrid", body)
        self.assertIn("title: Graph Neural Networks for Event Reconstruction", body)
        self.assertIn("authors: Alice, Bob", body)
        self.assertIn("abstract: We study graph neural networks for event reconstruction.", body)
        self.assertIn("pdf_url: https://arxiv.org/pdf/2501.00001.pdf", body)

    def test_build_email_subject_uses_source_and_count(self) -> None:
        config = CrawlConfig(source="inspire", mail_subject_prefix="Paper update")
        subject = build_email_subject([make_record("x", "hybrid"), make_record("y", "hybrid")], config)
        self.assertEqual(subject, "Paper update: 2 new inspire papers")

    def test_should_run_scheduled_update_without_state(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "results" / "papers.csv")
            self.assertTrue(should_run_scheduled_update(output_file, 5))

    def test_should_run_scheduled_update_respects_interval_days(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "results" / "papers.csv")
            state_file = build_run_state_filename(output_file)
            now = datetime.now(timezone.utc)
            save_run_state(
                {"last_successful_run_at": (now - timedelta(days=3)).isoformat()},
                state_file,
            )
            self.assertFalse(should_run_scheduled_update(output_file, 5, now=now))
            self.assertTrue(should_run_scheduled_update(output_file, 2, now=now))


class OutputTests(unittest.TestCase):
    def test_sort_records_uses_theme_then_score(self) -> None:
        records = [
            make_record("b-method", "ai_methodology", 90),
            make_record("a-hybrid-low", "hybrid", 60),
            make_record("c-hybrid-high", "hybrid", 95),
            make_record("d-science", "ai_for_science", 88),
        ]
        sorted_titles = [record.title for record in sort_records(records)]
        self.assertEqual(
            sorted_titles,
            ["c-hybrid-high", "a-hybrid-low", "d-science", "b-method"],
        )

    def test_build_theme_filename(self) -> None:
        self.assertEqual(
            build_theme_filename("papers.json", "ai_methodology"),
            "papers.ai_methodology.json",
        )

    def test_build_review_filename(self) -> None:
        self.assertEqual(
            build_review_filename("papers.json"),
            "papers.review.csv",
        )

    def test_flatten_csv_text_removes_newlines_and_tabs(self) -> None:
        self.assertEqual(flatten_csv_text("a\nb\tc"), "a b c")

    def test_save_to_csv_uses_concise_columns(self) -> None:
        from ml_physics_crawler.output import save_to_csv

        record = make_record("test-title", "hybrid", 88, "2026-04-11")
        record.authors = ["Alice", "Bob"]
        record.journal = "JHEP"
        record.doi = "10.1000/test"
        record.pdf_url = "https://example.org/test.pdf"
        record.review_status = "approved"

        with TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "papers.csv"
            save_to_csv([record], str(output_file))
            header = output_file.read_text(encoding="utf-8").splitlines()[0]

        self.assertEqual(
            header,
            "source,published,theme,ai_score,review_status,title,journal,doi,article_url,pdf_url",
        )

    def test_save_review_csv_uses_concise_columns(self) -> None:
        from ml_physics_crawler.output import save_review_csv

        record = make_record("test-title", "hybrid", 88, "2026-04-11")
        record.authors = ["Alice", "Bob"]
        record.journal = "JHEP"
        record.doi = "10.1000/test"
        record.pdf_url = "https://example.org/test.pdf"

        with TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "papers.review.csv"
            save_review_csv([record], str(output_file))
            header = output_file.read_text(encoding="utf-8").splitlines()[0]

        self.assertEqual(
            header,
            "review_status,review_notes,reviewed_at,theme,ai_score,published,title,journal,doi,article_url,pdf_url",
        )

    def test_resolve_review_file(self) -> None:
        self.assertEqual(resolve_review_file("papers.json"), "papers.review.csv")

    def test_build_approved_bibtex_filename(self) -> None:
        self.assertEqual(build_approved_bibtex_filename("papers.json"), "papers.approved.bib")

    def test_split_records_by_theme(self) -> None:
        records = [
            make_record("hybrid-paper", "hybrid"),
            make_record("method-paper", "ai_methodology"),
            make_record("science-paper", "ai_for_science"),
        ]
        grouped = split_records_by_theme(records)
        self.assertEqual(list(grouped.keys()), ["hybrid", "ai_for_science", "ai_methodology"])
        self.assertEqual(grouped["hybrid"][0].title, "hybrid-paper")

    def test_sort_records_for_review_prioritizes_pending(self) -> None:
        approved = make_record("approved-paper", "hybrid", 95)
        approved.review_status = "approved"
        pending = make_record("pending-paper", "ai_methodology", 10)
        rejected = make_record("rejected-paper", "hybrid", 99)
        rejected.review_status = "rejected"

        sorted_titles = [record.title for record in sort_records_for_review([approved, rejected, pending])]
        self.assertEqual(sorted_titles[0], "pending-paper")

    def test_build_run_summary_contains_counts_and_files(self) -> None:
        records = [
            make_record("hybrid-paper", "hybrid", 90),
            make_record("method-paper", "ai_methodology", 80),
        ]
        records[0].ai_decision = "keep"
        records[1].ai_decision = "drop"
        records[0].review_status = "approved"

        summary = build_run_summary(
            records,
            CrawlConfig(enable_ai_filter=True, days_back=7),
            ["papers.json", "papers.hybrid.json"],
            RunPlan(mode="incremental", crawl_config=CrawlConfig(days_back=7), cache_file="papers.records.json"),
            2,
            zotero_result={"created": 1, "skipped": 0, "collection_key": "ABCD1234"},
        )

        self.assertIn("total records: 2", summary)
        self.assertIn("days_back: 7", summary)
        self.assertIn("hybrid: 1", summary)
        self.assertIn("ai_methodology: 1", summary)
        self.assertIn("approved: 1", summary)
        self.assertIn("pending: 1", summary)
        self.assertIn("keep: 1", summary)
        self.assertIn("drop: 1", summary)
        self.assertIn("created: 1", summary)
        self.assertIn("papers.json", summary)

    def test_build_summary_filename(self) -> None:
        self.assertEqual(
            build_summary_filename("papers.json"),
            "papers.summary.json.txt",
        )

    def test_build_manifest_filename(self) -> None:
        self.assertEqual(
            build_manifest_filename("papers.json"),
            "papers.manifest.json",
        )

    def test_build_run_manifest_contains_core_fields(self) -> None:
        records = [
            make_record("hybrid-paper", "hybrid", 90),
            make_record("method-paper", "ai_methodology", 80),
        ]
        records[0].ai_decision = "keep"
        records[1].ai_decision = "drop"
        records[0].review_status = "approved"
        config = CrawlConfig(enable_ai_filter=True, days_back=7, output_file="papers.json")

        manifest = build_run_manifest(
            records,
            config,
            ["papers.json", "papers.hybrid.json"],
            "papers.summary.json.txt",
            RunPlan(mode="incremental", crawl_config=config, cache_file="papers.records.json", has_existing_cache=True),
            2,
        )

        self.assertEqual(manifest["total_records"], 2)
        self.assertEqual(manifest["config"]["days_back"], 7)
        self.assertEqual(manifest["run_plan"]["mode"], "incremental")
        self.assertEqual(manifest["theme_counts"]["hybrid"], 1)
        self.assertEqual(manifest["review_counts"]["approved"], 1)
        self.assertEqual(manifest["ai_decision_counts"]["keep"], 1)
        self.assertEqual(manifest["summary_file"], "papers.summary.json.txt")

    def test_build_records_cache_filename(self) -> None:
        self.assertTrue(build_records_cache_filename("papers.json").endswith(".ml_physics_crawler_state/papers/records.json"))

    def test_build_run_state_filename(self) -> None:
        self.assertTrue(build_run_state_filename("papers.json").endswith(".ml_physics_crawler_state/papers/run_state.json"))

    def test_resolve_run_plan_auto_without_cache_uses_full_bootstrap(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "papers.json")
            config = CrawlConfig(output_file=output_file, crawl_mode="auto", total_results=300, bootstrap_total_results=1000)

            plan = resolve_run_plan(config)

            self.assertEqual(plan.mode, "full")
            self.assertFalse(plan.has_existing_cache)
            self.assertEqual(plan.crawl_config.total_results, 1000)
            self.assertIsNone(plan.crawl_config.days_back)

    def test_resolve_run_plan_auto_with_cache_uses_incremental(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "papers.json")
            cache_file = build_records_cache_filename(output_file)
            save_records_cache([make_record("cached-paper", "hybrid")], cache_file)
            config = CrawlConfig(
                output_file=output_file,
                crawl_mode="auto",
                incremental_total_results=123,
                incremental_days_back=5,
            )

            plan = resolve_run_plan(config)

            self.assertEqual(plan.mode, "incremental")
            self.assertTrue(plan.has_existing_cache)
            self.assertEqual(plan.crawl_config.total_results, 123)
            self.assertEqual(plan.crawl_config.days_back, 5)

    def test_resolve_run_plan_incremental_rejects_inspire(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_run_plan(CrawlConfig(output_file="papers.json", crawl_mode="incremental", source="inspire"))

    def test_resolve_run_plan_auto_with_cache_allows_unlimited_incremental(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "papers.json")
            cache_file = build_records_cache_filename(output_file)
            save_records_cache([make_record("cached-paper", "hybrid")], cache_file)
            config = CrawlConfig(
                output_file=output_file,
                crawl_mode="auto",
                no_total_limit=True,
                incremental_days_back=5,
            )

            plan = resolve_run_plan(config)

            self.assertEqual(plan.mode, "incremental")
            self.assertIsNone(plan.crawl_config.total_results)

    def test_resolve_total_limit_only_disables_limit_for_time_window_arxiv(self) -> None:
        self.assertIsNone(
            resolve_total_limit(
                CrawlConfig(source="arxiv", no_total_limit=True, since_date="2026-04-01T00:00:00+00:00")
            )
        )
        self.assertEqual(
            resolve_total_limit(
                CrawlConfig(source="arxiv", no_total_limit=True, total_results=300),
                1000,
            ),
            1000,
        )

    def test_resolve_run_plan_prefers_since_date_from_state(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "papers.json")
            cache_file = build_records_cache_filename(output_file)
            save_records_cache([make_record("cached-paper", "hybrid")], cache_file)
            state_file = build_run_state_filename(output_file)
            save_run_state(
                {"last_successful_run_at": "2026-04-09T00:00:00+00:00"},
                state_file,
            )

            plan = resolve_run_plan(CrawlConfig(output_file=output_file, crawl_mode="auto"))

            self.assertEqual(plan.mode, "incremental")
            self.assertIsNotNone(plan.crawl_config.since_date)
            self.assertIsNone(plan.crawl_config.days_back)

    def test_resolve_run_plan_process_approved_uses_local_cache_only(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "papers.json")
            cache_file = build_records_cache_filename(output_file)
            save_records_cache([make_record("cached-paper", "hybrid")], cache_file)

            plan = resolve_run_plan(CrawlConfig(output_file=output_file, process_approved=True))

            self.assertEqual(plan.mode, "process_approved")
            self.assertTrue(plan.has_existing_cache)
            self.assertEqual(plan.cache_file, cache_file)

    def test_save_and_load_run_state(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "papers.json")
            state_file = build_run_state_filename(output_file)
            save_run_state({"last_successful_run_at": "2026-04-10T00:00:00+00:00"}, state_file)

            loaded = load_run_state(state_file)
            self.assertEqual(loaded["last_successful_run_at"], "2026-04-10T00:00:00+00:00")

    def test_apply_review_updates(self) -> None:
        with TemporaryDirectory() as tmpdir:
            review_file = Path(tmpdir) / "papers.review.csv"
            review_file.write_text(
                (
                    "review_status,review_notes,reviewed_at,theme,ai_score,ai_decision,published,title,authors,categories,tags,match_reason,article_url,pdf_url,journal,abstract\n"
                    "approved,keep this,2026-04-10,hybrid,90,keep,2026-04-10,approved-paper,,,,,https://example.org/approved-paper,,,\n"
                ),
                encoding="utf-8",
            )
            record = make_record("approved-paper", "hybrid")
            updated = apply_review_updates([record], str(review_file))
            self.assertEqual(updated[0].review_status, "approved")
            self.assertEqual(updated[0].review_notes, "keep this")

    def test_select_approved_records(self) -> None:
        approved = make_record("approved-paper", "hybrid")
        approved.review_status = "approved"
        pending = make_record("pending-paper", "ai_methodology")
        selected = select_approved_records([approved, pending])
        self.assertEqual([record.title for record in selected], ["approved-paper"])

    def test_build_pdf_path_uses_theme_directory(self) -> None:
        record = make_record("Graph Neural Networks for Event Reconstruction", "hybrid", published="2026-04-10T00:00:00Z")
        record.authors = ["Alice Wang"]
        path = build_pdf_path(record, "library/pdfs")
        self.assertTrue(str(path).startswith("library/pdfs/hybrid/"))
        self.assertTrue(build_pdf_filename(record).endswith(".pdf"))

    def test_export_approved_bibtex_only_includes_approved(self) -> None:
        with TemporaryDirectory() as tmpdir:
            approved = make_record("Approved Paper", "hybrid", published="2026-04-10T00:00:00Z")
            approved.authors = ["Alice Wang", "Bob Li"]
            approved.review_status = "approved"
            approved.doi = "10.1234/example"
            approved.review_notes = "keep"
            pending = make_record("Pending Paper", "ai_methodology", published="2026-04-10T00:00:00Z")
            output_file = str(Path(tmpdir) / "papers.approved.bib")

            export_approved_bibtex([approved, pending], output_file)

            content = Path(output_file).read_text(encoding="utf-8")
            self.assertIn("@article{wang20262501000011,", content)
            self.assertIn("Approved Paper", content)
            self.assertIn("10.1234/example", content)
            self.assertNotIn("Pending Paper", content)
            self.assertNotIn("archivePrefix", content)
            self.assertNotIn("primaryClass", content)

    def test_build_record_identity_prefers_doi_then_arxiv_id(self) -> None:
        record = make_record("Approved Paper", "hybrid")
        record.doi = "10.1234/example"
        self.assertEqual(build_record_identity(record), "doi:10.1234/example")
        record.doi = ""
        self.assertEqual(build_record_identity(record), "arxiv:2501.00001v1")

    def test_record_to_zotero_item_includes_collection_and_tags(self) -> None:
        record = make_record("Approved Paper", "hybrid", published="2026-04-10T00:00:00Z")
        record.authors = ["Alice Wang", "Bob Li"]
        record.doi = "10.1234/example"
        record.review_status = "approved"
        record.review_notes = "keep"
        item = record_to_zotero_item(record, collection_key="ABCD1234")
        self.assertEqual(item["itemType"], "journalArticle")
        self.assertEqual(item["collections"], ["ABCD1234"])
        self.assertEqual(item["DOI"], "10.1234/example")
        self.assertTrue(any(tag["tag"] == "hybrid" for tag in item["tags"]))


if __name__ == "__main__":
    unittest.main()
