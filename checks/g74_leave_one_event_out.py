# -*- coding: utf-8 -*-
"""G74 -- is the 4->12 span one event's doing?

The cluster bootstrap in g73 says how far a re-sample of the twelve events can
move the span.  It does not say whether the span survives deleting any single
event, and that is the question a referee asks next ("is this agora?").  This
script answers it exactly, with no resampling: drop one event, recompute the
event-weighted mean at each horizon and the 4->12 span, and also recompute the
EXACT sign-flip randomisation p for the span on the reduced set (2^n sign
patterns, enumerated, n = 11 or 12 -- no approximation is needed at this size).

Two uncertainties, two nulls -- they must not be quoted interchangeably:

  bootstrap (g73)     sampling: what would another draw of twelve events say
  sign-flip (here)    exchangeability: if the intervention did nothing, how
                      surprising is this sum of per-event differences

The leave-one-out set is not a robustness ornament: if deleting a single event
turns the span's p over 0.05, then the finding is one market's accounting and
the plan must say so in the same sentence as the point estimate.

Input is g73's product plus g70's stored sign-flip p's; the panel is not
re-read, so this cannot drift away from the trajectory it decomposes.
Calibration, two independent bindings:

  (a) full-set means recomputed from g73's stored per-event differences must
      reproduce g73's own stored point estimates and span to 1e-12 -- if not,
      the per-event table and the summary are two rulers over one thing;
  (b) the per-horizon sign-flip p computed here must reproduce g70's stored
      `all_units_p_by_post` for all three horizons under exactly ONE of the two
      conventions (one-sided negative / two-sided).  The convention is
      IDENTIFIED, not assumed: if neither matches, this enumerator disagrees
      with the one already in the paper and the paper's p is the one that has
      to be re-derived.  Same span, two nulls -- the sign-flip p is
      exchangeability under no effect, g73's interval is sampling variability,
      and they must not be quoted interchangeably.

usage: python -I -X utf8 g74_leave_one_event_out.py
"""
import hashlib
import io
import itertools
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
G73 = os.path.join(HERE, "g73_event_cluster_boot.json")
G70 = os.path.join(HERE, "g70_same_degree.json")
G67 = os.path.join(HERE, "g67_post_horizon.json")
OUT = os.path.join(HERE, "g74_leave_one_event_out.json")
POSTS = ("4", "8", "12")
ARMS = ("reselect", "frozen")


def main():
    t0 = time.time()
    g73 = json.load(io.open(G73, encoding="utf-8"))
    pe = g73["per_event_diffs_pp"]
    evs = sorted(pe["reselect"]["4"])
    n = len(evs)

    def means_from(arm, keep):
        """event-weighted mean at each horizon over the kept events"""
        out = {}
        for p in POSTS:
            vals = [pe[arm][p][e] for e in keep
                    if pe[arm][p].get(e) is not None]
            out[p] = sum(vals) / float(len(vals)) if vals else None
        return out

    def span_from(arm, keep):
        keep2 = [e for e in keep
                 if pe[arm]["4"].get(e) is not None
                 and pe[arm]["12"].get(e) is not None]
        return (means_from(arm, keep2)["12"] - means_from(arm, keep2)["4"],
                len(keep2))

    def signflip_p(arm, keep, side="negative"):
        """EXACT randomisation p for the span, all 2^n sign patterns.

        Under the null each event's paired difference d_i = d12_i - d4_i is
        symmetric about zero, so the distribution of sum(+-d_i) is the
        reference.  Two-sided is reported alongside the one-sided negative
        because the plan states a direction; quoting only the one-sided value
        would overstate the evidence for that direction.
        """
        keep2 = [e for e in keep
                 if pe[arm]["4"].get(e) is not None
                 and pe[arm]["12"].get(e) is not None]
        d = [pe[arm]["12"][e] - pe[arm]["4"][e] for e in keep2]
        obs = sum(d)
        tot = 0
        le = 0
        ge = 0
        for signs in itertools.product((1.0, -1.0), repeat=len(d)):
            s = sum(a * b for a, b in zip(signs, d))
            tot += 1
            if s <= obs + 1e-12:
                le += 1
            if abs(s) >= abs(obs) - 1e-12:
                ge += 1
        return {"n_patterns": tot, "observed_sum_pp": obs,
                "p_one_sided_negative": le / float(tot),
                "p_two_sided": ge / float(tot)}

    def signflip_level(arm, keep, p):
        """exact sign-flip for ONE horizon: are B1 and A distinguishable at p?"""
        keep2 = [e for e in keep if pe[arm][p].get(e) is not None]
        d = [pe[arm][p][e] for e in keep2]
        obs = sum(d)
        tot = le = ge = 0
        for signs in itertools.product((1.0, -1.0), repeat=len(d)):
            s = sum(a * b for a, b in zip(signs, d))
            tot += 1
            if s <= obs + 1e-12:
                le += 1
            if abs(s) >= abs(obs) - 1e-12:
                ge += 1
        return {"p_one_sided_negative": le / float(tot),
                "p_two_sided": ge / float(tot)}

    def signflip_span_by_date(arm, groups):
        """EXACT sign-flip at the closure-DATE level.

        Events sharing a closure week share one shock, so the exchangeable
        unit is the date, not the event: sum the per-event differences inside a
        date first, then enumerate 2^k sign patterns over the k dates.  The
        observed statistic is the same total (events keep their weight inside
        a cluster); what changes is which re-signings of the world count as
        equally likely.  Fewer clusters means a coarser set of attainable p's
        -- with k dates the smallest two-sided p is 2/2^k, so "p > 0.05" here
        can mean "not established", never "absent".
        """
        sums = []
        for g_ in groups:
            keep = [e for e in g_ if pe[arm]["4"].get(e) is not None
                    and pe[arm]["12"].get(e) is not None]
            if keep:
                sums.append(sum(pe[arm]["12"][e] - pe[arm]["4"][e]
                                for e in keep))
        obs = sum(sums)
        tot = le = ge = 0
        for signs in itertools.product((1.0, -1.0), repeat=len(sums)):
            s = sum(a * b for a, b in zip(signs, sums))
            tot += 1
            if s <= obs + 1e-12:
                le += 1
            if abs(s) >= abs(obs) - 1e-12:
                ge += 1
        return {"n_clusters": len(sums), "n_patterns": tot,
                "observed_sum_pp": obs,
                "p_floor_two_sided": 2.0 / tot,
                "p_one_sided_negative": le / float(tot),
                "p_two_sided": ge / float(tot)}

    # ---- calibration (b): identify g70's convention, do not assume it ------
    g70 = json.load(io.open(G70, encoding="utf-8"))
    ref_p = g70["calibration_vs_g67"]["all_units_p_by_post"]
    conv = {}
    for name in ("p_one_sided_negative", "p_two_sided"):
        conv[name] = [signflip_level("reselect", evs, p)[name] for p in POSTS]
    matched = [name for name in conv
               if all(abs(conv[name][i] - ref_p[p]) < 1e-12
                      for i, p in enumerate(POSTS))]
    assert len(matched) == 1, (
        "sign-flip convention not identified against g70: %r vs %r"
        % ({k: v for k, v in conv.items()}, ref_p))
    convention = matched[0]

    # ---- calibration (c): the LEVEL leave-one-out already exists in g67 ----
    # g67 stores, per horizon, a leave-one-out over the same twelve events with
    # the same statistic.  Reproducing it cell by cell is the only thing that
    # entitles this file to extend the same enumeration to the span; a new
    # statistic computed with a new enumerator on the same events is exactly a
    # second ruler nobody checked.
    g67 = json.load(io.open(G67, encoding="utf-8"))
    loo_repro = {}
    for p in POSTS:
        ref = g67["by_post"][p]["summary_all"]["substitution"]
        # g67 stores FRACTIONS; g73/g70 store pp.  Same trap as g73's span
        # calibration -- second occurrence, so it gets a name here: the unit is
        # part of the claim, and a 1e-12 tolerance is what makes a forgotten
        # factor of 100 a loud failure instead of a plausible number.
        PP = 100.0
        mine = {"mean": means_from("reselect", evs)[p] / PP,
                "p": signflip_level("reselect", evs, p)[convention]}
        assert abs(mine["mean"] - ref["mean"]) < 1e-12, (p, mine, ref)
        assert abs(mine["p"] - ref["exact_signflip_p"]) < 1e-12, (p, mine, ref)
        cells = []
        for row in ref["loo"]:
            drop = row["dropped"]
            keep = [e for e in evs if e != drop]
            m2 = means_from("reselect", keep)[p] / PP
            p2 = signflip_level("reselect", keep, p)[convention]
            assert abs(m2 - row["mean"]) < 1e-12, (p, drop, m2, row["mean"])
            assert abs(p2 - row["exact_p"]) < 1e-12, (p, drop, p2,
                                                      row["exact_p"])
            cells.append({"dropped": drop, "mean_pp": m2, "p": p2})
        assert len(cells) == n
        loo_repro[p] = {
            "n_cells_reproduced": len(cells),
            "cells": cells,
            "g67_loo_cross_0p05_events": ref["loo_cross_0p05_events"],
            "g67_loo_signflip_events": ref["loo_signflip_events"],
            "g67_p_floor": ref["p_floor"]}

    # ---- calibration: the per-event table must regenerate the summary ------
    res = {"stage": "G74", "source": os.path.basename(G73),
           "source_sha16": hashlib.sha256(
               open(G73, "rb").read()).hexdigest()[:16],
           "n_events": n, "events": evs,
           "signflip_convention_identified": convention,
           "g70_reference_p_by_post": ref_p,
           "g74_p_by_post": {p: signflip_level("reselect", evs, p)[convention]
                             for p in POSTS},
           "g67_level_loo_reproduced": loo_repro,
           "date_groups": g73["date_groups"],
           "by_arm": {},
           "by_date": {}}
    for arm in ARMS:
        full = means_from(arm, evs)
        for p in POSTS:
            ref = g73["point_estimates_pp"][arm][p]
            assert abs(full[p] - ref) < 1e-12, (arm, p, full[p], ref)
        sp, k = span_from(arm, evs)
        ref = g73["span_4_to_12_pp"][arm]
        assert abs(sp - ref) < 1e-12, (arm, sp, ref)
        assert k == n, (arm, k, n)

        # ---- leave one event out -------------------------------------------
        loo = {}
        for drop in evs:
            keep = [e for e in evs if e != drop]
            m = means_from(arm, keep)
            s, kk = span_from(arm, keep)
            loo[drop] = {"mean_pp": {p: m[p] for p in POSTS},
                         "span_pp": s, "n_kept": kk,
                         "span_shift_pp": s - sp,
                         "signflip": signflip_p(arm, keep),
                         "p_level_by_post": {
                             p: signflip_level(arm, keep, p)[convention]
                             for p in POSTS}}
        shifts = sorted(loo.items(), key=lambda kv: -abs(kv[1]["span_pp"] - sp))
        # a span that any single deletion can flatten is one event's arithmetic
        worst = shifts[0]
        survived = all(v["signflip"][convention] <= 0.05
                       for v in loo.values())
        res["by_arm"][arm] = {
            "mean_pp": {p: full[p] for p in POSTS},
            "span_pp": sp,
            "signflip_full": signflip_p(arm, evs),
            "leave_one_out": loo,
            "ranking_by_abs_shift": [
                {"dropped": k_, "span_pp": v["span_pp"],
                 "shift_pp": v["span_shift_pp"],
                 "p_span": v["signflip"][convention],
                 "sign_survives": (v["span_pp"] < 0) == (sp < 0)}
                for k_, v in shifts],
            "worst_deletion": {"event": worst[0],
                               "span_pp": worst[1]["span_pp"],
                               "shift_pp": worst[1]["span_shift_pp"],
                               "p_span": worst[1]["signflip"][convention]},
            "every_deletion_keeps_p_lea_005": survived,
        }
        dg = [sorted(v) for _, v in sorted(g73["date_groups"].items(),
                                           key=lambda kv: int(kv[0]))]
        res["by_date"][arm] = signflip_span_by_date(arm, dg)

    # the frozen arm is the control; the reselect arm is the claim
    rs = res["by_arm"]["reselect"]
    res["reading_contract"] = {
        "must_quote": "span with the worst single deletion named, not instead "
                      "of, the full-set span",
        "must_not_say": "that the span is robust, if any single deletion "
                        "pushes its p above 0.05 under the convention "
                        "identified against g70",
        "nulls_differ": "the sign-flip p is exchangeability under no effect; "
                        "g73's interval is sampling variability. Same span, "
                        "two different questions",
        "convention": convention,
    }
    res["verdict"] = {
        "full_span_pp": rs["span_pp"],
        "convention": convention,
        "full_p_span": rs["signflip_full"][convention],
        "full_p_span_one_sided_negative":
            rs["signflip_full"]["p_one_sided_negative"],
        "full_p_span_two_sided": rs["signflip_full"]["p_two_sided"],
        "worst_deletion": rs["worst_deletion"],
        "every_deletion_keeps_p_lea_005":
            rs["every_deletion_keeps_p_lea_005"],
        "by_date_reselect": res["by_date"]["reselect"],
        "by_date_frozen": res["by_date"]["frozen"],
    }

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    for arm in ARMS:
        a = res["by_arm"][arm]
        print("%-8s span %+.4f pp | full sign-flip p1 %.4f p2 %.4f"
              % (arm, a["span_pp"],
                 a["signflip_full"]["p_one_sided_negative"],
                 a["signflip_full"]["p_two_sided"]))
        for row in a["ranking_by_abs_shift"][:4]:
            print("   drop %-14s span %+.4f  shift %+.4f  p %.4f  sign_ok %s"
                  % (row["dropped"], row["span_pp"], row["shift_pp"],
                     row["p_span"], row["sign_survives"]))
        print("   every deletion keeps p<=0.05: %s"
              % a["every_deletion_keeps_p_lea_005"])
        bd = res["by_date"][arm]
        print("   by closure date: k=%d p1 %.6f p2 %.6f (floor %.6f)"
              % (bd["n_clusters"], bd["p_one_sided_negative"],
                 bd["p_two_sided"], bd["p_floor_two_sided"]))
    print("sha", hashlib.sha256(open(OUT, "rb").read()).hexdigest()[:16])
    print("size", os.path.getsize(OUT))
    print("elapsed_s", round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
