#!/usr/bin/env python3
"""
Extract text from Avar language PDFs to Markdown files for Cursor indexing.

Usage:
    pip install pdfplumber
    python extract_pdfs.py
"""

import pdfplumber
from pathlib import Path

# PDF files to extract (source_name, output_name, description)
PDFS = [
    ("Modern Avar Language.pdf", "modern_avar_language.md", 
     "Scientific description of Avar language grammar and phonetics"),
    ("Avar Language Guide.pdf", "avar_language_guide.md",
     "Russian self-learning guide to Avar language"),
    ("Russian Avar Dictionary.pdf", "russian_avar_dictionary.md",
     "Comprehensive Russian-Avar dictionary"),
]

def extract_pdf(pdf_path: Path, output_path: Path, description: str) -> int:
    """Extract text from PDF and save as Markdown. Returns page count."""
    pages_extracted = 0
    
    with pdfplumber.open(pdf_path) as pdf:
        with open(output_path, "w", encoding="utf-8") as out:
            # Write header with metadata
            title = pdf_path.stem.replace("_", " ")
            out.write(f"# {title}\n\n")
            out.write(f"> {description}\n\n")
            out.write(f"*Source: {pdf_path.name}*\n\n")
            out.write("---\n\n")
            
            total_pages = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    # Clean up common PDF artifacts
                    text = text.strip()
                    out.write(f"## Page {i + 1}\n\n")
                    out.write(f"{text}\n\n")
                    pages_extracted += 1
                
                # Progress indicator
                if (i + 1) % 50 == 0:
                    print(f"  ... processed {i + 1}/{total_pages} pages")
    
    return pages_extracted


def main():
    base_dir = Path(__file__).parent
    sources_dir = base_dir / "sources"
    docs_dir = base_dir / "docs"
    
    # Ensure directories exist
    docs_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("Avar Language PDF Extraction")
    print("=" * 60)
    
    for pdf_name, md_name, description in PDFS:
        # Check both locations (root and sources/)
        pdf_path = sources_dir / pdf_name
        if not pdf_path.exists():
            pdf_path = base_dir / pdf_name
        
        if not pdf_path.exists():
            print(f"\n⚠ Skipping {pdf_name} (not found)")
            continue
        
        output_path = docs_dir / md_name
        print(f"\n📄 Extracting: {pdf_name}")
        print(f"   → {output_path}")
        
        try:
            pages = extract_pdf(pdf_path, output_path, description)
            size_kb = output_path.stat().st_size / 1024
            print(f"   ✓ Done: {pages} pages, {size_kb:.1f} KB")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Extraction complete!")
    print("Cursor will now index the docs/ folder automatically.")
    print("=" * 60)


if __name__ == "__main__":
    main()
