# -*- coding: utf-8 -*-
"""Domain-matched control for the 89.89% cross-market title-equality share.

The 8.70% same-market figure in `pai_title_equality_v3.py` has a DIFFERENT
domain from the 89.89%: the latter compares the first title seen in market A
against the first title seen in market B (no week alignment), the former counts
ANY later row in the same market that carries a different title (whole panel).
Its complement 91.30% is therefore NOT a "same-market stability rate".

This script builds comparators on the SAME denominator:

  A. the 5,922 cross-market hashes, checked for a title change *within* each of
     the two markets (matched denominator);
  B. all hashes present in >=2 distinct ISO weeks of one market, two exposures:
     C2 = earliest week vs next distinct week (minimum exposure),
     C1 = earliest week vs latest week (maximum exposure);
  C. the exposure on the cross side: first-date gap between the two markets.

Gates reproduce `pai_title_equality_v3.json` (5,922 cross / 5,323 equal).
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
OUT = os.path.join(HERE, "pai_title_within_pair_v2.json")
PAIR = ("silkkitie", "valhalla")


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
assert len(white) == 26, len(white)

# h -> m -> [first_week, first_title, second_week, second_title,
#            last_week, last_title, first_date_ord, last_date_ord]
S = {}
rows = 0

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
        rows += 1
        d = f[idt].strip()
        try:
            y, mm, dd = (int(x) for x in d[:10].split("-"))
            dt = datetime.date(y, mm, dd)
        except Exception:
            continue
        w = dt.isocalendar()[:2]
        t = norm(f[it])
        per = S.setdefault(h, {})
        cur = per.get(m)
        if cur is None:
            per[m] = [w, t, None, None, w, t, dt, dt, None, None]
            continue
        fw, ft, sw, st, lw, lt, fdo, ldo, sdo, _ = cur
        if w < fw:
            sw, st, sdo = fw, ft, fdo
            fw, ft, fdo = w, t, dt
        elif w > fw and (sw is None or w < sw):
            sw, st, sdo = w, t, dt
        if w > lw:
            lw, lt, ldo = w, t, dt
        cur[0], cur[1], cur[2], cur[3], cur[4], cur[5], cur[6], cur[7], cur[8] = (
            fw, ft, sw, st, lw, lt, fdo, ldo, sdo)

cross = sorted(h for h, per in S.items() if len(per) == 2)
eq = sum(1 for h in cross if S[h][PAIR[0]][1] == S[h][PAIR[1]][1])

# A. matched denominator: within-market change among the cross hashes
chg_cross = 0
by_market = collections.Counter()
for h in cross:
    hit = False
    for m in PAIR:
        fw, ft, sw, st, lw, lt, _, _, _, _ = S[h][m]
        if (st is not None and st != ft) or lt != ft:
            hit = True
            by_market[m] += 1
    if hit:
        chg_cross += 1

# B. same-market controls over (hash, market) with >=2 distinct weeks
c2_n = c2_chg = c1_n = c1_chg = 0
c2_gaps = []
c1_gaps = []
for h, per in S.items():
    for m, (fw, ft, sw, st, lw, lt, fdo, ldo, sdo, _) in per.items():
        if sw is None:
            continue
        c2_n += 1
        c2_chg += st != ft
        c1_n += 1
        c1_chg += lt != ft
        c2_gaps.append((sdo - fdo).days)
        c1_gaps.append((ldo - fdo).days)
c2_gaps.sort()
c1_gaps.sort()

# C. cross-side exposure: days between the first occurrence in each market
gaps = [abs((S[h][PAIR[0]][6] - S[h][PAIR[1]][6]).days) for h in cross]
gaps.sort()
same_day = sum(1 for g in gaps if g == 0)
same_week = sum(1 for h in cross
                if S[h][PAIR[0]][0] == S[h][PAIR[1]][0])

out = {
    "src_sha16": sha16(SRC),
    "rows_in_pair": rows,
    "hashes_any": len(S),
    "cross_market_hashes": len(cross),
    "cross_title_exact_eq": eq,
    "cross_title_exact_eq_share": eq / float(len(cross)),
    "A_within_market_change_among_cross": chg_cross,
    "A_within_market_change_among_cross_share": chg_cross / float(len(cross)),
    "A_by_market": dict(by_market),
    "B_C2_first_vs_next_week_n": c2_n,
    "B_C2_first_vs_next_week_chg": c2_chg,
    "B_C2_share": c2_chg / float(c2_n),
    "B_C2_gap_days_median": statistics.median(c2_gaps),
    "B_C2_gap_days_p90": c2_gaps[int(0.9 * (len(c2_gaps) - 1))],
    "B_C1_gap_days_median": statistics.median(c1_gaps),
    "B_C1_gap_days_p90": c1_gaps[int(0.9 * (len(c1_gaps) - 1))],
    "B_C1_first_vs_last_week_n": c1_n,
    "B_C1_first_vs_last_week_chg": c1_chg,
    "B_C1_share": c1_chg / float(c1_n),
    "C_first_date_gap_median_days": statistics.median(gaps),
    "C_first_date_gap_p90_days": gaps[int(0.9 * (len(gaps) - 1))],
    "C_first_date_gap_max_days": gaps[-1],
    "C_same_first_date_share": same_day / float(len(gaps)),
    "C_same_first_week_share": same_week / float(len(gaps)),
    "gates": {"cross": 5922, "eq": 5323},
    "gate_ok": len(cross) == 5922 and eq == 5323,
}

with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)

print("rows_in_pair", rows, "hashes", len(S), "cross", len(cross), "eq", eq)
print("A within-market change among %d cross hashes: %d (%.4f)"
      % (len(cross), chg_cross, chg_cross / float(len(cross))))
print("B C2 first vs next week: %d/%d = %.4f" % (c2_chg, c2_n, c2_chg / float(c2_n)))
print("B C1 first vs last week: %d/%d = %.4f" % (c1_chg, c1_n, c1_chg / float(c1_n)))
print("C gap median %s days, same-day %.4f, same-week %.4f"
      % (statistics.median(gaps), same_day / float(len(gaps)), same_week / float(len(gaps))))
print("GATES", out["gate_ok"])
