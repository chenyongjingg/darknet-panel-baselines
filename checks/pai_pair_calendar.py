# -*- coding: utf-8 -*-
"""Can the two markets be observed on the same day at all?

`C_same_first_date_share = 0.00` is only evidence against "simultaneous mirror"
if the two markets' crawl calendars actually overlap. If their row dates are
disjoint, same-day 0 is mechanical. This checks the calendars themselves.
"""
import collections
import csv
import gzip
import hashlib
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "_vendorlevel", "listings_full.tsv.gz")
OUT = os.path.join(HERE, "pai_pair_calendar.json")
PAIR = ("silkkitie", "valhalla")


def sha16(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()[:16]


days = {m: collections.Counter() for m in PAIR}
weeks = {m: set() for m in PAIR}
with gzip.open(SRC, "rt", encoding="utf-8", errors="replace", newline="") as fh:
    rd = csv.reader(fh, delimiter="\t")
    head = next(rd)
    im, idt = head.index("market"), head.index("date")
    for f in rd:
        if len(f) <= max(im, idt):
            continue
        m = f[im].strip().strip("\r")
        if m not in PAIR:
            continue
        d = f[idt].strip()[:10]
        days[m][d] += 1
        weeks[m].add(d[:4] + "W" + d[5:7])

ds = {m: set(days[m]) for m in PAIR}
inter = ds[PAIR[0]] & ds[PAIR[1]]
uni = ds[PAIR[0]] | ds[PAIR[1]]
out = {
    "src_sha16": sha16(SRC),
    "distinct_days": {m: len(ds[m]) for m in PAIR},
    "shared_days": len(inter),
    "union_days": len(uni),
    "jaccard_days": len(inter) / float(len(uni)),
    "days_min_max": {m: [min(ds[m]), max(ds[m])] for m in PAIR},
    "shared_days_first10": sorted(inter)[:10],
    "shared_days_last5": sorted(inter)[-5:],
    "rows_on_shared_days": {m: sum(days[m][d] for d in inter) for m in PAIR},
    "distinct_yearmonths": {m: len({d[:7] for d in ds[m]}) for m in PAIR},
}
with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2)[:1200])
