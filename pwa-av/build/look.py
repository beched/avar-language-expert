#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""look.py WORD [WORD...] -> for each Russian word, top Avar headwords by gloss match."""
import sqlite3, sys, os, re
DB = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "avar.db"))
con = sqlite3.connect(DB); cur = con.cursor()
def norm(s): return (s or "").replace("Ӏ","").replace("ӏ","").replace("I","").lower()
for w in sys.argv[1:]:
    wl = w.lower()
    rows = cur.execute("""
      SELECT e.headword, s.ru_text, s.labels_json
      FROM senses s JOIN entries e ON s.entry_id=e.id
      WHERE s.ru_text LIKE ? ORDER BY length(e.headword) LIMIT 25""", ("%"+wl+"%",)).fetchall()
    # rank: exact gloss / word-boundary match first, shorter headword first
    scored=[]
    for hw, ru, lab in rows:
        g=(ru or "").lower(); s=0
        if g==wl: s+=100
        elif re.search(r"(^|[ ,;])"+re.escape(wl)+r"($|[ ,;])", g): s+=40
        elif wl in g: s+=10
        s-=len(hw)*0.5
        scored.append((s,hw,ru,(lab or "").strip('[]')))
    scored.sort(key=lambda x:-x[0])
    print("=== %s ===" % w)
    seen=set()
    for s,hw,ru,lab in scored[:8]:
        if hw in seen: continue
        seen.add(hw)
        print("  %-16s | %-38s | %s" % (hw, (ru or '')[:38], lab[:30]))
