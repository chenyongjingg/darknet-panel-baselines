# -*- coding: utf-8 -*-
"""How many name-instances the silkkitie/valhalla label collapse double-counts.

Section 3.3 of the manuscript says: because the two labels are one platform, a
seller present under both is counted as multi-homed when it is not. That
sentence needs a count, and the count needs to be taken under the *same* rule
the multi-homing share uses.

Two different questions hide behind the sentence, and they have different
answers:

  Q1  how many vendor strings appear under both labels at all, ignoring time;
  Q2  how many appear under both labels *in the same week*.

Q2 is the one that matters for the 0.5397 share, because that share requires
same-week presence across markets. A seller seen under the first label in one
week and under the second in a different week is not counted as multi-homed by
that construction, so Q1 overstates the bias.

Three name rules are run side by side, since the share's own band is a name
rule: case-folded and stripped; additionally internal whitespace collapsed;
and case-sensitive.

Reads : <listings.tsv.gz>, <panel_diag.json>, <gold.csv>
Writes: pai_both_labels_vendors.json next to this script.
"""
import collections
import csv
import datetime as dt
import gzip
import io
import json
import os
import re
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "pai_both_labels_vendors.json")
WEEK0 = dt.date(2013, 10, 7).toordinal()
MECH_LO, MECH_HI = dt.date(2014, 6, 9), dt.date(2016, 4, 17)
LABELS = ("silkkitie", "valhalla")
ALIASES = {"blackbankmarket": "blackbank", "piratemarket": "thepiratemarket",
           "middleearthmarketplace": "middleearth",
           "nucleusmarketplace": "nucleus", "alpacamarketplace": "alpaca",
           "realdeal": "realdealmarket", "hansa": "hansamarket",
           "tochka": "tochkafreemarket"}


def norm_key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def allow_set(diag_path, gold_path):
    a = {norm_key(k) for k in json.load(io.open(diag_path, encoding="utf-8"))}
    with io.open(gold_path, encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        c = "market" if "market" in rd.fieldnames else rd.fieldnames[0]
        a |= {norm_key(ALIASES.get(norm_key(r[c]), norm_key(r[c]))) for r in rd}
    return a


def v_key(s, rule):
    s = (s or "").strip()
    if rule == "exact":
        return s
    s = s.lower()
    if rule == "ws":
        s = re.sub(r"\s+", " ", s)
    return s


def main(listings, diag, gold):
    allow = allow_set(diag, gold)
    rules = ("fold", "ws", "exact")
    # rule -> label -> vendor -> set of weeks
    seen = {r: {lab: collections.defaultdict(set) for lab in LABELS}
            for r in rules}
    rows = {lab: 0 for lab in LABELS}
    dropped = collections.Counter()
    # positive control, taken on the first CTRL_N rows of the same pass: if the
    # three rules cannot separate vendor strings here, "same count under every
    # rule" in the two labels would be a fact about the instrument, not the data
    CTRL_N = 3000000
    ctrl = {"exact": set(), "fold": set(), "ws": set()}
    ctrl_rows = 0

    with gzip.open(listings, "rt", encoding="utf-8", newline="") as f:
        rd = csv.reader(f, delimiter="\t")
        nh = len(next(rd))
        for r in rd:
            if ctrl_rows < CTRL_N and len(r) == nh:
                ctrl_rows += 1
                for rule in rules:
                    ctrl[rule].add(v_key(r[2], rule))
            if len(r) != nh:
                dropped["field_count"] += 1
                continue
            try:
                d = dt.date(int(r[0][0:4]), int(r[0][5:7]), int(r[0][8:10]))
            except Exception:
                dropped["bad_date"] += 1
                continue
            if not (MECH_LO <= d <= MECH_HI):
                dropped["out_of_window"] += 1
                continue
            k = norm_key(r[1])
            if k not in allow:
                dropped["market_not_whitelisted"] += 1
                continue
            lab = k if k in LABELS else None
            if lab is None:
                continue
            w = (d.toordinal() - d.weekday() - WEEK0) // 7
            rows[lab] += 1
            for rule in rules:
                v = v_key(r[2], rule)
                if v and len(v) <= 64:
                    seen[rule][lab][v].add(w)

    out = {"source": os.path.basename(listings), "window": [str(MECH_LO), str(MECH_HI)],
           "labels": list(LABELS), "rows_kept": rows, "dropped": dict(dropped),
           "rules": {}}
    for rule in rules:
        a = seen[rule]["silkkitie"]
        b = seen[rule]["valhalla"]
        both = set(a) & set(b)
        same_week = [v for v in both if a[v] & b[v]]
        out["rules"][rule] = {
            "vendors_silkkitie": len(a),
            "vendors_valhalla": len(b),
            "both_labels_any_week": len(both),
            "both_labels_same_week": len(same_week),
        }
        # the shipped product reports counts only: a vendor handle is third-party
        # content and the check needs the count, not the strings. Set
        # PAI_EXAMPLES=1 locally to print eight of them while debugging.
        if os.environ.get("PAI_EXAMPLES") == "1":
            out["rules"][rule]["same_week_examples"] = sorted(same_week)[:8]
    out["name_rule_control"] = {
        "rows": ctrl_rows,
        "distinct_exact": len(ctrl["exact"]),
        "distinct_fold": len(ctrl["fold"]),
        "distinct_ws": len(ctrl["ws"]),
        "control_separates": len(ctrl["exact"]) > len(ctrl["fold"]),
    }
    out["gates"] = {
        "valhalla_vendors_at_least_silkkitie": (
            out["rules"]["ws"]["vendors_valhalla"] >=
            out["rules"]["ws"]["vendors_silkkitie"]),
        # collapsing whitespace may merge strings but must never split a market
        "ws_never_increases_distinct_vendors": all(
            out["rules"]["ws"]["vendors_" + lab] <=
            out["rules"]["fold"]["vendors_" + lab] for lab in LABELS),
        # the negative result (identical counts under every rule) is only
        # admissible if the rules can differ somewhere in this corpus
        "name_rule_control_separates": out["name_rule_control"]["control_separates"],
    }
    out["gate_ok"] = all(out["gates"].values())

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: pai_both_labels_vendors.py "
                         "<listings.tsv.gz> <panel_diag.json> <gold.csv>")
    main(*sys.argv[1:])
