#!/usr/bin/env python3
"""
Extract Avar Wikipedia articles from MediaWiki XML dump.

Usage:
    pip install mwparserfromhell
    python extract_wiki.py
"""

import xml.etree.ElementTree as ET
import re
from pathlib import Path

try:
    import mwparserfromhell
    HAS_MWPARSER = True
except ImportError:
    HAS_MWPARSER = False
    print("Note: Install mwparserfromhell for better wikitext parsing")
    print("      pip install mwparserfromhell\n")


def strip_wikitext_simple(text: str) -> str:
    """Simple wikitext cleanup without mwparserfromhell."""
    # Remove templates {{...}}
    text = re.sub(r'\{\{[^}]+\}\}', '', text)
    # Convert [[link|display]] to display, [[link]] to link
    text = re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', text)
    # Remove external links [url text] -> text
    text = re.sub(r'\[https?://[^\s\]]+\s*([^\]]*)\]', r'\1', text)
    # Remove categories
    text = re.sub(r'\[\[Категория:[^\]]+\]\]', '', text, flags=re.IGNORECASE)
    # Remove files/images
    text = re.sub(r'\[\[(Файл|File|Image):[^\]]+\]\]', '', text, flags=re.IGNORECASE)
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Convert '''bold''' and ''italic''
    text = re.sub(r"'''([^']+)'''", r'\1', text)
    text = re.sub(r"''([^']+)''", r'\1', text)
    # Remove ref tags and their content
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
    text = re.sub(r'<ref[^/]*/>', '', text)
    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def strip_wikitext(text: str) -> str:
    """Strip MediaWiki markup to plain text."""
    if HAS_MWPARSER:
        try:
            parsed = mwparserfromhell.parse(text)
            # Remove templates, tags, etc.
            for template in parsed.filter_templates():
                try:
                    parsed.remove(template)
                except ValueError:
                    pass
            text = parsed.strip_code()
        except Exception:
            text = strip_wikitext_simple(text)
    else:
        text = strip_wikitext_simple(text)
    
    return text.strip()


def extract_wiki(xml_path: Path, output_path: Path) -> tuple[int, int]:
    """Extract articles from MediaWiki XML dump."""
    
    # MediaWiki namespace
    ns = {'mw': 'http://www.mediawiki.org/xml/export-0.11/'}
    
    articles_count = 0
    skipped_count = 0
    
    with open(output_path, 'w', encoding='utf-8') as out:
        out.write("# Avar Wikipedia (av.wikipedia.org)\n\n")
        out.write("> Extracted articles from Avar Wikipedia for language learning.\n\n")
        out.write("---\n\n")
        
        # Parse XML iteratively (memory efficient for large files)
        context = ET.iterparse(xml_path, events=('end',))
        
        for event, elem in context:
            # Look for page elements
            if elem.tag == '{http://www.mediawiki.org/xml/export-0.11/}page':
                # Get namespace (0 = main articles)
                ns_elem = elem.find('mw:ns', ns)
                namespace = int(ns_elem.text) if ns_elem is not None else -1
                
                # Only process main namespace articles
                if namespace != 0:
                    elem.clear()
                    skipped_count += 1
                    continue
                
                # Get title
                title_elem = elem.find('mw:title', ns)
                title = title_elem.text if title_elem is not None else "Untitled"
                
                # Skip redirects
                redirect = elem.find('mw:redirect', ns)
                if redirect is not None:
                    elem.clear()
                    skipped_count += 1
                    continue
                
                # Get latest revision text
                revision = elem.find('mw:revision', ns)
                if revision is not None:
                    text_elem = revision.find('mw:text', ns)
                    if text_elem is not None and text_elem.text:
                        raw_text = text_elem.text
                        
                        # Skip stub articles (too short)
                        if len(raw_text) < 200:
                            elem.clear()
                            skipped_count += 1
                            continue
                        
                        # Skip redirects in text
                        if raw_text.strip().lower().startswith('#'):
                            elem.clear()
                            skipped_count += 1
                            continue
                        
                        # Strip wikitext markup
                        clean_text = strip_wikitext(raw_text)
                        
                        # Skip if too short after cleanup
                        if len(clean_text) < 100:
                            elem.clear()
                            skipped_count += 1
                            continue
                        
                        # Write article
                        out.write(f"## {title}\n\n")
                        out.write(f"{clean_text}\n\n")
                        out.write("---\n\n")
                        
                        articles_count += 1
                        
                        if articles_count % 500 == 0:
                            print(f"  ... extracted {articles_count} articles")
                
                # Clear element to save memory
                elem.clear()
    
    return articles_count, skipped_count


def main():
    base_dir = Path(__file__).parent
    
    # Find the wiki XML file
    xml_files = list(base_dir.glob("avwiki*.xml"))
    if not xml_files:
        print("Error: No avwiki*.xml file found")
        return
    
    xml_path = xml_files[0]
    output_path = base_dir / "docs" / "avar_wikipedia.md"
    
    print("=" * 60)
    print("Avar Wikipedia Extraction")
    print("=" * 60)
    print(f"\n📄 Processing: {xml_path.name}")
    print(f"   → {output_path}")
    
    try:
        articles, skipped = extract_wiki(xml_path, output_path)
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"\n   ✓ Done: {articles} articles extracted ({skipped} skipped)")
        print(f"   ✓ Output size: {size_mb:.1f} MB")
    except Exception as e:
        print(f"\n   ✗ Error: {e}")
        raise
    
    print("\n" + "=" * 60)
    print("Wikipedia extraction complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
