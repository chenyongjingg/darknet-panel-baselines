# -*- coding: utf-8 -*-
"""G90 -- the cap-treatment criterion: does the continuity share depend on the
28 page-capped market-weeks, and by how much?

THE QUESTION THIS ANSWERS
-------------------------
Section 6 of the draft says of the four rows: "A crawler with a higher page cap,
or a window containing a different set of closures, could move any of the four
rows, and nothing here estimates by how much."  That sentence is the gap the
review called DA-1.  The fix is not a narrower claim; it is a NUMBER, produced by
the only operation that isolates the cap: recompute the statistic with the capped
cells deleted, and compare that deletion against deletions that carry everything
the capped cells carry EXCEPT the cap.

WHY A WITHIN-EVENT CONTRAST AND NOT AN EXPOSED/CLEAN SPLIT
----------------------------------------------------------
g40 labels 5 of 12 events "exposed" (channels A and B) and 7 clean.  Those five
are also the five latest events (t >= 77) and the clean set spans t = 48..118, so
"exposed vs clean" is almost a time split; the ledger already records the
Spearman rho = -0.203 / permutation p = 0.5233 confound and the "print, do not
judge" rule for that layer.  A split cannot be repaired by another split.  This
script therefore compares each event WITH ITSELF: same closing market, same
t, same fixed survivor set, same rule; the only thing that changes is whether the
28 capped cells are in the vendor-presence map.

ARMS
----
  keep         shipped: every cell present                     (must reproduce
                                                               g19's 0.9120109394630586)
  drop28       the 28 capped cells deleted
  random28     R deletions of 28 uniformly random cells        (null for "delete 28")
  same_week28  for each capped cell, a DIFFERENT market's cell in the SAME WEEK --
               same count, same weeks, same era; this is the arm that carries the
               era confound without carrying the cap.  Whatever it does, the
               capped cells' own deletion must not do more.

READING
-------
  cap contribution   = keep - drop28, reported per event and pooled, in pp.
  era width          = the same_week28 spread; the cap's own contribution is only
                       resolvable if it falls outside this band.
  The criterion is the recipe, not a constant: on ANY panel, delete your capped
  cells, recompute, and compare the move against your own re-dating null width.
  A firing check is supplied from an existing product: applied to the
  listing-weighted multi-homing share (g44), the same deletion lands OUTSIDE its
  random-drop band, i.e. the recipe can fire.  The continuity share is where it
  does not.

CAUTION -- the deletion is an UPPER BOUND on the cap's damage, not a correction:
dropping a cell removes 100% of it, whereas the cap removed only an unknown tail.
The cap also truncates the capped cells' own vendor sets, so a size-matched arm
would under-match; that is why no size-matched arm is reported.

usage: python -I -X utf8 g90_cap_treatment_criterion.py [--reps N]
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
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MERGED = os.path.join(HERE, "g1work", "merged.pkl")
PANEL = r"D:\MDPI\_offline_repro\events\weekly_market.csv.gz"
DIAG = r"D:\MDPI\_build\_v33_work\verify\panel_diag.json"
EVENTS = r"D:\MDPI\_offline_repro\events\events.csv"
G18 = os.path.join(HERE, "g18_screened_placebo.json")
G19 = os.path.join(HERE, "g19_shipped_placebo.json")
G9D = os.path.join(HERE, "g9d_rows_in_capped_cells.json")
G44 = os.path.join(HERE, "g44_truncation_vs_headline_share.json")
G30 = os.path.join(HERE, "g30_same_unit_null.json")
OUT = os.path.join(HERE, "g90_cap_treatment_criterion.json")

PRE, POST = 8, 4
REPS = 200
BASE = 20261026


def sha16(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()[:16]


def pct(xs, q):
    s = sorted(xs)
    if not s:
        return None
    i = (len(s) - 1) * q
    lo = int(i)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def main():
    t0 = time.time()
    ap = sys.argv[1:]
    reps = REPS
    if "--reps" in ap:
        reps = int(ap[ap.index("--reps") + 1])

    with open(MERGED, "rb") as f:
        _cnt, _hs, wk, _drop = pickle.load(f)
    del _cnt, _hs, _drop
    cell = {k: frozenset(v) for k, v in wk.items()}
    del wk
    cells = sorted(cell)

    g9d = json.load(io.open(G9D, encoding="utf-8"))
    capset = frozenset(tuple(x.split("|")) for x in g9d["per_cell_raw_rows"])
    capset = frozenset((m, int(w)) for m, w in capset)
    assert len(capset) == 28, len(capset)
    assert all(c in cell for c in capset), "a capped cell is not in the vendor map"

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

    def make_stat(dropped):
        """Return stat() bound to a vendor-presence map with `dropped` removed."""
        dr = frozenset(dropped)

        def vunion(m, w0, w1):
            s = set()
            for w in range(max(0, w0), w1 + 1):
                if (m, w) in dr:
                    continue
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

        return stat

    stat_keep = make_stat(())
    stat_drop = make_stat(capset)

    # --- fixed survivor sets, once, from the shipped screen ---
    plan = []
    for r in events:
        d = r["market_key"]
        if d not in panel:
            continue
        t = int(float(r["t"]))
        S = survivors(d, t, r)
        touching = sorted("%s|%d" % (m, w) for (m, w) in capset
                          if (m == d and t - PRE <= w <= t + POST)
                          or (m in S and t - PRE <= w <= t + POST))
        plan.append({"row": r, "d": d, "t": t, "S": S, "touching": touching})
    assert len(plan) == 12, len(plan)

    def support_loss(d_key, t, S):
        """How much of the estimation window the deletion actually removes.

        A per-event move under `drop28` is only a cap-contribution if the
        deletion removed a TAIL rather than a window: for the three events whose
        surviving set contains the capped market itself, deleting its post
        weeks removes a large part of the post window, and the resulting move
        is support destruction, not truncation.
        """
        tot = {"pre": 0, "post": 0}
        lost = {"pre": 0, "post": 0}
        for tag, w0, w1 in (("pre", t - PRE, t - 1), ("post", t + 1, t + POST)):
            for m in [d_key] + list(S):
                for w in range(w0, w1 + 1):
                    n = len(cell.get((m, w), ()))
                    tot[tag] += n
                    if (m, w) in capset:
                        lost[tag] += n
        return {"pre_obs": tot["pre"], "post_obs": tot["post"],
                "pre_lost_frac": (lost["pre"] / tot["pre"]) if tot["pre"] else None,
                "post_lost_frac": (lost["post"] / tot["post"]) if tot["post"] else None}

    per_event = []
    for p in plan:
        k = p["d"], p["t"], p["S"]
        a = stat_keep(*k)
        b = stat_drop(*k)
        p["keep"], p["drop"] = a, b
        sup = support_loss(*k)
        per_event.append({
            "market": p["d"], "t": p["t"], "n_survivors": len(p["S"]),
            "capped_cells_touching": p["touching"],
            "n_capped_cells_touching": len(p["touching"]),
            "support_loss": sup,
            "keep": a, "drop": b,
            "d_ratio": (a["ratio"] - b["ratio"]) if (a and b and a["ratio"] is not None
                                                    and b["ratio"] is not None) else None,
            "d_new": (a["new"] - b["new"]) if (a and b) else None,
            "d_retained": (a["retained"] - b["retained"]) if (a and b) else None,
            "d_n_vpre": (a["n_vpre"] - b["n_vpre"]) if (a and b) else None,
        })

    def pooled(stat, key):
        vals = []
        for p in plan:
            v = stat(p["d"], p["t"], p["S"])
            if v and v.get(key) is not None:
                vals.append(v[key])
        return (sum(vals) / len(vals)) if vals else None

    keep = {k: pooled(stat_keep, k) for k in ("retained", "new", "union", "ratio")}
    drop = {k: pooled(stat_drop, k) for k in ("retained", "new", "union", "ratio")}

    g19 = json.load(io.open(G19, encoding="utf-8"))
    CAL = g19["pooled"]["real_fixed_S"]["ratio"]
    calib_ok = abs(keep["ratio"] - CAL) < 1e-12
    assert calib_ok, (keep["ratio"], CAL)

    # --- placebo deletions ---
    week_cells = collections.defaultdict(list)
    for (m, w) in cells:
        week_cells[w].append((m, w))

    def run(reps, rule, seed0):
        rng = random.Random(seed0)
        out = []
        fails = 0
        for i in range(reps):
            drop_set = set()
            if rule == "random":
                drop_set = set(rng.sample(cells, len(capset)))
            elif rule == "same_week":
                for c in sorted(capset):
                    pool = [x for x in week_cells[c[1]] if x not in drop_set]
                    if not pool:
                        drop_set = None
                        break
                    drop_set.add(rng.choice(pool))
                if drop_set is None:
                    fails += 1
                    continue
            st = make_stat(drop_set)
            v = pooled(st, "ratio")
            if v is not None:
                out.append(v)
        return out, fails

    rnd, rnd_fail = run(reps, "random", BASE + 901)
    sw, sw_fail = run(reps, "same_week", BASE + 902)

    def summarise(xs, ref):
        if not xs:
            return {"n": 0}
        return {"n": len(xs), "min": min(xs), "p05": pct(xs, 0.05),
                "p50": pct(xs, 0.50), "mean": sum(xs) / len(xs),
                "p95": pct(xs, 0.95), "max": max(xs),
                "sd": (sum((x - sum(xs) / len(xs)) ** 2 for x in xs)
                       / (len(xs) - 1)) ** 0.5,
                "n_ge_ref": sum(1 for x in xs if x >= ref),

                "p_at_least_ref": (sum(1 for x in xs if x >= ref) / len(xs))}

    # --- the firing check, from an existing product ---
    g44 = json.load(io.open(G44, encoding="utf-8"))
    fi = {
        "quantity": "listing-weighted same-week multi-homing share (row 3 of Table 1)",
        "base": g44["base"]["weighted"],
        "drop_capped": g44["drop_cells_keep_mask"]["weighted"],
        "random28_p05": g44["placebo"]["random28"]["p05"],
        "random28_p95": g44["placebo"]["random28"]["p95"],
    }
    fi["move_pp"] = 100.0 * (fi["drop_capped"] - fi["base"])
    fi["falls_outside_random_band"] = bool(
        fi["drop_capped"] > fi["random28_p95"] or fi["drop_capped"] < fi["random28_p05"])
    # The band-membership test above is NOT the right read, and the peer is right
    # about why: the base 0.5397 is itself above the band's upper edge, so "the
    # capped drop lands outside" would not distinguish the cap from the base.  The
    # sign test does: dropping cells can only REMOVE multi-homers, so every random
    # drop moves the share DOWN; the capped drop moves it UP.
    fi["random28_move_pp"] = {"p05": 100.0 * (fi["random28_p05"] - fi["base"]),
                              "p95": 100.0 * (fi["random28_p95"] - fi["base"])}
    fi["sign_separated"] = bool(fi["move_pp"] > 0
                                and fi["random28_move_pp"]["p95"] < 0)
    fi["reading"] = (
        "the same deletion recipe MOVES the multi-homing share: removing the 28 capped "
        "cells RAISES it by %.2f pp, while removing 28 random cells LOWERS it by %.2f "
        "to %.2f pp (relative to the same base) -- opposite signs, so the cap leaves a "
        "signature a random deletion of the same size cannot produce -> the recipe CAN "
        "fire. (Band membership is not the test: the base itself sits above the "
        "random-drop band's upper edge, so 'outside the band' would be true of the "
        "base as well.)"
        % (fi["move_pp"], fi["random28_move_pp"]["p05"], fi["random28_move_pp"]["p95"]))

    # --- the yardstick: SAME-UNIT null, not the single-draw pooled spread ---
    # g19.null_random_weeks is the pooled distribution of n=296 SINGLE draws, and
    # g30 names its own percentile for it `percentile_old_single_draw` (0.4527) --
    # that field is the deprecated ruler.  The statistic the paper reports is the
    # 12-EVENT MEAN, and its re-dating distribution is g30's `arms.g19_range`
    # (`percentile_same_unit` = 0.70975, which is the paper's "71.0th percentile").
    # The criterion must use that one; the two widths differ by a factor of ~4.3.
    g30 = json.load(io.open(G30, encoding="utf-8"))
    su = g30["arms"]["g19_range"]["by_key"]["ratio"]
    nullwidth = su["replicate_p95"] - su["replicate_p05"]
    oldwidth = (g19["null_random_weeks"]["ratio"]["p95"]
                - g19["null_random_weeks"]["ratio"]["p05"])
    move = keep["ratio"] - drop["ratio"]

    res = {
        "stage": "G90",
        "question": ("does the continuity share depend on the 28 page-capped "
                     "market-weeks, and by how much (a number for Section 6's "
                     "'nothing here estimates by how much')"),
        "inputs": {
            "merged": sha16(MERGED), "g9d": sha16(G9D), "g19": sha16(G19),
            "g18": sha16(G18), "g44": sha16(G44), "events": "events.csv",
            "panel": "weekly_market.csv.gz",
        },
        "params": {"PRE": PRE, "POST": POST, "reps": reps, "base_seed": BASE,
                   "n_capped_cells": len(capset),
                   "survivor_set": "fixed at the real date in every arm "
                                   "(drop the cells, keep the mask)"},
        "calibration": {"keep_ratio": keep["ratio"], "g19_real_fixed_S_ratio": CAL,
                        "exact": bool(calib_ok)},
        "pooled": {"keep": keep, "drop28": drop,
                   "cap_contribution_pp": {k: 100.0 * (keep[k] - drop[k])
                                           for k in ("retained", "new", "union", "ratio")}},
        "n_events": len(per_event),
        "n_events_touched_by_cap": sum(1 for e in per_event
                                       if e["n_capped_cells_touching"] > 0),
        "per_event": per_event,
        "placebo": {"random28": summarise(rnd, keep["ratio"]),
                    "same_week28": summarise(sw, keep["ratio"]),
                    "random28_unmatched": rnd_fail,
                    "same_week28_unmatched": sw_fail},
        "zero_baseline": {
            "source": "g30_same_unit_null.json arms.g19_range.by_key.ratio",
            "source_sha16": sha16(G30),
            "object": "distribution of the 12-event mean under re-dating (same unit "
                      "as the reported statistic)",
            "p05": su["replicate_p05"], "p50": su["replicate_p50"],
            "mean": su["replicate_mean"], "p95": su["replicate_p95"],
            "realised_percentile": su["percentile_same_unit"],
            "width": nullwidth,
            "deprecated_ruler_not_used": {
                "source": "g19.null_random_weeks.ratio (n=%d pooled SINGLE draws)"
                          % g19["null_random_weeks"]["ratio"]["n"],
                "p05": g19["null_random_weeks"]["ratio"]["p05"],
                "p95": g19["null_random_weeks"]["ratio"]["p95"],
                "realised_percentile": g19["real_percentile_in_null"]["ratio"],
                "width": oldwidth,
                "why": "g30 names this object's percentile percentile_old_single_draw; "
                       "it is the spread of one draw, not of the estimator the paper "
                       "reports. Using it as the criterion's yardstick understates the "
                       "instrument share by a factor of %.2f." % (oldwidth / nullwidth),
            },
        },
        "criterion": {
            "statement": (
                "Delete the capped market-weeks, recompute the share, and compare the "
                "move against (i) the same-week deletion band and (ii) the width of the "
                "SAME-UNIT re-dating null -- the p05-p95 span of the 12-event mean under "
                "re-dating (g30 arms.g19_range.by_key.ratio), which is the object whose "
                "percentile the paper reports. Not the pooled single-draw spread. The "
                "share's containment transfers to another panel crawled at the same or "
                "better coverage iff the move is inside both. The threshold is "
                "panel-relative and therefore portable: it is stated as a fraction of "
                "the null width, not as a constant."),
            "move_pp": 100.0 * move,
            "move_as_fraction_of_null_width": (move / nullwidth) if nullwidth else None,
            "same_week28_band": ([(sw and pct(sw, 0.05)), (sw and pct(sw, 0.95))]
                                 if sw else None),
            "verdict": None,
        },
        "firing_check_from_g44": fi,
        "elapsed_s": None,
    }

    # --- the deletion is only a cap-contribution where it removes a TAIL ---
    # For the three channel-B events the deletion takes 63.8-67.5% of the post
    # window's observations (a survivor's own post weeks), so their per-event
    # moves measure support destruction, not truncation.  The estimable arm is
    # the rest, where the deletion removes a pre-window tail.
    DESTROY = 0.10
    est = [e for e in per_event
           if (e["support_loss"]["post_lost_frac"] or 0.0) <= DESTROY]
    destroyed = [e["market"] for e in per_event if e not in est]
    pk = [e["keep"]["ratio"] for e in est if e["keep"] and e["keep"]["ratio"] is not None]
    pdr = [e["drop"]["ratio"] for e in est if e["drop"] and e["drop"]["ratio"] is not None]
    pe = {"n": len(est), "excluded_support_destroyed": destroyed,
          "threshold_post_lost_frac": DESTROY,
          "keep_ratio": sum(pk) / len(pk) if pk else None,
          "drop_ratio": sum(pdr) / len(pdr) if pdr else None}
    if pe["keep_ratio"] is not None and pe["drop_ratio"] is not None:
        pe["cap_contribution_pp"] = 100.0 * (pe["keep_ratio"] - pe["drop_ratio"])
        pe["as_fraction_of_null_width"] = (abs(pe["keep_ratio"] - pe["drop_ratio"])
                                           / nullwidth)
    res["pooled_estimable"] = pe

    mv = 100.0 * move
    swband = res["criterion"]["same_week28_band"]
    sw_halfwidth_pp = (100.0 * (swband[1] - swband[0]) / 2.0) if swband else None
    touched = [e for e in per_event if e["n_capped_cells_touching"] > 0]
    absd = [abs(100.0 * e["d_ratio"]) for e in touched if e["d_ratio"] is not None]
    spread = {
        "n_touched": len(touched),
        "mean_abs_d_pp": (sum(absd) / len(absd)) if absd else None,
        "max_abs_d_pp": max(absd) if absd else None,
        "sum_signed_d_pp_onevent": sum(100.0 * e["d_ratio"] for e in touched
                                       if e["d_ratio"] is not None),
        "note": ("the pooled move and the per-event moves are different objects: "
                 "a small pooled move can be offsetting per-event reclassification, "
                 "not insensitivity"),
    }
    res["per_event_spread"] = spread
    res["criterion"]["verdict"] = (
        "DELETION IS ONLY A CAP-CONTRIBUTION WHERE IT REMOVES A TAIL. In the %d "
        "events where the post window survives the deletion (%.0f%% loss threshold), "
        "the cap's own contribution is %.3f pp = %.2f%% of the SAME-UNIT re-dating "
        "null width "
        "(%.2f pp). In %s the deletion removes 63.8-67.5%% of the post window, so "
        "their -3.18 / +8.21 / -6.42 pp are support destruction and are NOT a cap "
        "effect; those events are excluded from the bound and must not be quoted per "
        "event. All-events pooled move (printed, not used): %.3f pp."
        % (pe["n"], 100 * DESTROY, pe["cap_contribution_pp"],
           100.0 * pe["as_fraction_of_null_width"], 100.0 * nullwidth,
           "/".join(pe["excluded_support_destroyed"]), mv))
    res["criterion"]["same_week28_halfwidth_pp"] = sw_halfwidth_pp
    res["elapsed_s"] = time.time() - t0

    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(res, indent=1, ensure_ascii=False) + "\n")

    print("CALIBRATION keep=%.16f g19=%.16f exact=%s" % (keep["ratio"], CAL, calib_ok))
    print("pooled keep  ", {k: round(v, 6) for k, v in keep.items()})
    print("pooled drop28", {k: round(v, 6) for k, v in drop.items()})
    print("cap contribution pp:", {k: round(100.0 * (keep[k] - drop[k]), 4)
                                   for k in keep})
    print("random28   p05/p50/p95 = %.4f / %.4f / %.4f (n=%d)"
          % (pct(rnd, .05), pct(rnd, .5), pct(rnd, .95), len(rnd)))
    print("same_week28 p05/p50/p95 = %.4f / %.4f / %.4f (n=%d)"
          % (pct(sw, .05), pct(sw, .5), pct(sw, .95), len(sw)))
    print("VERDICT:", res["criterion"]["verdict"])
    print("firing check:", fi["reading"])
    print()
    print("%-16s %4s %3s %-28s %8s %8s %8s" %
          ("event", "t", "nS", "capped cells touching", "keep", "drop", "d_pp"))
    for e in per_event:
        print("%-16s %4d %3d %-28s %8.4f %8.4f %8.2f" % (
            e["market"], e["t"], e["n_survivors"],
            (e["capped_cells_touching"][0][:26] if e["capped_cells_touching"] else "-"),
            e["keep"]["ratio"] if e["keep"] else float("nan"),
            e["drop"]["ratio"] if e["drop"] else float("nan"),
            100.0 * e["d_ratio"] if e["d_ratio"] is not None else 0.0))
    print("\nwrote %s (%.1fs, sha16 %s)" % (OUT, res["elapsed_s"], sha16(OUT)))


if __name__ == "__main__":
    main()
