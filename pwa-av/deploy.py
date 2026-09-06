#!/usr/bin/env python3
"""Copy the built PWA to the repo root, which is what GitHub Pages serves.

Pages is configured as "main / root", and the app's public URL is the site root
(https://beched.github.io/avar-language-expert/) -- not /pwa-av/. Keeping the
copy at the root preserves that URL, so Home-Screen installs and the registered
service worker scope keep working. Sources stay in pwa-av/.

Run after build.py:  python3 pwa-av/deploy.py
"""
import filecmp, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = HERE
DST = os.path.dirname(HERE)

FILES = ["index.html", "sw.js", "manifest.json",
         "icon-180.png", "icon-192.png", "icon-512.png"]

changed = []
for f in FILES:
    s, d = os.path.join(SRC, f), os.path.join(DST, f)
    if not os.path.exists(d) or not filecmp.cmp(s, d, shallow=False):
        shutil.copy2(s, d)
        changed.append(f)

src_audio, dst_audio = os.path.join(SRC, "audio"), os.path.join(DST, "audio")
os.makedirs(dst_audio, exist_ok=True)
for f in sorted(os.listdir(src_audio)):
    if not f.endswith(".mp3"):
        continue
    s, d = os.path.join(src_audio, f), os.path.join(dst_audio, f)
    if not os.path.exists(d) or not filecmp.cmp(s, d, shallow=False):
        shutil.copy2(s, d)
        changed.append(f"audio/{f}")
# drop audio the build no longer ships, so the precache list can't go stale
for f in sorted(os.listdir(dst_audio)):
    if f.endswith(".mp3") and not os.path.exists(os.path.join(src_audio, f)):
        os.remove(os.path.join(dst_audio, f))
        changed.append(f"-audio/{f}")

nj = os.path.join(DST, ".nojekyll")
if not os.path.exists(nj):
    open(nj, "w").close()
    changed.append(".nojekyll")

print(f"deployed to repo root: {len(changed)} file(s) updated"
      + (f" ({', '.join(changed[:6])}{'…' if len(changed) > 6 else ''})" if changed else ""))
