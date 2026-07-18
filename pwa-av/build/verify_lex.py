#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-check every Avar word in lexicon.py against avar.db. Flag mismatches."""
import sqlite3, os, re, sys
from lexicon import out as THEMES
from lexicon import EXEMPT

DB = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "avar.db"))
con = sqlite3.connect(DB); cur = con.cursor()
def k(s):  # palochka-insensitive key
    s = (s or "").lower()
    for v in "ӏіi‏|!":
        s = s.replace(v, "")
    return s.replace("ӏ","").replace("ӏ","").replace("i","")

# build in-memory index: normalized headword -> [glosses]
IDX = {}
for hw, eid in cur.execute("SELECT headword, id FROM entries").fetchall():
    IDX.setdefault(k(hw), []).append(eid)
GLOSS = {}
for eid, ru in cur.execute("SELECT entry_id, ru_text FROM senses").fetchall():
    if ru: GLOSS.setdefault(eid, []).append(ru)
FORM = {}
for form, eid in cur.execute("SELECT form, entry_id FROM forms").fetchall():
    FORM.setdefault(k(form), eid)

def check(av, ru):
    ids = IDX.get(k(av)) or ([FORM[k(av)]] if k(av) in FORM else [])
    if not ids:
        return "NOT_IN_DICT", []
    gl = []
    for eid in ids:
        gl += GLOSS.get(eid, [])
    rk = k(ru)
    for g in gl:
        gk = k(g)
        if rk == gk or re.search(r"(^|[ ,;.])"+re.escape(rk)+r"($|[ ,;.])", gk) or rk in gk:
            return "OK", gl
    # gloss doesn't contain the russian -> possibly wrong pick
    return "GLOSS_MISMATCH", gl

bad = 0
EXK = {k(x) for x in EXEMPT}
for t in THEMES:
    for w in t["words"]:
        if k(w["av"]) in EXK:
            continue
        status, gl = check(w["av"], w["ru"])
        if status != "OK":
            bad += 1
            print(f"[{t['id']:8s}] {w['ru']:14s} = {w['av']:16s} {status}  glosses={ [g[:30] for g in gl[:3]] }")
print(f"\n{bad} flagged.")
