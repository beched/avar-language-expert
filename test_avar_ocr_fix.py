#!/usr/bin/env python3
"""
Regression tests for the OCR post-correction rules.

    python test_avar_ocr_fix.py

Three properties are guarded, in order of how expensive a violation is:

1. Reported misreads stay fixed.
2. Russian prose is never touched. The Russian wordlist is gloss-derived and
   under-covers badly, so a Russian word missing from it must be left alone
   rather than "corrected" into an Avar lookalike.
3. Well-formed Avar words are never rewritten into *other* well-formed Avar
   words. This is the dangerous failure: `ункъго` (four) -> `анкьго` (seven)
   produces a valid word, so nothing downstream can detect it.
"""

import sys

from avar_ocr_fix import DB, Lexicon, fix

# Misreads reported against docs/avar_language_guide.md, with the reading the
# book actually has.
MISREADS = [
    ("8 000 — микъазарго", "микьазарго"),   # ь/ъ confusion
    ("са4т — час", "сагӏат"),               # digit for the гӏ ligature
    ("2Геч — яблоко", "гӏеч"),              # 2Г for гӏ
    ("3 000 — льдбазарго", "лъабазарго"),   # ь->ъ and д->а together
    ("12 — анила к@го", "кӏиго"),           # @ for ӏи
    ("11 — ани/Гила цо", "анцӏила"),        # и/Г for цӏ
    ("Йорчӏ@ми", "Йорчӏами"),               # @ for а, word absent from avar.db
    ("ЦИияб хабар щиб бугеб?", "ЦӀияб"),    # capital И for the palochka
]

# Real Russian, including ё, which the Avar ё-rule must not reach.
RUSSIAN = """
Имена прилагательные в аварском языке образуются почти от всех частей речи
с помощью суффиксов. Все прилагательные принимают конечные показатели
грамматических классов для согласования данного прилагательного с
определяемым им существительным. Запомните: для образования форм
эргативного падежа множественного числа используются два суффикса.
Определите к какому типу склонения относятся следующие существительные.
Просклоняйте по падежам существительные: лопата, реки, аулы, кузнец, охотник.
Ёлка ещё зелёная, лёд и мёд, всё её сестёр.
"""

# Correct Avar that must survive untouched. The numerals are the trap: they are
# minimal pairs of each other, and avar.db does not list `ункъго`.
UNTOUCHED = [
    "цо", "кӏиго", "лъабго", "ункъго", "щуго", "анлъго", "анкьго",
    "микьго", "ичӏго", "анцӏго", "къого", "тӏехь", "лъикӏав", "гьечӏо",
]


def main() -> int:
    if not DB.exists():
        print(f"skip: {DB} not found")
        return 0

    lex = Lexicon(DB)
    failures = []

    for source, expected in MISREADS:
        got, _ = fix(source, lex)
        if expected not in got:
            failures.append(f"misread: {source!r} -> {got!r}, expected {expected!r}")

    got, _ = fix(RUSSIAN, lex)
    for before, after in zip(RUSSIAN.split(), got.split()):
        if before != after:
            failures.append(f"russian touched: {before!r} -> {after!r}")

    for word in UNTOUCHED:
        got, _ = fix(word, lex)
        if got != word:
            failures.append(f"rewrote correct Avar: {word!r} -> {got!r}")

    for line in failures:
        print("FAIL", line)
    total = len(MISREADS) + len(UNTOUCHED) + 1
    print(f"{total - len(failures)}/{total} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
