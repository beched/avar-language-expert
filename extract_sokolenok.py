#!/usr/bin/env python3
"""
Extract text from Avarskiy Sokolenok children's magazine PDF.

Handles 2-column layout:
- Crops out header/footer areas (page numbers, "1/2024")
- Splits each page at the midpoint into left and right columns
- Extracts left column first, then right column
- Rejoins words split with hyphens at line endings and across columns

Usage:
    python extract_sokolenok.py
"""

import re
from pathlib import Path
import pdfplumber


PDF_NAME = "avarskiy-sokolenok-1-2024.pdf"
OUTPUT_NAME = "avarskiy_sokolenok_2024.md"

# Threshold: if one side has < this fraction of chars, treat as single-column
SINGLE_COL_THRESHOLD = 0.10

# Footer starts at this 'top' coordinate (page numbers, issue number)
FOOTER_TOP = 760


def is_two_column(page) -> bool:
    """Detect whether a page has 2-column layout based on character positions."""
    chars = [c for c in page.chars if c['top'] < FOOTER_TOP]
    if not chars:
        return False
    mid = page.width / 2
    left_chars = sum(1 for c in chars if c['x0'] < mid)
    right_chars = sum(1 for c in chars if c['x0'] >= mid)
    total = left_chars + right_chars
    if total == 0:
        return False
    return (left_chars / total) > SINGLE_COL_THRESHOLD and (right_chars / total) > SINGLE_COL_THRESHOLD


def rejoin_hyphens(text: str) -> str:
    """Rejoin words split with hyphens at line endings.

    E.g. 'бихьа-\\nна,' -> 'бихьана,'

    Only rejoins when the hyphen is at end of line and next line starts
    with a lowercase Cyrillic letter (to preserve real hyphens like "Рукъ-бакI").
    """
    text = re.sub(r'-\n([а-яёіїєґ])', r'\1', text)
    return text


def rejoin_columns(left_text: str, right_text: str) -> str:
    """Join left and right column text, handling hyphenation across columns.

    If left column ends with 'word-' and right column starts with lowercase,
    join them as one word. Handles the case where a title/author line sits
    between the hyphenated parts.
    """
    left_text = left_text.rstrip()
    right_text = right_text.lstrip()

    if not left_text or not right_text:
        return (left_text + "\n\n" + right_text).strip()

    # Check if left column ends mid-word (hyphen at end)
    if left_text.endswith('-'):
        lines_right = right_text.split('\n')
        # Try to find the continuation line (starts with lowercase)
        for idx, line in enumerate(lines_right):
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r'[а-яёіїєґ]', stripped):
                # This is the continuation. Everything before it is a header/title.
                header_lines = lines_right[:idx]
                continuation = stripped
                rest_lines = lines_right[idx + 1:]
                # Build result: header (if any), then joined word + rest
                parts = []
                header = '\n'.join(l for l in header_lines if l.strip())
                joined = left_text[:-1] + continuation
                if header:
                    parts.append(header)
                if rest_lines:
                    parts.append(joined + '\n' + '\n'.join(rest_lines))
                else:
                    parts.append(joined)
                return '\n\n'.join(parts)
            else:
                # First non-empty line starts with uppercase/title — could be
                # a header between the broken word. Keep looking.
                continue

    return left_text + "\n\n" + right_text


def extract_page(page) -> str:
    """Extract text from a single page, handling 2-column layout."""
    # Crop out footer area
    content_area = page.crop((0, 0, page.width, FOOTER_TOP))

    if is_two_column(page):
        mid = page.width / 2
        left_text = content_area.crop((0, 0, mid + 2, FOOTER_TOP)).extract_text() or ""
        right_text = content_area.crop((mid - 2, 0, page.width, FOOTER_TOP)).extract_text() or ""
        # Rejoin hyphens within each column
        left_text = rejoin_hyphens(left_text.strip())
        right_text = rejoin_hyphens(right_text.strip())
        # Combine columns, handling cross-column hyphenation
        return rejoin_columns(left_text, right_text)
    else:
        text = content_area.extract_text() or ""
        return rejoin_hyphens(text.strip())


def main():
    base_dir = Path(__file__).parent
    pdf_path = base_dir / "sources" / PDF_NAME
    output_path = base_dir / "docs" / OUTPUT_NAME

    if not pdf_path.exists():
        print(f"ERROR: {pdf_path} not found")
        return

    print(f"Extracting: {pdf_path.name}")
    print(f"Output: {output_path}")

    with pdfplumber.open(pdf_path) as pdf:
        with open(output_path, "w", encoding="utf-8") as out:
            out.write("# Аварский Соколёнок (1/2024, январь-февраль)\n\n")
            out.write("> Иллюстрированный детский журнал на аварском языке\n\n")
            out.write(f"*Source: {PDF_NAME}*\n\n")
            out.write("---\n\n")

            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = extract_page(page)
                if text:
                    two_col = is_two_column(page)
                    layout = "2-col" if two_col else "1-col"
                    print(f"  Page {i+1:2d}/{total} [{layout}]: {len(text):5d} chars")
                    out.write(f"## Страница {i + 1}\n\n")
                    out.write(f"{text}\n\n")
                else:
                    print(f"  Page {i+1:2d}/{total}: empty")

    size_kb = output_path.stat().st_size / 1024
    lines = sum(1 for _ in open(output_path, encoding="utf-8"))
    print(f"\nDone: {size_kb:.1f} KB, {lines} lines")


if __name__ == "__main__":
    main()
