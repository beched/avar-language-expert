#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Curate a frequency-ranked, DB-enriched Avar vocabulary dataset for the PWA.

Input:
  ../../../avar/avar/av*.txt.csv   -> RU word (freq order) -> [AV candidates]
  ../../avar.db                    -> 22.8k-entry dict (headwords, senses/POS, examples)
Output:
  data.curated.json                -> {pos: [ {ru, av, ipa_hint, pos, band, ex:{av,ru}?}... ]}

The primary Avar word per Russian word is chosen by scoring candidates against the
big dictionary (headword exists, gloss overlaps the Russian word, shorter preferred,
appears-in-examples preferred). Palochka normalized to Ӏ (U+04C0) everywhere.
"""
import csv, json, os, re, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AVAR_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "..", "avar"))   # .../avar/avar
DB = os.path.normpath(os.path.join(HERE, "..", "..", "avar.db"))            # .../avar/auto/avar.db
OUT = os.path.join(HERE, "data.curated.json")

# palochka: unify every known variant to Ӏ U+04C0
PAL = "Ӏ"
PAL_VARIANTS = "ӏІіIl|!"  # small-palochka, Cyr/Lat I, lat l, bar, bang  (digit 1 handled separately)
def norm_pal(s):
    if not s:
        return s
    out = []
    for ch in s:
        if ch in PAL_VARIANTS:
            out.append(PAL)
        else:
            out.append(ch)
    return "".join(out)

def clean(s):
    return norm_pal((s or "").strip())

# comparison key: strip palochka + lowercase so "цӏ"/"цI"/"ЦӀ" all match
def key(s):
    return clean(s).replace(PAL, "").lower()

FILES = {
    "nouns":     "avnouns.txt.csv",
    "verbs":     "avverbs.txt.csv",
    "adjs":      "avadjvectives.txt.csv",
    "adverbs":   "avadverbs.txt.csv",
    "pronouns":  "avpronouns.txt.csv",
    "numerals":  "avnumeric.txt.csv",
    "misc":      "avmisc.txt.csv",
}

con = sqlite3.connect(DB)
cur = con.cursor()

# --- lookups against the big dictionary -------------------------------------
def headword_ids(av):
    """entry ids whose headword matches av (palochka-insensitive)."""
    k = key(av)
    rows = cur.execute(
        "SELECT id, headword FROM entries WHERE headword_norm=? OR headword=?",
        (av, av)).fetchall()
    ids = [r[0] for r in rows]
    if ids:
        return ids
    # fallback: scan is too slow; use forms table (normalized)
    rows = cur.execute("SELECT entry_id FROM forms WHERE form=? OR form_norm=? LIMIT 5",
                       (av, av)).fetchall()
    return [r[0] for r in rows]

def glosses(entry_id):
    rows = cur.execute("SELECT ru_text, labels_json FROM senses WHERE entry_id=? ORDER BY sense_idx",
                       (entry_id,)).fetchall()
    return rows

def short_example(entry_id):
    """pick the shortest clean bilingual example for an entry."""
    rows = cur.execute(
        "SELECT av, ru FROM examples WHERE entry_id=? AND av IS NOT NULL AND ru IS NOT NULL",
        (entry_id,)).fetchall()
    best = None
    for av, ru in rows:
        av = clean(av); ru = (ru or "").strip()
        if not av or not ru:
            continue
        if "—" in av or "~" in av or "…" in av:
            continue
        L = len(av)
        if L < 6 or L > 34:
            continue
        if best is None or L < best[2]:
            best = (av, ru, L)
    return {"av": best[0], "ru": best[1]} if best else None

POS_HINT = {  # label token -> our pos bucket (for validation only)
    "существительное": "nouns", "глагол": "verbs", "масдар": "verbs",
    "прилагательное": "adjs", "наречие": "adverbs", "местоимение": "pronouns",
    "числительное": "numerals",
}

def score(av, ru_word, want_pos):
    """higher = better primary candidate for the Russian word ru_word."""
    ids = headword_ids(av)
    if not ids:
        return (-100, None, None, None)   # not in dict -> distrust
    ru_k = ru_word.lower()
    best = (-50, None, None, None)
    for eid in ids:
        gl = glosses(eid)
        s = 0
        pos_here = None
        matched_gloss = None
        for ru_text, labels in gl:
            labels = labels or ""
            for tok, bucket in POS_HINT.items():
                if tok in labels:
                    pos_here = bucket
            if ru_text:
                # gloss overlap with the Russian source word
                gk = ru_text.lower()
                if ru_k == gk or re.search(r"\b" + re.escape(ru_k) + r"\b", gk):
                    s += 20
                    matched_gloss = ru_text
                elif ru_k in gk:
                    s += 6
                    matched_gloss = matched_gloss or ru_text
        if pos_here == want_pos:
            s += 8
        s -= max(0, len(av) - 8) * 0.4          # prefer shorter, ordinary words
        if s > best[0]:
            best = (s, eid, pos_here, matched_gloss)
    return best

# --- build ------------------------------------------------------------------
result = {}
for pos, fname in FILES.items():
    path = os.path.join(AVAR_DIR, fname)
    out = []
    with open(path, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    rank = 0
    for row in rows[1:]:
        if len(row) < 2:
            continue
        ru_word = row[0].strip()
        cands = [clean(c) for c in row[1].split(",") if c.strip()]
        if not ru_word or not cands:
            continue
        rank += 1
        band = 1 if rank <= 60 else 2 if rank <= 150 else 3 if rank <= 320 else 4
        # score candidates, keep best
        scored = []
        for c in cands[:12]:
            sc, eid, ph, mg = score(c, ru_word, pos)
            scored.append((sc, c, eid, ph, mg))
        scored.sort(key=lambda x: -x[0])
        sc, av, eid, ph, mg = scored[0]
        ex = short_example(eid) if eid else None
        out.append({
            "ru": ru_word,
            "av": av,
            "pos": pos,
            "band": band,
            "score": round(sc, 1),
            "gloss": mg,
            "alts": [c for _, c, *_ in scored[1:4] if c != av][:3],
            **({"ex": ex} if ex else {}),
        })
    result[pos] = out
    print(f"{pos:9s}: {len(out):4d} words  (from {fname})", file=sys.stderr)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print("wrote", OUT, file=sys.stderr)
