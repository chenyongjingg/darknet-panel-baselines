# -*- coding: utf-8 -*-
"""G19 -- the shipped estimator's own placebo.

g18 rebuilt the survivor screen and matched `events.csv`'s `n_survivors` on
10 of 12 events (the two misses are the earliest, where the panel's coverage
flag is sparser than the pipeline's grid).  g17 showed the "nine in ten" ratio
is flat across random weeks, but under MY destination rule.  This script puts
the two together:

  * vendor sets come from `g1work/merged.pkl` (per market-week vendor presence,
    same listings file and same week grid as the pipeline);
  * destinations are the REBUILT survivor sets from g18, so for the 10
    calibrated events this is the shipped estimator;
  * the real-date shares are printed next to `events.csv`'s columns: if they
    agree, the instrument is the shipped one and the placebo is meaningful;
  * the placebo moves the date, with the survivor set both FIXED at the real
    date and RECOMPUTED at the shifted date, so a nullity cannot be blamed on
    re-selecting destinations.

usage: python -I -X utf8 g19_shipped_placebo.py
"""
import collections
import csv
import gzip
import hashlib
import io
import json
import os
import pickle
import random
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MERGED = os.path.join(HERE, "g1work", "merged.pkl")
PANEL = r"D:\MDPI\_offline_repro\events\weekly_market.csv.gz"
DIAG = r"D:\MDPI\_build\_v33_work\verify\panel_diag.json"
EVENTS = r"D:\MDPI\_offline_repro\events\events.csv"
G18 = os.path.join(HERE, "g18_screened_placebo.json")
OUT = os.path.join(HERE, "g19_shipped_placebo.json")

PRE, POST = 8, 4
SHIFTS = (0, -4, -8, -12, -16)
N_RANDOM = 200


def main():
    t0 = time.time()
    with open(MERGED, "rb") as f:
        _cnt, _hs, wk, _drop = pickle.load(f)
    del _cnt, _hs
    cell = {k: frozenset(v) for k, v in wk.items()}
    del wk

    panel = collections.defaultdict(dict)
    with gzip.open(PANEL, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            panel[r["market"]][int(r["week"])] = {
                "stock": float(r["stock"] or 0),
                "covered": int(float(r["covered"] or 0)),
            }
    diag = json.load(io.open(DIAG, encoding="utf-8"))
    cwk = {n: int(d["collapse"]["8"]) for n, d in diag.items()
           if (d.get("collapse") or {}).get("8") is not None}

    rows = list(csv.DictReader(io.open(EVENTS, encoding="utf-8")))
    events = [r for r in rows
              if r["clock"] == "detected" and r["insufficient"] in ("0", "False", "")]
    calibrated = {e["market"]: (e["n_survivors_rebuilt"] == int(e["n_survivors_shipped"]))
                  for e in json.load(io.open(G18, encoding="utf-8"))["per_event"]}

    markets = sorted(panel)
    weeks = sorted({w for m in panel for w in panel[m]})

    def cov_count(m, w0, w1):
        g = panel.get(m, {})
        return sum(1 for w in range(max(0, w0), w1 + 1)
                   if g.get(w, {}).get("covered", 0))

    def stock_sum(m, w0, w1):
        g = panel.get(m, {})
        return sum(g.get(w, {}).get("stock", 0) for w in range(max(0, w0), w1 + 1))

    op = collections.defaultdict(set)
    for r in rows:
        if r["cause"] == "raided":
            op[(r["end_corrected"] or r["gold_end"], r["cause"])].add(r["market_key"])

    def survivors(d_key, t, d_row):
        exc = op.get((d_row["end_corrected"] or d_row["gold_end"], d_row["cause"]), set())
        out = []
        for sm in markets:
            if sm == d_key or sm in exc:
                continue
            cs = cwk.get(sm)
            if cs is not None and t < cs <= t + POST:
                continue
            if cov_count(sm, t + 1, t + POST) < POST:
                continue
            if stock_sum(sm, t + 1, t + POST) < 1:
                continue
            out.append(sm)
        return out

    def vunion(m, w0, w1):
        s = set()
        for w in range(max(0, w0), w1 + 1):
            t = cell.get((m, w))
            if t:
                s |= t
        return s

    def stat(d_key, t, S):
        vpre = vunion(d_key, t - PRE, t - 1)
        if not vpre or not S:
            return None
        pre_u, post_u = set(), set()
        for sm in S:
            pre_u |= vpre & vunion(sm, t - PRE, t - 1)
            post_u |= vpre & vunion(sm, t + 1, t + POST)
        n = len(vpre)
        return {"n_vpre": n,
                "retained": len(post_u & pre_u) / n,
                "new": len(post_u - pre_u) / n,
                "union": len(post_u) / n,
                "ratio": (len(post_u & pre_u) / len(post_u)) if post_u else None}

    rng = random.Random(20261026)
    per_event = []
    for r in events:
        d = r["market_key"]
        t = int(float(r["t"]))
        if d not in panel:
            continue
        S0 = survivors(d, t, r)
        real = stat(d, t, S0)
        shipped = {"retained": float(r["retained_pre_home"]),
                   "new": float(r["new_placement"]),
                   "union": float(r["union_post_share"]),
                   "n_survivors": int(float(r["n_survivors"]))}
        rec = {"market": d, "t": t, "calibrated_screen": calibrated.get(d),
               "n_survivors_rebuilt": len(S0), "shipped": shipped,
               "real_fixed_S": real, "by_shift_fixed_S": {},
               "by_shift_recomputed_S": {}, "null": []}
        for sh in SHIFTS:
            rec["by_shift_fixed_S"][str(sh)] = stat(d, t + sh, S0)
            rec["by_shift_recomputed_S"][str(sh)] = stat(
                d, t + sh, survivors(d, t + sh, r))
        lo = max(min(weeks) + PRE + 1, t - 40)
        hi = min(max(weeks) - POST, t - 1)
        cand = [w for w in range(lo, hi + 1)]
        for w in rng.sample(cand, min(N_RANDOM, len(cand))):
            st = stat(d, w, S0)          # fixed survivor set: only the date moves
            if st is not None:
                rec["null"].append(st)
        per_event.append(rec)

    def mean_over(key, getter):
        vals = [getter(e) for e in per_event]
        vals = [v[key] for v in vals if v and v.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    def by_shift(key, which, sh):
        return mean_over(key, lambda e: e[which].get(str(sh)))

    pooled = {
        "shipped": {k: mean_over(k, lambda e: e["shipped"]) for k in
                    ("retained", "new", "union")},
        "real_fixed_S": {k: mean_over(k, lambda e: e["real_fixed_S"]) for k in
                         ("retained", "new", "union", "ratio")},
        "by_shift_fixed_S": {str(sh): {k: by_shift(k, "by_shift_fixed_S", sh)
                                       for k in ("retained", "new", "union", "ratio")}
                             for sh in SHIFTS},
        "by_shift_recomputed_S": {str(sh): {k: by_shift(k, "by_shift_recomputed_S", sh)
                                            for k in ("retained", "new", "union", "ratio")}
                                  for sh in SHIFTS},
    }

    nulls = {"ratio": [], "retained": [], "new": [], "union": []}
    for e in per_event:
        for st in e["null"]:
            for k in nulls:
                if st.get(k) is not None:
                    nulls[k].append(st[k])
    nullstat = {}
    for k, v in nulls.items():
        v.sort()
        nullstat[k] = {"n": len(v),
                       "mean": sum(v) / len(v) if v else None,
                       "p50": v[len(v) // 2] if v else None,
                       "p05": v[int(0.05 * (len(v) - 1))] if v else None,
                       "p95": v[int(0.95 * (len(v) - 1))] if v else None}

    # calibration of the shares themselves, on the events whose screen matched
    cal = [e for e in per_event if e["calibrated_screen"]]
    diffs = []
    for e in cal:
        if not e["real_fixed_S"]:
            continue
        diffs.append({
            "market": e["market"],
            "d_retained": e["real_fixed_S"]["retained"] - e["shipped"]["retained"],
            "d_new": e["real_fixed_S"]["new"] - e["shipped"]["new"],
            "d_union": e["real_fixed_S"]["union"] - e["shipped"]["union"],
        })

    res = {
        "stage": "G19",
        "inputs": {"merged": MERGED, "panel": PANEL, "diag": DIAG, "events": EVENTS},
        "params": {"PRE": PRE, "POST": POST, "shifts": list(SHIFTS),
                   "n_random": N_RANDOM,
                   "destinations": "rebuilt survivor screen (g18 rule)"},
        "pooled": pooled,
        "null_random_weeks": nullstat,
        "real_percentile_in_null": {
            k: (sum(1 for x in nulls[k] if x < pooled["real_fixed_S"][k])
                / max(1, len(nulls[k])))
            for k in ("ratio", "retained", "new", "union")},
        "share_calibration_on_matched_events": {
            "n": len(diffs), "rows": diffs,
            "max_abs_d_union": max((abs(d["d_union"]) for d in diffs), default=None),
        },
        "per_event": per_event,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    print("shipped means :", json.dumps({k: round(v, 4) for k, v in pooled["shipped"].items()}))
    print("real (S fixed):", json.dumps({k: round(v, 4) for k, v in pooled["real_fixed_S"].items()}))
    for sh in SHIFTS:
        f = pooled["by_shift_fixed_S"][str(sh)]
        r = pooled["by_shift_recomputed_S"][str(sh)]
        print("shift %+3d  fixed S ratio %.4f union %.4f | recomputed S ratio %.4f union %.4f"
              % (sh, f["ratio"], f["union"], r["ratio"], r["union"]))
    for k, v in nullstat.items():
        print("null %-8s n=%3d mean %.4f p50 %.4f p95 %.4f | real %.4f -> pct %.3f"
              % (k, v["n"], v["mean"], v["p50"], v["p95"],
                 pooled["real_fixed_S"][k], res["real_percentile_in_null"][k]))
    print("share calibration on %d matched events: max |d_union| = %s"
          % (res["share_calibration_on_matched_events"]["n"],
             res["share_calibration_on_matched_events"]["max_abs_d_union"]))
    print("sha", hashlib.sha256(open(OUT, "rb").read()).hexdigest()[:16])


if __name__ == "__main__":
    main()
