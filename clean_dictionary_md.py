#!/usr/bin/env python3
"""
Tidy the extracted Russian-Avar dictionary markdown.

`extract_pdf_inspector.mjs` recovers the two-column layout correctly, but the
PDF's own typesetting leaves artifacts that survive extraction. This pass fixes
them:

1. **Stress marks.** The book sets stress as a separately positioned glyph, so
   it extracts as a spacing acute (U+00B4) or a Greek tonos (U+0384) placed
   AFTER the vowel: `получи΄ть`, `АВТОПОИ´ ЛКА`. Both become a combining acute
   (U+0301) on the vowel, which is what makes the word searchable.
2. **Split words.** That glyph often carries a stray space, and line wrapping
   leaves `бери-\\n\\nчаб` and `гIада- дисеб`. Both are rejoined.
3. **Entries per line.** Headwords run inline, so `**БЕСЦÉЛЬНЫЙ,**` starts
   mid-paragraph. Each entry is put on its own line.
4. **Page furniture.** `## Page N` headings are dropped: entries routinely
   straddle a page break, and the headings cut them in half.

Usage:
    python clean_dictionary_md.py docs/russian_avar_dictionary.md
    python clean_dictionary_md.py FILE --dry-run
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import unicodedata
from collections import Counter
from pathlib import Path

DB = Path(__file__).with_name("avar.db")

COMBINING_ACUTE = "́"
VOWELS = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"

# Glyphs this PDF uses for a stress mark, all of which follow their vowel.
STRESS_GLYPHS = "´΄"

# The bigger stress artifact: a stressed Cyrillic vowel extracts as the
# LOOK-ALIKE LATIN letter carrying a precomposed acute -- `á` for а́, `É` for
# Е́. Nearly 60k of them, and every word containing one is unsearchable,
# because `БЕСЦВÉТНЫЙ` shares no substring with a Cyrillic query. The book has
# no Latin text, so the mapping is unambiguous.
LATIN_STRESSED = {
    "á": "а", "é": "е", "í": "и", "ó": "о", "ú": "у", "ý": "у",
    "Á": "А", "É": "Е", "Í": "И", "Ó": "О", "Ú": "У", "Ý": "У",
}

CYR_LETTER = "а-яёА-ЯЁIӀӏ"

# A stressed vowel plus the rest of its word, captured directly so the join
# candidate can be built without slicing a 5 MB string per match.
STRESSED_WORD = re.compile(
    f"([{CYR_LETTER}]*[{VOWELS}]{COMBINING_ACUTE}) ([а-яёА-ЯЁ]+)")

# Wrap artifact: letter, hyphen, whitespace, lowercase letter. A genuine
# compound has no space after the hyphen ("ракI-ракIалъ"); an inflection marker
# or dash has a space BEFORE it ("-ая, -ое"), so neither matches here.
WRAP = re.compile(f"([{CYR_LETTER}])-\\s+([а-яё])")

# A headword: a bold run written entirely in capitals.
HEADWORD = re.compile(
    f"\\*\\*([А-ЯЁ][А-ЯЁIӀ/\\-\\s,.{COMBINING_ACUTE}̀]{{2,}}?)\\*\\*")

# A gap inside an all-capitals (headword) run.
CAPS_GAP = re.compile(
    f"([А-ЯЁ]{{2,}}[{VOWELS.upper()}]{COMBINING_ACUTE}) ([А-ЯЁ]+)")

PAGE_HEADING = re.compile(r"(?m)^## Page \d+\s*$")


def strip_marks(text: str) -> str:
    d = unicodedata.normalize("NFD", text)
    return unicodedata.normalize(
        "NFC", "".join(c for c in d if c not in "́̀"))


def load_lexicon() -> set[str]:
    """Wordforms used only to confirm that closing a gap yields a real word."""
    con = sqlite3.connect(DB)
    words: set[str] = set()

    def add(text: str) -> None:
        for w in re.findall(r"[^\W_]+", text):
            words.add(strip_marks(w).lower())

    for (form,) in con.execute("SELECT form_norm FROM forms"):
        if form:
            add(form)
    for table, col in (("ru_index", "ru_term"), ("senses", "ru_text"),
                       ("examples", "ru"), ("examples", "av")):
        q = f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL"
        for (text,) in con.execute(q):
            add(text)
    con.close()
    words.discard("")
    return words


def fix_latin_stressed(text: str) -> tuple[str, int]:
    """Turn precomposed Latin accented vowels into Cyrillic + combining acute."""
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        n += 1
        return LATIN_STRESSED[m.group(0)] + COMBINING_ACUTE

    pattern = re.compile("[" + "".join(LATIN_STRESSED) + "]")
    return pattern.sub(repl, text), n


def fix_stress(text: str) -> tuple[str, int]:
    """Move a trailing stress glyph onto its vowel as a combining acute."""
    pattern = re.compile(f"([{VOWELS}])[{STRESS_GLYPHS}]")
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        n += 1
        return m.group(1) + COMBINING_ACUTE

    # Twice: a few vowels carry two stacked glyphs (`АБАЗИ´´`).
    for _ in range(2):
        text = pattern.sub(repl, text)
    # A stress glyph not sitting on a vowel cannot be placed -- drop it.
    text = re.sub(f"[{STRESS_GLYPHS}]", "", text)
    return text, n


def close_stress_gaps(text: str, lex: set[str]) -> tuple[str, int]:
    """Remove the stray space a stress glyph leaves inside a word.

    Only when the dictionary confirms the joined form. The space is genuine
    often enough (`пошли́ в лес`) that closing it blindly would merge words.
    """
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        joined = m.group(1) + m.group(2)
        if strip_marks(joined).lower() in lex:
            n += 1
            return joined
        return m.group(0)

    text = STRESSED_WORD.sub(repl, text)

    # Headwords are set in capitals and are single words, so a gap between two
    # capitalised fragments is the glyph artifact, not a word boundary. This
    # catches entries the gloss-derived lexicon does not list (АВТОПОИ́ ЛКА).
    def repl_caps(m: re.Match) -> str:
        nonlocal n
        n += 1
        return m.group(1) + m.group(2)

    text = CAPS_GAP.sub(repl_caps, text)
    return text, n


def rejoin_wraps(text: str) -> tuple[str, int]:
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        n += 1
        return m.group(1) + m.group(2)

    return WRAP.sub(repl, text), n


def split_entries(text: str) -> tuple[str, int]:
    """Put each headword at the start of its own line, comma outside the bold."""
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        head = m.group(1).strip()
        # The comma separates the headword from its inflection endings
        # ("-ая, -ое"), so it carries meaning -- but it belongs outside the
        # bold, not inside it.
        trailing = ""
        while head.endswith((",", ".")):
            trailing = head[-1] + trailing
            head = head[:-1].strip()
        if len(strip_marks(head).replace(" ", "")) < 3:
            return m.group(0)
        n += 1
        return f"\n**{head}**{trailing}"

    return HEADWORD.sub(repl, text), n


def clean(text: str, lex: set[str]) -> tuple[str, Counter]:
    stats: Counter = Counter()
    text = PAGE_HEADING.sub("", text)

    text, stats["latin_vowels_mapped"] = fix_latin_stressed(text)
    text, stats["stress_marks_placed"] = fix_stress(text)
    text, stats["wraps_rejoined"] = rejoin_wraps(text)
    text, stats["stress_gaps_closed"] = close_stress_gaps(text, lex)
    text, stats["entries_split"] = split_entries(text)

    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip() + "\n", stats


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    original = args.file.read_text(encoding="utf-8")
    lex = load_lexicon()
    cleaned, stats = clean(original, lex)

    before = len(re.findall(f"[{CYR_LETTER}]", original))
    after = len(re.findall(f"[{CYR_LETTER}]", cleaned))
    print(f"lexicon: {len(lex)} forms")
    for key, value in stats.items():
        print(f"  {key:<22} {value}")
    print(f"  cyrillic letters       {before} -> {after} ({after - before:+d})")

    if args.dry_run:
        return 0
    (args.output or args.file).write_text(cleaned, encoding="utf-8")
    print(f"wrote {args.output or args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
