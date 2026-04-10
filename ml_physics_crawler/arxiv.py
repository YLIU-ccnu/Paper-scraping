import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from .filtering import classify_record, deduplicate
from .models import CrawlConfig, PaperRecord
from .strategy import ARXIV_API, ARXIV_QUERY_ML_TERMS, HEADERS, ML_CATEGORIES, NS, SCIENCE_CATEGORIES
from .text_utils import clean_text


def build_arxiv_query() -> str:
    science_part = " OR ".join(f"cat:{category}" for category in sorted(SCIENCE_CATEGORIES))
    ml_part = " OR ".join([
        *(f"cat:{category}" for category in sorted(ML_CATEGORIES)),
        *ARXIV_QUERY_ML_TERMS,
    ])
    return f"(({science_part}) AND ({ml_part})) OR cat:cs.LG OR cat:stat.ML OR cat:cs.AI"


def build_arxiv_search_query(config: CrawlConfig) -> str:
    query = build_arxiv_query()
    end_date = datetime.now(timezone.utc)
    if config.since_date is not None:
        start_date = datetime.fromisoformat(config.since_date)
    elif config.days_back is not None:
        start_date = end_date - timedelta(days=config.days_back)
    else:
        return query

    date_range = (
        f"submittedDate:[{start_date.strftime('%Y%m%d%H%M')}"
        f" TO {end_date.strftime('%Y%m%d%H%M')}]"
    )
    return f"({query}) AND {date_range}"


def is_within_time_window(published: str, days_back: int | None, since_date: str | None = None) -> bool:
    if days_back is None and since_date is None:
        return True
    if not published:
        return False

    published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
    if since_date is not None:
        cutoff = datetime.fromisoformat(since_date)
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    return published_at >= cutoff


def fetch_arxiv_batch(start: int, max_results: int, config: CrawlConfig) -> str:
    try:
        import requests
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "缺少依赖 requests，请先执行 `pip install requests`。"
        ) from exc

    params = {
        "search_query": build_arxiv_search_query(config),
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    last_error = None
    for attempt in range(1, config.retries + 1):
        try:
            response = requests.get(
                ARXIV_API,
                params=params,
                headers=HEADERS,
                timeout=config.timeout,
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == config.retries:
                break
            print(f"[arXiv] batch {start} retry {attempt}/{config.retries} failed: {exc}")
            time.sleep(min(2 * attempt, 10))

    raise RuntimeError(f"arXiv 请求失败，start={start}, max_results={max_results}: {last_error}")


def arxiv_extract_categories(entry: ET.Element) -> list[str]:
    categories = set()
    primary = entry.find("arxiv:primary_category", NS)
    if primary is not None and primary.attrib.get("term"):
        categories.add(primary.attrib["term"])

    for category in entry.findall("atom:category", NS):
        term = category.attrib.get("term")
        if term:
            categories.add(term)

    return sorted(categories)


def arxiv_extract_text(entry: ET.Element, path: str) -> str:
    return clean_text(entry.findtext(path, default="", namespaces=NS))


def arxiv_extract_pdf_url(entry: ET.Element) -> str:
    for link in entry.findall("atom:link", NS):
        if link.attrib.get("title") == "pdf":
            return link.attrib.get("href", "")
    return ""


def arxiv_extract_authors(entry: ET.Element) -> list[str]:
    authors = []
    for author in entry.findall("atom:author", NS):
        name = clean_text(author.findtext("atom:name", default="", namespaces=NS))
        if name:
            authors.append(name)
    return authors


def arxiv_extract_id(arxiv_url: str) -> str:
    if not arxiv_url:
        return ""
    return arxiv_url.rstrip("/").split("/")[-1]


def parse_arxiv(xml_text: str, config: CrawlConfig) -> list[PaperRecord]:
    root = ET.fromstring(xml_text)
    records = []

    for entry in root.findall("atom:entry", NS):
        title = arxiv_extract_text(entry, "atom:title")
        abstract = arxiv_extract_text(entry, "atom:summary")
        arxiv_url = arxiv_extract_text(entry, "atom:id")
        published = arxiv_extract_text(entry, "atom:published")
        if not is_within_time_window(published, config.days_back, config.since_date):
            continue
        journal = arxiv_extract_text(entry, "arxiv:journal_ref") or "arXiv"
        doi = arxiv_extract_text(entry, "arxiv:doi")
        categories = arxiv_extract_categories(entry)

        text = f"{title} {abstract} {' '.join(categories)}"
        keep, match_reason, tags, theme = classify_record(text, categories, config.recall_mode)
        if not keep:
            continue

        records.append(PaperRecord(
            source="arXiv",
            arxiv_id=arxiv_extract_id(arxiv_url),
            title=title,
            authors=arxiv_extract_authors(entry),
            abstract=abstract,
            journal=journal,
            article_url=f"https://doi.org/{doi}" if doi else arxiv_url,
            pdf_url=arxiv_extract_pdf_url(entry),
            published=published,
            categories=categories,
            tags=tags,
            theme=theme,
            match_reason=match_reason,
        ))

    return records


def crawl_arxiv(config: CrawlConfig) -> list[PaperRecord]:
    records = []

    for start in range(0, config.total_results, config.batch_size):
        print(f"[arXiv] fetching {start} - {start + config.batch_size}")
        try:
            xml_text = fetch_arxiv_batch(start=start, max_results=config.batch_size, config=config)
            batch_records = parse_arxiv(xml_text, config)
            print(f"[arXiv] kept {len(batch_records)}")
            records.extend(batch_records)
        except Exception as exc:
            print(f"[arXiv] skipped batch {start}: {exc}")

        next_start = start + config.batch_size
        if next_start < config.total_results and config.sleep_seconds > 0:
            time.sleep(config.sleep_seconds)

    return deduplicate(records)
