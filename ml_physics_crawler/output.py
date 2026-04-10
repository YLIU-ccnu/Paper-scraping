import csv
import json
from dataclasses import asdict
from pathlib import Path

from .models import CrawlConfig, PaperRecord
from .strategy import THEME_ORDER, THEME_TITLES


def sort_records(records: list[PaperRecord]) -> list[PaperRecord]:
    return sorted(
        records,
        key=lambda record: (
            THEME_ORDER.get(record.theme or "uncategorized", 99),
            -(record.ai_score if record.ai_score is not None else -1),
            (record.published or ""),
            record.title.lower(),
        ),
        reverse=False,
    )


def build_theme_filename(filename: str, theme: str) -> str:
    path = Path(filename)
    suffix = path.suffix or ".txt"
    stem = path.stem
    return str(path.with_name(f"{stem}.{theme}{suffix}"))


def split_records_by_theme(records: list[PaperRecord]) -> dict[str, list[PaperRecord]]:
    grouped = {theme: [] for theme in THEME_ORDER}
    for record in sort_records(records):
        theme = record.theme or "uncategorized"
        grouped.setdefault(theme, []).append(record)
    return {theme: items for theme, items in grouped.items() if items}


def save_to_txt(records: list[PaperRecord], filename: str) -> None:
    sorted_records = sort_records(records)

    with open(filename, "w", encoding="utf-8") as file:
        current_theme = None
        for index, record in enumerate(sorted_records, start=1):
            theme = record.theme or "uncategorized"
            if theme != current_theme:
                current_theme = theme
                file.write(f"===== Theme: {THEME_TITLES.get(theme, theme)} =====\n\n")

            file.write(f"===== Paper {index} =====\n")
            file.write(f"来源: {record.source}\n")
            file.write(f"标题: {record.title}\n")
            file.write(f"作者: {', '.join(record.authors) if record.authors else 'N/A'}\n")
            file.write(f"分类: {', '.join(record.categories) if record.categories else 'N/A'}\n")
            file.write(f"主题: {record.theme or 'N/A'}\n")
            file.write(f"标签: {', '.join(record.tags) if record.tags else 'uncategorized'}\n")
            file.write(f"粗筛依据: {record.match_reason or 'N/A'}\n")
            file.write(f"期刊: {record.journal or 'N/A'}\n")
            file.write(f"发布时间: {record.published or 'N/A'}\n")
            file.write(f"文献地址: {record.article_url or 'N/A'}\n")
            file.write(f"pdf_url: {record.pdf_url or 'N/A'}\n")
            file.write(f"AI评分: {record.ai_score if record.ai_score is not None else 'N/A'}\n")
            file.write(f"AI结论: {record.ai_decision or 'N/A'}\n")
            file.write(f"AI理由: {record.ai_reason or 'N/A'}\n")
            file.write(f"摘要: {record.abstract or 'N/A'}\n")
            file.write("\n")


def save_to_json(records: list[PaperRecord], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as file:
        json.dump([asdict(record) for record in sort_records(records)], file, ensure_ascii=False, indent=2)


def save_to_csv(records: list[PaperRecord], filename: str) -> None:
    fieldnames = [
        "source",
        "title",
        "authors",
        "abstract",
        "journal",
        "article_url",
        "pdf_url",
        "published",
        "categories",
        "theme",
        "tags",
        "match_reason",
        "ai_score",
        "ai_decision",
        "ai_reason",
    ]

    with open(filename, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for record in sort_records(records):
            row = asdict(record)
            row["authors"] = "; ".join(record.authors)
            row["categories"] = "; ".join(record.categories)
            row["tags"] = "; ".join(record.tags)
            writer.writerow(row)


def save_theme_splits(records: list[PaperRecord], config: CrawlConfig) -> None:
    generated_files = []
    grouped_records = split_records_by_theme(records)
    for theme, theme_records in grouped_records.items():
        theme_filename = build_theme_filename(config.output_file, theme)
        if config.output_format == "txt":
            save_to_txt(theme_records, theme_filename)
        elif config.output_format == "json":
            save_to_json(theme_records, theme_filename)
        elif config.output_format == "csv":
            save_to_csv(theme_records, theme_filename)
        else:
            continue
        generated_files.append(theme_filename)
    return generated_files


def save_records(records: list[PaperRecord], config: CrawlConfig) -> list[str]:
    if config.output_format == "txt":
        save_to_txt(records, config.output_file)
    elif config.output_format == "json":
        save_to_json(records, config.output_file)
    elif config.output_format == "csv":
        save_to_csv(records, config.output_file)
    else:
        raise ValueError(f"不支持的输出格式: {config.output_format}")

    return [config.output_file, *save_theme_splits(records, config)]
