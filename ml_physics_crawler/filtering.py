from .strategy import ML_CATEGORIES, ML_KEYWORDS, SCIENCE_CATEGORIES, SCIENCE_KEYWORDS
from .models import PaperRecord
from .text_utils import matched_keywords


def detect_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = []

    if any(keyword in lowered for keyword in [
        "particle physics", "collider", "jet", "detector", "phenomenology",
        "hep-ph", "hep-ex", "amplitude", "parton",
    ]):
        tags.append("particle_physics")

    if any(keyword in lowered for keyword in [
        "nuclear physics", "nuclear matter", "nuclear structure",
        "nuclear reaction", "nucl-th", "nucl-ex", "nucleus", "nuclei",
    ]):
        tags.append("nuclear_physics")

    if any(keyword in lowered for keyword in [
        "heavy ion", "heavy-ion", "quark-gluon plasma", "qgp",
        "flow", "jet quenching", "nuclear collision",
    ]):
        tags.append("high_energy_nuclear")

    if any(keyword in lowered for keyword in [
        "theoretical physics", "quantum field theory", "qft",
        "string theory", "ads/cft", "effective field theory",
        "eft", "hep-th", "lattice qcd",
    ]):
        tags.append("theoretical_physics")

    if any(keyword in lowered for keyword in [
        "materials science", "molecular dynamics", "quantum chemistry", "chemistry",
        "protein", "drug discovery", "genomics", "bioinformatics", "biology",
        "astronomy", "astrophysics", "cosmology", "earth science", "climate",
    ]):
        tags.append("science_application")

    if any(keyword in lowered for keyword in [
        "machine learning", "deep learning", "transformer", "diffusion",
        "foundation model", "language model", "graph neural network",
        "representation learning", "scientific machine learning", "ai for science",
    ]):
        tags.append("ai_for_science_or_method")

    return sorted(set(tags))


def should_keep_record(
    has_science: bool,
    has_ml: bool,
    category_has_science: bool,
    category_has_ml: bool,
    recall_mode: str,
) -> bool:
    if recall_mode == "strict":
        return has_science and has_ml

    if recall_mode == "balanced":
        return (
            (has_science and has_ml)
            or (category_has_science and has_ml)
            or (category_has_ml and has_science)
        )

    return has_science or has_ml


def classify_theme(
    has_science: bool,
    has_ml: bool,
    category_has_science: bool,
    category_has_ml: bool,
    matched_science: list[str],
    matched_ml: list[str],
) -> str:
    if has_science and has_ml:
        if category_has_science and category_has_ml:
            return "hybrid"
        if matched_science and matched_ml:
            return "hybrid"
        return "ai_for_science"

    if has_science:
        return "science_application"

    if has_ml:
        if category_has_ml or matched_ml:
            return "ai_methodology"

    return "uncategorized"


def classify_record(text: str, categories: list[str], recall_mode: str) -> tuple[bool, str, list[str], str]:
    matched_ml = matched_keywords(text, ML_KEYWORDS)
    matched_science = matched_keywords(text, SCIENCE_KEYWORDS)
    category_has_science = bool(set(categories) & SCIENCE_CATEGORIES)
    category_has_ml = bool(set(categories) & ML_CATEGORIES)
    has_science = category_has_science or bool(matched_science)
    has_ml = category_has_ml or bool(matched_ml)

    keep = should_keep_record(
        has_science=has_science,
        has_ml=has_ml,
        category_has_science=category_has_science,
        category_has_ml=category_has_ml,
        recall_mode=recall_mode,
    )

    match_parts = []
    if category_has_science:
        match_parts.append("science_category")
    if category_has_ml:
        match_parts.append("ml_category")
    if matched_science:
        match_parts.append(f"science_keywords={', '.join(matched_science[:5])}")
    if matched_ml:
        match_parts.append(f"ml_keywords={', '.join(matched_ml[:5])}")

    theme = classify_theme(
        has_science=has_science,
        has_ml=has_ml,
        category_has_science=category_has_science,
        category_has_ml=category_has_ml,
        matched_science=matched_science,
        matched_ml=matched_ml,
    )

    return (
        keep,
        "; ".join(match_parts) if match_parts else "matched_by_query",
        detect_tags(text),
        theme,
    )


def deduplicate(records: list[PaperRecord]) -> list[PaperRecord]:
    seen = set()
    deduplicated = []

    for record in records:
        key = (record.title.lower(), record.article_url.lower())
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(record)

    return deduplicated
