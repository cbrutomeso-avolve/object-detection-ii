---
name: object-detection-eval
description: Use when running or evaluating an object-detection PoC
  in computer vision against a COCO-format ground truth. Triggers when
  the user asks to "evaluate the detector", "compute precision/recall",
  "score predictions against ground truth", or sets up a detection
  experiment. Standardizes the prediction schema and the metric
  computation (precision, recall, F1, mean IoU, latency), reported both
  micro-averaged and macro-averaged across feature classes.
allowed-tools: Read, Write, Edit, Bash
---

## Scope

Class-agnostic. Works for any number of categories declared in the COCO
file. Never hardcode a category name in metric code; iterate over
`coco.loadCats(coco.getCatIds())` and key per-class results by
`category_id`.

## Ground truth: COCO format

Lives at `dataset/annotations/annotations.json` with the COCO detection
schema:

```json
{
  "images": [
    { "id": 1, "file_name": "plan_001.png", "width": 4096, "height": 2048 }
  ],
  "categories": [
    { "id": 1, "name": "<class_name>" }
  ],
  "annotations": [
    {
      "id": 100,
      "image_id": 1,
      "category_id": 1,
      "bbox": [x, y, w, h],
      "area": 1234,
      "iscrowd": 0
    }
  ]
}
```

Adding classes only grows `categories` and `annotations` — schema, metric
code, and this skill stay unchanged.

Conventions that bite if forgotten:
- `bbox` is `[x, y, w, h]`, not `[x1, y1, x2, y2]`.
- `category_id` references `categories[].id`, not the index.
- `image_id` references `images[].id`, not the file name.
- A prediction matches a GT only when their `category_id` is equal.
  Resolve names to IDs once at load time; never compare by string in the
  matching loop.

## Predictions: COCO results format

The detector writes `outputs/predictions_<run_id>.json` as a flat list
(the format `pycocotools` expects):

```json
[
  { "image_id": 1, "category_id": 1, "bbox": [x, y, w, h], "score": 0.87 }
]
```

One entry per detection. Predictions and the matching metrics file share
the same `run_id`, which is `<YYYY-MM-DD>_<HHMM>_<short-tag>` (e.g.
`2026-04-30_1456_baseline`). This keeps every metric file traceable to
the exact predictions it scored, sorts chronologically with `ls`, and
reads at a glance.

## IoU matching rule

For each `(image_id, category_id)` group:

1. Sort predictions by `score` descending.
2. For each prediction, compute IoU against every still-unmatched GT in
   that group. Pick the GT with the highest IoU.
3. If `best_iou >= iou_threshold`, mark the GT matched, count the
   prediction as TP, store the IoU value. Otherwise count as FP.
4. After all predictions are walked, every GT still unmatched is FN.

Each GT is consumed by at most one prediction; higher-confidence
predictions claim first.

IoU formula: `intersection_area / union_area`. Convert COCO `[x, y, w, h]`
to corners with `x2 = x + w`, `y2 = y + h`.

**Picking `iou_threshold`.** The conventional value is 0.5. Use a lower
value (e.g. 0.25) when the GT bboxes were annotated with surrounding
padding included while the detector outputs tight symbol boxes — at 0.5
correct localisations are scored as FP+FN pairs purely from padding
mismatch. Sanity check: if `iou_threshold = X` and `iou_threshold = X/2`
yield identical metrics, predictions are either matching cleanly or are
at totally different locations and the chosen threshold is unambiguous.
The active threshold is always recorded in
`metrics_<run_id>.json["iou_threshold"]`.

## Metrics (always report all of them)

For each class declared in the COCO file — including zero-instance ones,
which report all zeros:

- `precision_c = TP_c / (TP_c + FP_c)`
- `recall_c    = TP_c / (TP_c + FN_c)`
- `f1_c        = 2 * P * R / (P + R)`

Use 0 when the denominator is 0.

**Macro-averaged**: simple mean of the per-class precision/recall/F1 over
*all* declared categories. Treats every class equally regardless of
instance count and surfaces a class the detector is silently failing on.

**Micro-averaged**: pool TP/FP/FN across all classes first, then compute
precision and recall once on the totals. Dominated by classes with more
instances. Headline number.

With a single class, macro and micro are identical by construction.

Also report:
- Mean IoU of true positives (overall).
- Per-class TP/FP/FN counts.
- Miss list — each FN with `image_id`, `gt_id`, `category_id`, and the GT
  `bbox`. Mechanical only — no cause attribution in the metrics file
  (see "Miss analysis" below).
- Latency per page, measured wall-clock around the full detector call
  (preprocessing + matching + filters + NMS). Report avg / median / P95 /
  max plus per-page values.

## Output format

### Stdout

```
| Class       | TP | FP | FN | Precision | Recall | F1  | Mean IoU |
|-------------|----|----|----|-----------|--------|-----|----------|
| <class_a>   | .. | .. | .. |    ..     |   ..   | ..  |    ..    |
| **macro**   | —  | —  | —  |    ..     |   ..   | ..  |    —     |
| **micro**   | .. | .. | .. |    ..     |   ..   | ..  |    ..    |
```

Class rows are generated dynamically from `coco.loadCats(getCatIds())`.
Followed by overall mean IoU, latency summary, and miss list.

### Disk

Always write both files, even on failed runs (a bad run is data too —
the failure pattern informs the next iteration):

- `metrics/metrics_<run_id>.json`:

  ```json
  {
    "run_id": "2026-04-30_1456_baseline",
    "iou_threshold": 0.25,
    "ground_truth": "dataset/annotations/annotations.json",
    "predictions": "outputs/predictions_<run_id>.json",
    "latency": {
      "target_max_seconds_per_page": 10.0,
      "meets_target": true,
      "avg_seconds_per_page": 0.0,
      "median_seconds_per_page": 0.0,
      "p95_seconds_per_page": 0.0,
      "max_seconds_per_page": 0.0,
      "per_page": [
        { "image_id": 0, "file_name": "plan_001.png", "seconds": 0.0 }
      ]
    },
    "per_class": {
      "<class_name>": {
        "category_id": 1,
        "tp": 0, "fp": 0, "fn": 0,
        "precision": 0.0, "recall": 0.0, "f1": 0.0
      }
    },
    "macro": { "precision": 0.0, "recall": 0.0, "f1": 0.0 },
    "micro": { "tp": 0, "fp": 0, "fn": 0,
               "precision": 0.0, "recall": 0.0, "f1": 0.0 },
    "mean_iou_tp": 0.0,
    "misses": [
      { "image_id": 0, "gt_id": 0, "category_id": 1, "bbox": [0, 0, 0, 0] }
    ]
  }
  ```

- `metrics/metrics_<run_id>.md` — same content as the stdout block plus
  the per-page latency table and the miss list. Human-readable artifact
  for PRs and the code-reviewer pass.

Rules:
- Never overwrite an existing `run_id`. Fail loudly; the user picks a
  new tag.
- `per_class` enumerates every category in the COCO file — including
  zero-instance classes — same rule as the metric loop.
- Commit `metrics/` to the repo. Files are tiny and the run history is
  the narrative of the PoC.

## Miss analysis (separate, interpretive)

Attributing a cause to each FN (rotation, occlusion, scale, color shift,
novel format) is a judgement call made by inspecting GT crops against
references. It is not a metric, must not appear in
`metrics_<run_id>.{json,md}` (which must reproduce byte-for-byte from
the same predictions), and belongs in a separate artifact
`metrics/analysis_<run_id>.md`. Header that file with a line such as
*"Subjective miss analysis. Two observers may disagree; the metrics file
does not change."*

Throw-away analysis can stay inline in chat. The metrics file is the
contract; the analysis is commentary.

## Decision rule

Set explicit precision, recall, and latency targets at the start of the
PoC and record them in the run's params. Default targets:

- `micro precision >= 0.8`
- `micro recall >= 0.8`
- `max latency per page <= 10 s` (CPU-only PoC)

After each run, compare to the targets:

- If a metric misses, do NOT silently retune. Still write
  `metrics/metrics_<run_id>.{json,md}`. Surface the miss and propose
  **at most 2 concrete changes** (e.g. "tighten NMS to 0.4", "add a 15°
  rotation step"). The user decides which to apply.
- If accuracy and latency both miss, propose 2 total changes (not 2 per
  metric). Prioritise changes that move the larger gap without exploding
  the other axis.

## Multi-reference handling

When a class has multiple reference images representing different visual
formats (e.g. solid disk + ring + asterisk for a "sprinkler" class), the
detector runs once per reference and the candidate boxes are unioned
*before* NMS; NMS is then applied globally per class. For metrics, the
references collapse to a single category — the GT does not distinguish
sub-formats; they all share one `category_id`.

## Tooling

Prefer `pycocotools` for IoU and matching when available — it is the
reference implementation and avoids subtle bugs. Pin it in
`requirements.txt` if missing. Hand-rolled IoU is acceptable for
exploratory notebook cells but the final metric report uses
`pycocotools`.
