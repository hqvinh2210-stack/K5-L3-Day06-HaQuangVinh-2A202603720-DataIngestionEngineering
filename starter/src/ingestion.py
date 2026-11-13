"""Read and normalize source data while preserving page traceability."""

import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while preserving paragraphs."""
    text = unicodedata.normalize("NFC", text)

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\u00a0", " ")

    lines = []

    for line in text.splitlines():
        normalized_line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(normalized_line)

    normalized_text = "\n".join(lines)

    normalized_text = re.sub(
        r"\n{3,}",
        "\n\n",
        normalized_text,
    )

    return normalized_text.strip()


def load_ocr_json(
    path: Path,
    document_id: str,
    source: str,
) -> list[DocumentPage]:
    """Load ChatGPT OCR JSON into one DocumentPage per physical page."""
    data = json.loads(path.read_text(encoding="utf-8"))

    raw_pages = data.get("pages")
    declared_total = data.get("total_pages")

    if not isinstance(raw_pages, list):
        raise ValueError("OCR JSON must contain a pages list")

    if declared_total != len(raw_pages):
        raise ValueError(
            "Declared page count does not match pages list: "
            f"{declared_total} != {len(raw_pages)}"
        )

    pages: list[DocumentPage] = []
    seen_pages: set[int] = set()
    current_section = "preamble"

    for raw_page in raw_pages:
        page_number = raw_page.get("page")
        raw_text = raw_page.get("text")

        if not isinstance(page_number, int):
            raise ValueError(
                f"Invalid page number: {page_number!r}"
            )

        if page_number in seen_pages:
            raise ValueError(
                f"Duplicate page number: {page_number}"
            )

        if not isinstance(raw_text, str):
            raise ValueError(
                f"Page {page_number} has invalid text"
            )

        text = normalize_text(raw_text)

        if not text:
            raise ValueError(
                f"Page {page_number} is empty after normalization"
            )

        section_match = re.search(
            r"(?im)^\s*(?:Chương\s+([IVXLCDM]+)|(Phụ\s+lục))\b",
            text,
        )
        if section_match:
            current_section = (
                "phu_luc"
                if section_match.group(2)
                else f"chuong_{section_match.group(1).lower()}"
            )

        seen_pages.add(page_number)

        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=page_number,
                text=text,
                metadata={
                    "printed_page": raw_page.get("printed_page"),
                    "document_type": "nghi_dinh",
                    "year": 2023,
                    "language": "vi",
                    "ocr_source": "chatgpt",
                    "section": current_section,
                },
            )
        )

    pages.sort(key=lambda item: item.page)

    expected_pages = set(range(1, declared_total + 1))
    missing_pages = expected_pages - seen_pages

    if missing_pages:
        raise ValueError(
            f"Missing pages: {sorted(missing_pages)}"
        )

    return pages


def load_pdf(
    path: Path,
    document_id: str,
    source: str,
) -> list[DocumentPage]:
    """Load a PDF with a text layer while preserving physical page numbers.

    The lab corpus is scanned and therefore uses ``load_ocr_json``. This
    loader remains useful for reproducible experiments with text PDFs and
    fails clearly instead of silently accepting empty scanned pages.
    """
    reader = PdfReader(path)
    pages: list[DocumentPage] = []
    current_section = "preamble"

    for page_number, pdf_page in enumerate(reader.pages, start=1):
        text = normalize_text(pdf_page.extract_text() or "")
        if not text:
            raise ValueError(
                f"PDF page {page_number} has no text layer; run OCR first"
            )

        section_match = re.search(
            r"(?im)^\s*(?:Chương\s+([IVXLCDM]+)|(Phụ\s+lục))\b",
            text,
        )
        if section_match:
            current_section = (
                "phu_luc"
                if section_match.group(2)
                else f"chuong_{section_match.group(1).lower()}"
            )

        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=page_number,
                text=text,
                metadata={
                    "printed_page": None,
                    "document_type": "pdf",
                    "language": "und",
                    "ocr_source": None,
                    "section": current_section,
                },
            )
        )

    return pages
