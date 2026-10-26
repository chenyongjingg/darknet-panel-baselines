# -*- coding: utf-8 -*-
"""G52 -- the R3 headline rests on ONE choice that is not in any table: what
counts as the same vendor.

Two presences in two markets are the "same vendor" because their name strings
are equal AFTER strip().lower().  Nothing else is checked, and nothing has ever
varied that rule.  Every number in §5.3 -- 0.539658, the equal-vendor share, the
coverage floor -- is conditional on it, so a reviewer is entitled to ask what
the headline does when the rule changes.

The rule moves the answer in BOTH directions, which is why it cannot be argued
away:
  * COARSER keys merge names that differ only in spacing / punctuation / unicode
    form -> more vendors look multi-homing -> the share rises (a CEILING);
  * the RAW key (no strip, no lower) splits one seller into several identities
    -> the share falls (a FLOOR).
So the honest object is a band whose ends are different rules, not a point.

Seven rules are evaluated in one pass over the 16 pre-split shards:
  raw                  the field exactly as stored
  strip_lower          the baseline (this is what every other file uses)
  nfkc                 NFKC + strip + lower
  nfkc_ws              + collapse internal whitespace runs to one space
  nfkc_nows            + delete all whitespace
  nfkc_alnum           + delete everything that is not alphanumeric (unicode)
  nfkc_alnum_ascii     + the same, restricted to ASCII alphanumerics

The baseline MUST reproduce 0.5396584255637941 bit for bit; if it does not, the
shards are not the file the headline came from and nothing here is comparable.
That assertion is also what makes the shards usable at all: they are a cached
copy of an input, and a cached copy that does not reproduce its own product is
not evidence.

usage: python -I -X utf8 g52_vendor_key_grid.py [--workers N]
"""

import collections
import csv
import datetime as dt
import hashlib
import io
import json
import os
import pickle
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "g1work")
P44 = os.path.join(HERE, "g44_truncation_vs_headline_share.json")
OUT = os.path.join(HERE, "g52_vendor_key_grid.json")
HEADLINE = 0.5396584255637941
MIN_TOT = 50
PARTS = 16
WEEK0 = dt.date(2013, 10, 7).toordinal()

WHITELIST = {
    "agora", "alphabay", "evolution", "nucleus", "valhalla", "abraxas",
    "middleearth", "silkroad2", "tochkafreemarket", "hansamarket", "blackbank",
    "cloudnine", "oxygen", "pandora", "silkkitie", "dream", "realdealmarket",
    "oasis", "andromeda", "outlaw", "onionmarket", "thepiratemarket", "alpaca",
    "haven", "bungee54", "1776",
}


def mkey(s):
    return (s or "").lower().replace(" ", "")


def k_raw(v):
    return v


def k_strip_lower(v):
    return v.strip().lower()


def k_nfkc(v):
    return unicodedata.normalize("NFKC", v).strip().lower()


def k_nfkc_ws(v):
    return " ".join(k_nfkc(v).split())


def k_nfkc_nows(v):
    return "".join(k_nfkc(v).split())


def k_nfkc_alnum(v):
    return "".join(c for c in k_nfkc(v) if c.isalnum())


def k_nfkc_alnum_ascii(v):
    return "".join(c for c in k_nfkc(v) if c.isascii() and c.isalnum())


RULES = collections.OrderedDict([
    ("raw", k_raw),
    ("strip_lower", k_strip_lower),
    ("nfkc", k_nfkc),
    ("nfkc_ws", k_nfkc_ws),
    ("nfkc_nows", k_nfkc_nows),
    ("nfkc_alnum", k_nfkc_alnum),
    ("nfkc_alnum_ascii", k_nfkc_alnum_ascii),
])


def scan_part(i):
    t0 = time.time()
    wk = {name: collections.defaultdict(collections.Counter) for name in RULES}
    rows = kept = 0
    with io.open(os.path.join(WORK, "part_%02d" % i), encoding="utf-8",
                 newline="") as f:
        rd = csv.reader(f, delimiter="\t")
        for row in rd:
            if not row or row[0] == "date":
                continue                       # header (only part_00 has one)
            rows += 1
            if len(row) < 4:
                continue
            market = mkey(row[1])
            if market not in WHITELIST:
                continue
            if not row[2].strip():
                continue                       # empty vendor: no identity to key
            try:
                y, mo, d = row[0].split("-")
                w = (dt.date(int(y), int(mo), int(d)).toordinal() - WEEK0) // 7
            except ValueError:
                continue
            kept += 1
            for name, fn in RULES.items():
                kk = fn(row[2])
                if kk:
                    wk[name][(market, w)][kk] += 1
    print("part %02d rows %d kept %d %.1fs"
          % (i, rows, kept, time.time() - t0), flush=True)
    return {"rows": rows, "kept": kept,
            "wk": {name: {k: dict(v) for k, v in d.items()}
                   for name, d in wk.items()}}


def share_of(wk):
    """Listing-weighted same-week multi-homing share for one key rule."""
    hom = collections.defaultdict(set)
    for (m, w), d in wk.items():
        for v in d:
            hom[(w, v)].add(m)
    num = den = 0
    cells = 0
    for (m, w), d in wk.items():
        tot = sum(d.values())
        if tot < MIN_TOT:
            continue
        cells += 1
        den += tot
        for v, n in d.items():
            if len(hom[(w, v)]) >= 2:
                num += n
    return num, den, cells


def main():
    workers = PARTS
    argv = sys.argv[1:]
    for j, a in enumerate(argv):
        if a == "--workers":
            workers = int(argv[j + 1])

    t0 = time.time()
    import multiprocessing as mp
    with mp.Pool(workers) as pool:
        parts = pool.map(scan_part, range(PARTS), chunksize=1)
    rows = sum(p["rows"] for p in parts)
    kept = sum(p["kept"] for p in parts)

    grid = collections.OrderedDict()
    baseline = None
    for name in RULES:
        wk = collections.defaultdict(collections.Counter)
        for p in parts:
            for cell, d in p["wk"][name].items():
                wk[cell].update(d)
        num, den, cells = share_of(wk)
        keys = {v for d in wk.values() for v in d}
        grid[name] = {"share": num / den, "numerator": num, "denominator": den,
                      "cells": cells, "distinct_vendor_keys": len(keys)}
        if name == "strip_lower":
            baseline = num / den
        del wk
        print("%-18s share %.10f  keys %7d  %.1fs"
              % (name, grid[name]["share"], len(keys), time.time() - t0),
              flush=True)

    # the kept-row count is not this file's to define either: g44 already
    # reconciled the whitelist rows down to 23,047,251, and an independent scan
    # that lands anywhere else is reading a different file.
    g44 = json.load(io.open(P44, encoding="utf-8"))
    assert kept == g44["reconciliation_with_g9b"]["wk_rows_total"], (
        "kept rows %d vs g44 %d" % (kept,
                                    g44["reconciliation_with_g9b"]
                                    ["wk_rows_total"]))

    assert baseline is not None
    assert abs(baseline - HEADLINE) < 1e-15, (
        "the baseline rule does not reproduce the headline on these shards "
        "(%r vs %r) -- the shards are not the input the headline came from"
        % (baseline, HEADLINE))

    # merge pressure: how many raw strings does each rule fold together?
    n_raw = grid["raw"]["distinct_vendor_keys"]
    for name in RULES:
        g = grid[name]
        g["keys_vs_raw"] = g["distinct_vendor_keys"] / n_raw
        g["share_minus_baseline_pp"] = 100.0 * (g["share"] - baseline)

    shares = [g["share"] for g in grid.values()]
    res = {
        "stage": "G52",

        "inputs": {"part_00..15": {"file": "g1work/part_*", "parts": PARTS},
                   "g44_truncation_vs_headline_share.json": {
                       "file": "g44_truncation_vs_headline_share.json",
                       "sha256_16": hashlib.sha256(
                           io.open(P44, "rb").read()).hexdigest()[:16]}},
        "rows_scanned": rows, "rows_kept": kept,
        "rows_kept_matches_g44": True,
        "min_tot": MIN_TOT,
        "baseline_rule": "strip().lower()",
        "baseline_reproduces_headline": True,
        "grid": grid,
        "band": {"min": min(shares), "max": max(shares),
                 "width_pp": 100.0 * (max(shares) - min(shares)),
                 "min_rule": min(grid, key=lambda k: grid[k]["share"]),
                 "max_rule": max(grid, key=lambda k: grid[k]["share"]),
                 "reading": "the identity rule moves the headline across this "
                            "band; the low end splits sellers, the high end "
                            "merges them, so neither end is a correction"},
        "not_claimed": [
            "no rule here is 'the true identity'; the band is a range of "
            "definitions, not a confidence interval",
            "the alnum rules delete digits-free punctuation only -- a rule "
            "that also stripped trailing digits would merge different "
            "sellers and is deliberately not tried"],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("rows %d kept %d" % (rows, kept))
    print("band [%.6f (%s), %.6f (%s)] width %.2f pp"
          % (res["band"]["min"], res["band"]["min_rule"], res["band"]["max"],
             res["band"]["max_rule"], res["band"]["width_pp"]))


if __name__ == "__main__":
    main()
