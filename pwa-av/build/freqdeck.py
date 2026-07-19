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
def normpal(s):  # canonical palochka U+04C0 (source data uses Latin I/i/l, Cyrillic І/і as palochka)
    for v in "ӏІіIli": s = s.replace(v, "Ӏ")
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
 "хотеть":"бокьизе","думать":"пикру гьабизе","жить":"гӀумру гьабизе","место":"бакӀ",
 "рука":"квер","голова":"бетӀер","вода":"лъим","земля":"ракь","отец":"эмен","мать":"эбел",
 "ребёнок":"лъимер","глаз":"бер","ночь":"сордо","друг":"гьудул","сила":"къуват",
 "белый":"хъахӀаб","чёрный":"чӀегӀераб","красный":"багӀараб","старый":"басрияб",
 "молодой":"бахӀараб","хотеть":"бокьизе","начать":"байбихьизе","найти":"батизе",
 "давать":"кьезе","взять":"босизе","держать":"кквезе","стоять":"чӀезе","сидеть":"гӀодов чӀезе",
 "помощь":"кумек","деньги":"гӀарац","общество":"жамагӀат","цель":"мурад","результат":"хӀасил",
 "тело":"черх","услышать":"рагӀизе","слышать":"рагӀизе",
 "особенно":"хасго","рядом":"аскӀо","плечо":"гъеж",
 "становиться":"лъугьине","единство":"цолъи","цена":"багьа","голос":"гьаракь","древний":"некӀсияб","крик":"ахӀи","лист":"тӀамах",
 "шум":"сас","страсть":"гӀишкъу","местный":"гьанисеб",
 # verified homonym/sense corrections (broad freq had picked a wrong-sense word):
 "смерть":"хвел","школа":"мактаб","основа":"кьучӀ","знак":"ишара",
 "условие":"шартӀ","внимание":"хал","цвет":"кьер",
 "мир":"дуниял","человечество":"инсаният","главный":"бетӀераб","искусство":"махщел",
 "потребность":"къваригӀел","существование":"бетӀербахъи","работник":"хӀалтӀухъан",
 "цель":"мурад","снять":"ччукӀизе","страшный":"хӀинкъараб","личный":"хасаб",
 "поздно":"кватӀун","обязанность":"вазипа","закрыть":"бацизе",
 "собственный":"бетӀергьанаб","легко":"бигьаго","тяжело":"бакӀго",
 "рисунок":"сурат",
}
# supplement (AV-frequency) words to skip: directional/redundant forms
SUPP_DROP = {"цебеса","лахӀ"}   # лахӀ=сажа/мишень — never a good everyday supplement word
# force these exact ru->av cards (native-speaker preference among close synonyms)
MANUAL = {"внутри": "жаниб"}
# russian words to drop from the deck (loanwords / no clean single-word native equivalent)
DROP = {"московский","момент","советский","русский","коммунизм","социализм",
        "вдруг","внезапно","ясно","единый","глава","машина","автомобиль","совсем","минута","опыт","случай","рост","век","образ","конечный","вечер","принимать","срок","труба","теория","правда","родной","снимать","уж",
       "мера","довольно"}
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

# --- corpus frequency ------------------------------------------------------
# TWO frequency signals:
#  EVERYDAY = dictionary examples + kids' magazine + folk tales + textbooks (spoken/narrative)
#  FREQ     = EVERYDAY + newspaper (hakikat) + Wikipedia (broad, but skews to FORMAL Arabisms)
# We rank by FREQ but REQUIRE everyday presence, so news-only formal words (маданият, таварих,
# вилаят…) are rejected while genuinely everyday words are kept.
from collections import Counter
DOCS = os.path.normpath(os.path.join(HERE, "..", "..", "docs"))
def count_file(counter, fn):
    p = os.path.join(DOCS, fn)
    if not os.path.exists(p): return
    with open(p, encoding="utf-8", errors="ignore") as f:
        for tok in re.split(r"[^а-яёӏ]+", f.read().lower()):
            if tok: counter[k(tok)] += 1
EVERYDAY = Counter()
for (av,) in cur.execute("SELECT av FROM examples WHERE av IS NOT NULL"):
    for tok in re.split(r"[^а-яёӏ]+", av.lower()):
        if tok: EVERYDAY[k(tok)] += 1
for fn in ("avarskiy_sokolenok_2024.md", "hitinal_avaraze.md", "avar_mats.md"):
    count_file(EVERYDAY, fn)
FREQ = Counter(EVERYDAY)
for fn in ("hakikat.md", "avar_wikipedia.md", "ob_avarskom.md"):
    count_file(FREQ, fn)
print("corpus tokens; everyday distinct:", len(EVERYDAY), "broad:", len(FREQ))
_FORM2E = {}
for _form, _eid in cur.execute("SELECT form, entry_id FROM forms"):
    _FORM2E.setdefault(k(_form), _eid)
def _lemma(fr):
    L = Counter()
    for _t, _c in fr.items():
        _e = _FORM2E.get(_t)
        if _e is not None: L[_e] += _c
    return L
LEMMA_FREQ = _lemma(FREQ)
EVERYDAY_LEMMA = _lemma(EVERYDAY)
def _wf(av, base, lem):
    best = base.get(k(av), 0)
    for eid in HWID.get(k(av), []):
        f = lem.get(eid, 0)
        if f > best: best = f
    return best
def word_freq(av):     return _wf(av, FREQ, LEMMA_FREQ)       # broad (ranking)
def everyday_freq(av): return _wf(av, EVERYDAY, EVERYDAY_LEMMA)  # spoken/narrative (gate)
EVERYDAY_MIN = 5       # a deck word must occur >= this in everyday text (else it's news-only formal)
# --- rarity: entries whose relevant sense is bookish/archaic/dialectal/etc. ---
RARE_RE = re.compile("книжн|устар|редк|поэт|диалект|религи|фольк|детск|бранн|пренебр")
LABELS = {}                       # (entry_id, sense_idx) -> labels_json  (sense_idx is 1-based!)
for eid, si, lab in cur.execute("SELECT entry_id, sense_idx, labels_json FROM senses"):
    LABELS[(eid, si)] = lab or ""
# palochka-PRESERVING key (so цӀакъ 'очень' != цакъ 'зубик' — avoid homonym mixups)
def kp(s):
    s = (s or "").lower()
    for v in "ӏІіIli": s = s.replace(v, "Ӏ")   # incl. Latin small i (from lowercased Latin-I palochka)
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
EX = {}          # eid -> [(av, ru, len), ...] shortest-first
for eid, av, ru in cur.execute("SELECT entry_id, av, ru FROM examples WHERE av IS NOT NULL AND ru IS NOT NULL"):
    e = clean_example(av, ru)
    if not e: continue
    EX.setdefault(eid, []).append(e)
for eid in EX: EX[eid].sort(key=lambda e: e[2])
_STOP = set("и в во на о об с к по за из у не что как для от до а но или это тебя его её их "
            "так все весь чем чём кого кому кто где чего либо кем чему бы же ли ни".split())
def _stems(text):
    import re as _re
    return {w[:4] for w in _re.findall(r"[а-яёӀ]+", (text or "").lower()) if len(w) >= 4 and w not in _STOP}
def pick_example(eid, ru=None):
    """From an entry's examples, prefer one whose gloss ACTUALLY illustrates the target
    meaning `ru` (shares a word-stem), so we don't show an idiom for a different sense
    (лицо→гьумер picked 'небеса'); fall back to the shortest."""
    exs = EX.get(eid)
    if not exs: return None
    if ru:
        want = _stems(ru)
        if want:
            for av, rg, ln in exs:                       # already shortest-first
                if _stems(rg) & want: return (av, rg, ln)
    return exs[0]

def eids_for(av, ru=None):
    """Entry ids for headword `av`, ORDERED so the homonym whose senses match the
    target meaning `ru` comes first. This is what makes examples/forms/senses
    sense-aware: e.g. ряд->кьер must use entry 9807 (ряд/строй), not 9804 (цвет),
    so we never show 'кьер ине = обесцвечиваться' as an example for 'ряд'."""
    ids = HWID_EXACT.get(kp(av), [])
    if not ru or len(ids) < 2:
        return ids
    rk = ru.lower().strip()
    exact, sub, rest = [], [], []
    for eid in ids:
        terms = set()
        txt = ""
        for si, g in SENSE.get(eid, []):
            gl = gloss_terms(g); terms |= set(gl); txt += " " + (g or "").lower()
        if rk in terms:        exact.append(eid)
        elif rk in txt:        sub.append(eid)
        else:                  rest.append(eid)
    return exact + sub + rest
def forms_of(av, ru=None):
    for eid in eids_for(av, ru):
        f = ENTRY_FORMS.get(eid)
        if f: return f[:6]
    return None
def example_of(av, ru=None):
    for eid in eids_for(av, ru):
        e = pick_example(eid, ru)
        if e: return {"av": e[0], "ru": e[1]}
    return None
def alt_obj(av, ru=None):  # a synonym carrying an example for THIS meaning
    o = {"av": normpal(av)}
    ex = example_of(av, ru)
    if ex: o["ex"] = {"av": normpal(ex["av"]), "ru": ex["ru"]}
    return o
def senses_of(av, ru=None):  # the word's OTHER meanings (of the matching homonym)
    order = eids_for(av, ru) if ru else sorted(
        HWID_EXACT.get(kp(av), []), key=lambda e: -LEMMA_FREQ.get(e, 0))
    for eid in order:
        ss = SENSE.get(eid)
        if not ss: continue
        out = []
        for si, g in ss:
            t = gloss_terms(g)
            if t: out.append(", ".join(t[:2]))
            if len(out) >= 4: break
        if len(out) >= 2: return out          # only worth showing if >1 meaning
        return None
    return None

# --- reverse index: russian word -> candidate Avar headwords (single word) ---
REV = {}
for hw, eid, ru in cur.execute(
        "SELECT e.headword, e.id, s.ru_text FROM senses s JOIN entries e ON s.entry_id=e.id WHERE s.ru_text IS NOT NULL"):
    if " " in hw or "-" in hw: continue
    for term in re.split(r"[;,.]", ru.lower()):
        term = term.strip()
        if term: REV.setdefault(term, set()).add(hw)

# set of Russian words (from all dictionary glosses) — to catch Avar "words" that
# are really Russian loans (автомобиль, машина, телефон…) regardless of their gloss.
RU_WORDS = set()
for _t, _hws in REV.items():
    for _w in _t.split():
        if len(_w) >= 5 and re.fullmatch(r"[а-яё]+", _w): RU_WORDS.add(_w)
def is_loan(av, ru):
    ak, rk = k(av), k(ru.lower())
    if not ak or not rk: return True
    if ak == rk: return True
    if NATIVE.search(av.lower()): return False       # has native letters -> genuine Avar
    # no native letters: a Russian loanword if it IS a Russian dictionary word (len>=5)
    if len(ak) >= 5 and av.lower() in RU_WORDS: return True
    cp = 0
    for a, b in zip(ak, rk):
        if a == b: cp += 1
        else: break
    if cp >= 4 or (ak.startswith(rk) or rk.startswith(ak)):
        return True
    return False

def gloss_terms(g):
    return [t.strip() for t in re.split(r"[;,]", (g or "").lower()) if t.strip()]

def valid_sense(av, ru):
    """True if `ru` is a genuine, non-deep, non-rare meaning of `av`.
    Gate: ru must appear as a gloss TERM within the first 2 senses and first 3 terms,
    in a sense not labelled bookish/archaic/dialectal. (Rejects deep-secondary junk like
    случай→хӀал, where случай is the 5th synonym of хӀал's 1st sense.)"""
    rk = ru.lower().strip()
    for eid in HWID.get(k(av), []):
        for pos_i, (si, g) in enumerate(SENSE.get(eid, [])):
            if pos_i > 1: break
            terms = gloss_terms(g)
            if rk not in terms: continue
            if terms.index(rk) > 2: continue
            if RARE_RE.search(LABELS.get((eid, si), "")): continue
            return (True, pos_i == 0 and terms.index(rk) == 0)
    return (False, False)

def score_av(av, ru):
    """Among words that genuinely mean `ru`, the EVERYDAY one = the most FREQUENT.
    Frequency is the primary signal; a word whose PRIMARY meaning is `ru` is strongly
    preferred over one where `ru` is a secondary sense — because for a secondary sense the
    broad corpus frequency is a LIE: it counts the word's dominant OTHER meaning, not this
    one (e.g. иргадулаб wf=251 is all 'очередной', its sense-2 'смерть' is near-zero; so it
    must not out-rank хвел for 'смерть'). Known everyday-secondary picks (шум→сас) use OVER."""
    ok, primary = valid_sense(av, ru)
    if not ok: return None
    ev = everyday_freq(av)
    if ev < EVERYDAY_MIN: return None                      # reject news-only formal words
    wf = word_freq(av)
    if not primary:
        # secondary-sense homonym: broad corpus freq measures the word's DOMINANT OTHER
        # meaning, not this one, so it must not out-rank a word whose PRIMARY sense is `ru`.
        # Cap the frequency signal, but keep it mild so real everyday secondaries survive
        # (verified homonym picks like шум→сас are pinned in OVER anyway).
        wf = min(wf, max(ev, 30))
    return wf + (4 if primary else 0) - max(0, len(av) - 10) * 0.3

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
    # primary: forced override / seed, else best scored. OVER/SEED are HAND-VERIFIED and
    # trusted absolutely — NOT run through is_loan (which false-positives on native/Arabic
    # words that happen to be Russian dictionary words too, e.g. 'мурад' is also a RU name,
    # so is_loan wrongly rejected the verified цель→мурад override).
    primary = OVER.get(ru_word) or SEED.get(ru_word)
    if not primary:
        if not scored: return None, []
        top = scored[0]
        # require the word to actually be USED in the corpus (drops rare literary Arabisms
        # like таварих=2, вилаят=1, машгъуллъизе=1). OVER/SEED words bypass this.
        if top[1] < 15: return None, []
        primary = top[2]
    # alternates: other common (freq>0) synonyms/senses, distinct from primary
    alts, seen = [], {kp(primary)}
    for s, fr, av in scored:
        if fr < 3: continue                # only reasonably-used synonyms
        if kp(av) in seen: continue
        seen.add(kp(av)); alts.append(alt_obj(av, ru_word))
        if len(alts) >= 2: break
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
        if kp(av) in seen_av: continue     # palochka-PRESERVING: хал(внимание) ≠ хӀал(состояние)
        seen_av.add(kp(av))
        entry = {"ru": ru, "av": av, "pos": pos}
        alts = alts[:2]
        if alts: entry["alts"] = alts
        fm = forms_of(av, ru)
        if fm and len(fm) > 1: entry["forms"] = [normpal(x) for x in fm]
        ex = example_of(av, ru)
        if ex: entry["ex"] = {"av": normpal(ex["av"]), "ru": ex["ru"]}
        sn = senses_of(av, ru)
        if sn: entry["senses"] = sn
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
# ---- manual native-speaker-preferred cards (inserted near the top) ----------
_have = {w["ru"] for w in deck}
_man = []
for ru, av in MANUAL.items():
    if ru in _have: continue
    e = {"ru": ru, "av": normpal(av), "pos": "?"}
    fm = forms_of(av, ru);  ex = example_of(av, ru);  sn = senses_of(av, ru)
    if fm and len(fm) > 1: e["forms"] = [normpal(x) for x in fm]
    if ex: e["ex"] = {"av": normpal(ex["av"]), "ru": ex["ru"]}
    if sn: e["senses"] = sn
    _man.append(e)
deck = deck[:60] + _man + deck[60:]      # place them in the common tier
# ---- supplement: fill with the most FREQUENT Avar words the RU->AV pass missed ----
# Robust to homonyms: aggregate corpus frequency PER HEADWORD (not per fragile entry),
# then pick that word's cleanest content sense, and DEDUP BY MEANING (so a rarer synonym
# of an already-present meaning is never added as its own card).
POSMAP = {"существительное":"nouns","глагол":"verbs","масдар":"verbs",
          "прилагательное":"adjs","наречие":"adverbs","имя числительное":"num"}
def pos_of(eid):
    for si in range(1, 8):
        for tok, p in POSMAP.items():
            if tok in LABELS.get((eid, si), ""): return p
    return None
FIRSTSENSE = {}
for eid, si, ru in cur.execute("SELECT entry_id, sense_idx, ru_text FROM senses ORDER BY entry_id, sense_idx"):
    if eid not in FIRSTSENSE and ru: FIRSTSENSE[eid] = (si, ru)
BADGLOSS = re.compile(r"(указыв|выступает|в сочетани|частиц|обознач|служит|^форма |в знач|грамматическ|Ⅰ|Ⅱ|Ⅲ)")
PREP = re.compile(r"^(в|во|на|от|под|из|у|к|за|по|с|со|об|при|о|до|над|через|около)\s")
# aggregate frequency per headword-key + list its entries
# (word_freq = max of base-token count and lemma count — the base form of common adverbs
#  like жаниб f=837 isn't always in the `forms` table, so LEMMA_FREQ alone undercounts them)
HK_FREQ, HK_EIDS, HEADWORD = {}, {}, {}
for hw, eid in cur.execute("SELECT headword, id FROM entries"):
    key = kp(hw)
    if key not in HK_FREQ: HK_FREQ[key] = word_freq(hw)
    HK_EIDS.setdefault(key, []).append((hw, eid))
    HEADWORD[eid] = hw
seen_all = {kp(w["av"]) for w in deck}
covered = {w["ru"].split(",")[0].strip() for w in deck}   # meanings already in the deck
SUPP_FLOOR = 40
supp = []
for key, fr in sorted(HK_FREQ.items(), key=lambda x: -x[1]):
    if fr < SUPP_FLOOR: break
    if key in seen_all or key in SUPP_DROP: continue
    chosen = None                                         # find this word's cleanest content sense
    for hw, eid in HK_EIDS[key]:
        if " " in hw or "-" in hw or hw in SUPP_DROP: continue
        p = pos_of(eid); fs = FIRSTSENSE.get(eid)
        if p is None or not fs: continue
        si, gloss = fs
        if RARE_RE.search(LABELS.get((eid, si), "")): continue
        terms = gloss_terms(gloss)
        if not terms or BADGLOSS.search(gloss): continue
        if p == "adverbs" and PREP.match(terms[0]): continue
        chosen = (hw, terms, p); break
    if not chosen: continue
    hw, terms, p = chosen
    if terms[0] in covered: continue                      # meaning already covered by a commoner word
    av = normpal(hw)
    if is_loan(av, terms[0]): continue
    if everyday_freq(av) < EVERYDAY_MIN: continue          # skip news-only formal words
    seen_all.add(key); covered.add(terms[0])
    entry = {"ru": ", ".join(terms[:2])[:32], "av": av, "pos": p}
    a2 = []
    for c in sorted(REV.get(terms[0], set()), key=lambda h: -word_freq(h)):
        if " " in c or "-" in c or kp(c) == key or word_freq(c) < 8: continue
        a2.append(alt_obj(c, terms[0]))
        if len(a2) >= 2: break
    if a2: entry["alts"] = a2
    fm = forms_of(av, terms[0])
    if fm and len(fm) > 1: entry["forms"] = [normpal(x) for x in fm]
    ex = example_of(av, terms[0])
    if ex: entry["ex"] = {"av": normpal(ex["av"]), "ru": ex["ru"]}
    sn = senses_of(av, terms[0])
    if sn: entry["senses"] = sn
    supp.append(entry)
print(f"supplement (frequent corpus words, meaning-deduped): +{len(supp)}")
deck = deck + supp

if os.environ.get("AUDIT"):
    with open(os.path.join(HERE, "audit.tsv"), "w", encoding="utf-8") as af:
        af.write("i\tru\tav\tpos\tev\twf\texample\tsenses\n")
        for i, w in enumerate(deck):
            av = w["av"]; ex = w.get("ex")
            af.write(f"{i}\t{w['ru']}\t{av}\t{w['pos']}\t{everyday_freq(av)}\t{word_freq(av)}\t"
                     f"{(ex['av']+' = '+ex['ru']) if ex else ''}\t{' | '.join(w.get('senses',[]))}\n")
    print("wrote audit.tsv")
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

# ---- enrichment map: forms/example/synonyms for EVERY Avar word (used to enrich
#      themed + lesson flashcards too, so no card is just a bare category tag) ----
ENRICH = {}
for eid, fr in sorted(LEMMA_FREQ.items(), key=lambda x: -x[1]):   # common entries win the key
    hw = HEADWORD.get(eid, "")
    if not hw or " " in hw or "-" in hw: continue
    key = kp(hw)
    if key in ENRICH: continue
    e = {}
    fm = ENTRY_FORMS.get(eid)
    if fm and len(fm) > 1: e["forms"] = [normpal(x) for x in fm[:6]]
    fs = FIRSTSENSE.get(eid)
    ex = pick_example(eid, fs[1] if fs else None)
    if ex: e["ex"] = {"av": normpal(ex[0]), "ru": ex[1]}
    if fs:
        terms = gloss_terms(fs[1])
        if terms:
            a = []
            for c in sorted(REV.get(terms[0], set()), key=lambda h: -word_freq(h)):
                if " " in c or "-" in c or kp(c) == key: continue
                if word_freq(c) < 4: continue
                a.append(alt_obj(c, terms[0]))
                if len(a) >= 2: break
            if a: e["alts"] = a
    if e: ENRICH[key] = e
json.dump(ENRICH, open(os.path.join(HERE, "data.enrich.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("enrichment entries:", len(ENRICH))
