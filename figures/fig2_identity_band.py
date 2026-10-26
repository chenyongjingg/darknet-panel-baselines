# -*- coding: utf-8 -*-
"""Figure 2 -- the identity-rule band around the name-matched multi-market share.

Product read (sha256[:16], bytes):
  products/g52_vendor_key_grid.json       5f97f78a7b064512   2777

Every rule in `grid` is drawn at the share it produces, so the figure shows the
whole grid rather than only its two ends. The band is the min-to-max span of
those rules: `raw` (no strip, no lower: one seller appears as several) and
`nfkc_alnum` (unicode-normalised, punctuation deleted: different sellers
appear as one). The point at 0.5397 is the baseline rule `strip_lower`, which is
one definition on the band, not its centre and not a confidence interval.

The two sub-widths are taken from the product's own `share_minus_baseline_pp`
fields rather than recomputed, so the figure cannot disagree with the product
about which side of the point carries which distance.

Output: fig2_identity_band.png and .pdf at 17.5 cm width, 300 dpi.
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

BLUE = "#0072B2"
GREY = "#8C8C8C"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8,
    "axes.linewidth": 0.6,
})

with io.open(os.path.join(ROOT, "products", "g52_vendor_key_grid.json"),
             encoding="utf-8") as fh:
    g52 = json.load(fh)

grid = g52["grid"]
band = g52["band"]
lo, hi = band["min"], band["max"]
point = grid["strip_lower"]["share"]
left_pp = abs(grid["raw"]["share_minus_baseline_pp"])
right_pp = abs(grid["nfkc_alnum"]["share_minus_baseline_pp"])

# the band has to be the span of the rules actually drawn, otherwise the arrow
# claims a width the ticks do not show
shares = sorted(v["share"] for v in grid.values())
assert abs(shares[0] - lo) < 1e-12 and abs(shares[-1] - hi) < 1e-12, shares
assert abs(left_pp + right_pp - band["width_pp"]) < 1e-9

fig = plt.figure(figsize=(17.5 / 2.54, 6.4 / 2.54))
ax = fig.add_axes([0.075, 0.10, 0.900, 0.86])
ax.set_xlim(0.452, 0.568)
ax.set_ylim(-2.05, 1.45)
ax.set_axis_off()

# a scale bar, because every other number in the panel is a distance on it
ax.hlines(-1.04, 0.460, 0.560, color="#444444", lw=0.5)
for t in (0.46, 0.48, 0.50, 0.52, 0.54, 0.56):
    ax.vlines(t, -1.08, -1.04, color="#444444", lw=0.5)
    ax.text(t, -1.12, "%.2f" % t, ha="center", va="top", fontsize=6.8,
            color="#333333")
ax.text(0.564, -1.04, "share", ha="left", va="center", fontsize=6.8,
        color="#333333")

# the band
ax.axvspan(lo, hi, ymin=0.0, ymax=1.0, color=GREY, alpha=0.16, lw=0)

y_rule = 0.0
ax.hlines(y_rule, 0.454, 0.566, color="#444444", lw=0.8)
for name, cell in sorted(grid.items(), key=lambda kv: kv[1]["share"]):
    ax.plot([cell["share"]], [y_rule], "o", ms=4.6, mfc=BLUE, mec="white",
            mew=0.7, zorder=4)

# the whole band, above the rule line
ax.annotate("", xy=(lo, 0.62), xytext=(hi, 0.62),
            arrowprops=dict(arrowstyle="<|-|>", color="#333333", lw=0.8,
                            shrinkA=0, shrinkB=0))
ax.text((lo + hi) / 2, 0.72, "%.2f pp: the span of seven identity rules"
        % band["width_pp"], ha="center", va="bottom", fontsize=8)

# the two sides, below it
ax.annotate("", xy=(lo, -0.42), xytext=(point, -0.42),
            arrowprops=dict(arrowstyle="<|-|>", color=GREY, lw=0.8,
                            shrinkA=0, shrinkB=0))
ax.text((lo + point) / 2, -0.55, "%.2f pp\nsplitting side" % left_pp,
        ha="center", va="top", fontsize=7.4, color="#4D4D4D")
ax.annotate("", xy=(point, -0.42), xytext=(hi, -0.42),
            arrowprops=dict(arrowstyle="<|-|>", color=GREY, lw=0.8,
                            shrinkA=0, shrinkB=0))
ax.text((point + hi) / 2, -0.55, "%.2f pp\nmerging side" % right_pp,
        ha="center", va="top", fontsize=7.4, color="#4D4D4D")

# the point, with its rule named
ax.plot([point], [y_rule], "o", ms=7.0, mfc=BLUE, mec="white", mew=1.0, zorder=5)
ax.annotate("0.5397\nthe printed value: strip + lower",
            xy=(point, y_rule), xytext=(point, 0.20),
            ha="center", va="bottom", fontsize=7.6, color=BLUE)

# the two ends, named
ax.text(lo, -1.42, "%.4f\nraw key: every spelling\nis a different vendor"
        % lo, ha="center", va="top", fontsize=7.2, color="#333333")
ax.text(hi, -1.42, "%.4f\nalphanumeric key: spelling\nvariants are one vendor"
        % hi, ha="center", va="top", fontsize=7.2, color="#333333")

meta = {"CreationDate": None, "ModDate": None}
for ext in ("png", "pdf"):
    out = os.path.join(HERE, "fig2_identity_band." + ext)
    fig.savefig(out, dpi=300, metadata=meta if ext == "pdf" else None)
    print("wrote", out, os.path.getsize(out), "B")
