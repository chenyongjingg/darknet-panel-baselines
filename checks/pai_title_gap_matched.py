# -*- coding: utf-8 -*-
"""Same-market title change at ~9 days of exposure — the missing cell.

The cross-market pairing compares each slot's first silkkitie title with its
first valhalla title at a median first-date gap of 9 days (10.11% differ).
C2 (3 days) and C1 (42 days) bracket 9 days but do not sit on it, so any
"less durable" claim mixes market identity with exposure length.

This instrument puts a same-market point ON the 9-day axis:
for every (hash, market) with >=2 observations, take the first observation and
the observation closest to +9 days, and ask whether its title differs.

Same denominator as C1/C2 (all (hash, market) pairs with >=2 distinct dates),
so 3 / 9 / 42 days become one exposure-response curve on one axis.

Three windows are reported so the choice of the +-2 day band is not load-bearing:
strict 8-10, main 6-12, wide 4-14.
"""
import collections
import csv
import datetime
import gzip
import hashlib
import io
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "_vendorlevel", "listings_full.tsv.gz")
WHITE = os.path.join(ROOT, "_vendorlevel", "18_market_strings.csv")
OUT = os.path.join(HERE, "pai_title_gap_matched.json")
PAIR = ("silkkitie", "valhalla")
WINDOWS = {"strict_8_10": (8, 10), "main_6_12": (6, 12), "wide_4_14": (4, 14)}


def sha16(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()[:16]


def norm(t):
    return " ".join(t.strip().lower().split())


white = set()
with io.open(WHITE, encoding="utf-8", newline="") as fh:
    for r in csv.DictReader(fh):
        if r.get("whitelisted", "").strip() == "1":
            white.add(r["market_string"].strip())
assert len(white) == 26

# ---------- pass 1: first date / first title per (hash, market) ----------
# NOTE 11:50 — eligibility must use the SAME domain as C2/C1, which require
# >=2 distinct ISO WEEKS (32,006 pairs). Counting >=2 distinct DATES gives
# 33,442 and would make the three points sit on different denominators.
first = {}
distinct_dates = collections.Counter()
distinct_weeks = collections.defaultdict(set)
with gzip.open(SRC, "rt", encoding="utf-8", errors="replace", newline="") as fh:
    rd = csv.reader(fh, delimiter="\t")
    head = next(rd)
    im, ih, it, idt = (head.index("market"), head.index("hash"),
                       head.index("title"), head.index("date"))
    for f in rd:
        if len(f) <= max(im, ih, it, idt):
            continue
        m = f[im].strip().strip("\r")
        if m not in PAIR:
            continue
        h = f[ih].strip()
        if not h:
            continue
        d = f[idt].strip()[:10]
        try:
            dt = datetime.date(*[int(x) for x in d.split("-")])
        except Exception:
            continue
        k = (h, m)
        cur = first.get(k)
        if cur is None:
            first[k] = [dt, norm(f[it])]
            distinct_dates[k] = {dt}
        else:
            distinct_dates[k].add(dt)
            if dt < cur[0]:
                first[k] = [dt, norm(f[it])]
        distinct_weeks[k].add(dt.isocalendar()[:2])

eligible = {k for k, ws in distinct_weeks.items() if len(ws) >= 2}
n_dates_2plus = sum(1 for k, ds in distinct_dates.items() if len(ds) >= 2)

# ---------- pass 2: observation closest to +9 days ----------
best = {w: {} for w in WINDOWS}  # window -> k -> (abs(delta-9), delta, title)

with gzip.open(SRC, "rt", encoding="utf-8", errors="replace", newline="") as fh:
    rd = csv.reader(fh, delimiter="\t")
    head = next(rd)
    im, ih, it, idt = (head.index("market"), head.index("hash"),
                       head.index("title"), head.index("date"))
    for f in rd:
        if len(f) <= max(im, ih, it, idt):
            continue
        m = f[im].strip().strip("\r")
        if m not in PAIR:
            continue
        h = f[ih].strip()
        k = (h, m)
        if k not in eligible:
            continue
        d = f[idt].strip()[:10]
        try:
            dt = datetime.date(*[int(x) for x in d.split("-")])
        except Exception:
            continue
        delta = (dt - first[k][0]).days
        for w, (lo, hi) in WINDOWS.items():
            if lo <= delta <= hi:
                cand = (abs(delta - 9), delta, norm(f[it]))
                cur = best[w].get(k)
                if cur is None or cand[:2] < cur[:2]:
                    best[w][k] = cand

out = {
    "src_sha16": sha16(SRC),
    "pair": list(PAIR),
    "eligible_pairs_2plus_weeks": len(eligible),
    "pairs_with_2plus_distinct_dates": n_dates_2plus,
    "windows": {},
    "gates": {"eligible": 32006},
    "gate_ok": None,
}
for w in WINDOWS:
    n = chg = 0
    gaps = []
    for k, (_, delta, title) in best[w].items():
        n += 1
        chg += title != first[k][1]
        gaps.append(delta)
    gaps.sort()
    out["windows"][w] = {
        "n": n,
        "changed": chg,
        "share": chg / float(n) if n else None,
        "gap_median": statistics.median(gaps) if gaps else None,
        "gap_p10": gaps[int(0.1 * (len(gaps) - 1))] if gaps else None,
        "gap_p90": gaps[int(0.9 * (len(gaps) - 1))] if gaps else None,
    }

out["gate_ok"] = len(eligible) == 32006
with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
