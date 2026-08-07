#!/usr/bin/env python3
"""
Post-correction for OCR'd Avar text.

OCR engines have no Avar language model, so they mangle Avar in three
predictable ways. This module fixes them in that order:

1. **Palochka.** The letter Ӏ (U+04C0) exists in no OCR alphabet, so engines
   emit whatever looks similar: I l 1 | / ! Ї і Į. In Avar the palochka only
   ever follows г к х ц ч т, which makes it recoverable from context.
2. **Latin homoglyphs.** Cyrillic words come back with Latin lookalikes spliced
   in (`6yxlyne6` for букӀунеб). Mixed-script tokens get transliterated back.
3. **Everything else.** Remaining tokens are checked against a lexicon built
   from avar.db; unknown ones get a Levenshtein-nearest suggestion.

Usage:
    python avar_ocr_fix.py score  FILE...      # % of tokens in lexicon
    python avar_ocr_fix.py fix    FILE -o OUT  # write corrected text
    python avar_ocr_fix.py report FILE         # unknown tokens + suggestions
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

DB = Path(__file__).with_name("avar.db")

PALOCHKA = "Ӏ"          # U+04C0 CYRILLIC LETTER PALOCHKA
PALOCHKA_LOWER = "ӏ"    # U+04CF

# Consonants a palochka may follow: гӀ кӀ хӀ цӀ чӀ тӀ (and their doubled forms).
PALOCHKA_BASES = "гкхцчт" + "xktc"  # + Latin lookalikes of those bases

# Glyphs OCR engines substitute for the palochka. Several of these are
# punctuation, so palochka repair has to run BEFORE tokenisation -- otherwise
# `к[иго` is split into two tokens and the word is never recoverable.
PALOCHKA_LOOKALIKES = "IlІіiї1|/!\\Įĺľ[]{}()"

# Capital letters tesseract also uses for the palochka (ЦТияб = цӀияб,
# ГЛалиева = ГӀалиева, ЦИияб = ЦӀияб). These are ambiguous -- "ТА" is a real
# letter pair -- so they are only applied when the result is a known word.
PALOCHKA_CAPITALS = "ГЛТАШИНП"

# Avar-only digraphs. Effectively absent from Russian orthography, so they are
# a reliable signal that a token is Avar and safe to correct against the Avar
# lexicon. Without this guard, Russian words missing from the (gloss-derived,
# under-covering) Russian wordlist get "corrected" into Avar look-alikes.
AVAR_MARKERS = ("къ", "гъ", "хъ", "кь", "лъ", "цӏ", "кӏ", "гӏ", "хӏ", "тӏ", "чӏ")

# Pre-tokenisation palochka repair: a lookalike glyph directly after one of
# гкхцчт is a palochka. Latin lookalikes of those bases (x for х, k for к,
# t for т, c for ц) are included, because a token that OCR'd wholly into Latin
# still has to survive tokenisation before deromanize() can repair it.
# Tesseract also renders the palochka as a stray capital Г.
PALOCHKA_RE = re.compile(
    r"([гкхцчтГКХЦЧТxXkKtTcC])[" + re.escape("Il1|/!\\[]{}()іІїĺľ") + r"Г]")

# Latin -> Cyrillic homoglyphs. Only applied to tokens that are already
# mixed-script, so genuine Latin/Russian words are never touched.
HOMOGLYPH = {
    "a": "а", "b": "ь", "c": "с", "e": "е", "g": "д", "h": "н", "k": "к",
    "m": "м", "n": "п", "o": "о", "p": "р", "s": "ѕ", "t": "т", "u": "и",
    "x": "х", "y": "у", "v": "ѵ", "l": "л", "w": "ш", "r": "г",
    "A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н", "K": "К", "M": "М",
    "O": "О", "P": "Р", "T": "Т", "X": "Х", "Y": "У",
    # digit-for-letter confusions seen in this corpus
    "6": "б", "3": "з", "0": "о", "4": "ч",
}

CYRILLIC = re.compile(r"[а-яёА-ЯЁӀӏ]")
LATIN = re.compile(r"[a-zA-Z]")

# Lines the extractor writes itself (headings, blockquote, source note). These
# are English on purpose and must survive the Latin-homoglyph pass.
MARKDOWN_CHROME = re.compile(r"\s*(#{1,6}\s|>|\*Source:|---\s*$)")
# A token is a run of letters/digits plus internal hyphens. `@` and `/` are
# admitted as internal characters because tesseract prints them inside words
# (кӏиго -> к@го, анцӏила -> ани/Гила); left out, they split the word in two
# and the damage becomes invisible to every rule below.
TOKEN = re.compile(r"[^\W_@]+(?:[-@/][^\W_@]+)*[@]?|@[^\W_@]+", re.UNICODE)


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------

def strip_accents(text: str) -> str:
    """Drop combining acute/grave. The book marks stress; the lexicon does not."""
    decomposed = unicodedata.normalize("NFD", text)
    kept = "".join(ch for ch in decomposed if ch not in "́̀")
    return unicodedata.normalize("NFC", kept)


def fix_palochka_text(text: str) -> str:
    """Whole-text palochka repair, run before tokenisation.

    Applied repeatedly because doubled letters (цӀцӀ, кӀкӀ) need two passes,
    and because a repair can expose the next one.
    """
    def repl(m: re.Match) -> str:
        base = m.group(1)
        return base + (PALOCHKA_LOWER if base.islower() else PALOCHKA)

    for _ in range(3):
        new = PALOCHKA_RE.sub(repl, text)
        if new == text:
            break
        text = new
    return text


def fix_palochka(token: str) -> str:
    """Replace palochka lookalikes that sit right after г к х ц ч т."""
    out = []
    for i, ch in enumerate(token):
        if ch in PALOCHKA_LOOKALIKES and out:
            prev = out[-1]
            if prev.lower() in PALOCHKA_BASES:
                out.append(PALOCHKA_LOWER if prev.islower() else PALOCHKA)
                continue
        out.append(ch)
    return "".join(out)


def looks_avar(token: str) -> bool:
    """True if the token carries Avar-only orthography."""
    n = normalize(token)
    return PALOCHKA_LOWER in n or any(m in n for m in AVAR_MARKERS)


def palochka_capital_candidates(token: str):
    """Yield variants with a capital in PALOCHKA_CAPITALS read as a palochka."""
    for i, ch in enumerate(token):
        if i > 0 and ch in PALOCHKA_CAPITALS and token[i - 1].lower() in PALOCHKA_BASES:
            prev = token[i - 1]
            mark = PALOCHKA_LOWER if prev.islower() else PALOCHKA
            yield token[:i] + mark + token[i + 1:]


# Scanned books mark stress on the vowel, and the OCR reads that mark as a
# diaeresis: е́ comes back as `ё`. Avar orthography has no `ё` at all, so in a
# token carrying Avar-only orthography this is unconditionally an error.
# Measured on the Avar Language Guide: 494 of 494 such tokens were absent from
# the 78k-form lexicon, and `ё`->`е` alone resolved 53% of them.
# Russian text in the same book keeps its `ё` -- there the letter is real.
YO = str.maketrans("ёЁ", "еЕ")

# Candidate substitutions: plausible for this corpus but not safe on their own,
# so a rewrite is kept only when it yields a word the lexicon knows.
#
# Mined rather than guessed: each unresolved Avar token in the guide was
# aligned against its nearest lexicon neighbour and the character-level edits
# aggregated (see the `report` mode). Only recurring, explicable edits are
# listed; one-off alignments and edits confined to page numbers were dropped.
#
#   ь <-> ъ    near-identical in print, and the pair is phonemic in Avar
#              (лъикӏ vs льикӏ, халкъ vs халкь) -- so both directions
#   й -> и     stressed и, its acute read as the и-breve
#   4 6 0 3 2  digits set in place of the letter they resemble
#   6 -> е/о   мегӏ6р, кӏод6
#   д б -> о   a final о that picked up the descender of the line below
#   21 2 -> гӏ the гӏ ligature, which no Russian model has
#   е -> а     unstressed а reduced in print
BOOK_SUBS = (
    ("ь", "ъ"), ("ъ", "ь"),
    ("й", "и"),
    ("4", "а"), ("4", "ч"), ("4", "гӏа"),
    ("6", "б"), ("6", "е"), ("6", "о"),
    ("0", "о"), ("3", "з"),
    # The гӏ ligature, which no Russian model has. Longest forms first so
    # `2Геч` resolves as гӏеч rather than leaving a stray Г behind.
    ("2г", "гӏ"), ("21", "гӏ"), ("2", "гӏ"),
    ("и/г", "цӏ"), ("/г", "ӏ"),
    ("@", "а"), ("@", "ӏи"), ("@", "ӏ"),
    ("д", "о"), ("д", "а"), ("б", "о"),
    ("е", "а"),
)

# Deliberately NOT included: у -> а. It is attested, but avar.db is missing
# `ункъго` (four), and the rule rewrote it to `анкьго` (seven) -- a valid word,
# so nothing downstream could catch it. Turning one numeral into another is a
# worse outcome than leaving OCR noise in place, and a textbook is full of
# numerals. Any rule that can map one well-formed Avar word onto a different
# well-formed Avar word needs this much scrutiny before being added.

# How many of the above may be combined in one token. Real damage clusters:
# `льйкӏаб` needs ь->ъ *and* й->и, which no single substitution reaches. Three
# keeps the search small while covering every multi-edit case observed.
MAX_SUBS = 3
# Ceiling on rewrites generated per token, so a token full of substitutable
# letters cannot blow up the search.
MAX_CANDIDATES = 400


def strip_avar_yo(token: str) -> str:
    """Undo stressed-е-read-as-ё, but only inside Avar-looking tokens."""
    return token.translate(YO) if looks_avar(token) else token


def strip_at(token: str) -> str:
    """Fall back to `@` -> а when no lexicon-confirmed reading was found.

    `@` is never a letter, so leaving it is always wrong -- but the word it
    damaged is not always in the lexicon to confirm a repair (`Йорчӏ@ми` is a
    greeting, absent from avar.db). а is the commonest reading by a wide
    margin, so it is the right guess when there is nothing to check against.
    """
    return token.replace("@", "а") if "@" in token else token


def _apply_once(token: str):
    """Yield every single-occurrence application of one BOOK_SUBS rule."""
    lowered = token.lower()
    for src, dst in BOOK_SUBS:
        start = 0
        while True:
            i = lowered.find(src, start)
            if i < 0:
                break
            start = i + 1
            replacement = dst.upper() if token[i].isupper() else dst
            yield token[:i] + replacement + token[i + len(src):]


def book_variants(token: str):
    """Yield lexicon-checkable repairs for this corpus's systematic misreads.

    Breadth-first over BOOK_SUBS, shortest rewrites first, so that damage
    needing several edits at once is reachable: `льйкӏаб` needs ь->ъ *and*
    й->и, and neither alone produces a word. Fewer substitutions means a more
    likely reading, so the first lexicon hit wins.
    """
    seen = {token}
    frontier = [token]
    produced = 0
    for _ in range(MAX_SUBS):
        nxt = []
        for word in frontier:
            for cand in _apply_once(word):
                if cand in seen:
                    continue
                seen.add(cand)
                nxt.append(cand)
                yield cand
                produced += 1
                if produced >= MAX_CANDIDATES:
                    return
        frontier = nxt


def is_suspicious(token: str) -> bool:
    """Does the token carry OCR damage worth trying to repair?

    Only damaged tokens are eligible for fuzzy correction. A clean, well-formed
    word that merely happens to be missing from the lexicon must be left alone.
    """
    return bool(LATIN.search(token)) or any(ch.isdigit() for ch in token) \
        or "@" in token or "/" in token or strip_accents(token) != token


def deromanize(token: str) -> str:
    """Map Latin/digit homoglyphs to Cyrillic.

    The book contains no Latin text, so any token carrying Latin letters is an
    OCR failure -- whether it is mixed-script (`ц1але`) or has been rendered
    wholly in Latin (`6yxlyne6` for букӀунеб). Both are transliterated back.
    Pure-digit tokens (page numbers, exercise numbers) are left alone.
    """
    if not LATIN.search(token):
        return token
    return "".join(HOMOGLYPH.get(ch, ch) for ch in token)


def normalize(token: str) -> str:
    """Lexicon key: accent-free, lowercase, palochka as U+04CF."""
    t = strip_accents(token).lower()
    t = t.replace(PALOCHKA, PALOCHKA_LOWER).replace("ӏ", PALOCHKA_LOWER)
    return t


def clean_token(token: str) -> str:
    """Deterministic repairs only -- no dictionary needed.

    Two rounds: deromanizing can expose a palochka base, and repairing a
    palochka can expose another Latin homoglyph.
    """
    for _ in range(2):
        token = fix_palochka(deromanize(fix_palochka(token)))
    return token


# --------------------------------------------------------------------------
# lexicon
# --------------------------------------------------------------------------

class Lexicon:
    """Avar and Russian wordlists, both derived from avar.db."""

    def __init__(self, db_path: Path = DB):
        con = sqlite3.connect(db_path)
        self.avar: set[str] = set()
        self.russian: set[str] = set()

        for (form,) in con.execute("SELECT form_norm FROM forms"):
            if form:
                self.avar.add(normalize(form))
        for (hw,) in con.execute("SELECT headword_norm FROM entries"):
            if hw:
                self.avar.add(normalize(hw))
        # Example sentences carry inflected forms the `forms` table lacks.
        for (av,) in con.execute("SELECT av FROM examples WHERE av IS NOT NULL"):
            for tok in TOKEN.findall(av):
                self.avar.add(normalize(tok))

        for table, col in (("ru_index", "ru_term"), ("senses", "ru_text"),
                           ("examples", "ru")):
            q = f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL"
            for (text,) in con.execute(q):
                for tok in TOKEN.findall(text):
                    self.russian.add(normalize(tok))
        con.close()

        self.avar.discard("")
        self.russian.discard("")
        self.all = self.avar | self.russian
        # rapidfuzz wants a list; keep Avar-only for suggestions since the
        # Russian side of this corpus is glosses, not running text.
        self._avar_list = sorted(self.avar)

    def knows(self, token: str) -> bool:
        return normalize(token) in self.all

    @lru_cache(maxsize=100_000)
    def suggest(self, token: str, max_distance: int = 2):
        """Nearest Avar word by Levenshtein, or None."""
        from rapidfuzz import process, distance

        norm = normalize(token)
        hit = process.extractOne(
            norm, self._avar_list,
            scorer=distance.Levenshtein.distance,
            score_cutoff=max_distance,
        )
        return (hit[0], hit[1]) if hit else None


# --------------------------------------------------------------------------
# pipeline
# --------------------------------------------------------------------------

def is_scoreable(token: str) -> bool:
    """Words worth judging: length >= 3 and not a bare number.

    Deliberately includes Latin-looking tokens. The source book is Russian and
    Avar throughout, so `6yxlyne6` is a mangled word, not a foreign one, and
    excluding it would hide the very failure being measured.
    """
    return len(token) >= 3 and not token.isdigit() and any(
        ch.isalpha() or ch.isdigit() for ch in token)


def score(text: str, lex: Lexicon) -> dict:
    """Quality metrics for an OCR run.

    The headline number is `avar_pct`: of the tokens carrying a palochka --
    which are unambiguously Avar -- how many are real words? The all-token
    rate is reported too but discriminates poorly, because the book is mostly
    Russian and the only Russian wordlist available here is built from
    dictionary glosses, so it under-covers running prose.
    """
    repaired = fix_palochka_text(text)
    raw = [t for t in TOKEN.findall(repaired) if is_scoreable(t)]
    cleaned = [clean_token(t) for t in raw]

    avar = [c for c in cleaned if PALOCHKA_LOWER in normalize(c)]
    avar_known = sum(1 for c in avar if normalize(c) in lex.avar)

    return {
        "tokens": len(raw),
        "all_pct": round(100 * sum(1 for c in cleaned if lex.knows(c)) / (len(raw) or 1), 1),
        "avar_tokens": len(avar),
        "avar_pct": round(100 * avar_known / (len(avar) or 1), 1),
        "latin_left": sum(1 for c in cleaned if LATIN.search(c)),
    }


def fix(text: str, lex: Lexicon, use_fuzzy: bool = False,
        max_distance: int = 1) -> tuple[str, Counter]:
    """Rewrite text in three tiers, most confident first.

    1. Unambiguous deterministic repair (palochka lookalikes, Latin homoglyphs).
       Applied whether or not the result is a known word -- these substitutions
       are always wrong to leave in place.
    2. Ambiguous deterministic repair (capital Г/Л/Т/А/Ш as palochka). Applied
       only when it produces a word the lexicon knows.
    3. Levenshtein-nearest Avar word, for Avar-looking tokens only. Russian
       prose is never fuzzy-corrected: the Russian wordlist here is built from
       dictionary glosses and is too thin to tell a rare word from a broken one
       (unguarded, it turned `прочтет` into `протез`).

       Tier 3 is OFF by default. A manual audit of 78 distance-1 corrections
       put precision near 70%, and the errors are systematic rather than
       random -- it rewrites noun-class prefixes (букӀунге -> вукӀунге) and
       confuses рекӀ-/ретӀ-, which silently changes meaning. Use `report` to
       review the suggestions, or `--fuzzy` to accept them wholesale.
    """
    stats: Counter = Counter()

    def repl(m: re.Match) -> str:
        token = m.group(0)
        if not is_scoreable(token):
            return token
        if lex.knows(token):
            stats["already_ok"] += 1
            return token

        cleaned = clean_token(token)
        if cleaned != token and lex.knows(cleaned):
            stats["fixed_deterministic"] += 1
            return _match_case(token, cleaned)

        for candidate in palochka_capital_candidates(cleaned):
            if lex.knows(candidate):
                stats["fixed_palochka_capital"] += 1
                return _match_case(token, candidate)

        # `ё` inside Avar orthography is always wrong, so this one is applied
        # unconditionally -- but if it alone yields a known word, stop here.
        deyo = strip_avar_yo(cleaned)
        if deyo != cleaned:
            stats["fixed_avar_yo"] += 1
            cleaned = deyo
            if lex.knows(cleaned):
                return _match_case(token, cleaned)

        # Guarded for the same reason tier 3 is. Rules like е->а and ъ->ь are
        # phonemic in Avar but destructive in Russian, and the Russian wordlist
        # is too thin to distinguish a rare word from a broken one -- so a
        # clean, merely-unlisted Russian word must never be rewritten. Only
        # tokens that are recognisably Avar, or that carry visible damage
        # (a digit, `@`, `/`, Latin, a stray accent), are eligible.
        #
        # A token with neither property still gets a narrower chance: OCR can
        # strip every Avar marker off a word (лъабазарго -> льдбазарго, which
        # reads as plain Russian). There the rewrite must land on a form that
        # is *both* in the Avar wordlist and Avar-looking, so the only way a
        # Russian word can be touched is by turning into a real Avar word --
        # which needs two independent coincidences rather than one.
        marked = looks_avar(cleaned) or is_suspicious(cleaned)
        for candidate in book_variants(cleaned):
            if marked:
                if lex.knows(candidate):
                    stats["fixed_book_variant"] += 1
                    return _match_case(token, candidate)
            elif looks_avar(candidate) and normalize(candidate) in lex.avar:
                stats["fixed_book_variant_avar_only"] += 1
                return _match_case(token, candidate)

        # Nothing confirmed, but `@` cannot stay -- guess the commonest reading.
        deat = strip_at(cleaned)
        if deat != cleaned:
            stats["fixed_at_fallback"] += 1
            cleaned = deat

        # An Avar-looking token absent from 76k forms is very likely broken,
        # so damage evidence is not additionally required for those.
        if use_fuzzy and looks_avar(cleaned):
            hit = lex.suggest(cleaned, max_distance)
            if hit:
                stats["fixed_fuzzy"] += 1
                return _match_case(token, hit[0])
            stats["unresolved_avar"] += 1
        else:
            stats["left_alone"] += 1

        # Keep tier-1 repairs even when unverified; they are safe on their own.
        return _match_case(token, cleaned) if cleaned != token else token

    # Markdown structure is ours, not the scanner's: `## Page 40` is English by
    # construction, and deromanizing it produced `## Раде 40`.
    out = []
    for line in fix_palochka_text(text).split("\n"):
        out.append(line if MARKDOWN_CHROME.match(line) else TOKEN.sub(repl, line))
    return "\n".join(out), stats


def _match_case(original: str, replacement: str) -> str:
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def report(text: str, lex: Lexicon, limit: int = 40) -> None:
    """List unresolved Avar tokens with their nearest dictionary match.

    Restricted to Avar-looking tokens for the same reason tier 3 is: suggesting
    Avar words for Russian ones is noise, not signal.
    """
    unknown: Counter = Counter()
    for token in TOKEN.findall(fix_palochka_text(text)):
        cleaned = clean_token(token)
        if is_scoreable(token) and looks_avar(cleaned) and not lex.knows(cleaned):
            unknown[token] += 1
    print(f"{sum(unknown.values())} unknown tokens ({len(unknown)} distinct)\n")
    for token, count in unknown.most_common(limit):
        hit = lex.suggest(clean_token(token), 2)
        arrow = f"  ->  {hit[0]}  (d={hit[1]})" if hit else "  ->  ?"
        print(f"{count:5}x  {token:<24}{arrow}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["score", "fix", "report"])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--max-distance", type=int, default=1,
                    help="max Levenshtein distance for fuzzy correction")
    ap.add_argument("--fuzzy", action="store_true",
                    help="also apply Levenshtein corrections (~70%% precise; "
                         "see fix() -- off by default)")
    args = ap.parse_args()

    lex = Lexicon()
    print(f"lexicon: {len(lex.avar)} Avar forms, {len(lex.russian)} Russian",
          file=sys.stderr)

    for path in args.files:
        text = path.read_text(encoding="utf-8")
        if args.mode == "score":
            s = score(text, lex)
            print(f"{path.name:<22} tokens={s['tokens']:<6} "
                  f"all={s['all_pct']:>5}%  "
                  f"avar-tokens={s['avar_tokens']:<5} "
                  f"AVAR-CORRECT={s['avar_pct']:>5}%  "
                  f"latin-left={s['latin_left']}")
        elif args.mode == "report":
            report(text, lex)
        else:
            out, stats = fix(text, lex, args.fuzzy, args.max_distance)
            dest = args.output or path.with_suffix(".fixed.md")
            dest.write_text(out, encoding="utf-8")
            print(f"{path.name} -> {dest}: {dict(stats)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
