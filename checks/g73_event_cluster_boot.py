# -*- coding: utf-8 -*-
"""G73 -- how uncertain is the reselect trajectory, given that the 12 events
share their destination markets?

Every interval this paper prints for the substitution contrast is either an
exact sign-flip p (which treats the 12 per-event differences as exchangeable
under the null) or nothing at all.  The reviewer's cheaper question is the
sampling one: the events are not independent draws of anything -- agora and
oxygen share a destination set, three events share a date -- so the honest
interval resamples EVENTS, not units.

Four objects, because they answer four different questions:

  cluster          resample the 12 events with replacement and recompute each
                   horizon AND the 4->12 difference inside the same draw (the
                   difference is paired within event, so it must be resampled
                   as a pair)
  cluster_by_date  the same, but the resampling unit is the closure DATE: 12
                   events fall on 8 dates (three on t=57, two on t=101 and two
                   on t=108), and events sharing a date share whatever else
                   moved that week.  8 clusters is very few, so this is the
                   pessimistic dependence structure and is reported as such.
  unit_paired      resample units, but draw ONE unit set per event and read
                   BOTH horizons off it.  This is the standard units-nested-in-
                   events bootstrap: it keeps the within-unit pairing the span
                   is built on.  A vendor is drawn from the union of its event's
                   units across horizons and contributes to a horizon only if
                   it is present there -- presence changes 4->12 are the
                   reselection mechanism itself, not noise to be discarded.
  unit_unpaired    resample units with each horizon drawn SEPARATELY.  This
                   destroys the within-unit pairing, so it is NOT a
                   conservative alternative to the cluster: it is wider for the
                   span and narrower for a single horizon.  It is kept in the
                   product only to show that inversion, and the version this
                   file first shipped with was exactly this strawman -- a
                   referee is entitled to reject a unit bootstrap that throws
                   away the pairing, so the paired one above is the one that
                   can be quoted.
  frozen           the cluster bootstrap on the frozen-destination-set arm,
                   whose point span is ~0 by construction.  A bootstrap that
                   cannot produce a wide interval where the truth is flat is
                   not an instrument; this is its control.

Clusters are few, and a percentile interval on few clusters undercovers, so
every cluster interval is also reported with a t(G-1) critical value (11 df for
events, 7 df for dates).

Calibration: the reselect point estimates must reproduce g67's stored
event-weighted means to 1e-12, and the frozen arm must reproduce g70's stored
`frozen_set_all_units` means (also event-weighted) to 1e-12, plus both spans
against g70's `spans_pp` -- otherwise this is another uncalibrated ruler over
the same units.

usage: python -I -X utf8 g73_event_cluster_boot.py
"""
import collections
import csv
import gzip
import hashlib
import io
import json
import math
import os
import pickle
import random
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MERGED = os.path.join(HERE, "g1work", "merged.pkl")
PANEL = r"D:/MDPI/_offline_repro/events/weekly_market.csv.gz"
DIAG = r"D:/MDPI/_build/_v33_work/verify/panel_diag.json"
EVENTS = r"D:/MDPI/_offline_repro/events/events.csv"
G67 = os.path.join(HERE, "g67_post_horizon.json")
G70 = os.path.join(HERE, "g70_same_degree.json")
OUT = os.path.join(HERE, "g73_event_cluster_boot.json")

PRE, POSTS = 8, (4, 8, 12)
REPS, SEED = 4000, 20261026
# t_{0.975} for 11 df, which is the G-1 the twelve clusters give
T975_DF11 = 2.200985160082949
# and for 7 df, which is what 8 closure dates give
T975_DF7 = 2.3646242515927844


def main():
    t0 = time.time()
    with open(MERGED, "rb") as f:
        _cnt, _hs, wk, _drop = pickle.load(f)
    del _cnt, _hs
    panel = collections.defaultdict(dict)
    with gzip.open(PANEL, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            panel[r["market"]][int(r["week"])] = {
                "stock": float(r["stock"] or 0),
                "covered": int(float(r["covered"] or 0))}
    diag = json.load(io.open(DIAG, encoding="utf-8"))
    cwk = {n: int(d["collapse"]["8"]) for n, d in diag.items()
           if (d.get("collapse") or {}).get("8") is not None}
    rows = list(csv.DictReader(io.open(EVENTS, encoding="utf-8")))
    events = [r for r in rows if r["clock"] == "detected"
              and r["insufficient"] in ("0", "False", "")]
    markets = sorted(panel)
    op = collections.defaultdict(set)
    for r in rows:
        if r["cause"] == "raided":
            op[(r["end_corrected"] or r["gold_end"], r["cause"])].add(
                r["market_key"])

    def cov_count(m, w0, w1):
        g = panel.get(m, {})
        return sum(1 for w in range(max(0, w0), w1 + 1)
                   if g.get(w, {}).get("covered", 0))

    def stock_sum(m, w0, w1):
        g = panel.get(m, {})
        return sum(g.get(w, {}).get("stock", 0)
                   for w in range(max(0, w0), w1 + 1))

    def vset(m, w0, w1):
        s = set()
        for w in range(max(0, w0), w1 + 1):
            c = wk.get((m, w))
            if c:
                s |= set(c)
        return s

    def survivors(d_key, t, d_row, post):
        exc = op.get((d_row["end_corrected"] or d_row["gold_end"],
                      d_row["cause"]), set())
        out = []
        for sm in markets:
            if sm == d_key or sm in exc:
                continue
            cs = cwk.get(sm)
            if cs is not None and t < cs <= t + post:
                continue
            if cov_count(sm, t + 1, t + post) < post:
                continue
            if stock_sum(sm, t + 1, t + post) < 1:
                continue
            out.append(sm)
        return out

    def build(post, s_override=None):
        """returns (units, keyed): keyed[event][vendor] = attributes at THIS
        horizon.  The keyed form is what the paired unit bootstrap needs -- a
        vendor is the same vendor at 4 and at 12 even when its arm changed,
        and only a keyed structure can let one draw feed both horizons."""
        units = []
        keyed = {}
        for r in events:
            d = r["market_key"]
            t = int(float(r["t"]))
            if d not in panel:
                continue
            S = (s_override(r) if s_override
                 else survivors(d, t, r, post))
            vpre = vset(d, t - PRE, t - 1)
            if not vpre or not S:
                continue
            pre_m = {sm: vpre & vset(sm, t - PRE, t - 1) for sm in S}
            post_m = {sm: vpre & vset(sm, t + 1, t + post) for sm in S}
            deg = collections.Counter()
            for sm in S:
                for v in pre_m[sm]:
                    deg[v] += 1
            kev = {}
            # sorted(): `vpre` is a set, and set iteration order is per-process.
            # The units list order feeds the bootstrap's rng.randrange index
            # stream, so an unsorted walk here made the PRODUCT differ between
            # runs (line 504) while every count stayed identical -- counts can
            # be stable and the receipt still not be an identity.
            for v in sorted(vpre):
                kept = sum(1 for sm in S if v in pre_m[sm] and v in post_m[sm])
                arrive = any(v in post_m[sm] and v not in pre_m[sm] for sm in S)
                at = {"k": deg[v], "kept": kept,
                      "arrive": 1 if arrive else 0}
                kev[v] = at
                units.append(dict(at, event=d, vendor=v))
            keyed[d] = kev
        return units, keyed

    s4 = survivors

    def _s4(r):
        d = r["market_key"]
        return (survivors(d, int(float(r["t"])), r, 4) if d in panel else [])

    def per_event(p_units):
        g = collections.defaultdict(list)
        for u in p_units:
            g[u["event"]].append(u)
        return dict(g)

    arms, keyed = {}, {}
    for arm_name, ov in (("reselect", None), ("frozen", _s4)):
        bp = {p: build(p, ov) for p in POSTS}
        arms[arm_name] = {p: per_event(bp[p][0]) for p in POSTS}
        keyed[arm_name] = {p: bp[p][1] for p in POSTS}
    evs = sorted(arms["reselect"][POSTS[0]])
    for a in arms:
        for p in POSTS:
            assert sorted(arms[a][p]) == evs, (a, p)

    # ---- closure dates as an alternative clustering ------------------------
    ev_date = {}
    for r in events:
        ev_date.setdefault(r["market_key"], int(float(r["t"])))
    for e in evs:
        assert e in ev_date, e
    date_groups_map = collections.defaultdict(list)
    for e in evs:
        date_groups_map[ev_date[e]].append(e)
    date_keys = sorted(date_groups_map)
    date_groups = [sorted(date_groups_map[k]) for k in date_keys]

    def diff_of(units):
        """B1 - A inside one event, on whatever units are handed in"""
        z = [u for u in units if u["k"] == 0]
        nr = [u for u in units if u["k"] == 1 and u["kept"] == 0]
        if not z or not nr:
            return None
        a = sum(u["arrive"] for u in z) / float(len(z))
        b = sum(u["arrive"] for u in nr) / float(len(nr))
        return b - a

    def point(pe):
        return {p: [d for d in (diff_of(pe[p][e]) for e in evs)
                    if d is not None] for p in POSTS}

    pts = {a: point(arms[a]) for a in arms}
    means = {a: {p: sum(pts[a][p]) / float(len(pts[a][p])) for p in POSTS}
             for a in arms}

    rng = random.Random(SEED)

    def boot_cluster(a, groups):
        """resample clusters (a list of event-name lists); the 4->12 difference
        is paired inside the draw.  The event scheme is this same function with
        groups = [[e] for e in evs], so there is one code path, not two."""
        draws = {p: [] for p in POSTS}
        span = []
        n = len(groups)
        pe = arms[a]
        for _ in range(REPS):
            draw = []
            for _ in range(n):
                draw.extend(groups[rng.randrange(n)])
            vals = {}
            for p in POSTS:
                ds = [d for d in (diff_of(pe[p][e]) for e in draw)
                      if d is not None]
                vals[p] = sum(ds) / float(len(ds)) if ds else None
                if vals[p] is not None:
                    draws[p].append(vals[p])
            if vals[4] is not None and vals[12] is not None:
                span.append(vals[12] - vals[4])
        return draws, span

    def boot_unit_paired(a):
        """draw ONE unit set per event and read both horizons off it.

        A vendor is drawn from the union of its event's units at 4/8/12 and
        contributes to a horizon only where it is present.  The pairing -- the
        thing the span is built on -- is preserved, which is exactly what
        boot_unit() below throws away."""
        draws = {p: [] for p in POSTS}
        span = []
        K = keyed[a]
        union = {e: sorted(set(K[4].get(e, {})) | set(K[8].get(e, {}))
                           | set(K[12].get(e, {}))) for e in evs}
        for _ in range(REPS):
            samp = {e: [union[e][rng.randrange(len(union[e]))]
                        for _ in range(len(union[e]))] for e in evs
                    if union[e]}
            vals = {}
            for p in POSTS:
                ds = []
                for e in evs:
                    if e not in samp:
                        continue
                    kev = K[p].get(e, {})
                    z = [kev[v] for v in samp[e]
                         if v in kev and kev[v]["k"] == 0]
                    nr = [kev[v] for v in samp[e]
                          if v in kev and kev[v]["k"] == 1
                          and kev[v]["kept"] == 0]
                    if not z or not nr:
                        continue
                    a_ = sum(u["arrive"] for u in z) / float(len(z))
                    b_ = sum(u["arrive"] for u in nr) / float(len(nr))
                    ds.append(b_ - a_)
                vals[p] = sum(ds) / float(len(ds)) if ds else None
                if vals[p] is not None:
                    draws[p].append(vals[p])
            if vals[4] is not None and vals[12] is not None:
                span.append(vals[12] - vals[4])
        return draws, span

    def boot_unit():
        """resample units inside each event, horizons in SEPARATE draws --
        this is the pairing-destroying variant, kept to make the inversion
        visible rather than to estimate anything"""
        draws = {p: [] for p in POSTS}
        span = []
        pe = arms["reselect"]
        for _ in range(REPS):
            vals = {}
            for p in POSTS:
                ds = []
                for e in evs:
                    xs = pe[p][e]
                    if not xs:
                        continue
                    sample = [xs[rng.randrange(len(xs))]
                              for _ in range(len(xs))]
                    d = diff_of(sample)
                    if d is not None:
                        ds.append(d)
                vals[p] = sum(ds) / float(len(ds)) if ds else None
                if vals[p] is not None:
                    draws[p].append(vals[p])
            if vals[4] is not None and vals[12] is not None:
                span.append(vals[12] - vals[4])
        return draws, span

    def quant(v, q):
        s = sorted(v)
        i = int(round(q * (len(s) - 1)))
        return s[max(0, min(len(s) - 1, i))]

    def sd(v):
        m = sum(v) / float(len(v))
        return math.sqrt(sum((x - m) ** 2 for x in v) / float(len(v) - 1))

    def interval(v, centre, crit):
        lo, hi = quant(v, 0.025), quant(v, 0.975)
        se = sd(v)
        tlo, thi = centre - crit * se, centre + crit * se
        return {"pct_lo": lo, "pct_hi": hi, "pct_width_pp": 100.0 * (hi - lo),
                "se": se, "t_lo": tlo, "t_hi": thi,
                "t_width_pp": 100.0 * (thi - tlo),
                "crit": crit,
                "pct_excludes_zero": (lo > 0 and hi > 0) or (lo < 0 and hi < 0),
                "t_excludes_zero": (tlo > 0 and thi > 0) or (tlo < 0 and thi < 0),
                "share_negative": sum(1 for x in v if x < 0) / float(len(v))}

    event_groups = [[e] for e in evs]

    def scheme(a, groups, crit):
        d, sp = boot_cluster(a, groups)
        return {"posts": {str(p): interval(d[p], means[a][p], crit)
                          for p in POSTS},
                "span": interval(sp, means[a][12] - means[a][4], crit),
                "n_clusters": len(groups),
                "sizes": sorted((len(g) for g in groups), reverse=True)}

    cl = {a: scheme(a, event_groups, T975_DF11) for a in arms}
    cl_date = {a: scheme(a, date_groups, T975_DF7) for a in arms}

    dp, dsp = boot_unit_paired("reselect")
    du, ddu = boot_unit()
    unit_paired = {"posts": {str(p): interval(dp[p], means["reselect"][p],
                                              T975_DF11) for p in POSTS},
                   "span": interval(dsp, means["reselect"][12]
                                    - means["reselect"][4], T975_DF11),
                   "pairing": "one unit set per event per replicate, read at "
                              "all three horizons"}
    unit = {"posts": {str(p): interval(du[p], means["reselect"][p],
                                       T975_DF11) for p in POSTS},
            "span": interval(ddu, means["reselect"][12]
                             - means["reselect"][4], T975_DF11),
            "pairing": "DESTROYED: each horizon drawn from its own resample"}

    res = {
        "stage": "G73",
        "question": "how uncertain is the reselect trajectory once the events "
                    "are resampled as clusters instead of units",
        "params": {"PRE": PRE, "POSTS": list(POSTS), "reps": REPS,
                   "seed": SEED, "n_events": len(evs),
                   "n_date_clusters": len(date_groups),
                   "t975_df11": T975_DF11, "t975_df7": T975_DF7},
        "point_estimates_pp": {a: {str(p): 100.0 * means[a][p] for p in POSTS}
                               for a in arms},
        "span_4_to_12_pp": {a: 100.0 * (means[a][12] - means[a][4])
                            for a in arms},
        "cluster": cl,
        "cluster_by_date": cl_date,
        "date_groups": {str(ev_date[g[0]]): g for g in date_groups},
        "unit_bootstrap_reselect": unit,
        "unit_bootstrap_paired_reselect": unit_paired,
        "per_event_diffs_pp": {
            a: {str(p): dict(zip(evs, [100.0 * x if x is not None else None
                                       for x in pts[a][p]]))
                for p in POSTS} for a in arms},
        "pairing_note": "the UNPAIRED unit bootstrap draws each horizon from "
                        "its own resample, so it is WIDER for the span (which "
                        "is paired by design) and narrower for a single "
                        "horizon. It is not a conservative alternative; it "
                        "answers a different question, and quoting it as one "
                        "would be a strawman. The paired variant is the one "
                        "that can be quoted",
        "reading_contract": {
            "must_quote": "the t(G-1) interval, not the percentile one: 12 "
                          "clusters undercover",
            "must_not_say": "a level interval that includes zero may not be "
                            "described as 'the deficit is present at this "
                            "horizon'; the span and the level are separate "
                            "claims and the span is the one that survives",
        },
        "elapsed_note": "runtime is printed, never stored",
    }

    # ---- calibration -------------------------------------------------------
    g67 = json.load(io.open(G67, encoding="utf-8"))
    for p in POSTS:
        ref = g67["by_post"][str(p)]["summary_all"]["substitution"]["mean"]
        assert abs(means["reselect"][p] - ref) < 1e-12, (p, ref)
    g70 = json.load(io.open(G70, encoding="utf-8"))
    for p in POSTS:
        ref = g70["trajectories"]["frozen_set_all_units"][str(p)]["mean"]
        assert abs(means["frozen"][p] - ref) < 1e-12, (p, ref)
    # NB: means are fractions, g70's stored span is in pp -- the factor of 100
    # is part of the claim, not cosmetic.  A 1e-12 tolerance turns a forgotten
    # 100 into a loud failure; a loose tolerance would have let it through and
    # the reported span would be off by two orders of magnitude.
    assert abs(100.0 * (means["frozen"][12] - means["frozen"][4])
               - g70["spans_pp"]["frozen_set_all_units"]) < 1e-12
    # the headline span must reproduce g70's stored event-weighted all_units
    # span: difference-of-means == mean-of-differences only because every event
    # contributes at both horizons, and that equality is the thing this asserts
    assert abs(100.0 * (means["reselect"][12] - means["reselect"][4])
               - g70["spans_pp"]["all_units"]) < 1e-12
    # the control arm must be flat: a wide interval there is the instrument
    # showing it can produce wide intervals over nothing
    frozen_span_pp = 100.0 * (means["frozen"][12] - means["frozen"][4])
    assert abs(frozen_span_pp) < 1.0, frozen_span_pp

    res["width_ratios"] = {
        "cluster_over_unit_unpaired_pct":
            cl["reselect"]["span"]["pct_width_pp"] / unit["span"]["pct_width_pp"],
        "cluster_over_unit_paired_pct":
            cl["reselect"]["span"]["pct_width_pp"]
            / unit_paired["span"]["pct_width_pp"],
        "cluster_over_date_cluster_pct":
            cl["reselect"]["span"]["pct_width_pp"]
            / cl_date["reselect"]["span"]["pct_width_pp"],
    }
    res["reading_contract"]["design_vs_sampling"] = (
        "a tight interval here is sampling variability over events and says "
        "NOTHING about the design choice of redrawing S as the window grows: "
        "that comparison is g70's frozen-destination-set arm, whose span is "
        "%+.4f pp. An effect can have a narrow interval and still be mostly "
        "the screen being redrawn" % frozen_span_pp)

    def f(x):
        return "%+.4f" % (100.0 * x)

    for a in arms:
        for p in POSTS:
            s = cl[a]["posts"][str(p)]
            print("%-8s POST=%-2d point %s | pct [%s, %s] | t [%s, %s] "
                  "| SE %.4f | P(neg) %.3f"
                  % (a, p, f(means[a][p]), f(s["pct_lo"]), f(s["pct_hi"]),
                     f(s["t_lo"]), f(s["t_hi"]), 100.0 * s["se"],
                     s["share_negative"]))
        s = cl[a]["span"]
        print("%-8s SPAN 4->12 point %s | pct [%s, %s] | t [%s, %s] "
              "| P(neg) %.4f"
              % (a, f(means[a][12] - means[a][4]), f(s["pct_lo"]),
                 f(s["pct_hi"]), f(s["t_lo"]), f(s["t_hi"]),
                 s["share_negative"]))
    print("-- by closure date (%d clusters, df %d) --"
          % (len(date_groups), len(date_groups) - 1))
    for a in arms:
        s = cl_date[a]["span"]
        print("%-8s DATE SPAN point %s | pct [%s, %s] | t [%s, %s] "
              "| P(neg) %.4f"
              % (a, f(means[a][12] - means[a][4]), f(s["pct_lo"]),
                 f(s["pct_hi"]), f(s["t_lo"]), f(s["t_hi"]),
                 s["share_negative"]))
        s = cl_date[a]["posts"]["12"]
        print("%-8s DATE POST=12 point %s | pct [%s, %s] | t [%s, %s]"
              % (a, f(means[a][12]), f(s["pct_lo"]), f(s["pct_hi"]),
                 f(s["t_lo"]), f(s["t_hi"])))
    us = unit["span"]
    print("unit-bootstrap UNPAIRED SPAN (pairing destroyed): pct [%s, %s] "
          "width %.2f | t width %.2f"
          % (f(us["pct_lo"]), f(us["pct_hi"]), us["pct_width_pp"],
             us["t_width_pp"]))
    ps = unit_paired["span"]
    print("unit-bootstrap PAIRED   SPAN: pct [%s, %s] width %.2f | t width %.2f"
          % (f(ps["pct_lo"]), f(ps["pct_hi"]), ps["pct_width_pp"],
             ps["t_width_pp"]))
    print("span width cluster/unit (pct): %.2fx | (t): %.2fx"
          % (cl["reselect"]["span"]["pct_width_pp"] / us["pct_width_pp"],
             cl["reselect"]["span"]["t_width_pp"] / us["t_width_pp"]))
    print("span width cluster/unit_PAIRED (pct): %.2fx | (t): %.2fx"
          % (cl["reselect"]["span"]["pct_width_pp"] / ps["pct_width_pp"],
             cl["reselect"]["span"]["t_width_pp"] / ps["t_width_pp"]))

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print("sha", hashlib.sha256(open(OUT, "rb").read()).hexdigest()[:16])
    print("size", os.path.getsize(OUT))
    print("elapsed_s", round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
