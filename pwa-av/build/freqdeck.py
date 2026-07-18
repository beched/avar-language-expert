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
 "особенно":"хасго","рядом":"аскӀо","плечо":"гъеж",
}
# russian words to drop from the deck (loanword-ish or better explained as a pattern)
DROP = {"московский","момент","советский","русский","коммунизм","социализм"}
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
# lemma frequency: sum the corpus counts of ALL a word's inflected forms (via forms table),
# so a word's true commonness isn't undercounted by only its base form.
_FORM2E = {}
for _form, _eid in cur.execute("SELECT form, entry_id FROM forms"):
    _FORM2E.setdefault(k(_form), _eid)
LEMMA_FREQ = Counter()
for _tok, _c in FREQ.items():
    _e = _FORM2E.get(_tok)
    if _e is not None: LEMMA_FREQ[_e] += _c
def word_freq(av):
    best = FREQ.get(k(av), 0)
    for eid in HWID.get(k(av), []):
        f = LEMMA_FREQ.get(eid, 0)
        if f > best: best = f
    return best
# --- rarity: entries whose relevant sense is bookish/archaic/dialectal/etc. ---
RARE_RE = re.compile("книжн|устар|редк|поэт|диалект|религи|фольк")
ENTRY_LABELS = {}
for eid, lab in cur.execute("SELECT entry_id, labels_json FROM senses"):
    ENTRY_LABELS.setdefault(eid, []).append(lab or "")
# palochka-PRESERVING key (so цӀакъ 'очень' != цакъ 'зубик' — avoid homonym mixups)
def kp(s):
    s = (s or "").lower()
    for v in "ӏІіIl": s = s.replace(v, "Ӏ")
    return s
HWID_EXACT = {}
for hw, eid in cur.execute("SELECT headword, id FROM entries"):
    HWID_EXACT.setdefault(kp(hw), []).append(eid)

# --- forms (from entry_json) + one clean usage example per entry ------------
ENTRY_FORMS = {}
for eid, ej in cur.execute("SELECT id, entry_json FROM entries"):
    try:
        forms = json.loads(ej).get("forms") or []
        if forms: ENTRY_FORMS[eid] = forms
    except Exception:
        pass
def clean_example(av, ru):
    av = (av or "").strip(); ru = (ru or "").strip()
    if not av or not ru: return None
    if any(c in av for c in "—~…()[]"): return None          # dashes / sense-markers / brackets
    toks = av.split()
    if len(toks) < 2 or len(toks[0]) < 2: return None         # truncated (e.g. "б анищ")
    if not (6 <= len(av) <= 40): return None
    return (av, ru, len(av))
EX = {}
for eid, av, ru in cur.execute("SELECT entry_id, av, ru FROM examples WHERE av IS NOT NULL AND ru IS NOT NULL"):
    e = clean_example(av, ru)
    if not e: continue
    if eid not in EX or e[2] < EX[eid][2]:
        EX[eid] = e

def forms_of(av):
    for eid in HWID_EXACT.get(kp(av), []):
        f = ENTRY_FORMS.get(eid)
        if f: return f[:6]
    return None
def example_of(av):
    for eid in HWID_EXACT.get(kp(av), []):
        e = EX.get(eid)
        if e: return {"av": e[0], "ru": e[1]}
    return None

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

def gloss_terms(g):
    return [t.strip() for t in re.split(r"[;,]", (g or "").lower()) if t.strip()]

def score_av(av, ru):
    """How good is av as the translation of ru? Weighted by WHERE ru sits in the gloss
    (is it the primary meaning or a minor 5th synonym?). Frequency is only a tie-breaker."""
    rk = ru.lower().strip()
    best = None
    for eid in HWID.get(k(av), []):
        senses = SENSE.get(eid, [])
        labels = ENTRY_LABELS.get(eid, [])
        for pos_i, (si, g) in enumerate(senses):
            terms = gloss_terms(g)
            if rk not in terms: continue          # must be a real gloss TERM, not a substring
            j = terms.index(rk)                    # 0 = first/primary term of this sense
            if pos_i == 0 and j == 0:   base = 100 # ru IS the headword's primary meaning
            elif pos_i == 0 and j == 1: base = 78
            elif pos_i == 0:            base = max(0, 55 - j*10)   # buried in 1st sense
            elif pos_i == 1 and j == 0: base = 62
            elif pos_i == 1:            base = max(0, 40 - j*8)
            else:                       base = max(0, 34 - pos_i*4 - j*6)
            lab = labels[si] if si < len(labels) else ""
            if RARE_RE.search(lab or ""): base -= 70
            base -= max(0, len(av)-9) * 0.5
            if NATIVE.search(av.lower()): base += 3
            if best is None or base > best: best = base
    if best is None: return None
    fr = word_freq(av)
    if fr == 0: best -= 12                          # unattested -> slight distrust
    best += min(14, fr ** 0.5 * 2.2)                # modest tie-breaker only
    return best if best >= 50 else None             # require a genuinely good sense match

def best_avar(ru_word, cands):
    """returns (primary_av, [alt_av...]) — common native words for ru_word, or (None, [])."""
    pool = set(c.strip() for c in cands) | REV.get(ru_word.lower().strip(), set())
    scored = []
    for av in pool:
        if not av or " " in av or "-" in av: continue
        if is_loan(av, ru_word): continue
        s = score_av(av, ru_word)
        if s is None: continue
        scored.append((s, word_freq(av), av))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    # primary: forced override / seed, else best scored
    primary = OVER.get(ru_word) or SEED.get(ru_word)
    if primary and is_loan(primary, ru_word): primary = None
    if not primary:
        if not scored: return None, []
        top = scored[0]
        if top[1] == 0 and top[0] < 90: return None, []   # reject exotic-only
        primary = top[2]
    # alternates: other common (freq>0) synonyms/senses, distinct from primary
    alts, seen = [], {k(primary)}
    for s, fr, av in scored:
        if fr < 3: continue                # only reasonably-used synonyms
        if k(av) in seen: continue
        seen.add(k(av)); alts.append(av)
        if len(alts) >= 3: break
    return primary, alts

# ============ deck from frequent Russian words -> common Avar equivalents ====
# (RU->AV: gives real noun/verb/adj coverage a learner wants; picks are ranked by
#  Avar corpus frequency + primary-sense position, so exotic/wrong-sense words are avoided.)
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
        if ru in DROP: continue
        cands = [c.strip() for c in row[1].split(",") if c.strip()]
        av, alts = best_avar(ru, cands)
        if not av: continue
        av = normpal(av)
        if k(av) in seen_av: continue
        seen_av.add(k(av))
        entry = {"ru": ru, "av": av, "pos": pos}
        alts = [normpal(a) for a in alts][:2]
        if alts: entry["alts"] = alts
        fm = forms_of(av)
        if fm and len(fm) > 1: entry["forms"] = [normpal(x) for x in fm]
        ex = example_of(av)
        if ex: entry["ex"] = {"av": normpal(ex["av"]), "ru": ex["ru"]}
        out.append(entry)
    resolved[pos] = out
    print(f"{pos:8s}: {len(out):4d} resolved")
# interleave POS to ~real distribution (noun-heavy), in frequency order
WEIGHT = {"nouns": 55, "verbs": 20, "adjs": 15, "adverbs": 10}
pattern = []
for i in range(100):
    owed = {p: WEIGHT[p]*(i+1)/100 - pattern.count(p) for p in WEIGHT}
    pattern.append(max(owed, key=owed.get))
idx = {p: 0 for p in resolved}; deck = []
pi = 0
while any(idx[p] < len(resolved[p]) for p in resolved) and len(deck) < 1000:
    p = pattern[pi % 100]; pi += 1
    if idx[p] < len(resolved[p]):
        deck.append(resolved[p][idx[p]]); idx[p] += 1
n = len(deck)
levels = [
    {"id": "l1", "title": "⭐ Топ-250", "words": deck[:250]},
    {"id": "l2", "title": "⭐⭐ 251–500", "words": deck[250:500]},
    {"id": "l3", "title": "⭐⭐⭐ 501–%d" % n, "words": deck[500:n]},
]
for L in levels:
    c = Counter(w["pos"] for w in L["words"])
    print(L["title"], len(L["words"]), dict(c))
json.dump(levels, open(os.path.join(HERE, "data.freq.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("total deck (by Avar corpus frequency):", n)
