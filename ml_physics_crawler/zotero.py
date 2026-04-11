import os
import secrets
from typing import Any

from .models import CrawlConfig, PaperRecord
from .pdf import select_approved_records


ZOTERO_API_BASE = "https://api.zotero.org"
ZOTERO_API_VERSION = "3"


def build_library_prefix(config: CrawlConfig) -> str:
    if not config.zotero_library_id:
        raise RuntimeError("缺少 Zotero library id，请设置 --zotero-library-id 或环境变量。")
    return f"/{config.zotero_library_type}/{config.zotero_library_id}"


def resolve_zotero_api_key(config: CrawlConfig) -> str:
    api_key = config.zotero_api_key or os.getenv("ZOTERO_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 Zotero API key，请设置 --zotero-api-key 或环境变量 ZOTERO_API_KEY。")
    return api_key


def build_zotero_headers(config: CrawlConfig, write: bool = False) -> dict[str, str]:
    headers = {
        "Zotero-API-Version": ZOTERO_API_VERSION,
        "Zotero-API-Key": resolve_zotero_api_key(config),
        "Content-Type": "application/json",
    }
    if write:
        headers["Zotero-Write-Token"] = secrets.token_hex(16)
    return headers


def creator_from_author(author: str) -> dict[str, str]:
    parts = author.strip().split()
    if len(parts) >= 2:
        return {
            "creatorType": "author",
            "firstName": " ".join(parts[:-1]),
            "lastName": parts[-1],
        }
    return {
        "creatorType": "author",
        "name": author.strip() or "Unknown",
    }


def build_record_identity(record: PaperRecord) -> str:
    if record.doi:
        return f"doi:{record.doi.strip().lower()}"
    if record.arxiv_id:
        return f"arxiv:{record.arxiv_id.strip().lower()}"
    return f"title:{record.title.strip().lower()}"


def record_to_zotero_item(record: PaperRecord, collection_key: str | None = None) -> dict[str, Any]:
    item = {
        "itemType": "journalArticle",
        "title": record.title,
        "creators": [creator_from_author(author) for author in record.authors] or [{"creatorType": "author", "name": "Unknown"}],
        "abstractNote": record.abstract,
        "publicationTitle": record.journal or "arXiv",
        "url": record.article_url,
        "date": record.published[:10] if record.published else "",
        "DOI": record.doi,
        "tags": [{"tag": tag} for tag in [record.theme, *record.tags] if tag],
        "extra": "\n".join(
            part for part in [
                f"arXiv: {record.arxiv_id}" if record.arxiv_id else "",
                f"PDF: {record.pdf_url}" if record.pdf_url else "",
                f"Review status: {record.review_status}" if record.review_status else "",
                f"Review notes: {record.review_notes}" if record.review_notes else "",
            ] if part
        ),
    }
    if collection_key:
        item["collections"] = [collection_key]
    return item


def fetch_paginated_json(path: str, config: CrawlConfig, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        import requests
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少依赖 requests，请先执行 `pip install requests`。") from exc

    items: list[dict[str, Any]] = []
    start = 0
    while True:
        query = {"format": "json", "limit": 100, "start": start}
        if params:
            query.update(params)
        response = requests.get(
            f"{ZOTERO_API_BASE}{path}",
            headers=build_zotero_headers(config, write=False),
            params=query,
            timeout=config.timeout,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        start += 100
    return items


def ensure_collection(config: CrawlConfig) -> str | None:
    collection_name = config.zotero_collection
    if not collection_name:
        return None

    try:
        import requests
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少依赖 requests，请先执行 `pip install requests`。") from exc

    prefix = build_library_prefix(config)
    collections = fetch_paginated_json(f"{prefix}/collections", config)
    for collection in collections:
        data = collection.get("data", {})
        if data.get("name") == collection_name:
            return data.get("key")

    response = requests.post(
        f"{ZOTERO_API_BASE}{prefix}/collections",
        headers=build_zotero_headers(config, write=True),
        json=[{"name": collection_name}],
        timeout=config.timeout,
    )
    response.raise_for_status()
    result = response.json()
    key = result.get("success", {}).get("0")
    if not key:
        raise RuntimeError(f"创建 Zotero collection 失败: {result}")
    return key


def fetch_existing_identities(config: CrawlConfig, collection_key: str | None = None) -> set[str]:
    prefix = build_library_prefix(config)
    path = f"{prefix}/collections/{collection_key}/items/top" if collection_key else f"{prefix}/items/top"
    items = fetch_paginated_json(path, config)
    identities: set[str] = set()
    for item in items:
        data = item.get("data", {})
        doi = (data.get("DOI") or "").strip().lower()
        if doi:
            identities.add(f"doi:{doi}")
        extra = data.get("extra") or ""
        for line in extra.splitlines():
            if line.lower().startswith("arxiv:"):
                identities.add(f"arxiv:{line.split(':', 1)[1].strip().lower()}")
        title = (data.get("title") or "").strip().lower()
        if title:
            identities.add(f"title:{title}")
    return identities


def sync_approved_to_zotero(records: list[PaperRecord], config: CrawlConfig) -> dict[str, Any]:
    approved_records = select_approved_records(records)
    if not approved_records:
        return {"created": 0, "skipped": 0, "collection_key": None}

    try:
        import requests
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少依赖 requests，请先执行 `pip install requests`。") from exc

    prefix = build_library_prefix(config)
    collection_key = ensure_collection(config)
    existing_identities = fetch_existing_identities(config, collection_key=collection_key)

    new_items = []
    skipped = 0
    for record in approved_records:
        identity = build_record_identity(record)
        if identity in existing_identities:
            skipped += 1
            continue
        existing_identities.add(identity)
        new_items.append(record_to_zotero_item(record, collection_key=collection_key))

    if not new_items:
        return {"created": 0, "skipped": skipped, "collection_key": collection_key}

    response = requests.post(
        f"{ZOTERO_API_BASE}{prefix}/items",
        headers=build_zotero_headers(config, write=True),
        json=new_items[:50],
        timeout=config.timeout,
    )
    response.raise_for_status()
    result = response.json()
    created = len(result.get("success", {}))
    failed = result.get("failed", {})
    if failed:
        raise RuntimeError(f"Zotero 同步部分失败: {failed}")
    return {"created": created, "skipped": skipped, "collection_key": collection_key}
