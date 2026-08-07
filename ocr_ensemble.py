#!/usr/bin/env python3
"""
Second-opinion OCR: let Apple Vision vote on tesseract's words.

The two engines fail differently on this corpus, measured over 8 sampled pages
of the Avar Language Guide (share of tokens found in avar.db, after
`avar_ocr_fix.fix`):

    tesseract  all=65.6%  avar=63.7%
    vision     all=58.6%  avar=34.7%
    ensemble   all=68.8%  avar=67.1%

Vision scores far worse on its own -- it tends to *delete* the palochka
(мегӏер -> мегр), and a deleted character cannot be recovered, whereas
tesseract's misreads (тӏГахьел, тӏ]ахьизул) keep a lookalike that
`fix_palochka_text` maps back. Vision also shatters tables into single-column
runs, so it must never be trusted with page structure.

Hence the asymmetry here: **tesseract owns the layout, Vision only votes on
tokens.** Tesseract's text is kept verbatim, whitespace and line breaks
included, and a word is swapped in from Vision only where tesseract's word is
absent from the lexicon and Vision's is present. Reading order, columns and
line breaks therefore cannot regress.

Vision is macOS-only. `available()` reports whether it can be used; callers
should fall back to plain tesseract when it cannot.
"""

from __future__ import annotations

import difflib
import re

from avar_ocr_fix import Lexicon, normalize

TOKEN = re.compile(r"[^\W_]+")

_ocrmac = None


def available() -> bool:
    """True if Apple's Vision framework can be reached from this process."""
    global _ocrmac
    if _ocrmac is None:
        try:
            from ocrmac import ocrmac
            _ocrmac = ocrmac
        except Exception:
            _ocrmac = False
    return bool(_ocrmac)


def vision_text(image) -> str:
    """Recognise `image` (a PIL image) with Vision, Russian preferred."""
    annotations = _ocrmac.OCR(
        image, language_preference=["ru-RU"], recognition_level="accurate"
    ).recognize()
    return "\n".join(text for text, _, _ in annotations)


def vote(tess: str, vision: str, lex: Lexicon) -> tuple[str, int]:
    """Substitute Vision's word wherever it is a real word and tesseract's is not.

    Both sides are aligned on normalised tokens, and only 1:1 `replace` runs are
    considered -- an insertion or deletion means the engines disagree about how
    many words are present, which is exactly the case where trusting Vision
    would corrupt tesseract's layout.
    """
    t_spans = list(TOKEN.finditer(tess))
    v_words = TOKEN.findall(vision)
    if not t_spans or not v_words:
        return tess, 0

    t_words = [m.group(0) for m in t_spans]
    matcher = difflib.SequenceMatcher(
        a=[normalize(w) for w in t_words],
        b=[normalize(w) for w in v_words],
        autojunk=False,
    )

    swaps = 0
    edits: list[tuple[int, int, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "replace" or (i2 - i1) != (j2 - j1):
            continue
        for k in range(i2 - i1):
            ours, theirs = t_words[i1 + k], v_words[j1 + k]
            if lex.knows(ours) or not lex.knows(theirs):
                continue
            span = t_spans[i1 + k]
            edits.append((span.start(), span.end(), theirs))
            swaps += 1

    # Applied back-to-front so earlier offsets stay valid.
    out = tess
    for start, end, word in reversed(edits):
        out = out[:start] + word + out[end:]
    return out, swaps


def refine(tess: str, image, lex: Lexicon) -> tuple[str, int]:
    """Run Vision on `image` and use it to vote on `tess`. No-op if unavailable."""
    if not available():
        return tess, 0
    try:
        return vote(tess, vision_text(image), lex)
    except Exception:
        # A single page failing in Vision must not abort a 125-page run.
        return tess, 0
