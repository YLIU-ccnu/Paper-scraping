import json
import os
import time

from .models import CrawlConfig, PaperRecord
from .strategy import AI_FILTER_SYSTEM_PROMPT, AI_FILTER_USER_PROMPT_TEMPLATE


def build_ai_filter_prompt(record: PaperRecord) -> str:
    return AI_FILTER_USER_PROMPT_TEMPLATE.format(
        title=record.title,
        authors=", ".join(record.authors) if record.authors else "N/A",
        categories=", ".join(record.categories) if record.categories else "N/A",
        tags=", ".join(record.tags) if record.tags else "N/A",
        match_reason=record.match_reason or "N/A",
        abstract=record.abstract,
    )


def call_ai_filter(record: PaperRecord, config: CrawlConfig) -> tuple[bool, int | None, str]:
    try:
        import requests
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "缺少依赖 requests，请先执行 `pip install requests`。"
        ) from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("启用 AI 筛选时需要设置环境变量 OPENAI_API_KEY。")

    payload = {
        "model": config.ai_model,
        "messages": [
            {"role": "system", "content": AI_FILTER_SYSTEM_PROMPT},
            {"role": "user", "content": build_ai_filter_prompt(record)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    response = requests.post(
        f"{config.ai_base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=config.timeout,
    )
    response.raise_for_status()

    data = response.json()
    result = json.loads(data["choices"][0]["message"]["content"])

    score = result.get("score")
    if isinstance(score, bool):
        score = int(score)
    if not isinstance(score, int):
        score = None

    keep = bool(result.get("keep"))
    reason = str(result.get("reason", "")).strip()
    if score is not None and score < config.ai_min_score:
        keep = False

    return keep, score, reason


def should_apply_ai_filter(record: PaperRecord, config: CrawlConfig) -> bool:
    if not config.enable_ai_filter:
        return False
    if config.ai_filter_scope == "all":
        return True
    if config.ai_filter_scope == "none":
        return False

    # Borderline mode: skip clearly strong matches and focus spending on ambiguous samples.
    if record.theme in {"hybrid", "ai_methodology"}:
        return False
    if "science_category" in record.match_reason and "ml_category" in record.match_reason:
        return False
    return True


def apply_ai_filter(records: list[PaperRecord], config: CrawlConfig) -> list[PaperRecord]:
    if not config.enable_ai_filter:
        return records

    filtered = []
    for index, record in enumerate(records, start=1):
        if not should_apply_ai_filter(record, config):
            record.ai_decision = "skipped"
            filtered.append(record)
            continue

        print(f"[AI] screening {index}/{len(records)}: {record.title[:80]}")
        try:
            keep, score, reason = call_ai_filter(record, config)
            record.ai_score = score
            record.ai_decision = "keep" if keep else "drop"
            record.ai_reason = reason
            if keep:
                filtered.append(record)
        except Exception as exc:
            record.ai_decision = "error"
            record.ai_reason = str(exc)
            print(f"[AI] skipped AI decision for '{record.title[:60]}': {exc}")
            filtered.append(record)

        if config.sleep_seconds > 0:
            time.sleep(min(config.sleep_seconds, 1.0))

    return filtered
