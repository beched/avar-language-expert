#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-sort ARAB in arabisms.py by real corpus frequency and dump the counts.

Corpus: docs/hakikat.md + avar_wikipedia.md + avar_mats.md + hitinal_avaraze.md +
avarskiy_sokolenok_2024.md (~1.74M tokens). A card's count = sum of all tokens
that begin with its stem followed by an attested Avar case/derivation ending
(palochka-insensitive), so «халкъ» also collects халкъалъул, халкъалда, халкъал…

Usage:  python3 arab_freq.py            # report only
        python3 arab_freq.py --write    # rewrite arabisms.py in frequency order
                                        # + write arab_freq.tsv
"""
import collections, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DOCS = [
    "docs/hakikat.md", "docs/avar_wikipedia.md", "docs/avar_mats.md",
    "docs/hitinal_avaraze.md", "docs/avarskiy_sokolenok_2024.md",
]
SRC = os.path.join(HERE, "arabisms.py")

# case / number / derivation endings that may follow a nominal stem
SUF = re.compile(
    r"^(го|ул|уда|удаса|алъ|алъул|алъе|алъда|алъуб|алда|алде|алдаса|ал|аби|абаз|"
    r"абазул|ас|асул|асе|асда|аз|азул|азда|ялъ|ялъул|ялъе|ялда|дул|дуе|де|е|да|"
    r"лъ|лъул|лъун|лъи|лъизе|аб|ав|ай|зе|ун|ана|ила|улеб|ги|цин|хун|)$"
)


def norm(s):
    s = s.lower()
    for v in "ӏІіIli":          # every palochka spelling used in the sources
        s = s.replace(v, "Ӏ")
    return s


def corpus_counts():
    cnt = collections.Counter()
    for f in DOCS:
        path = os.path.join(ROOT, f)
        with open(path, encoding="utf-8", errors="ignore") as fh:
            cnt.update(re.findall(r"[а-яёӀ]+", norm(fh.read())))
    return cnt


def load_arab(src):
    ns = {}
    exec("ARAB = " + src.split("ARAB = ", 1)[1].split("\n]", 1)[0] + "\n]", ns)
    return ns["ARAB"]


def main():
    src = open(SRC, encoding="utf-8").read()
    arab = load_arab(src)
    cnt = corpus_counts()
    toks = list(cnt.items())
    freq = {}
    for e in arab:
        stem = norm(e[0])
        freq[e[0]] = sum(c for t, c in toks
                         if t.startswith(stem) and SUF.match(t[len(stem):]))

    old = {e[0]: i for i, e in enumerate(arab)}
    # ties keep the previous (hand-curated) relative order
    ordered = sorted(arab, key=lambda e: (-freq[e[0]], old[e[0]]))
    moved = sum(1 for i, e in enumerate(ordered) if old[e[0]] != i)
    print(f"{len(arab)} arabisms, {moved} change position")
    for e in ordered[:15]:
        print(f"  {e[0]:<14} {freq[e[0]]:>6}")

    if "--write" not in sys.argv:
        return
    def q(x):
        return "'" + x.replace("\\", "\\\\").replace("'", "\\'") + "'"

    body = "\n".join("  (" + ", ".join(q(x) for x in e) + ")," for e in ordered)
    head, tail = src.split("ARAB = [\n", 1)
    tail = tail.split("\n]", 1)[1]
    open(SRC, "w", encoding="utf-8").write(head + "ARAB = [\n" + body + "\n]" + tail)
    with open(os.path.join(HERE, "arab_freq.tsv"), "w", encoding="utf-8") as fh:
        fh.write("rank\tav\tcorpus_count\n")
        for i, e in enumerate(ordered):
            fh.write(f"{i}\t{e[0]}\t{freq[e[0]]}\n")
    print("rewrote arabisms.py + arab_freq.tsv")


if __name__ == "__main__":
    main()
