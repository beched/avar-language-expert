#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build a frequency-ranked, loanword-filtered, POS-balanced Avar flashcard deck
(~1000 words in 3 cumulative levels). Native Avar only — Russian loanwords that
are identical/near-identical to the Russian word are dropped.

Source: avar/avar/av*.txt.csv give Russian words in frequency order (per POS);
we resolve each to the best *attested* Avar equivalent in avar/auto/avar.db and
keep only high-confidence, non-loan single words.

Out: data.freq.json  ->  {"levels":[{"id","title","words":[{ru,av,pos}]}...]}
"""
import csv, json, os, re, sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
AVAR = os.path.normpath(os.path.join(HERE, "..", "..", "..", "avar"))
DB = os.path.normpath(os.path.join(HERE, "..", "..", "avar.db"))
con = sqlite3.connect(DB); cur = con.cursor()

def k(s):  # palochka-insensitive, lowercase
    s = (s or "").lower()
    for v in "ӏіiI": s = s.replace(v, "")
    return s
def normpal(s):  # canonical palochka U+04C0
    for v in "ӏІіIl": s = s.replace(v, "Ӏ")
    return s

# --- seed: my 200 hand-verified themed words (correct) ----------------------
SEED = {}
for t in json.load(open(os.path.join(HERE, "data.lex.json"), encoding="utf-8")):
    for w in t["words"]:
        SEED.setdefault(w["ru"], w["av"])

# --- overrides for the most frequent words (guarantee the top of the deck) --
OVER = {
 "быть":"букӀине","время":"заман","мочь":"кӀвезе","дело":"иш","работа":"хӀалтӀи",
 "слово":"рагӀи","говорить":"бицине","стать":"лъугьине","сделать":"гьабизе",
 "смотреть":"балагьизе","работать":"хӀалтӀизе","понять":"бичӀчӀизе","сказать":"абизе",
 "пойти":"ине","спросить":"гьикъизе","получить":"щвезе","рука":"квер","глаз":"бер",
 "хороший":"лъикӀаб","высокий":"борхатаб","знать":"лъазе","дать":"кьезе","видеть":"бихьизе",
 "хотеть":"бокьизе","думать":"пикру гьабизе","жить":"бетӀербахъизе","место":"бакӀ",
 "рука":"квер","голова":"бетӀер","вода":"лъим","земля":"ракь","отец":"эмен","мать":"эбел",
 "ребёнок":"лъимер","глаз":"бер","ночь":"сордо","друг":"гьудул","сила":"къуват",
 "белый":"хъахӀаб","чёрный":"чӀегӀераб","красный":"багӀараб","старый":"басрияб",
 "молодой":"бахӀараб","хотеть":"бокьизе","начать":"байбихьизе","найти":"батизе",
 "давать":"кьезе","взять":"босизе","держать":"кквезе","стоять":"чӀезе","сидеть":"гӀодов чӀезе",
 "помощь":"кумек","деньги":"гӀарац","общество":"жамагӀат","цель":"мурад","результат":"хӀасил",
 "тело":"черх","услышать":"рагӀизе","слышать":"рагӀизе",
}
def prim_ok(av, ru):  # (av, ru) is a real dictionary pair with ru in a sense?
    return _validate(av, ru) is not None

# entry senses ordered: entry_id -> [ (sense_idx, ru_text) ]
SENSE = {}
for eid, si, ru in cur.execute("SELECT entry_id, sense_idx, ru_text FROM senses ORDER BY entry_id, sense_idx"):
    if ru: SENSE.setdefault(eid, []).append((si, ru))
HWID = {}
for hw, eid in cur.execute("SELECT headword, id FROM entries"):
    HWID.setdefault(k(hw), []).append(eid)

NATIVE = re.compile(r"(ӏ|лъ|къ|хъ|гъ|гь|тӏ|цӏ|чӏ|кӏ|хь|хӏ|гӏ)")

# --- corpus frequency: how common each word is in the 36k example sentences ---
from collections import Counter
FREQ = Counter()
for (av,) in cur.execute("SELECT av FROM examples WHERE av IS NOT NULL"):
    for tok in re.split(r"[^а-яёӏ]+", av.lower()):
        if tok: FREQ[k(tok)] += 1
# --- rarity: entries whose relevant sense is bookish/archaic/dialectal/etc. ---
RARE_RE = re.compile("книжн|устар|редк|поэт|диалект|религи|фольк")
ENTRY_LABELS = {}
for eid, lab in cur.execute("SELECT entry_id, labels_json FROM senses"):
    ENTRY_LABELS.setdefault(eid, []).append(lab or "")
# --- reverse index: russian word -> candidate Avar headwords (single word) ---
REV = {}
for hw, eid, ru in cur.execute(
        "SELECT e.headword, e.id, s.ru_text FROM senses s JOIN entries e ON s.entry_id=e.id WHERE s.ru_text IS NOT NULL"):
    if " " in hw or "-" in hw: continue
    for term in re.split(r"[;,.]", ru.lower()):
        term = term.strip()
        if term: REV.setdefault(term, set()).add(hw)

def is_loan(av, ru):
    ak, rk = k(av), k(ru.lower())
    if not ak or not rk: return True
    if ak == rk: return True
    if NATIVE.search(av.lower()): return False
    cp = 0
    for a, b in zip(ak, rk):
        if a == b: cp += 1
        else: break
    if cp >= 4 or (ak.startswith(rk) or rk.startswith(ak)):
        return True
    return False

def score_av(av, ru):
    """rank av as a common, correct, non-exotic translation of ru. None if unfit."""
    rk = ru.lower().strip()
    best = None
    for eid in HWID.get(k(av), []):
        senses = SENSE.get(eid, [])
        labels = ENTRY_LABELS.get(eid, [])
        for pos_i, (si, g) in enumerate(senses):
            gk = g.lower()
            exact = (gk == rk) or bool(re.search(r"(^|[ ,;.])"+re.escape(rk)+r"($|[ ,;.])", gk))
            if not exact and rk not in gk: continue
            base = 100 if (gk == rk) else 55 if exact else 12
            if pos_i > 0: base *= 0.5 if exact else 0.15
            # this sense bookish/archaic/dialectal?
            lab = labels[si] if si < len(labels) else ""
            if RARE_RE.search(lab or ""): base -= 70
            base -= max(0, len(av)-8) * 0.6
            if NATIVE.search(av.lower()): base += 3
            if best is None or base > best: best = base
    if best is None: return None
    # commonness: how often the word actually occurs in real Avar text
    fr = FREQ.get(k(av), 0)
    best += min(45, fr * 1.5)          # strong pull toward common words
    return best

def best_avar(ru_word, cands):
    """best common native single-word Avar for ru_word (CSV + reverse-lookup candidates)."""
    if ru_word in OVER:
        return None if is_loan(OVER[ru_word], ru_word) else OVER[ru_word]
    if ru_word in SEED:
        return None if is_loan(SEED[ru_word], ru_word) else SEED[ru_word]
    pool = set(c.strip() for c in cands) | REV.get(ru_word.lower().strip(), set())
    scored = []
    for av in pool:
        if not av or " " in av or "-" in av: continue
        if is_loan(av, ru_word): continue
        s = score_av(av, ru_word)
        if s is None: continue
        scored.append((s, FREQ.get(k(av), 0), av))
    if not scored: return None
    scored.sort(key=lambda x: (-x[0], -x[1]))
    top = scored[0]
    # reject exotic picks: if the best word never occurs in the corpus, drop the word
    if top[1] == 0 and top[0] < 90:
        return None
    return top[2]

FILES = [("nouns", "avnouns.txt.csv"), ("verbs", "avverbs.txt.csv"),
         ("adjs", "avadjvectives.txt.csv"), ("adverbs", "avadverbs.txt.csv")]

resolved = {}
for pos, fn in FILES:
    out, seen_av = [], set()
    with open(os.path.join(AVAR, fn), encoding="utf-8") as f:
        rows = list(csv.reader(f))[1:]
    for row in rows:
        if len(row) < 2: continue
        ru = row[0].strip()
        cands = [c.strip() for c in row[1].split(",") if c.strip()]
        av = best_avar(ru, cands)
        if not av: continue
        av = normpal(av)
        ak = k(av)
        if ak in seen_av: continue                   # dedup by avar form
        seen_av.add(ak)
        out.append({"ru": ru, "av": av, "pos": pos})
    resolved[pos] = out
    print(f"{pos:8s}: {len(out):4d} resolved (of {len(rows)})")

# POS balance ~ real distribution; interleave in frequency order
WEIGHT = {"nouns": 55, "verbs": 20, "adjs": 15, "adverbs": 10}
idx = {p: 0 for p in resolved}
master = []
# weighted round-robin
import itertools
ticket = []
for p, w in WEIGHT.items():
    ticket += [p] * w
# deterministic interleave: cycle a fixed shuffled-by-weight pattern
pattern = []
# build a smooth pattern of length 100 matching weights
for i in range(100):
    # pick the pos most "owed" so far
    owed = {p: WEIGHT[p]*(i+1)/100 - pattern.count(p) for p in WEIGHT}
    pattern.append(max(owed, key=owed.get))
pi = 0
while any(idx[p] < len(resolved[p]) for p in resolved):
    p = pattern[pi % 100]; pi += 1
    if idx[p] < len(resolved[p]):
        master.append(resolved[p][idx[p]]); idx[p] += 1
    if len(master) >= 1000: break

def lvl(words, a, b):
    return words[a:b]

n = len(master)
levels = [
    {"id": "l1", "title": "⭐ Топ-250", "words": master[:250]},
    {"id": "l2", "title": "⭐⭐ 251–500", "words": master[250:500]},
    {"id": "l3", "title": "⭐⭐⭐ 501–%d" % n, "words": master[500:n]},
]
from collections import Counter
for L in levels:
    c = Counter(w["pos"] for w in L["words"])
    print(L["title"], len(L["words"]), dict(c))

json.dump(levels, open(os.path.join(HERE, "data.freq.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("total deck:", sum(len(L["words"]) for L in levels))
