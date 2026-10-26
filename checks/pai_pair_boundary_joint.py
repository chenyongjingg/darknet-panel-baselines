# -*- coding: utf-8 -*-
"""Joint (s_last, v_first) table for the 5,922 cross-label slots.

`pai_pair_boundary.py` prints the marginal top days: 5,385 slots have
s_last = 2015-11-26 and 5,385 slots have v_first = 2015-11-27. Equal marginals
do NOT prove it is the same 5,385 slots. This instrument prints the JOINT count,
so the sentence "these slots switched label overnight" is a measured cell and
not an inference from two marginals.

Also counts, for each of the 5,922: how many other markets (outside the pair)
hold the same hash — this is the direct check behind "the panel has no other
pair of distinct markets with linkable hashes".
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
WHITE = os.path.join(ROOT, "_vendorlevel", "18_market_strings.csv")
CAL = os.path.join(HERE, "pai_pair_calendar.json")
OUT = os.path.join(HERE, "pai_pair_boundary_joint.json")
PAIR = ("silkkitie", "valhalla")


def sha16(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()[:16]


cal = json.load(io.open(CAL, encoding="utf-8"))
LAUNCH = datetime.date(*[int(x) for x in cal["days_min_max"][PAIR[1]][0].split("-")])

white = set()
with io.open(WHITE, encoding="utf-8", newline="") as fh:
    for r in csv.DictReader(fh):
        if r.get("whitelisted", "").strip() == "1":
            white.add(r["market_string"].strip())
assert len(white) == 26

# h -> m -> [first_date, last_date]   (whitelist only, so the domain matches
# pai_pair_handover_opportunity.py: 26 markets / 5,922 cross hashes)
D = {}
with gzip.open(SRC, "rt", encoding="utf-8", errors="replace", newline="") as fh:
    rd = csv.reader(fh, delimiter="\t")
    head = next(rd)
    im, ih, idt = head.index("market"), head.index("hash"), head.index("date")
    for f in rd:
        if len(f) <= max(im, ih, idt):
            continue
        m = f[im].strip().strip("\r")
        if m not in white:
            continue
        h = f[ih].strip()
        if not h:
            continue
        d = f[idt].strip()[:10]
        try:
            dt = datetime.date(*[int(x) for x in d.split("-")])
        except Exception:
            continue
        cur = D.setdefault(h, {}).get(m)
        if cur is None:
            D[h][m] = [dt, dt]
        else:
            if dt < cur[0]:
                cur[0] = dt
            if dt > cur[1]:
                cur[1] = dt

cross = [h for h, per in D.items() if PAIR[0] in per and PAIR[1] in per]
assert len(cross) == 5922, len(cross)

joint = collections.Counter()
n_launch_eve = 0      # s_last == LAUNCH-1 and v_first == LAUNCH
n_other_pair = 0      # hash also present in a market outside the pair
other_market_touch = collections.Counter()
for h in cross:
    s_first, s_last = D[h][PAIR[0]]
    v_first, v_last = D[h][PAIR[1]]
    joint[(s_last.isoformat(), v_first.isoformat())] += 1
    if (LAUNCH - s_last).days == 1 and (v_first - LAUNCH).days == 0:
        n_launch_eve += 1
    extra = [m for m in D[h] if m not in PAIR]
    if extra:
        n_other_pair += 1
        for m in extra:
            other_market_touch[m] += 1

top = joint.most_common(6)
out = {
    "src_sha16": sha16(SRC),
    "valhalla_launch": LAUNCH.isoformat(),
    "cross_market_hashes": len(cross),
    "joint_launch_eve_to_launch_day": n_launch_eve,
    "joint_launch_eve_to_launch_share": n_launch_eve / float(len(cross)),
    "joint_top": [[a, b, c] for (a, b), c in top],
    "hashes_also_in_a_third_market": n_other_pair,
    "third_market_touch_top": other_market_touch.most_common(5),
    "gates": {"cross": 5922},
    "gate_ok": len(cross) == 5922,
}
with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
