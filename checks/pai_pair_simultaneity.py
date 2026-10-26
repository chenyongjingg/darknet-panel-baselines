# -*- coding: utf-8 -*-
"""Are the 5,922 shared slots ever observed in BOTH markets on the SAME day?

The calendar check (`pai_pair_calendar.py`) shows the two markets' crawl windows
overlap on only 9 of 189 days, so "same-day first occurrence = 0" is weak. This
script asks the direct question on the level of the slots themselves:
  - did any shared hash have rows in both markets on the same calendar day?
  - is silkkitie's last day strictly before valhalla's first day (succession)?
  - or do the two observation intervals overlap without a same-day hit?
"""
import collections
import csv
import datetime
import gzip
import hashlib
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "_vendorlevel", "listings_full.tsv.gz")
OUT = os.path.join(HERE, "pai_pair_simultaneity.json")
PAIR = ("silkkitie", "valhalla")


def sha16(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()[:16]


D = {}
with gzip.open(SRC, "rt", encoding="utf-8", errors="replace", newline="") as fh:
    rd = csv.reader(fh, delimiter="\t")
    head = next(rd)
    im, ih, idt = head.index("market"), head.index("hash"), head.index("date")
    for f in rd:
        if len(f) <= max(im, ih, idt):
            continue
        m = f[im].strip().strip("\r")
        if m not in PAIR:
            continue
        h = f[ih].strip()
        if not h:
            continue
        d = f[idt].strip()[:10]
        per = D.setdefault(h, {})
        s = per.get(m)
        if s is None:
            per[m] = {d}
        else:
            s.add(d)

cross = [h for h, per in D.items() if len(per) == 2]
same_day = 0
succ = 0
abut = 0
rev = 0
for h in cross:
    a = D[h][PAIR[0]]
    b = D[h][PAIR[1]]
    if a & b:
        same_day += 1
        continue
    if max(a) < min(b):
        succ += 1
    elif max(b) < min(a):
        rev += 1
    else:
        abut += 1

out = {
    "src_sha16": sha16(SRC),
    "cross_market_hashes": len(cross),
    "both_markets_same_day": same_day,
    "both_markets_same_day_share": same_day / float(len(cross)),
    "silkkitie_strictly_before_valhalla": succ,
    "valhalla_strictly_before_silkkitie": rev,
    "intervals_overlap_without_same_day": abut,
    "gates": {"cross": 5922},
    "gate_ok": len(cross) == 5922,
}
with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
