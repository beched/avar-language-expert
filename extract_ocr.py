#!/usr/bin/env python3
"""
Extract text from scanned PDFs using OCR (Tesseract).

Usage:
    pip install pdf2image pytesseract
    python extract_ocr.py
    
Requires: tesseract with Russian language pack
    brew install tesseract tesseract-lang
"""

import pytesseract
from pdf2image import convert_from_path
from pathlib import Path

# Configuration
PDF_FILE = "sources/Avar Language Guide.pdf"
OUTPUT_FILE = "docs/avar_language_guide.md"
DESCRIPTION = "Russian self-learning guide to Avar language"
LANG = "rus+eng"  # Russian + English for mixed content
DPI = 200  # Balance between quality and speed


def extract_with_ocr(pdf_path: Path, output_path: Path, description: str) -> int:
    """Extract text from scanned PDF using OCR."""
    print(f"Converting PDF to images (DPI={DPI})...")
    
    # Convert PDF pages to images
    images = convert_from_path(pdf_path, dpi=DPI)
    total_pages = len(images)
    print(f"Found {total_pages} pages")
    
    pages_extracted = 0
    
    with open(output_path, "w", encoding="utf-8") as out:
        # Write header
        title = pdf_path.stem.replace("_", " ")
        out.write(f"# {title}\n\n")
        out.write(f"> {description}\n\n")
        out.write(f"*Source: {pdf_path.name} (OCR extracted)*\n\n")
        out.write("---\n\n")
        
        for i, image in enumerate(images):
            print(f"  OCR page {i + 1}/{total_pages}...", end="\r")
            
            # Run OCR
            text = pytesseract.image_to_string(image, lang=LANG)
            text = text.strip()
            
            if text:
                out.write(f"## Page {i + 1}\n\n")
                out.write(f"{text}\n\n")
                pages_extracted += 1
        
        print()  # New line after progress
    
    return pages_extracted


def main():
    base_dir = Path(__file__).parent
    pdf_path = base_dir / PDF_FILE
    output_path = base_dir / OUTPUT_FILE
    
    if not pdf_path.exists():
        print(f"Error: {pdf_path} not found")
        return
    
    print("=" * 60)
    print("OCR Extraction: Avar Language Guide")
    print("=" * 60)
    print(f"\n📄 Processing: {pdf_path.name}")
    print(f"   → {output_path}")
    
    try:
        pages = extract_with_ocr(pdf_path, output_path, DESCRIPTION)
        size_kb = output_path.stat().st_size / 1024
        print(f"\n   ✓ Done: {pages} pages extracted, {size_kb:.1f} KB")
    except Exception as e:
        print(f"\n   ✗ Error: {e}")
        raise
    
    print("\n" + "=" * 60)
    print("OCR extraction complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
