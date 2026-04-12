import smtplib
from email.message import EmailMessage

from .models import CrawlConfig, PaperRecord
from .text_utils import clean_text


def build_email_subject(records: list[PaperRecord], config: CrawlConfig) -> str:
    source = (config.source or "papers").lower()
    return f"{config.mail_subject_prefix}: {len(records)} new {source} papers"


def format_record_block(record: PaperRecord, index: int) -> str:
    authors = ", ".join(record.authors) if record.authors else "N/A"
    abstract = clean_text(record.abstract) or "N/A"
    return "\n".join(
        [
            f"[{index}]",
            f"theme: {record.theme or 'N/A'}",
            f"title: {record.title or 'N/A'}",
            f"authors: {authors}",
            f"abstract: {abstract}",
            f"pdf_url: {record.pdf_url or 'N/A'}",
        ]
    )


def build_email_body(records: list[PaperRecord], config: CrawlConfig, summary: str) -> str:
    lines = [
        "This is an automated paper update.",
        "",
        f"source: {config.source}",
        f"new_records: {len(records)}",
        "",
    ]
    if not records:
        lines.extend(
            [
                "No new papers matched this run.",
                "",
                summary,
            ]
        )
        return "\n".join(lines)

    lines.append("Detailed updates:")
    lines.append("")
    for index, record in enumerate(records, start=1):
        lines.append(format_record_block(record, index))
        lines.append("")
    lines.append("Run summary:")
    lines.append(summary)
    return "\n".join(lines).strip() + "\n"


def send_update_email(records: list[PaperRecord], config: CrawlConfig, summary: str) -> None:
    message = EmailMessage()
    message["Subject"] = build_email_subject(records, config)
    message["From"] = config.mail_from
    message["To"] = config.mail_to
    message.set_content(build_email_body(records, config, summary))

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=config.timeout) as server:
        server.starttls()
        server.login(config.smtp_user, config.smtp_password)
        server.send_message(message)
