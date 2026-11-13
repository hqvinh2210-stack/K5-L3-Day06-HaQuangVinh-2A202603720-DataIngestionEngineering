"""Fixed-size and structure-aware chunking."""
import re

from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split text into overlapping character windows."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")

    chunks: list[Chunk] = []
    step = size - overlap
    for index, start in enumerate(range(0, len(page.text), step)):
        end = min(start + size, len(page.text))
        text = page.text[start:end].strip()
        if text:
            chunks.append(
                Chunk(
                    chunk_id=(
                        f"{page.document_id}:p{page.page:03d}:"
                        f"fixed:{index:03d}"
                    ),
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=text,
                    metadata={
                        **page.metadata,
                        "chunk_method": "fixed",
                        "chunk_index": index,
                        "char_start": start,
                        "char_end": end,
                        "size": size,
                        "overlap": overlap,
                    },
                )
            )
        if end >= len(page.text):
            break
    return chunks


def _split_oversized(text: str, max_size: int) -> list[str]:
    pieces: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_size:
        cuts = [
            remaining.rfind(separator, 0, max_size + 1)
            for separator in ("\n", ". ", "; ", ", ", " ")
        ]
        cut = max(cuts)
        cut = max_size if cut < max_size // 2 else cut + 1
        piece = remaining[:cut].strip()
        if piece:
            pieces.append(piece)
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Group paragraphs without exceeding max_size."""
    if max_size <= 0:
        raise ValueError("max_size must be positive")

    pieces: list[str] = []
    for paragraph in re.split(r"\n\s*\n", page.text):
        paragraph = paragraph.strip()
        if paragraph:
            pieces.extend(_split_oversized(paragraph, max_size))

    grouped: list[str] = []
    current = ""
    for piece in pieces:
        candidate = piece if not current else f"{current}\n\n{piece}"
        if len(candidate) <= max_size:
            current = candidate
        else:
            if current:
                grouped.append(current)
            current = piece
    if current:
        grouped.append(current)

    return [
        Chunk(
            chunk_id=(
                f"{page.document_id}:p{page.page:03d}:"
                f"paragraph:{index:03d}"
            ),
            document_id=page.document_id,
            source=page.source,
            page=page.page,
            text=text,
            metadata={
                **page.metadata,
                "chunk_method": "paragraph",
                "chunk_index": index,
                "max_size": max_size,
            },
        )
        for index, text in enumerate(grouped)
    ]
