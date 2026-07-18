#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate app icons: dark rounded tile, snowy mountains, palochka accent."""
from PIL import Image, ImageDraw, ImageFont
import os
OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

def icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded background gradient-ish (two stacked rects)
    r = int(size * 0.22)
    d.rounded_rectangle([0, 0, size, size], radius=r, fill=(26, 42, 63))
    d.rounded_rectangle([0, int(size*0.5), size, size], radius=r, fill=(26, 36, 51))
    # sun
    d.ellipse([size*0.60, size*0.16, size*0.60+size*0.16, size*0.16+size*0.16], fill=(243, 177, 58))
    # mountains
    s = size
    d.polygon([(s*0.05,s*0.78),(s*0.34,s*0.40),(s*0.60,s*0.78)], fill=(87,168,255))
    d.polygon([(s*0.40,s*0.80),(s*0.68,s*0.34),(s*0.98,s*0.80)], fill=(51,198,125))
    # snow caps
    d.polygon([(s*0.34,s*0.40),(s*0.27,s*0.49),(s*0.34,s*0.47),(s*0.41,s*0.49)], fill=(255,255,255))
    d.polygon([(s*0.68,s*0.34),(s*0.60,s*0.45),(s*0.68,s*0.42),(s*0.76,s*0.45)], fill=(255,255,255))
    # ground line
    d.rectangle([0, int(s*0.80), s, int(s*0.83)], fill=(20, 28, 40))
    # palochka accent "Ӏ" as a small red bar bottom-left
    bw = max(2, int(s*0.03))
    d.rectangle([s*0.12, s*0.86, s*0.12+bw, s*0.94], fill=(239, 84, 102))
    return img

for sz, name in [(192, "icon-192.png"), (512, "icon-512.png"), (180, "icon-180.png")]:
    icon(sz).save(os.path.join(OUT, name))
    print("wrote", name)
