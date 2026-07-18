#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch the still-missing special sounds via curl + Commons md5 hashed paths
(no API), one at a time with generous gaps to stay under the rate limit.
"""
import hashlib, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.normpath(os.path.join(HERE, "..", "audio"))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

# slug -> [candidate Commons filenames best-first]
MISSING = {
 "hI":  ["Voiceless pharyngeal fricative.ogg"],
 "kh":  ["Voiceless uvular fricative.ogg"],
 "hy":  ["Voiceless velar fricative.ogg"],
 "kI":  ["Velar ejective.ogg", "Velar ejective stop.ogg", "Voiceless velar ejective.ogg"],
 "tI":  ["Alveolar ejective.ogg", "Alveolar ejective stop.ogg", "Voiceless alveolar ejective.ogg"],
 "tsI": ["Alveolar ejective affricate.ogg", "Ejective alveolar sibilant affricate.ogg",
         "Alveolar sibilant ejective affricate.ogg"],
 "chI": ["Palato-alveolar ejective affricate.ogg", "Postalveolar ejective affricate.ogg",
         "Voiceless palato-alveolar ejective affricate.ogg"],
 "lh":  ["Voiceless alveolar lateral fricative.ogg"],
 "lhI": ["Voiceless alveolar lateral affricate.ogg", "Alveolar lateral affricate.ogg"],
 "kkh": ["Alveolar lateral ejective affricate.ogg", "Voiceless alveolar lateral ejective affricate.ogg"],
 "q":   ["Glottal stop.ogg"],
}

def url_for(fname):
    f = fname.replace(" ", "_")
    f = f[0].upper() + f[1:]
    h = hashlib.md5(f.encode("utf-8")).hexdigest()
    return "https://upload.wikimedia.org/wikipedia/commons/%s/%s/%s" % (h[0], h[:2], f)

def curl(url, dst):
    r = subprocess.run(["curl", "-s", "-L", "-A", UA, "-o", dst, "-w", "%{http_code}", url],
                       capture_output=True, text=True)
    return r.stdout.strip()

got, miss = [], []
for slug, cands in MISSING.items():
    dst_mp3 = os.path.join(AUDIO, slug + ".mp3")
    if os.path.exists(dst_mp3) and os.path.getsize(dst_mp3) > 500:
        got.append(slug); continue
    ok = False
    for fname in cands:
        tmp = os.path.join(AUDIO, "_c.ogg")
        code = curl(url_for(fname), tmp)
        if code == "200" and os.path.exists(tmp) and os.path.getsize(tmp) > 800:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp,
                            "-ac", "1", "-ar", "44100", "-b:a", "96k", dst_mp3], check=True)
            os.remove(tmp)
            print("OK  %-4s <- %s" % (slug, fname), flush=True)
            got.append(slug); ok = True; break
        else:
            print("  %s -> %s (%s)" % (slug, fname, code), flush=True)
            if os.path.exists(tmp): os.remove(tmp)
            time.sleep(8)   # gap between candidate attempts
    if not ok:
        miss.append(slug)
    time.sleep(22)          # generous gap between letters
print("\nGOT:", got, "\nSTILL MISSING:", miss, flush=True)
