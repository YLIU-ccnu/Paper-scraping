import html
import re


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_keywords(text: str, keywords: list[str]) -> bool:
    normalized = normalize_keyword_text(text)
    return any(keyword_matches(normalized, keyword) for keyword in keywords)


def matched_keywords(text: str, keywords: list[str]) -> list[str]:
    normalized = normalize_keyword_text(text)
    return [keyword for keyword in keywords if keyword_matches(normalized, keyword)]


def normalize_keyword_text(text: str) -> str:
    return clean_text(text).lower()


def keyword_matches(normalized_text: str, keyword: str) -> bool:
    normalized_keyword = normalize_keyword_text(keyword)
    if not normalized_keyword:
        return False

    # Use word-boundary matching for acronym-like or phrase keywords to avoid
    # false positives such as matching "vae" inside unrelated words.
    if re.fullmatch(r"[\w -]+", normalized_keyword):
        pattern_body = re.escape(normalized_keyword).replace(r"\ ", r"\s+")
        if normalized_keyword[-1].isalnum() and not normalized_keyword.endswith("s"):
            pattern_body += r"s?"
        pattern = r"\b" + pattern_body + r"\b"
        return re.search(pattern, normalized_text) is not None

    return normalized_keyword in normalized_text
