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


def build_bibtex_entry_type(record: PaperRecord) -> str:
    if record.doi or (record.journal and record.journal.lower() != "arxiv"):
        return "article"
    return "misc"


def paper_to_bibtex(record: PaperRecord) -> str:
    authors = " and ".join(record.authors) if record.authors else "Unknown"
    year = (record.published or "")[:4]
    month = ""
    if len(record.published) >= 7:
        month = record.published[5:7]

    note_parts = []
    if record.arxiv_id:
        note_parts.append(f"arXiv:{record.arxiv_id}")
    if record.review_notes:
        note_parts.append(record.review_notes)

    fields = {
        "title": record.title,
        "author": authors,
        "year": year,
        "month": month,
        "journal": record.journal if build_bibtex_entry_type(record) == "article" else "",
        "howpublished": f"arXiv preprint {record.arxiv_id}" if build_bibtex_entry_type(record) == "misc" and record.arxiv_id else "",
        "abstract": record.abstract,
        "doi": record.doi,
        "url": record.article_url,
        "keywords": ", ".join([record.theme, *record.tags]),
        "note": "; ".join(note_parts),
    }

    entry_type = build_bibtex_entry_type(record)
    lines = ["@" + entry_type + "{" + build_bibtex_key(record) + ","]
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
