from pathlib import Path

from .models import PaperRecord
from .pdf import select_approved_records


def build_approved_bibtex_filename(output_file: str) -> str:
    path = Path(output_file)
    return str(path.with_name(f"{path.stem}.approved.bib"))


def sanitize_bibtex_value(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
    )


def build_bibtex_key(record: PaperRecord) -> str:
    author_part = "unknown"
    if record.authors:
        author_part = record.authors[0].split()[-1].lower()
    year_part = (record.published or "unknown")[:4]
    id_part = (record.arxiv_id or "paper").replace(".", "").replace("v", "")
    return f"{author_part}{year_part}{id_part}"


def paper_to_bibtex(record: PaperRecord) -> str:
    authors = " and ".join(record.authors) if record.authors else "Unknown"
    year = (record.published or "")[:4]
    fields = {
        "title": record.title,
        "author": authors,
        "year": year,
        "journal": record.journal or "arXiv",
        "abstract": record.abstract,
        "url": record.article_url,
        "eprint": record.arxiv_id,
        "archivePrefix": "arXiv" if record.arxiv_id else "",
        "primaryClass": record.categories[0] if record.categories else "",
        "keywords": ", ".join([record.theme, *record.tags]),
        "doi": record.doi,
        "note": record.review_notes,
    }

    lines = [f"@article{{{build_bibtex_key(record)}}},"]
    for key, value in fields.items():
        if value:
            lines.append(f"  {key} = {{{sanitize_bibtex_value(value)}}},")
    lines.append("}")
    return "\n".join(lines)


def export_approved_bibtex(records: list[PaperRecord], filename: str) -> str:
    approved_records = select_approved_records(records)
    with open(filename, "w", encoding="utf-8") as file:
        for index, record in enumerate(approved_records):
            if index:
                file.write("\n\n")
            file.write(paper_to_bibtex(record))
        file.write("\n")
    return filename
