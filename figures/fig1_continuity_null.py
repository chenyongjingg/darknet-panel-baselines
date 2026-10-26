# -*- coding: utf-8 -*-
"""Figure 1 -- the continuity share beside the null the same panel produces by
re-dating the closures.

Products read (sha256[:16], bytes):
  products/g19_shipped_placebo.json       3f05a10fa31aa764   83517
  products/g30_same_unit_null.json        ed123a376324a7ce   52706
  products/g47_percentile_seed_band.json  9da1754eb8772a15   18189

What is plotted, and what is not:
  * the twelve realised per-event shares come from g19 `per_event[*].real_fixed_S.ratio`;
    their unweighted mean is g30's `real` (0.912011), which the script asserts;
  * the null summary (mean, median, 5th and 95th percentiles) comes from
    g30 `arms.g19_range.by_key.ratio`, i.e. 20,000 re-dating draws of the same statistic;
  * no null draw is re-generated here and no quantile is interpolated: the shaded
    interval is drawn between the two stored percentiles and nothing is claimed
    about the shape of the distribution between them;
  * every number that appears in the figure also appears in the manuscript text.

Output: fig1_continuity_null.png and .pdf at 17.5 cm width, 300 dpi.
"""
import io
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

BLUE = "#0072B2"     # realised value
GREY = "#8C8C8C"     # null

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
})


def load(name):
    with io.open(os.path.join(ROOT, "products", name), encoding="utf-8") as fh:
        return json.load(fh)


g19 = load("g19_shipped_placebo.json")
g30 = load("g30_same_unit_null.json")
g47 = load("g47_percentile_seed_band.json")

key = g30["arms"]["g19_range"]["by_key"]["ratio"]
real = key["real"]
null_mean = key["replicate_mean"]
null_p05 = key["replicate_p05"]
null_p50 = key["replicate_p50"]
null_p95 = key["replicate_p95"]
pct = key["percentile_same_unit"]

seed = g47["arms"]["g19_range"]["ratio"]
seed_min, seed_max = seed["band_min"], seed["band_max"]

rows = [(e["market"], e["real_fixed_S"]["ratio"]) for e in g19["per_event"]]
rows.sort(key=lambda r: -r[1])
mean_check = sum(v for _, v in rows) / len(rows)
# the twelve per-event values must average to the stored 12-event mean, otherwise
# this figure is drawn from a different statistic than the one the text prints
assert abs(mean_check - real) < 1e-12, (mean_check, real)
assert len(rows) == key["n_events"]

fig = plt.figure(figsize=(17.5 / 2.54, 9.2 / 2.54))
ax = fig.add_axes([0.155, 0.175, 0.575, 0.715])

y = list(range(len(rows)))[::-1]

ax.axvspan(null_p05, null_p95, color=GREY, alpha=0.18, lw=0, zorder=0)
ax.axvline(null_mean, color=GREY, ls=(0, (4, 2)), lw=1.1, zorder=2)
ax.axvline(null_p50, color=GREY, ls=(0, (1, 2)), lw=1.1, zorder=2)
ax.axvline(real, color=BLUE, lw=1.7, zorder=3)

for yi, (name, v) in zip(y, rows):
    ax.plot([v], [yi], "o", ms=4.4, mfc=BLUE, mec="white", mew=0.6, zorder=4)

ax.set_yticks(y)
ax.set_yticklabels([n for n, _ in rows])
ax.set_ylim(-0.6, len(rows) - 0.25)
ax.set_xlim(0.72, 1.02)
ax.set_xlabel("Continuity share: fraction of post-closure vendors already present "
              "before closure", labelpad=3)
ax.set_xticks([0.75, 0.80, 0.85, 0.90, 0.95, 1.00])
ax.tick_params(axis="both", length=2.5, pad=2)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
ax.grid(axis="x", color="black", alpha=0.07, lw=0.5)
ax.set_axisbelow(True)

mid = (null_p05 + null_p95) / 2
ax.text(mid, len(rows) - 0.05,
        "5th-95th percentile of the null: %.4f to %.4f" % (null_p05, null_p95),
        ha="center", va="bottom", fontsize=7.2, color="#5A5A5A")
ax.annotate("realised, 12-event mean %.4f" % real,
            xy=(real, 8.4), xytext=(real - 0.006, 8.4),
            ha="right", va="center", fontsize=7.4, color=BLUE)
ax.annotate("null mean %.4f" % null_mean,
            xy=(null_mean, 0.45), xytext=(null_mean - 0.008, 0.45),
            ha="right", va="center", fontsize=7.2, color="#5A5A5A")
ax.annotate("null median %.4f" % null_p50,
            xy=(null_p50, 1.45), xytext=(null_p50 - 0.008, 1.45),
            ha="right", va="center", fontsize=7.2, color="#5A5A5A")

handles = [Line2D([0], [0], color=BLUE, lw=1.7, label="realised"),
           Line2D([0], [0], color=GREY, ls=(0, (4, 2)), lw=1.1, label="null mean"),
           Line2D([0], [0], color=GREY, ls=(0, (1, 2)), lw=1.1, label="null median"),
           Line2D([0], [0], marker="s", color="none", mfc=GREY, alpha=0.45,
                  ms=7, label="null 5th-95th percentile")]
ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=7.0,
          handlelength=1.7, labelspacing=0.3, borderaxespad=0.2)

# right-hand column: the percentile scale, stated rather than drawn
axr = fig.add_axes([0.725, 0.175, 0.265, 0.715])
axr.set_axis_off()
axr.text(0.0, 0.99, "Where the realised value\nsits in that null",
         transform=axr.transAxes, ha="left", va="top", fontsize=7.6)
axr.text(0.0, 0.86, "%.1fth percentile" % (pct * 100),
         transform=axr.transAxes, ha="left", va="top",
         fontsize=9.0, color=BLUE, fontweight="bold")
axr.text(0.0, 0.78,
         "seed band %.2f to %.2f\n(50 seeds of %s draws)"
         % (seed_min * 100, seed_max * 100, format(g47["params"]["n_rep"], ",")),
         transform=axr.transAxes, ha="left", va="top",
         fontsize=7.2, color="#5A5A5A")
axr.text(0.0, 0.63,
         "The null is the same statistic\nin the same unit: one draw\nper event, then the twelve-\nevent mean.",
         transform=axr.transAxes, ha="left", va="top",
         fontsize=7.2, color="#5A5A5A")

meta = {"CreationDate": None, "ModDate": None}
for ext in ("png", "pdf"):
    out = os.path.join(HERE, "fig1_continuity_null." + ext)
    fig.savefig(out, dpi=300, metadata=meta if ext == "pdf" else None)
    print("wrote", out, os.path.getsize(out), "B")
