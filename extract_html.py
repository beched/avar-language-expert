#!/usr/bin/env python3
"""
Simple HTML to Markdown converter using regex.
"""

from pathlib import Path
import re


def html_to_md(html: str) -> str:
    # Remove invisible font spacers first
    html = re.sub(r'<font[^>]*color="#FFFFFF"[^>]*>[^<]*</font>', '', html, flags=re.I)
    
    # Tables: extract and convert separately
    tables = []
    def save_table(m):
        tables.append(convert_table(m.group(0)))
        return f'__TABLE_{len(tables)-1}__'
    html = re.sub(r'<table[^>]*>.*?</table>', save_table, html, flags=re.DOTALL | re.I)
    
    # Convert inline formatting
    html = re.sub(r'<b>(.*?)</b>', r'**\1**', html, flags=re.DOTALL | re.I)
    html = re.sub(r'<strong>(.*?)</strong>', r'**\1**', html, flags=re.DOTALL | re.I)
    html = re.sub(r'<i>(.*?)</i>', r'*\1*', html, flags=re.DOTALL | re.I)
    html = re.sub(r'<em>(.*?)</em>', r'*\1*', html, flags=re.DOTALL | re.I)
    
    # Convert centered paragraphs to headers
    def center_to_header(m):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text.isupper():
            return f'\n\n## {text}\n\n'
        return f'\n\n{text}\n\n'
    html = re.sub(r'<p[^>]*align="center"[^>]*>(.*?)</p>', center_to_header, html, flags=re.DOTALL | re.I)
    
    # Convert paragraphs
    html = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\n\1\n\n', html, flags=re.DOTALL | re.I)
    
    # Convert dd elements
    html = re.sub(r'<dd[^>]*>', '\n\n', html, flags=re.I)
    
    # Convert hr
    html = re.sub(r'<hr[^>]*/?>', '\n\n---\n\n', html, flags=re.I)
    
    # Remove all remaining tags
    html = re.sub(r'<[^>]+>', '', html)
    
    # Restore tables
    for i, t in enumerate(tables):
        html = html.replace(f'__TABLE_{i}__', f'\n\n{t}\n\n')
    
    # Decode entities
    html = html.replace('&nbsp;', ' ')
    html = html.replace('&quot;', '"')
    html = html.replace('&lt;', '<')
    html = html.replace('&gt;', '>')
    html = html.replace('&amp;', '&')
    
    # Normalize whitespace
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r' *\n *', '\n', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    
    return html.strip()


def convert_table(table_html: str) -> str:
    """Convert HTML table to markdown."""
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.I)
    if not rows:
        return ''
    
    lines = []
    for row in rows:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL | re.I)
        texts = []
        for cell in cells:
            # Remove tags, get text
            t = re.sub(r'<[^>]+>', '', cell).strip()
            # Skip invisible 'о' spacers
            if t == 'о':
                t = ''
            texts.append(t)
        if texts:
            lines.append('| ' + ' | '.join(texts) + ' |')
    
    if len(lines) > 1:
        n = lines[0].count('|') - 1
        lines.insert(1, '|' + '---|' * n)
    
    return '\n'.join(lines)


def convert(src: Path, dst: Path, title: str, desc: str):
    with open(src, encoding='utf-8') as f:
        html = f.read()
    
    md = html_to_md(html)
    
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(f'# {title}\n\n')
        f.write(f'> {desc}\n\n')
        f.write('---\n\n')
        f.write(md)


FILES = [
    ('avar-language.html', 'avar_grammar_1967.md',
     'Аварский язык (Мадиева Г.И., 1967)',
     'Языки народов СССР. Т. 4. М., 1967. С. 255-271'),
    ('avar-language-2.html', 'avar_grammar_1999.md',
     'Аварский язык (Алексеев М.Е., 1999)',
     'Языки мира: Кавказские языки. М., 1999. С. 203-216'),
    ('ob avarskom.html', 'ob_avarskom.md',
     'Об аварском языке (Telegram канал)',
     'Образовательный канал об аварском языке: грамматика, примеры, объяснения'),
    ('hakikat.html', 'hakikat.md',
     'ХӀакъикъат — аварская газета',
     'Корпус современных аварских текстов из газеты ХӀакъикъат'),
]


if __name__ == '__main__':
    base = Path(__file__).parent
    for s, d, t, desc in FILES:
        sp = base / 'sources' / s
        dp = base / 'docs' / d
        if sp.exists():
            convert(sp, dp, t, desc)
            sz = dp.stat().st_size // 1024
            print(f'✓ {d} ({sz} KB)')
