# darknet-panel-baselines

Derived products, and the check scripts that write them, for the manuscript

> **Baselines and detection floors: what a darknet market panel can and cannot say about displacement**

The article is under review. This repository holds the numbers it prints and the code that produced them.

```
products/         13 JSON files, no raw data
checks/           13 scripts that write the products, plus verify.py
MANIFEST.sha256   SHA-256 and byte size of every file above
```

## What is not in this repository

No listing rows, no page bodies, no listing titles, no seller handles, no crawler output, and no market address. The panel behind these numbers is a third-party archive of publicly observable listings and is not redistributed here. Each script reads its inputs from constants at the top of the file, so reproducing a product needs that archive and an edit to those constants.

## How to read a hash

The article identifies each product by the first sixteen hex digits of the SHA-256 of its bytes, followed by its size in bytes. Those are the pairs printed in its Data availability statement.

A hash here is a receipt: it says which bytes a quoted number was read from. It is not a claim that the same bytes can be rebuilt. `g90_cap_treatment_criterion.json` records its own wall-clock `elapsed_s`, so re-running its script reproduces its numbers and not its file.

The check is one command:

```
python checks/verify.py
```

It reads `MANIFEST.sha256`, recomputes the SHA-256 of every listed file, and exits non-zero if anything is missing or changed. `--table` prints the product table below from the files on disk, so the table and the manifest cannot drift apart silently.

## Products

| product | bytes | sha256[:16] | what it binds | article |
|---|---|---|---|---|
| `pai_title_within_pair_v2.json` | 990 | `61dc6c1a08cdedff` | Name matches across the `silkkitie`/`valhalla` pair: 5,922 shared names, 89.89% with identical listing titles | §3.3 content check |
| `pai_pair_calendar.json` | 797 | `b98c4407f1f62ffc` | Observation calendars of the two labels and the days they share | §3.3 premise |
| `pai_pair_simultaneity.json` | 323 | `02d77274d1782a88` | Same-day co-occurrence: 0 of 5,922 | §3.3 |
| `pai_pair_handover_opportunity.json` | 1,099 | `a3b140edf4296d45` | The risk set for a handover: 202 slots in which the first label was last seen on or after the second launched | §3.3, and the correction that replaced a circular opportunity count |
| `pai_pair_boundary_joint.json` | 723 | `24ea453a8ecc5019` | The launch-eve to launch-day boundary, and how much of it is a third market | §3.3 |
| `pai_title_gap_matched.json` | 749 | `5218a4471a67f99a` | Title change rate at a matched gap between observations | §3.3 |
| `pai_both_labels_vendors.json` | 1,081 | `ef6cd359d3a2b564` | Sellers seen under both labels: 346 at any time, 290 in the same week, identical under three name rules | §3.3, the one correction not applied |
| `g19_shipped_placebo.json` | 83,517 | `3f05a10fa31aa764` | The re-dating placebo, event by event: the zero baseline | §3.1 |
| `g30_same_unit_null.json` | 52,706 | `ed123a376324a7ce` | The same null in the unit of the reported statistic, 12-event mean rather than one draw | §3.1, §3.2 |
| `g47_percentile_seed_band.json` | 18,189 | `9da1754eb8772a15` | Seed band of that percentile, and the additive identity that splits it by exposure | §3.1 |
| `g73_event_cluster_boot.json` | 15,197 | `50adf2a03d7d72cf` | Resampling by closure date instead of by event | §3.2 |
| `g74_leave_one_event_out.json` | 24,852 | `5a81b4371d4b9b34` | Leave-one-event-out sweep, under both arms | §4.1 |
| `g90_cap_treatment_criterion.json` | 14,702 | `6f25e8fb6a0eb6f3` | Page-cap deletion criterion, its two guards and its firing check | §4.4 |

## One product is not the yardstick its neighbours suggest

`g19_shipped_placebo.json` contains `null_random_weeks`, the spread of 296 pooled single draws. It is easy to read its percentile as the percentile of the reported statistic, and the article does not use it for that. `g30_same_unit_null.json` stores both quantities side by side and labels the difference: `percentile_same_unit` is 0.70975, `percentile_old_single_draw` is 0.45270. The bands quoted in the article come from the same-unit distribution, whose 5th to 95th percentile span is 11.10 pp; the single-draw span is 47.88 pp, and treating it as the criterion's yardstick understates the instrument's own share by a factor of 4.31. `g90` carries that comparison in its `zero_baseline` block.

## Scripts

Each script runs as `python <script>.py` and reads its inputs from paths written into the file. `pai_both_labels_vendors.py` is the exception: it takes three paths as arguments (listings archive, panel diagnostics, market list). None of those inputs is published.

`pai_both_labels_vendors.py` reports counts only. Vendor handles are third-party content and the check needs the count rather than the strings; setting `PAI_EXAMPLES=1` in the environment prints eight of them during local debugging.

## What has been re-run

`pai_both_labels_vendors.json` was rebuilt from its script after the example handles were removed. The rerun reproduced every numeric field of the version it replaced: 346, 290, 489 and 918 sellers, 2,674 against 2,644 distinct strings in the name-rule control, both row counts, and all three gate flags. The two files differ in the removed field and in nothing else.

The other twelve are the files the article's numbers were read from, not files rebuilt afterwards.

## Citation

Cite the article, and cite a product by filename and hash if you rely on a specific number. A bibliographic entry will be added here once the article appears.
