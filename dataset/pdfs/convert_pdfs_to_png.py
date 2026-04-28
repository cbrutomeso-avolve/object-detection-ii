from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image


MAX_DIMENSION = 3072


def parse_pages(spec: str | None, total_pages: int) -> list[int]:
    """Parse a 1-based page specification like '1,3-5'."""
    if not spec:
        return list(range(total_pages))

    pages: set[int] = set()
    parts = [part.strip() for part in spec.split(",") if part.strip()]

    for part in parts:
        if "-" in part:
            start_text, end_text = [value.strip() for value in part.split("-", 1)]
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError(f"Invalid page range '{part}': start must be <= end.")
            for page_number in range(start, end + 1):
                if not 1 <= page_number <= total_pages:
                    raise ValueError(
                        f"Page {page_number} is out of range for a PDF with {total_pages} pages."
                    )
                pages.add(page_number - 1)
        else:
            page_number = int(part)
            if not 1 <= page_number <= total_pages:
                raise ValueError(
                    f"Page {page_number} is out of range for a PDF with {total_pages} pages."
                )
            pages.add(page_number - 1)

    return sorted(pages)


def sanitize_filename(name: str) -> str:
    """Create a filesystem-friendly stem for the output image."""
    cleaned = re.sub(r"[^\w\-\.]+", "_", name.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "document"


def render_page(page: fitz.Page, dpi: int) -> Image.Image:
    pixmap = page.get_pixmap(dpi=dpi, alpha=False)
    mode = "RGB" if pixmap.n < 4 else "RGBA"
    return Image.frombytes(mode, [pixmap.width, pixmap.height], pixmap.samples)


def resize_if_needed(image: Image.Image) -> Image.Image:
    width, height = image.size
    scale = min(MAX_DIMENSION / width, MAX_DIMENSION / height, 1.0)

    if scale == 1.0:
        return image

    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def convert_pdf(pdf_path: Path, output_dir: Path, dpi: int, pages_spec: str | None) -> int:
    converted = 0
    output_dir.mkdir(parents=True, exist_ok=True)

    with fitz.open(pdf_path) as document:
        page_indexes = parse_pages(pages_spec, document.page_count)
        safe_stem = sanitize_filename(pdf_path.stem)

        for page_index in page_indexes:
            page = document.load_page(page_index)
            image = resize_if_needed(render_page(page, dpi))
            output_path = output_dir / f"{safe_stem}_page_{page_index + 1:03d}.png"
            image.save(output_path, format="PNG")
            converted += 1
            print(f"[OK] {pdf_path.name} page {page_index + 1} -> {output_path.name}")

    return converted


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert all PDFs in this folder to PNG using a target DPI, "
            "keeping aspect ratio and capping images at 3072x3072."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory containing PDF files. Defaults to this script's folder.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "images",
        help="Directory where PNG files will be written. Defaults to ../images.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Rendering DPI before optional downscaling. Defaults to 200.",
    )
    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help="1-based pages to export, e.g. '1', '1,3,5', or '2-4'. Defaults to all pages.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.dpi <= 0:
        parser.error("--dpi must be a positive integer.")

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()

    if not input_dir.exists():
        parser.error(f"Input directory does not exist: {input_dir}")

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {input_dir}")
        return 0

    total_converted = 0

    for pdf_path in pdf_files:
        try:
            total_converted += convert_pdf(pdf_path, output_dir, args.dpi, args.pages)
        except Exception as exc:
            print(f"[ERROR] Failed to convert {pdf_path.name}: {exc}", file=sys.stderr)

    print(f"Finished. Exported {total_converted} page(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
