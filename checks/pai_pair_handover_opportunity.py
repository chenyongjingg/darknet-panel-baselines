# -*- coding: utf-8 -*-
"""Opportunity structure for the "5,922/5,922 strict handover" statement.

The peer's objection: with two crawl windows that overlap on only 9 of 189 days,
an ordering of 100% could be produced by the calendar alone, not by behaviour.
The right test is to count, per shared slot, whether an alternative arrangement
was even possible:

  launch      = the first date valhalla has any row (read from the calendar JSON)
  s_last      = the slot's last observation in silkkitie
  v_first     = the slot's first observation in valhalla
  opportunity = s_last >= v_first      (a same-day or reverse arrangement could occur)
  reverse     = v_last <  s_first

If `s_last < launch` for essentially every slot, then the slot went silent in A
*before B existed*, and the 100% ordering is a calendar fact, not a behavioural
one. Print that number next to the 5,922 so the reader can see which it is.

Gates: cross = 5,922 and the day-level ordering reproduces `pai_pair_simultaneity`.
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
CAL = os.path.join(HERE, "pai_pair_calendar.json")
OUT = os.path.join(HERE, "pai_pair_handover_opportunity.json")
PAIR = ("silkkitie", "valhalla")


def sha16(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()[:16]


cal = json.load(io.open(CAL, encoding="utf-8"))
LAUNCH = datetime.date(*[int(x) for x in cal["days_min_max"][PAIR[1]][0].split("-")])
SK_END = datetime.date(*[int(x) for x in cal["days_min_max"][PAIR[0]][1].split("-")])

white = set()
with io.open(WHITE, encoding="utf-8", newline="") as fh:
    for r in csv.DictReader(fh):
        if r.get("whitelisted", "").strip() == "1":
            white.add(r["market_string"].strip())
assert len(white) == 26

# h -> m -> [first_date, last_date]
D = {}
on_or_after_launch_rows = 0
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

cross = [h for h, per in D.items() if len(per) == 2]

n_before_launch = 0
n_after_launch = 0
n_opportunity = 0
n_reverse = 0
s_last_dates = []
v_first_dates = []
s_gap_days = []

for h in cross:
    s_first, s_last = D[h][PAIR[0]]
    v_first, v_last = D[h][PAIR[1]]
    s_last_dates.append(s_last)
    v_first_dates.append(v_first)
    s_gap_days.append((v_first - s_last).days)
    if s_last < LAUNCH:
        n_before_launch += 1
    else:
        n_after_launch += 1
        if s_last >= v_first:
            n_opportunity += 1
    if v_last < s_first:
        n_reverse += 1

# also: how many of these hashes have ANY silkkitie row after valhalla's launch
# (this is the same as n_after_launch, kept as a named quantity)
s_last_dates.sort()
v_first_dates.sort()
s_gap_days.sort()


def q(xs, p):
    return xs[int(p * (len(xs) - 1))]


out = {
    "src_sha16": sha16(SRC),
    "calendar_sha16": sha16(CAL),
    "whitelist_markets": len(white),
    "valhalla_launch": LAUNCH.isoformat(),
    "silkkitie_end": SK_END.isoformat(),
    "cross_market_hashes": len(cross),
    "silkkitie_last_before_valhalla_launch": n_before_launch,
    "silkkitie_last_on_or_after_launch": n_after_launch,
    # RENAMED 12:1x -- `s_last >= v_first` is the EVENT condition, so this
    # count is 0 whenever the event count is 0 (circular). The risk set is
    # `silkkitie_last_on_or_after_launch`. The key is prefixed so no downstream
    # reader can pick up a 0 and mistake it for "no slot could have differed".
    "DEPRECATED_slots_with_real_opportunity": n_opportunity,
    "deprecated": {
        "slots_with_real_opportunity":
            "circular: it is the event condition (0 whenever the event is 0); "
            "use silkkitie_last_on_or_after_launch as the risk set",
    },
    "reverse_cases": n_reverse,
    "silkkitie_last_date_min": s_last_dates[0].isoformat(),
    "silkkitie_last_date_median": q(s_last_dates, 0.5).isoformat(),
    "silkkitie_last_date_p90": q(s_last_dates, 0.9).isoformat(),
    "silkkitie_last_date_max": s_last_dates[-1].isoformat(),
    "valhalla_first_date_min": v_first_dates[0].isoformat(),
    "valhalla_first_date_median": q(v_first_dates, 0.5).isoformat(),
    "valhalla_first_date_p90": q(v_first_dates, 0.9).isoformat(),
    "valhalla_first_date_max": v_first_dates[-1].isoformat(),
    "gap_s_last_to_v_first_days_median": statistics.median(s_gap_days),
    "gap_s_last_to_v_first_days_p10": q(s_gap_days, 0.10),
    "gap_s_last_to_v_first_days_p90": q(s_gap_days, 0.90),
    "gates": {"cross": 5922, "launch": LAUNCH.isoformat()},
    "gate_ok": len(cross) == 5922,
}

with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)

print(json.dumps(out, ensure_ascii=False, indent=2))
