#!/usr/bin/env python3
"""
Extract clean text content from Telegram HTML exports.
Includes date separators between posts.
"""

from pathlib import Path
import re
from html import unescape
from datetime import datetime
from collections import defaultdict


def extract_telegram_with_dates(html: str) -> str:
    """Extract post text content with date separators from timestamps."""
    posts_with_dates = []
    
    # Find all text divs with their positions
    text_pattern = r'<div class="text"[^>]*>(.*?)</div>'
    
    for text_match in re.finditer(text_pattern, html, re.DOTALL):
        text_content = text_match.group(1)
        text_pos = text_match.start()
        
        # Look backwards from text position to find nearest timestamp
        # Timestamps are typically within 2000 chars before the text div
        lookback = html[max(0, text_pos - 2000):text_pos]
        timestamp_match = re.search(r'title="(\d{2})\.(\d{2})\.(\d{4})\s+\d{2}:\d{2}', lookback)
        
        # Parse date
        if timestamp_match:
            day, month, year = timestamp_match.groups()
            try:
                date_obj = datetime(int(year), int(month), int(day))
                # Convert month to Russian format
                months_ru = ['', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                           'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
                date_key = f'{int(day)} {months_ru[int(month)]} {year}'
                sort_key = date_obj
            except:
                date_key = None
                sort_key = None
        else:
            date_key = None
            sort_key = None
        
        # Clean HTML
        clean = re.sub(r'<a[^>]*>', '', text_content)
        clean = re.sub(r'</a>', '', clean)
        clean = re.sub(r'<br\s*/?>', '\n', clean)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        
        # Decode entities
        clean = unescape(clean)
        
        # Normalize whitespace
        clean = re.sub(r'[ \t]+', ' ', clean)
        clean = re.sub(r' *\n *', '\n', clean)
        clean = re.sub(r'\n{3,}', '\n\n', clean)
        clean = clean.strip()
        
        if clean and len(clean) > 10:
            posts_with_dates.append((sort_key, date_key, clean))
    
    # Sort chronologically
    posts_with_dates.sort(key=lambda x: x[0] if x[0] else datetime.max)
    
    # Build output grouped by date
    output = []
    current_date = None
    
    for sort_key, date_key, text in posts_with_dates:
        if date_key != current_date:
            current_date = date_key
            if date_key:
                output.append(f'\n## {date_key}\n')
            else:
                output.append('\n## (Без даты)\n')
        output.append(f'{text}\n')
    
    return '\n'.join(output)


def convert_telegram(src: Path, dst: Path, title: str, desc: str):
    """Convert Telegram HTML export to clean markdown."""
    print(f'Reading {src.name}...')
    with open(src, encoding='utf-8') as f:
        html = f.read()
    
    print(f'Extracting posts...')
    text = extract_telegram_with_dates(html)
    
    print(f'Writing {dst.name}...')
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(f'# {title}\n\n')
        f.write(f'> {desc}\n\n')
        f.write('---\n')
        f.write(text)


FILES = [
    ('ob avarskom.html', 'ob_avarskom.md',
     'Об аварском языке',
     'Образовательный канал об аварском языке: грамматика, примеры, объяснения'),
    ('hakikat.html', 'hakikat.md',
     'ХӀакъикъат',
     'Корпус современных аварских текстов из газеты ХӀакъикъат'),
    ('hitinal-avaraze.html', 'hitinal_avaraze.md',
     'ГьитIинал аваразе',
     'Корпус аварских текстов из канала ХӀинал аваразул'),
    ('avar_mats.html', 'avar_mats.md',
     'Авар мацӀ | Аварский язык',
     'Корпус текстов из Telegram-канала Авар мацӀ (уроки, грамматика, лексика)'),
]


if __name__ == '__main__':
    base = Path(__file__).parent
    for s, d, t, desc in FILES:
        sp = base / 'sources' / s
        dp = base / 'docs' / d
        if sp.exists():
            print(f'\n=== {s} ===')
            convert_telegram(sp, dp, t, desc)
            sz = dp.stat().st_size // 1024
            lines = sum(1 for _ in open(dp, encoding='utf-8'))
            print(f'✓ {d} ({sz} KB, {lines:,} lines)')
        else:
            print(f'✗ {s} not found')
