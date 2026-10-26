# -*- coding: utf-8 -*-
"""G30 -- the percentile must rank a 12-event mean against a 12-event mean.

g19 compared two objects in different units.  On the observation side it pooled
every single (event, random-week) draw into one distribution -- 296 values for
the ratio -- and on the real side it put the MEAN OVER 12 EVENTS.  A mean of 12
has ~1/12 the variance of one draw, so its percentile is pulled toward 50 no
matter what the data say.  Every percentile in g19's
`real_percentile_in_null` is therefore an artifact of the comparison, and the
sentence built on them ("all four percentiles sit between 45 and 68") is not
supported by any measurement.

The repair needs no new data: the per-event draws are still in g19's product.
A replicate is now formed the way the real value is --

    replicate r = mean over events of (one randomly drawn week for that event)

-- so both sides are 12-event means and the only thing that differs is whether
the weeks are real or random.  Three arms:

    g17_range    g17's own draws (all whitelist destinations), unit fixed
    g19_range    g19's own draws (event - 40 .. -1 weeks), unit fixed
    same_era     g28's band A (5-12 weeks before the event): unit AND era fixed
    band_C       g28's band C (27-40 weeks): the far tail, for the contrast

For each arm the report gives the real value, the replicate distribution, the
percentile, a two-sided empirical p, and -- printed next to it -- the OLD
single-draw percentile, so the size of the unit error is visible in the same
row rather than asserted in prose.

usage: python -I -X utf8 g30_same_unit_null.py
"""
import hashlib
import io
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
G17 = os.path.join(HERE, "g17_identity_placebo.json")
G19 = os.path.join(HERE, "g19_shipped_placebo.json")
G28 = os.path.join(HERE, "g28_time_local_placebo.json")
OUT = os.path.join(HERE, "g30_same_unit_null.json")
KEYS = ("ratio", "retained", "new", "union")
N_REP = 20000
SEED = 20261026


def main():
    g17 = json.load(io.open(G17, encoding="utf-8"))
    g19 = json.load(io.open(G19, encoding="utf-8"))
    g28 = json.load(io.open(G28, encoding="utf-8"))
    rng = random.Random(SEED)

    arms = {}

    # g17 has the same defect as g19 -- it pools single (event, week) draws and
    # ranks the 12-event mean (shipped_means) inside them -- so its headline
    # 18.2nd percentile is on the same broken ruler.  Same repair, same code.
    p17 = {k: {} for k in KEYS}
    real17 = {}
    for e in g17["per_event"]:
        for k in KEYS:
            v = [x for x in e["null"].get(k, []) if x is not None]
            if v:
                p17[k][e["market"]] = v
        real17[e["market"]] = g17["shipped_means"]
    arms["g17_range"] = {"real_by_market": real17,
                         "event_pools": {k: {m: len(v) for m, v in p17[k].items()}
                                         for k in KEYS},
                         "_pool": p17}

    # ---- arm 1: g19's own draws, unit corrected -------------------------
    ev19 = [e for e in g19["per_event"] if e["null"]]
    pools = {}
    for k in KEYS:
        pools[k] = {e["market"]: [x[k] for x in e["null"] if x.get(k) is not None]
                    for e in ev19}
        pools[k] = {m: v for m, v in pools[k].items() if v}
    real19 = {e["market"]: e["real_fixed_S"] for e in ev19 if e["real_fixed_S"]}
    arms["g19_range"] = {"real_by_market": real19,
                         "event_pools": {k: {m: len(v) for m, v in pools[k].items()}
                                         for k in KEYS},
                         "_pool": pools}

    # ---- arms 2/3: g28's per-week values, band A and band C -------------
    for arm, band in (("same_era", "A_5_12"), ("band_C", "C_27_40")):
        pools = {k: {} for k in KEYS}
        real_by = {e["market"]: e["real"] for e in g28["per_event"]}
        for e in g28["per_event"]:
            for k in KEYS:
                v = [x[k] for x in e["bands"][band]["raw"]
                     if x.get(k) is not None]
                if v:
                    pools[k][e["market"]] = v
        arms[arm] = {"real_by_market": real_by,
                     "event_pools": {k: {m: len(v) for m, v in pools[k].items()}
                                     for k in KEYS},
                     "_pool": pools}

    def rank(sorted_vals, x):
        return sum(1 for v in sorted_vals if v < x) / len(sorted_vals)

    res = {"stage": "G30",
           "question": "percentile of a 12-event mean must be taken in the "
                       "same unit",
           "inputs": {"g17": G17, "g19": G19, "g28": G28},
           "params": {"n_rep": N_REP, "seed": SEED,
                      "replicate": "mean over events of one drawn week each"},
           "arms": {}}

    for arm, spec in arms.items():
        # one RNG per arm, seeded from the arm name: adding or removing an arm
        # must not move another arm's numbers, or every quoted percentile goes
        # stale the next time the script grows
        rng = random.Random(SEED ^ int(hashlib.sha256(
            arm.encode("utf-8")).hexdigest()[:8], 16))
        pools = spec.pop("_pool")
        out = {"event_pools": spec["event_pools"], "by_key": {}}
        for k in KEYS:
            pl = pools[k]
            if not pl:
                continue
            markets = sorted(pl)
            # the real side must be the mean over the SAME events the null uses
            rv = [spec["real_by_market"][m][k] for m in markets
                  if spec["real_by_market"].get(m, {}).get(k) is not None]
            if not rv:
                continue
            realv = sum(rv) / len(rv)
            reps = []
            for _ in range(N_REP):
                reps.append(sum(pl[m][rng.randrange(len(pl[m]))]
                                for m in markets) / len(markets))
            reps.sort()
            # the OLD comparison, reproduced on purpose: rank the 12-event mean
            # inside the pooled single-draw values
            flat = sorted(x for m in markets for x in pl[m])
            old_pct = rank(flat, realv)
            pct = rank(reps, realv)
            ge = sum(1 for v in reps if v >= realv) / N_REP
            le = sum(1 for v in reps if v <= realv) / N_REP
            out["by_key"][k] = {
                "n_events": len(rv),
                "n_events_in_pool": len(markets),
                "real": realv,
                "replicate_mean": sum(reps) / N_REP,
                "replicate_p05": reps[int(0.05 * (N_REP - 1))],
                "replicate_p50": reps[N_REP // 2],
                "replicate_p95": reps[int(0.95 * (N_REP - 1))],
                "percentile_same_unit": pct,
                "p_two_sided": min(1.0, 2 * min(ge, le)),
                "percentile_old_single_draw": old_pct,
                "n_pooled_single_draws": len(flat),
            }
        res["arms"][arm] = out

    # ---- the dependence the per-event draws break -----------------------
    # drawing an independent week per event treats the 12 events as independent,
    # but they fall on only 8 distinct death weeks and share the panel state of
    # whatever week they are re-timed to.  A COMMON shift keeps every event on
    # the same offset, so whatever is shared stays shared.  Few offsets survive
    # (36 at most), so this is reported as a rank among shifts with its own
    # resolution, not as a p-value.
    wk = {k: {} for k in KEYS}
    for e in g28["per_event"]:
        for band in ("A_5_12", "B_13_26", "C_27_40"):
            for x in e["bands"][band]["raw"]:
                for k in KEYS:
                    if x.get(k) is not None:
                        wk[k].setdefault(e["market"], {})[x["w"] - e["t"]] = x[k]
    cs = {}
    for k in KEYS:
        offsets = sorted({d for m in wk[k] for d in wk[k][m]})
        vals = []
        for d in offsets:
            v = [wk[k][m][d] for m in wk[k] if d in wk[k][m]]
            if len(v) >= 6:                      # need most events present
                vals.append((d, sum(v) / len(v), len(v)))
        if not vals:
            continue
        rvv = [x["real"][k] for x in g28["per_event"]
               if x["real"].get(k) is not None]
        rv = sum(rvv) / len(rvv)
        sv = sorted(x[1] for x in vals)
        cs[k] = {"n_offsets": len(vals),
                 "real": rv,
                 "shift_mean_lo": sv[0], "shift_mean_hi": sv[-1],
                 "shift_mean_p50": sv[len(sv) // 2],
                 "rank_of_real": sum(1 for x in sv if x < rv) / len(sv),
                 "by_offset": {str(d): v for d, v, _ in vals}}
    res["common_shift"] = {
        "note": "one offset for all events; preserves the dependence the "
                "per-event draws remove; resolution is 1/n_offsets",
        "by_key": cs}

    # what the peer asked for: the same-era per-event pools in g19's shape, so
    # they can recompute rather than quote my summary.
    export = {}
    for arm, band in (("same_era", "A_5_12"), ("band_C", "C_27_40")):
        evs = []
        for e in g28["per_event"]:
            rows = []
            for x in e["bands"][band]["raw"]:
                rows.append({"w": x["w"], "ratio": x.get("ratio"),
                             "retained": x.get("retained"), "new": x.get("new"),
                             "union": x.get("union"),
                             "n_post_u": x.get("n_post_u")})
            evs.append({"market": e["market"], "t": e["t"],
                        "real": {k: e["real"].get(k) for k in KEYS},
                        "null": rows})
        export[arm] = evs
    res["per_event_null"] = {
        "note": "same shape as g19.per_event[].null, one dict per drawn week; "
                "real is the event's own value under the same destination rule, "
                "so both sides of the comparison share a population",
        "arms": export}

    res["sha_note"] = ("old_single_draw reproduces g19's real_percentile_in_null; "
                       "the difference between it and same_unit is the unit error")
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    for arm in arms:
        print("== %s ==" % arm)
        for k in KEYS:
            b = res["arms"][arm]["by_key"].get(k)
            if not b:
                continue
            print("  %-8s real %+.4f  n_ev %2d  null mean %+.4f "
                  "[p05 %+.4f, p95 %+.4f]  pct %6.2f (old %6.2f)  p2 %.4f"
                  % (k, b["real"], b["n_events"], b["replicate_mean"],
                     b["replicate_p05"], b["replicate_p95"],
                     100 * b["percentile_same_unit"],
                     100 * b["percentile_old_single_draw"], b["p_two_sided"]))
    print("== common shift (one offset for all events) ==")
    for k in KEYS:
        c = res["common_shift"]["by_key"].get(k)
        if not c:
            continue
        print("  %-8s real %+.4f  shifts n=%d mean [%+.4f, %+.4f] p50 %+.4f  "
              "rank %.2f" % (k, c["real"], c["n_offsets"], c["shift_mean_lo"],
                             c["shift_mean_hi"], c["shift_mean_p50"],
                             c["rank_of_real"]))
    print("sha", hashlib.sha256(open(OUT, "rb").read()).hexdigest()[:16])


if __name__ == "__main__":
    main()
