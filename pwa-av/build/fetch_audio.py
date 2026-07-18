#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch IPA phoneme audio samples from Wikimedia Commons for the Avar alphabet,
transcode to mp3 (iOS-safe), and write ../audio/<slug>.mp3 + audio_manifest.json.

For each Avar letter we give a prioritized list of candidate Commons file titles.
The MediaWiki imageinfo API returns the real upload URL for the first title that
exists; we download it and transcode with ffmpeg. Missing ones are logged.
"""
import json, os, subprocess, sys, time, urllib.parse, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.normpath(os.path.join(HERE, "..", "audio"))
os.makedirs(AUDIO, exist_ok=True)
API = "https://commons.wikimedia.org/w/api.php"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

# letter -> (slug, ipa, [candidate Commons file titles best-first])
LETTERS = [
    ("а",  "a",   "a",     ["Open front unrounded vowel.ogg", "Open central unrounded vowel.ogg"]),
    ("е",  "e",   "e",     ["Close-mid front unrounded vowel.ogg", "Mid front unrounded vowel.ogg"]),
    ("и",  "i",   "i",     ["Close front unrounded vowel.ogg"]),
    ("о",  "o",   "o",     ["Close-mid back rounded vowel.ogg", "Mid back rounded vowel.ogg"]),
    ("у",  "u",   "u",     ["Close back rounded vowel.ogg"]),
    ("б",  "b",   "b",     ["Voiced bilabial plosive.ogg", "Voiced bilabial stop.ogg"]),
    ("п",  "p",   "p",     ["Voiceless bilabial plosive.ogg", "Voiceless bilabial stop.ogg"]),
    ("д",  "d",   "d",     ["Voiced alveolar plosive.ogg", "Voiced alveolar stop.ogg"]),
    ("т",  "t",   "t",     ["Voiceless alveolar plosive.ogg", "Voiceless alveolar stop.ogg"]),
    ("г",  "g",   "ɡ",     ["Voiced velar plosive.ogg", "Voiced velar stop.ogg"]),
    ("к",  "k",   "k",     ["Voiceless velar plosive.ogg", "Voiceless velar stop.ogg"]),
    ("м",  "m",   "m",     ["Bilabial nasal.ogg"]),
    ("н",  "n",   "n",     ["Alveolar nasal.ogg", "Dental and alveolar nasal.ogg"]),
    ("р",  "r",   "r",     ["Alveolar trill.ogg", "Dental and alveolar trill.ogg"]),
    ("л",  "l",   "l",     ["Alveolar lateral approximant.ogg", "Dental and alveolar lateral approximant.ogg"]),
    ("в",  "w",   "w",     ["Voiced labial-velar approximant.ogg", "Voiced labiovelar approximant.ogg"]),
    ("й",  "j",   "j",     ["Palatal approximant.ogg"]),
    ("с",  "s",   "s",     ["Voiceless alveolar sibilant.ogg", "Voiceless alveolar fricative.ogg"]),
    ("з",  "z",   "z",     ["Voiced alveolar sibilant.ogg", "Voiced alveolar fricative.ogg"]),
    ("ш",  "sh",  "ʃ",     ["Voiceless palato-alveolar sibilant.ogg", "Voiceless postalveolar fricative.ogg"]),
    ("ж",  "zh",  "ʒ",     ["Voiced palato-alveolar sibilant.ogg", "Voiced postalveolar fricative.ogg"]),
    ("ц",  "ts",  "t͡s",    ["Voiceless alveolar sibilant affricate.ogg", "Voiceless alveolar affricate.ogg"]),
    ("ч",  "ch",  "t͡ʃ",    ["Voiceless palato-alveolar affricate.ogg", "Voiceless postalveolar affricate.ogg"]),
    # Avar-specific / harder sounds
    ("гъ", "gh",  "ʁ",     ["Voiced uvular fricative.ogg"]),
    ("гь", "h",   "h",     ["Voiceless glottal fricative.ogg", "Voiceless glottal transition.ogg"]),
    ("гӀ", "gI",  "ʕ",     ["Voiced pharyngeal fricative.ogg", "Voiced pharyngeal approximant.ogg"]),
    ("хӀ", "hI",  "ħ",     ["Voiceless pharyngeal fricative.ogg"]),
    ("х",  "kh",  "χ",     ["Voiceless uvular fricative.ogg"]),
    ("хь", "hy",  "x",     ["Voiceless velar fricative.ogg"]),
    ("хъ", "qh",  "q͡χː",   ["Voiceless uvular plosive.ogg", "Voiceless uvular stop.oga"]),
    ("къ", "qI",  "qχʼ",   ["Uvular ejective.ogg", "Uvular ejective stop.ogg", "Voiceless uvular plosive.ogg"]),
    ("кӀ", "kI",  "kʼ",    ["Velar ejective.ogg", "Velar ejective stop.ogg"]),
    ("тӀ", "tI",  "tʼ",    ["Alveolar ejective.ogg", "Alveolar ejective stop.ogg"]),
    ("цӀ", "tsI", "t͡sʼ",   ["Alveolar ejective sibilant affricate.ogg", "Alveolar ejective affricate.ogg", "Ejective alveolar sibilant affricate.ogg"]),
    ("чӀ", "chI", "t͡ʃʼ",   ["Palato-alveolar ejective affricate.ogg", "Postalveolar ejective affricate.ogg"]),
    ("лъ", "lh",  "ɬ",     ["Voiceless alveolar lateral fricative.ogg", "Voiceless dental and alveolar lateral fricative.ogg"]),
    ("лӀ", "lhI", "t͡ɬː",   ["Voiceless alveolar lateral affricate.ogg"]),
    ("кь", "kkh", "t͡ɬʼː",  ["Alveolar lateral ejective affricate.ogg"]),
    ("ъ",  "q",   "ʔ",     ["Glottal stop.ogg"]),
]

def _get(url, timeout):
    """GET with retry/backoff on 429 and transient errors."""
    for attempt in range(10):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                "Accept": "*/*", "Referer": "https://commons.wikimedia.org/"})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(30, 4 * (attempt + 1))
                print(f"  429, sleeping {wait}s", file=sys.stderr); time.sleep(wait); continue
            raise
        except Exception:
            time.sleep(1.5); continue
    raise RuntimeError("giving up: " + url)

def api_url(title):
    q = {"action": "query", "format": "json", "prop": "imageinfo",
         "iiprop": "url|mime", "titles": "File:" + title}
    data = json.loads(_get(API + "?" + urllib.parse.urlencode(q), 30))
    time.sleep(2.5)  # be polite to the API
    pages = data.get("query", {}).get("pages", {})
    for _, p in pages.items():
        if "missing" in p:
            continue
        ii = p.get("imageinfo")
        if ii:
            return ii[0]["url"]
    return None

def download(url, dst):
    with open(dst, "wb") as f:
        f.write(_get(url, 60))

manifest = {}
missing = []
for letter, slug, ipa, cands in LETTERS:
    mp3done = os.path.join(AUDIO, slug + ".mp3")
    if os.path.exists(mp3done) and os.path.getsize(mp3done) > 500:
        manifest[letter] = {"file": "audio/" + slug + ".mp3", "ipa": ipa, "src": cands[0]}
        print(f"skip {letter} (exists)", file=sys.stderr); continue
    time.sleep(10)  # pace per-letter to avoid sustained rate limiting
    got = None
    src_title = None
    for title in cands:
        try:
            url = api_url(title)
        except Exception as e:
            print(f"  api err {title}: {e}", file=sys.stderr); continue
        if url:
            got = url; src_title = title; break
    if not got:
        print(f"MISSING {letter} ({ipa}) tried {cands}", file=sys.stderr)
        missing.append(letter); continue
    time.sleep(4)  # space out download requests
    ext = os.path.splitext(got)[1].lower() or ".ogg"
    tmp = os.path.join(AUDIO, "_tmp" + ext)
    mp3 = os.path.join(AUDIO, slug + ".mp3")
    try:
        download(got, tmp)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp,
                        "-ac", "1", "-ar", "44100", "-b:a", "96k", mp3], check=True)
        os.remove(tmp)
        manifest[letter] = {"file": "audio/" + slug + ".mp3", "ipa": ipa, "src": src_title}
        print(f"OK  {letter:3s} {ipa:6s} <- {src_title}", file=sys.stderr)
    except Exception as e:
        print(f"FAIL {letter} {e}", file=sys.stderr); missing.append(letter)
        if os.path.exists(tmp): os.remove(tmp)

with open(os.path.join(HERE, "audio_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)
print(f"\nDONE {len(manifest)} ok, {len(missing)} missing: {missing}", file=sys.stderr)
