from typing import Any

from .filtering import classify_record, deduplicate
from .models import CrawlConfig, PaperRecord
from .strategy import HEADERS, INSPIRE_API, INSPIRE_DEFAULT_QUERY, INSPIRE_DEFAULT_TOPCITE


def build_inspire_query(config: CrawlConfig) -> str:
    base_query = config.inspire_query or INSPIRE_DEFAULT_QUERY
    if config.inspire_topcite:
        return f"({base_query}) and topcite {config.inspire_topcite}+"
    return base_query


def fetch_inspire_records(config: CrawlConfig) -> dict[str, Any]:
    try:
        import requests
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少依赖 requests，请先执行 `pip install requests`。") from exc

    params = {
        "q": build_inspire_query(config),
        "size": config.total_results,
        "sort": "mostcited",
    }
    response = requests.get(
        INSPIRE_API,
        params=params,
        headers=HEADERS,
        timeout=config.timeout,
    )
    response.raise_for_status()
    return response.json()


def safe_get_first_title(metadata: dict[str, Any]) -> str:
    titles = metadata.get("titles") or []
    if titles and isinstance(titles[0], dict):
        return (titles[0].get("title") or "").strip()
    return ""


def safe_get_abstract(metadata: dict[str, Any]) -> str:
    abstracts = metadata.get("abstracts") or []
    if abstracts and isinstance(abstracts[0], dict):
        return (abstracts[0].get("value") or "").strip()
    return ""


def safe_get_authors(metadata: dict[str, Any]) -> list[str]:
    authors = []
    for author in metadata.get("authors") or []:
        full_name = (author.get("full_name") or "").strip()
        if full_name:
            authors.append(full_name)
    return authors


def safe_get_doi(metadata: dict[str, Any]) -> str:
    dois = metadata.get("dois") or []
    if dois and isinstance(dois[0], dict):
        return (dois[0].get("value") or "").strip()
    return ""


def safe_get_arxiv_id(metadata: dict[str, Any]) -> str:
    eprints = metadata.get("arxiv_eprints") or []
    if eprints and isinstance(eprints[0], dict):
        return (eprints[0].get("value") or "").strip()
    return ""


def safe_get_primary_categories(metadata: dict[str, Any]) -> list[str]:
    categories = []
    for category in metadata.get("inspire_categories") or []:
        term = (category.get("term") or "").strip()
        if term:
            categories.append(term)
    return sorted(set(categories))


def safe_get_published(metadata: dict[str, Any]) -> str:
    return (metadata.get("earliest_date") or "").strip()


def safe_get_journal(metadata: dict[str, Any]) -> str:
    publication_info = metadata.get("publication_info") or []
    if publication_info and isinstance(publication_info[0], dict):
        return (publication_info[0].get("journal_title") or "").strip()
    return "INSPIRE"


def safe_get_article_url(hit: dict[str, Any], metadata: dict[str, Any], doi: str, arxiv_id: str) -> str:
    if doi:
        return f"https://doi.org/{doi}"
    if arxiv_id:
        return f"https://arxiv.org/abs/{arxiv_id}"
    links = hit.get("links") or {}
    return (links.get("json") or links.get("self") or "").strip()


def safe_get_pdf_url(metadata: dict[str, Any], arxiv_id: str) -> str:
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    documents = metadata.get("documents") or []
    for document in documents:
        url = (document.get("url") or "").strip()
        if url:
            return url
    return ""


def parse_inspire(data: dict[str, Any], config: CrawlConfig) -> list[PaperRecord]:
    records = []
    for hit in (data.get("hits") or {}).get("hits", []):
        metadata = hit.get("metadata") or {}
        title = safe_get_first_title(metadata)
        abstract = safe_get_abstract(metadata)
        authors = safe_get_authors(metadata)
        doi = safe_get_doi(metadata)
        arxiv_id = safe_get_arxiv_id(metadata)
        categories = safe_get_primary_categories(metadata)
        published = safe_get_published(metadata)
        journal = safe_get_journal(metadata)
        article_url = safe_get_article_url(hit, metadata, doi, arxiv_id)
        pdf_url = safe_get_pdf_url(metadata, arxiv_id)

        text = f"{title} {abstract} {' '.join(categories)}"
        keep, match_reason, tags, theme = classify_record(text, categories, config.recall_mode)
        if not keep:
            continue

        records.append(
            PaperRecord(
                source="INSPIRE",
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                journal=journal,
                doi=doi,
                article_url=article_url,
                pdf_url=pdf_url,
                published=published,
                categories=categories,
                tags=tags,
                theme=theme,
                match_reason=match_reason or "matched_by_inspire",
            )
        )
    return records


def crawl_inspire(config: CrawlConfig) -> list[PaperRecord]:
    data = fetch_inspire_records(config)
    return deduplicate(parse_inspire(data, config))
