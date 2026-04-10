import argparse
import json
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .ai_filter import apply_ai_filter
from .arxiv import crawl_arxiv
from .filtering import deduplicate
from .models import CrawlConfig, PaperRecord, RunPlan
from .output import save_records
from .state import (
    build_records_cache_filename,
    build_run_state_filename,
    has_cached_records,
    load_records_cache,
    load_run_state,
    save_records_cache,
    save_run_state,
)
from .strategy import THEME_ORDER


def parse_args() -> CrawlConfig:
    parser = argparse.ArgumentParser(description="抓取 arXiv 上与 AI for Science 或相关 AI 方法论文。")
    parser.add_argument("--total-results", type=int, default=300, help="总共抓取多少条 arXiv 结果。")
    parser.add_argument(
        "--crawl-mode",
        choices=["auto", "full", "incremental"],
        default="auto",
        help="抓取模式：auto 首次全量后续增量，full 强制全量，incremental 强制增量。",
    )
    parser.add_argument("--bootstrap-total-results", type=int, default=1000, help="首次全量初始化时抓取的结果上限。")
    parser.add_argument("--incremental-total-results", type=int, default=300, help="增量模式下抓取的结果上限。")
    parser.add_argument("--batch-size", type=int, default=100, help="每次请求拉取多少条结果。")
    parser.add_argument("--days-back", type=int, help="只保留最近 N 天的论文。")
    parser.add_argument("--incremental-days-back", type=int, default=7, help="增量模式默认回看最近 N 天。")
    parser.add_argument("--sleep-seconds", type=float, default=3.0, help="两次请求之间的等待秒数。")
    parser.add_argument("--output-file", default="ml_physics_papers.txt", help="输出 txt 文件名。")
    parser.add_argument(
        "--output-format",
        choices=["txt", "json", "csv"],
        default="txt",
        help="输出格式，支持 txt/json/csv。",
    )
    parser.add_argument("--retries", type=int, default=3, help="单个请求失败后的最大重试次数。")
    parser.add_argument("--timeout", type=float, default=30.0, help="单个请求的超时时间（秒）。")
    parser.add_argument("--enable-ai-filter", action="store_true", help="启用 AI 二次筛选。")
    parser.add_argument(
        "--ai-filter-scope",
        choices=["all", "borderline", "none"],
        default="borderline",
        help="AI 二次筛选范围：all 全量、borderline 仅边界样本、none 不调用模型。",
    )
    parser.add_argument("--ai-model", default="gpt-4o-mini", help="AI 筛选使用的模型名称。")
    parser.add_argument("--ai-base-url", default="https://api.openai.com/v1", help="AI 接口基础地址。")
    parser.add_argument("--ai-min-score", type=int, default=60, help="AI 保留论文的最低分数阈值。")
    parser.add_argument(
        "--recall-mode",
        choices=["strict", "balanced", "broad"],
        default="broad",
        help="粗筛召回模式：strict 最严格，balanced 折中，broad 尽量少漏。",
    )
    args = parser.parse_args()

    if args.total_results <= 0:
        parser.error("--total-results 必须大于 0")
    if args.bootstrap_total_results <= 0:
        parser.error("--bootstrap-total-results 必须大于 0")
    if args.incremental_total_results <= 0:
        parser.error("--incremental-total-results 必须大于 0")
    if args.batch_size <= 0:
        parser.error("--batch-size 必须大于 0")
    if args.days_back is not None and args.days_back <= 0:
        parser.error("--days-back 必须大于 0")
    if args.incremental_days_back <= 0:
        parser.error("--incremental-days-back 必须大于 0")
    if args.sleep_seconds < 0:
        parser.error("--sleep-seconds 不能小于 0")
    if args.retries <= 0:
        parser.error("--retries 必须大于 0")
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
    if not 0 <= args.ai_min_score <= 100:
        parser.error("--ai-min-score 必须在 0 到 100 之间")

    return CrawlConfig(
        crawl_mode=args.crawl_mode,
        total_results=args.total_results,
        bootstrap_total_results=args.bootstrap_total_results,
        incremental_total_results=args.incremental_total_results,
        batch_size=args.batch_size,
        days_back=args.days_back,
        incremental_days_back=args.incremental_days_back,
        sleep_seconds=args.sleep_seconds,
        output_file=args.output_file,
        output_format=args.output_format,
        retries=args.retries,
        timeout=args.timeout,
        enable_ai_filter=args.enable_ai_filter,
        ai_filter_scope=args.ai_filter_scope,
        ai_model=args.ai_model,
        ai_base_url=args.ai_base_url,
        ai_min_score=args.ai_min_score,
        recall_mode=args.recall_mode,
    )


def resolve_run_plan(config: CrawlConfig) -> RunPlan:
    cache_file = build_records_cache_filename(config.output_file)
    state_file = build_run_state_filename(config.output_file)
    has_cache = has_cached_records(cache_file)
    run_state = load_run_state(state_file)
    last_successful_run_at = run_state.get("last_successful_run_at")

    if config.crawl_mode == "auto":
        if has_cache:
            since_date = None
            if last_successful_run_at:
                since_dt = datetime.fromisoformat(last_successful_run_at)
                since_date = (since_dt - timedelta(hours=6)).isoformat()
            return RunPlan(
                mode="incremental",
                crawl_config=replace(
                    config,
                    total_results=config.incremental_total_results,
                    days_back=None if since_date else (config.days_back if config.days_back is not None else config.incremental_days_back),
                    since_date=since_date,
                ),
                cache_file=cache_file,
                has_existing_cache=True,
            )
        return RunPlan(
            mode="full",
            crawl_config=replace(
                config,
                total_results=max(config.total_results, config.bootstrap_total_results),
                days_back=None,
            ),
            cache_file=cache_file,
            has_existing_cache=False,
        )

    if config.crawl_mode == "incremental":
        since_date = None
        if last_successful_run_at:
            since_dt = datetime.fromisoformat(last_successful_run_at)
            since_date = (since_dt - timedelta(hours=6)).isoformat()
        return RunPlan(
            mode="incremental",
            crawl_config=replace(
                config,
                days_back=None if since_date else (config.days_back if config.days_back is not None else config.incremental_days_back),
                since_date=since_date,
            ),
            cache_file=cache_file,
            has_existing_cache=has_cache,
        )

    return RunPlan(
        mode="full",
        crawl_config=config,
        cache_file=cache_file,
        has_existing_cache=has_cache,
    )


def build_run_summary(
    records: list[PaperRecord],
    config: CrawlConfig,
    generated_files: list[str],
    plan: RunPlan,
    fetched_count: int,
) -> str:
    lines = []
    lines.append("Run summary:")
    lines.append(f"- run_mode: {plan.mode}")
    lines.append(f"- fetched_this_run: {fetched_count}")
    lines.append(f"- total records: {len(records)}")
    if config.since_date is not None:
        lines.append(f"- since_date: {config.since_date}")
    if config.days_back is not None:
        lines.append(f"- days_back: {config.days_back}")
    lines.append(f"- cache_file: {plan.cache_file}")

    theme_counts = Counter(record.theme or "uncategorized" for record in records)
    if theme_counts:
        lines.append("- themes:")
        for theme, _ in sorted(THEME_ORDER.items(), key=lambda item: item[1]):
            count = theme_counts.get(theme, 0)
            if count:
                lines.append(f"  {theme}: {count}")

    if config.enable_ai_filter:
        decision_counts = Counter(record.ai_decision or "unknown" for record in records)
        lines.append("- ai decisions:")
        for decision in ["keep", "drop", "error", "skipped", "unknown"]:
            count = decision_counts.get(decision, 0)
            if count:
                lines.append(f"  {decision}: {count}")

    lines.append("- files:")
    for filename in generated_files:
        lines.append(f"  {filename}")

    return "\n".join(lines)


def build_summary_filename(output_file: str) -> str:
    path = Path(output_file)
    suffix = path.suffix or ".txt"
    return str(path.with_name(f"{path.stem}.summary{suffix}.txt"))


def write_run_summary(summary: str, output_file: str) -> str:
    summary_filename = build_summary_filename(output_file)
    with open(summary_filename, "w", encoding="utf-8") as file:
        file.write(summary)
        file.write("\n")
    return summary_filename


def build_manifest_filename(output_file: str) -> str:
    path = Path(output_file)
    return str(path.with_name(f"{path.stem}.manifest.json"))


def build_run_manifest(
    records: list[PaperRecord],
    config: CrawlConfig,
    generated_files: list[str],
    summary_file: str,
    plan: RunPlan,
    fetched_count: int,
) -> dict:
    theme_counts = Counter(record.theme or "uncategorized" for record in records)
    ai_decision_counts = Counter(record.ai_decision or "unknown" for record in records)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": asdict(config),
        "run_plan": {
            "mode": plan.mode,
            "cache_file": plan.cache_file,
            "has_existing_cache": plan.has_existing_cache,
            "effective_config": asdict(plan.crawl_config),
        },
        "fetched_this_run": fetched_count,
        "total_records": len(records),
        "theme_counts": dict(theme_counts),
        "ai_decision_counts": dict(ai_decision_counts),
        "generated_files": generated_files,
        "summary_file": summary_file,
    }


def write_run_manifest(manifest: dict, output_file: str) -> str:
    manifest_filename = build_manifest_filename(output_file)
    with open(manifest_filename, "w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return manifest_filename


def run(config: CrawlConfig) -> int:
    plan = resolve_run_plan(config)
    fetched_records = crawl_arxiv(plan.crawl_config)
    fetched_records = apply_ai_filter(fetched_records, plan.crawl_config)

    if plan.mode == "incremental" and plan.has_existing_cache:
        existing_records = load_records_cache(plan.cache_file)
        records = deduplicate(fetched_records + existing_records)
    else:
        records = fetched_records

    cache_file = save_records_cache(records, plan.cache_file)
    generated_files = save_records(records, plan.crawl_config)
    summary = build_run_summary(records, plan.crawl_config, generated_files, plan, len(fetched_records))
    summary_file = write_run_summary(summary, config.output_file)
    manifest = build_run_manifest(records, plan.crawl_config, [cache_file, *generated_files], summary_file, plan, len(fetched_records))
    manifest_file = write_run_manifest(manifest, config.output_file)
    state_file = build_run_state_filename(config.output_file)
    save_run_state(
        {
            "last_successful_run_at": datetime.now(timezone.utc).isoformat(),
            "last_run_mode": plan.mode,
            "cache_file": plan.cache_file,
            "manifest_file": manifest_file,
            "summary_file": summary_file,
            "total_records": len(records),
        },
        state_file,
    )
    print(f"Saved {len(records)} papers to {plan.crawl_config.output_file} ({plan.crawl_config.output_format})")
    print(summary)
    print(f"Summary file: {summary_file}")
    print(f"Manifest file: {manifest_file}")
    return 0


def main() -> int:
    return run(parse_args())
