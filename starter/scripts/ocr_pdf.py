"""OCR a scanned PDF into traceable UTF-8 text files, one per page."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import easyocr
import numpy as np
import pypdfium2 as pdfium


DEFAULT_PDF = Path(__file__).resolve().parents[2] / "13nd.signed.pdf"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "ocr_text"
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[1] / ".cache" / "easyocr"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OCR a scanned Vietnamese PDF with EasyOCR."
    )
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int)
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Use a CUDA GPU. The default is CPU mode.",
    )
    return parser.parse_args()


def reading_order(item: tuple[Any, str, float]) -> tuple[float, float]:
    box = item[0]
    top = min(float(point[1]) for point in box)
    left = min(float(point[0]) for point in box)
    return top, left


def ocr_page(
    reader: easyocr.Reader,
    page: pdfium.PdfPage,
    dpi: int,
) -> tuple[str, int, float]:
    bitmap = page.render(scale=dpi / 72)
    try:
        image = bitmap.to_pil().convert("RGB")
        results = reader.readtext(
            np.asarray(image),
            detail=1,
            paragraph=False,
            decoder="greedy",
        )
    finally:
        bitmap.close()

    results.sort(key=reading_order)
    lines: list[str] = []
    confidences: list[float] = []

    for _, raw_text, confidence in results:
        text = " ".join(raw_text.split())
        if not text:
            continue
        lines.append(text)
        confidences.append(float(confidence))

    average_confidence = (
        sum(confidences) / len(confidences) if confidences else 0.0
    )
    return "\n".join(lines), len(lines), average_confidence


def main() -> None:
    args = parse_args()
    pdf_path = args.pdf.resolve()
    output_dir = args.output_dir.resolve()

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if args.dpi < 72:
        raise ValueError("DPI must be at least 72")
    if args.start_page < 1:
        raise ValueError("start-page must be at least 1")

    output_dir.mkdir(parents=True, exist_ok=True)
    DEFAULT_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading EasyOCR models for Vietnamese and English...")
    reader = easyocr.Reader(
        ["vi", "en"],
        gpu=args.gpu,
        model_storage_directory=str(DEFAULT_MODEL_DIR),
        verbose=False,
    )
    pdf = pdfium.PdfDocument(pdf_path)

    try:
        page_count = len(pdf)
        end_page = args.end_page or page_count
        if end_page > page_count:
            raise ValueError(
                f"end-page {end_page} exceeds PDF page count {page_count}"
            )
        if args.start_page > end_page:
            raise ValueError("start-page must not exceed end-page")

        manifest: dict[str, Any] = {
            "source": str(pdf_path),
            "engine": "EasyOCR",
            "languages": ["vi", "en"],
            "dpi": args.dpi,
            "gpu": args.gpu,
            "pdf_page_count": page_count,
            "processed_page_range": [args.start_page, end_page],
            "pages": [],
        }

        for page_number in range(args.start_page, end_page + 1):
            page = pdf[page_number - 1]
            try:
                text, line_count, average_confidence = ocr_page(
                    reader, page, args.dpi
                )
            finally:
                page.close()

            output_path = output_dir / f"page-{page_number:02d}.txt"
            output_path.write_text(text + ("\n" if text else ""), encoding="utf-8")

            page_stats = {
                "page": page_number,
                "file": output_path.name,
                "characters": len(text),
                "lines": line_count,
                "average_confidence": round(average_confidence, 4),
            }
            manifest["pages"].append(page_stats)
            print(
                f"Page {page_number:02d}/{end_page:02d}: "
                f"{len(text):5d} chars, {line_count:3d} lines, "
                f"confidence {average_confidence:.3f}",
                flush=True,
            )

        manifest_path = output_dir / "ocr_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"OCR manifest: {manifest_path}")
        print("OCR completed")
    finally:
        pdf.close()


if __name__ == "__main__":
    main()
