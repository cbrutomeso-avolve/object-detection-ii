---
name: object-detection-eval
description: Use when running or evaluating an object-detection PoC
  in computer vision against a COCO-format ground truth. Triggers when
  the user asks to "evaluate the detector", "compute precision/recall",
  "score predictions against ground truth", or sets up a detection
  experiment. Standardizes the prediction schema and the metric
  computation (precision, recall, F1, mean IoU) at IoU>=0.5, reported
  both micro-averaged and macro-averaged across feature classes.
allowed-tools: Read, Write, Edit, Bash
---

## Scope

Phase 1 of this project evaluates a single class (sprinkler), but this
skill is class-agnostic and works for any number of categories declared
in the COCO file. Never hardcode a category name in metric code.

## Ground truth: COCO format (input)

The GT lives at `dataset/annotations/annotations.json` and follows
the COCO detection schema:

```json
{
  "images": [
    { "id": 1, "file_name": "plan_001.png", "width": 4096, "height": 2048 }
  ],
  "categories": [
    { "id": 1, "name": "sprinkler" }
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

When more classes are added later, `categories` and `annotations` grow.
Nothing else changes — not the schema, not the metric code, not this
skill.

Notes that bite if forgotten:
- `bbox` is `[x, y, w, h]`, NOT `[x1, y1, x2, y2]`.
- `category_id` references `categories[].id`, not the index.
- `image_id` references `images[].id`, not the file_name.
- A prediction's category must match the GT category by `category_id`.
  Resolve names to IDs once at load time; never compare by string in
  the matching loop.

## Predictions: COCO results format (output)

The detector dumps `outputs/predictions_<run_id>.json` in COCO results
format (the format `pycocotools` expects):

```json
[
  {
    "image_id": 1,
    "category_id": 1,
    "bbox": [x, y, w, h],
    "score": 0.87
  }
]
```

Flat list, not the nested COCO dict. One entry per detection.

Predictions (`outputs/predictions_<run_id>.json`) and metrics
(`metrics/metrics_<run_id>.json` + `metrics/metrics_<run_id>.md`) share the
same `run_id` so a single evaluation always traces back to the exact
detector output it scored.

`run_id` format: `<YYYY-MM-DD>_<HHMM>_<short-tag>` (e.g.
`2026-04-28_1430_sprinkler-baseline`). Sorts chronologically with `ls`,
short-tag describes the experiment.

## Matching rules (IoU >= 0.5)

For each (image_id, category_id) group:

1. Sort predictions in that group by `score` descending.
2. Walk predictions in order. For each prediction:
   - Compute IoU against every still-unmatched GT box of the same
     `category_id` in the same `image_id`.
   - If the best IoU >= 0.5, mark that GT box matched, count the
     prediction as TP, store the IoU value.
   - Otherwise, count the prediction as FP.
3. Any GT box still unmatched at the end is a FN.

Each GT box can be matched at most once. Higher-confidence predictions
get first claim — lower-score predictions on the same GT become FPs.

IoU formula: intersection_area / union_area. Convert COCO `[x, y, w, h]`
to corners with `x2 = x + w`, `y2 = y + h`.

## Metrics (always report all of them)

For each class c (iterate over every category in the COCO file, even
if some have zero predictions or zero GT — report them as zeros):

- precision_c = TP_c / (TP_c + FP_c)        (0 if denom is 0)
- recall_c    = TP_c / (TP_c + FN_c)        (0 if denom is 0)
- f1_c        = 2 * P * R / (P + R)         (0 if P + R is 0)

**Macro-averaged**: simple mean of the per-class metrics over ALL
declared categories. Treats every class equally regardless of instance
count. Surfaces a class the detector is silently failing on.

**Micro-averaged**: pool TP, FP, FN across all classes first, then
compute precision and recall once on the totals. Dominated by classes
with more instances. Use this as the headline number.

When phase 1 has one class, macro and micro will be identical — that
is correct, not a bug. They diverge as soon as a second class is added.

Also report:
- Mean IoU of true positives (overall, not per class)
- Per-class TP / FP / FN counts
- Miss list: each FN with `image_id`, `gt_id`, `category_id`, and the
  GT `bbox`. The list is mechanical — no cause attribution. See
  "Miss analysis (separate, interpretive)" below.

## Output format (stdout + disk)

### 1. Print to stdout (this exact structure)

```
| Class       | TP | FP | FN | Precision | Recall | F1  | Mean IoU |
|-------------|----|----|----|-----------|--------|-----|----------|
| sprinkler   | .. | .. | .. |    ..     |   ..   | ..  |    ..    |
| **macro**   | —  | —  | —  |    ..     |   ..   | ..  |    —     |
| **micro**   | .. | .. | .. |    ..     |   ..   | ..  |    ..    |
```

Followed by:
- Overall mean IoU (true positives only).
- Miss list grouped by hypothesized cause.

The class rows are generated dynamically from the COCO `categories`
list. Never hardcode class names in the table.

### 2. Persist to disk (always, even on bad runs)

Create `metrics/` at the repo root if it does not exist. Write two
files per run, both keyed by the same `run_id` as the predictions:

- `metrics/metrics_<run_id>.json` — structured, machine-readable.
  Schema:

  ```json
  {
    "run_id": "2026-04-28_1430_sprinkler-baseline",
    "iou_threshold": 0.5,
    "ground_truth": "dataset/annotations/annotations.json",
    "predictions": "outputs/predictions_<run_id>.json",
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

- `metrics/metrics_<run_id>.md` — the same markdown table printed to
  stdout, plus the overall mean IoU and the miss list. Human-readable
  artifact for PRs and the code-reviewer pass.

Rules:
- Never overwrite an existing `run_id`. If it exists, fail loudly — the
  user picks a new tag.
- `per_class` enumerates **every** category from the COCO file, even
  zero-instance ones. Same rule as the metric loop.
- Commit `metrics/` to the repo. Files are tiny and the run history is
  the narrative of the PoC.

## Miss analysis (separate, interpretive)

Attributing a cause to each FN (rotation, occlusion, scale, color
shift, novel format) is a **judgement call** made by inspecting the
GT crop against the references. It is not a metric and it does NOT
belong in `metrics_<run_id>.json` or `metrics_<run_id>.md`, both of
which must stay reproducible from the predictions alone — same input,
same output, byte-for-byte.

When the user asks for a miss analysis, write it as a separate
artifact `metrics/analysis_<run_id>.md`, clearly labeled as
interpretive (e.g. a header line: *"Subjective miss analysis. Two
observers may disagree; the metrics file does not change."*).

The interpretive layer can also live inline in chat instead of a file
when the analysis is throwaway. The metrics file is the contract; the
analysis is commentary.

## Decision rule

If micro precision < 0.7 OR micro recall < 0.8, do NOT silently retune
parameters. Still write `metrics/metrics_<run_id>.json` and `.md` —
a bad run is data too, and the failure pattern (which class, which
counts) is exactly what informs the next iteration. Then propose at
most 2 concrete changes (e.g. "tighten NMS to 0.4", "add 15-degree
rotation step") and stop. The user decides.

## Multi-reference handling

When a feature class has multiple reference images (e.g. sprinkler =
water-flow switch + valve supervisory), the detector runs once per
reference and the candidate boxes are unioned BEFORE NMS, then NMS is
applied globally for that class. For metrics, treat them as a single
class — the GT does not distinguish sub-formats; they all share one
`category_id`.

## Tooling

Prefer `pycocotools` for IoU and matching when available — it is the
reference implementation and avoids subtle bugs. If it is not in
requirements.txt yet, add it (`pycocotools`) with a pinned version and
install before evaluating. Hand-rolled IoU is fine for the notebook's
exploratory cells but not for the final metric report.