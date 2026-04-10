import csv
from pathlib import Path

from .models import PaperRecord
from .output import build_review_filename


VALID_REVIEW_STATUSES = {"pending", "approved", "rejected"}


def build_record_key(title: str, article_url: str) -> tuple[str, str]:
    return (title.strip().lower(), article_url.strip().lower())


def normalize_review_status(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in VALID_REVIEW_STATUSES:
        return normalized
    return "pending"


def load_review_updates(review_file: str) -> dict[tuple[str, str], dict[str, str]]:
    path = Path(review_file)
    if not path.exists():
        return {}

    updates = {}
    with open(path, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            title = row.get("title", "")
            article_url = row.get("article_url", "")
            if not title or not article_url:
                continue
            updates[build_record_key(title, article_url)] = {
                "review_status": normalize_review_status(row.get("review_status", "")),
                "review_notes": (row.get("review_notes", "") or "").strip(),
                "reviewed_at": (row.get("reviewed_at", "") or "").strip(),
            }
    return updates


def apply_review_updates(records: list[PaperRecord], review_file: str) -> list[PaperRecord]:
    updates = load_review_updates(review_file)
    if not updates:
        return records

    for record in records:
        key = build_record_key(record.title, record.article_url)
        update = updates.get(key)
        if not update:
            continue
        record.review_status = update["review_status"]
        record.review_notes = update["review_notes"]
        record.reviewed_at = update["reviewed_at"]

    return records


def resolve_review_file(output_file: str) -> str:
    return build_review_filename(output_file)
