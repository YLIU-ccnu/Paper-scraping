import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ml_physics_crawler.ai_filter import should_apply_ai_filter
from ml_physics_crawler.cli import (
    build_manifest_filename,
    build_run_manifest,
    build_run_summary,
    build_summary_filename,
    resolve_run_plan,
)
from ml_physics_crawler.filtering import classify_record, should_keep_record
from ml_physics_crawler.models import CrawlConfig, PaperRecord, RunPlan
from ml_physics_crawler.output import build_theme_filename, sort_records, split_records_by_theme
from ml_physics_crawler.state import (
    build_records_cache_filename,
    build_run_state_filename,
    load_run_state,
    save_records_cache,
    save_run_state,
)


def make_record(title: str, theme: str, ai_score: int | None = None, published: str = "") -> PaperRecord:
    return PaperRecord(
        source="arXiv",
        title=title,
        authors=[],
        abstract="",
        journal="arXiv",
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

    def test_split_records_by_theme(self) -> None:
        records = [
            make_record("hybrid-paper", "hybrid"),
            make_record("method-paper", "ai_methodology"),
            make_record("science-paper", "ai_for_science"),
        ]
        grouped = split_records_by_theme(records)
        self.assertEqual(list(grouped.keys()), ["hybrid", "ai_for_science", "ai_methodology"])
        self.assertEqual(grouped["hybrid"][0].title, "hybrid-paper")

    def test_build_run_summary_contains_counts_and_files(self) -> None:
        records = [
            make_record("hybrid-paper", "hybrid", 90),
            make_record("method-paper", "ai_methodology", 80),
        ]
        records[0].ai_decision = "keep"
        records[1].ai_decision = "drop"

        summary = build_run_summary(
            records,
            CrawlConfig(enable_ai_filter=True, days_back=7),
            ["papers.json", "papers.hybrid.json"],
            RunPlan(mode="incremental", crawl_config=CrawlConfig(days_back=7), cache_file="papers.records.json"),
            2,
        )

        self.assertIn("total records: 2", summary)
        self.assertIn("days_back: 7", summary)
        self.assertIn("hybrid: 1", summary)
        self.assertIn("ai_methodology: 1", summary)
        self.assertIn("keep: 1", summary)
        self.assertIn("drop: 1", summary)
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

    def test_save_and_load_run_state(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "papers.json")
            state_file = build_run_state_filename(output_file)
            save_run_state({"last_successful_run_at": "2026-04-10T00:00:00+00:00"}, state_file)

            loaded = load_run_state(state_file)
            self.assertEqual(loaded["last_successful_run_at"], "2026-04-10T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
