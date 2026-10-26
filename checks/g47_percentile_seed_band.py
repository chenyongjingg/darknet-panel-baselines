# -*- coding: utf-8 -*-
"""G47 -- the seed band of the §5.1 percentiles (g30's same-unit ranks).

Why this exists: a percentile produced by 20,000 Monte-Carlo replicates with one
seed is a DRAW, not a constant.  Two people running the same code with different
seeds get different last digits, and neither is wrong.  That is exactly how a
reproducible number came to look stale on the other side of this project: four
percentiles were reported as "no exact holder in any product" when every one of
them sat inside the seed band of a quantity that was computing them correctly.
An audit that demands an exact holder will report a false negative for EVERY
seeded statistic, so the witness has to be a band, not a scalar.

The §5.3 block already prints its band (5 x 20k over the clean-7 arm).  The §5.1
table -- ratio / retained / new / union at 71.0 / 99.4 / 62.5 / 98.9 -- does not.
This script supplies it, and does so as a SECOND implementation of g30's core:
it re-reads g17/g19/g28 itself and must reproduce g30's stored
`percentile_same_unit` BIT FOR BIT at g30's seed before any other seed is
allowed to speak.  A band computed by a ruler that cannot reproduce the thing it
is bounding would bound nothing.

usage: python -I -X utf8 g47_percentile_seed_band.py [--seeds 5] [--reps N]
"""

import hashlib
import io
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
G17 = os.path.join(HERE, "g17_identity_placebo.json")
G19 = os.path.join(HERE, "g19_shipped_placebo.json")
G28 = os.path.join(HERE, "g28_time_local_placebo.json")
G30 = os.path.join(HERE, "g30_same_unit_null.json")
P40 = os.path.join(HERE, "g40_exposure_channels.json")
OUT = os.path.join(HERE, "g47_percentile_seed_band.json")
KEYS = ("ratio", "retained", "new", "union")
BASE_SEED = 20261026
N_REP = 20000


def extra_seed(i):
    """Deterministic pseudo-seed number i.

    A hard-coded tuple looks reproducible and is not scalable: the first version
    listed five seeds, so `--seeds 50` silently ran six and the band looked
    stable when it had only been sampled six times.  Deriving the seeds keeps
    `--seeds N` meaning what it says, and the list is written into the product
    so the band can be replayed without this function.
    """
    return int(hashlib.sha256(("g47:%d" % i).encode("utf-8")).hexdigest()[:8],
               16)


def stamp(path):
    if not os.path.exists(path):
        return {"file": os.path.basename(path), "absent": True}
    return {"file": os.path.basename(path),
            "sha256_16": hashlib.sha256(
                io.open(path, "rb").read()).hexdigest()[:16]}


def build_arms(g17, g19, g28):
    """Same four arms, same pools, same real-side means as g30 -- rebuilt here."""
    arms = {}
    p17 = {k: {} for k in KEYS}
    real17 = {}
    for e in g17["per_event"]:
        for k in KEYS:
            v = [x for x in e["null"].get(k, []) if x is not None]
            if v:
                p17[k][e["market"]] = v
        real17[e["market"]] = g17["shipped_means"]
    arms["g17_range"] = {"real_by_market": real17, "pool": p17}

    ev19 = [e for e in g19["per_event"] if e["null"]]
    pools = {}
    for k in KEYS:
        pools[k] = {e["market"]: [x[k] for x in e["null"] if x.get(k) is not None]
                    for e in ev19}
        pools[k] = {m: v for m, v in pools[k].items() if v}
    real19 = {e["market"]: e["real_fixed_S"] for e in ev19 if e["real_fixed_S"]}
    arms["g19_range"] = {"real_by_market": real19, "pool": pools}

    for arm, band in (("same_era", "A_5_12"), ("band_C", "C_27_40")):
        pools = {k: {} for k in KEYS}
        real_by = {e["market"]: e["real"] for e in g28["per_event"]}
        for e in g28["per_event"]:
            for k in KEYS:
                v = [x[k] for x in e["bands"][band]["raw"]
                     if x.get(k) is not None]
                if v:
                    pools[k][e["market"]] = v
        arms[arm] = {"real_by_market": real_by, "pool": pools}
    return arms


def percentile(pl, real_by_market, k, rng, reps):
    """One key's rank, drawing from the ARM's RNG in KEYS order.

    The RNG must be the arm's, created once and consumed across keys in KEYS
    order -- g30 does exactly that.  A fresh RNG per key restarts the stream and
    silently changes every key after the first: measured, band_C/new came out
    0.85995 against g30's 0.8603, which is what caught it.
    """
    markets = sorted(pl[k])
    rv = [real_by_market[m][k] for m in markets
          if real_by_market.get(m, {}).get(k) is not None]
    if not markets or not rv:
        return None           # g30 also skips without consuming any draws
    realv = sum(rv) / len(rv)
    vals = []
    for _ in range(reps):
        vals.append(sum(pl[k][m][rng.randrange(len(pl[k][m]))]
                        for m in markets) / len(markets))
    vals.sort()
    pct = sum(1 for v in vals if v < realv) / len(vals)
    return {"percentile": pct, "real": realv, "n_events": len(markets)}


def main():
    seeds_n = 5
    reps = N_REP
    if "--seeds" in sys.argv:
        seeds_n = int(sys.argv[sys.argv.index("--seeds") + 1])
    if "--reps" in sys.argv:
        reps = int(sys.argv[sys.argv.index("--reps") + 1])

    g17 = json.load(io.open(G17, encoding="utf-8"))
    g19 = json.load(io.open(G19, encoding="utf-8"))
    g28 = json.load(io.open(G28, encoding="utf-8"))
    g30 = json.load(io.open(G30, encoding="utf-8"))
    arms = build_arms(g17, g19, g28)

    res = {"stage": "G47",
           "inputs": {"g17_identity_placebo.json": stamp(G17),
                      "g19_shipped_placebo.json": stamp(G19),
                      "g28_time_local_placebo.json": stamp(G28),
                      "g30_same_unit_null.json": stamp(G30),
                      "g40_exposure_channels.json": stamp(P40)},
           "params": {"base_seed": BASE_SEED, "seeds": seeds_n, "n_rep": reps,
                      "extra_seeds": [extra_seed(i)
                                      for i in range(1, seeds_n)]},
           "arms": {}}

    seed_list = [BASE_SEED] + [extra_seed(i) for i in range(1, seeds_n)]
    worst_cal = 0.0
    for arm in sorted(arms):
        pool = arms[arm]["pool"]
        real = arms[arm]["real_by_market"]
        # replay each seed ONCE for the whole arm, keys in KEYS order -- the
        # same consumption order as g30, so the draws sit where g30 put them
        by_seed = []
        for s in seed_list:
            rng = random.Random(s ^ int(hashlib.sha256(
                arm.encode("utf-8")).hexdigest()[:8], 16))
            by_seed.append({kk: percentile(pool, real, kk, rng, reps)
                            for kk in KEYS if pool.get(kk)})
        out = {}
        for k in KEYS:
            if not pool.get(k):
                continue
            got = [d[k] for d in by_seed if d.get(k)]
            if not got:
                continue
            stored = g30["arms"][arm]["by_key"][k]["percentile_same_unit"]
            # calibration: the re-implementation must land exactly on g30's
            # number at g30's own seed, or the band below bounds nothing
            assert abs(got[0]["percentile"] - stored) < 1e-15, (
                "%s/%s: re-implementation gives %r, g30 stored %r"
                % (arm, k, got[0]["percentile"], stored))
            worst_cal = max(worst_cal, abs(got[0]["percentile"] - stored))
            pcts = [x["percentile"] for x in got]
            out[k] = {"g30_stored": stored,
                      "band_min": min(pcts), "band_max": max(pcts),
                      "band_width_pp": (max(pcts) - min(pcts)) * 100.0,
                      # a zero-width band at 0 or 100 is a CEILING, not
                      # robustness: the rank cannot move because every replicate
                      # is already on one side of the real value
                      "at_boundary": stored in (0.0, 1.0),
                      "values": pcts,
                      "real": got[0]["real"],
                      "n_events": got[0]["n_events"]}
        res["arms"][arm] = out

    res["calibration"] = {"rule": "second implementation reproduces g30's "
                                  "percentile_same_unit bit-for-bit at "
                                  "g30's seed before any other seed is used",
                          "worst_abs_diff": worst_cal}

    # ---- the n behind 0.0622, and the identity that pins it ----------------
    # A mean quoted without its n is the same defect class as a percentile
    # quoted without its band: "exposed 0.0622 vs clean 0.0181" is 5 vs 7, not
    # 12 vs 7 -- the 12-event mean is 0.036494.  The three numbers are tied by
    #   5 * exposed + 7 * clean == 12 * all12
    # so if any of them is ever recomputed over a different event set, the
    # identity breaks instead of the prose quietly changing meaning.
    g40all = json.load(io.open(P40, encoding="utf-8"))
    g40p = g40all["permutation_exposed_vs_not"]
    n_clean = len(g40all["exposure_clean"])
    ident = {}
    worst_id = 0.0
    for k in KEYS:
        a = g40p[k]["mean_exposed"]      # the 5 capped-exposed events
        b = g40p[k]["mean_unexposed"]    # the 7 clean events
        c = g30["arms"]["same_era"]["by_key"][k]["real"]   # all 12
        # n_exposed follows from the identity given the two other counts; it is
        # solved for rather than trusted, and must come out an integer
        n_a = None
        for cand in range(1, 13):
            if abs(cand * a + (12 - cand) * b - 12 * c) < 1e-12:
                n_a = cand
                break
        assert n_a is not None, "%s: no integer split satisfies the identity" % k
        assert (n_a, 12 - n_a) == (5, 7), "%s: split is %r, not 5/7" % (k, n_a)
        assert 12 - n_a == n_clean, "clean count disagrees with g40: %r" % (n_clean,)
        worst_id = max(worst_id, abs(n_a * a + (12 - n_a) * b - 12 * c))
        ident[k] = {"n_exposed": n_a, "n_clean": 12 - n_a,
                    "mean_exposed": a, "mean_clean": b, "mean_all12": c,
                    "exposed_share_of_all12_mean": (n_a * a) / (12 * c)}
    res["mean_identity"] = {
        "identity": "n_exposed*mean_exposed + n_clean*mean_clean == 12*mean_all12",
        "worst_abs_residual": worst_id,
        "by_key": ident,
        "reading": "0.0622 is the 5-event mean; the 12-event mean is 0.036494. "
                   "Quoting the pair as 12-vs-7 would move the permutation's "
                   "sampling space as well as the numbers"}
    widest = max((v["band_width_pp"], a, k)
                 for a, d in res["arms"].items() for k, v in d.items())
    res["summary"] = {"widest_band_pp": widest[0], "widest_at": "%s/%s"
                      % (widest[1], widest[2]),
                      "reading": "these percentiles move by up to a few tenths "
                                 "of a point between seeds; a single-seed value "
                                 "must be quoted with its band or not compared "
                                 "to anyone else's"}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for arm in sorted(res["arms"]):
        for k, v in res["arms"][arm].items():
            print("%-9s %-9s stored %.2f  band [%.2f, %.2f]  width %.2f pp"
                  % (arm, k, v["g30_stored"] * 100,
                     v["band_min"] * 100, v["band_max"] * 100,
                     v["band_width_pp"]))
    for k, v in res["mean_identity"]["by_key"].items():
        print("identity %-9s n=%d+%d  exposed %.6f  clean %.6f  all12 %.6f  "
              "exposed share %.1f%%"
              % (k, v["n_exposed"], v["n_clean"], v["mean_exposed"],
                 v["mean_clean"], v["mean_all12"],
                 100 * v["exposed_share_of_all12_mean"]))
    print("calibration worst_abs_diff = %r" % worst_cal)
    print("widest band %.2f pp at %s" % (widest[0], res["summary"]["widest_at"]))


if __name__ == "__main__":
    main()
