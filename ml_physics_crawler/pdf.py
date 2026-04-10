import re
from pathlib import Path

from .models import CrawlConfig, PaperRecord


def slugify_filename(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered)
    return lowered.strip("-") or "paper"


def build_pdf_filename(record: PaperRecord) -> str:
    first_author = slugify_filename(record.authors[0].split()[-1] if record.authors else "unknown")
    year = (record.published or "unknown")[:4] if record.published else "unknown"
    title = slugify_filename(record.title)[:80]
    arxiv_part = slugify_filename(record.arxiv_id or "no-id")
    return f"{first_author}_{year}_{arxiv_part}_{title}.pdf"


def build_pdf_path(record: PaperRecord, pdf_dir: str) -> Path:
    theme = record.theme or "uncategorized"
    return Path(pdf_dir) / theme / build_pdf_filename(record)


def select_approved_records(records: list[PaperRecord]) -> list[PaperRecord]:
    return [record for record in records if (record.review_status or "pending") == "approved"]


def download_approved_pdfs(records: list[PaperRecord], config: CrawlConfig) -> list[str]:
    approved_records = select_approved_records(records)
    if not approved_records:
        return []

    try:
        import requests
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "缺少依赖 requests，请先执行 `pip install requests`。"
        ) from exc

    downloaded_files = []
    for record in approved_records:
        if not record.pdf_url:
            continue

        destination = build_pdf_path(record, config.pdf_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            downloaded_files.append(str(destination))
            continue

        response = requests.get(record.pdf_url, timeout=config.timeout, stream=True)
        response.raise_for_status()
        with open(destination, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
        downloaded_files.append(str(destination))

    return downloaded_files
