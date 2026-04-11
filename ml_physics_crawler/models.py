from dataclasses import dataclass


@dataclass
class CrawlConfig:
    process_approved: bool = False
    source: str = "arxiv"
    crawl_mode: str = "auto"
    total_results: int = 300
    bootstrap_total_results: int = 1000
    incremental_total_results: int = 300
    batch_size: int = 100
    days_back: int | None = None
    incremental_days_back: int = 7
    since_date: str | None = None
    sleep_seconds: float = 3.0
    output_file: str = "ml_physics_papers.txt"
    output_format: str = "txt"
    retries: int = 3
    timeout: float = 30.0
    enable_ai_filter: bool = False
    ai_filter_scope: str = "borderline"
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_min_score: int = 60
    recall_mode: str = "broad"
    download_approved_pdfs: bool = False
    pdf_dir: str = "library/pdfs"
    export_approved_bibtex: bool = False
    bibtex_file: str | None = None
    sync_zotero: bool = False
    zotero_library_type: str = "users"
    zotero_library_id: str | None = None
    zotero_api_key: str | None = None
    zotero_collection: str | None = None
    inspire_query: str | None = None
    inspire_topcite: int | None = None


@dataclass
class RunPlan:
    mode: str
    crawl_config: CrawlConfig
    cache_file: str
    has_existing_cache: bool = False


@dataclass
class PaperRecord:
    source: str
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    journal: str
    doi: str
    article_url: str
    pdf_url: str
    published: str
    categories: list[str]
    tags: list[str]
    theme: str = ""
    ai_score: int | None = None
    ai_decision: str = ""
    ai_reason: str = ""
    match_reason: str = ""
    review_status: str = "pending"
    review_notes: str = ""
    reviewed_at: str = ""
