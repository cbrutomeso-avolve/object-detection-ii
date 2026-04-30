# Phase 1: Object-Detection PoC Notebook

## Goal

Deliver a Jupyter notebook that, given a plan PNG and one or more reference crops of a feature, finds every instance of that feature on the page. Phase 1 covers the sprinkler class only, but the codebase stays class-agnostic — adding a new class later (fire alarm, smoke detector, etc.) is a data-only change.

## Scope

In:
- `notebook/poc_detector.ipynb` — orchestration, exploration, evaluation.
- `notebook/detector.py` — pure detector functions, importable by Phase 2 API.
- `notebook/trials.md` — iteration log of every parameter / approach tried, with metrics, so future work doesn't redo the search.
- `requirements.txt` — pinned dependencies.
- COCO results predictions written to `outputs/predictions_<run_id>.json`.
- Metrics written to `metrics/metrics_<run_id>.json` + `metrics/metrics_<run_id>.md` per the `object-detection-eval` skill.
- Debug overlays and failure visualizations under `outputs/`.

Out:
- No model training. No GPU. No paid APIs. No multi-page PDF ingestion. No production API or UI (Phase 2 / 3).

## Constraints

From `CLAUDE.md`:
- Python 3.11, FastAPI/Pydantic v2 stack later, OpenCV is the chosen detector library.
- Open-source only, offline, no API keys.
- CPU, **MAX latency ≤10s/page**.
- Multi-class from day one; no string literal `"sprinkler"` in detection or eval code.
- Predictions follow the COCO results schema documented in `object-detection-eval`.
- Bbox is `[x, y, w, h]` in pixels.
- Branch `feat/poc-notebook`; the plan ships on the branch before code.

## Approach (final)

**OpenCV grayscale `cv2.matchTemplate` (TM_CCOEFF_NORMED), multi-scale templates, multi-reference union, color and saturation filtering, ROI mask, greedy NMS.** Evaluation IoU = 0.25 (justified in `notebook/trials.md`).

The original plan was to use Sobel edge maps with rotation sweeps and symmetry verification. That was abandoned during iteration: edge maps fired on every line in the plan (text, dimensions, walls), grayscale matching with the right scale grid was both faster and more discriminative.

### Pipeline

1. **Per-page preprocessing** — convert to grayscale once.
2. **Per-reference preprocessing** — trim near-white border to a tight crop; precompute mean BGR (for color filter) and mean HSV saturation (for saturation filter).
3. **Multi-scale matching** — for each reference, scale the trimmed crop to each `target_sizes_px`, run `cv2.matchTemplate(page_gray, tpl, TM_CCOEFF_NORMED)`, threshold at `tau`, extract local-max peaks via dilate-equality trick.
4. **Color filter** — reject candidates whose patch mean BGR is more than `color_max_distance` from the matching reference's mean BGR.
5. **Saturation filter** — reject candidates whose patch mean HSV saturation differs from the reference's mean saturation by more than `sat_max_distance`.
6. **ROI mask** — keep only candidates whose centre falls inside the largest connected ink blob (drawing area, excluding legend/title block/vicinity map).
7. **Multi-reference union + per-class greedy NMS** at `iou_nms`.

### Why these choices

- **Scale step ~10%**: empirically, `matchTemplate`'s score peak is sharp (a 33-px GT scores 0.92 at template size 33 but 0.54 at size 30). DENSE2 (`[9, 10, 11, 12, 13, 14, 15, 17, 19, 21, 24, 27, 31, 35, 40, 46, 53, 61]`) covers the GT size distribution (9–57 px) without exploding cost.
- **Grayscale beats edge maps** for this dataset because text glyphs have high edge density and match clean templates on the edge channel; grayscale matching with the right scale gives a sharper distinction between sprinklers and clutter.
- **Color + saturation filters** are the precision drivers — they reject the circular text glyphs (O, D, Q) and other black-on-white false positives that survive the score threshold.
- **ROI mask** is small precision win (~1–2 % F1) for plans where legend symbols look identical to real placements.

### Reference selection

For each page X, references = `dataset/images/sprinklers/<image_basename>/*.png` for that page. Loader signature: `load_references(image_basename, category_name) → list[np.ndarray]`. Class-agnostic; the path template `dataset/images/{category_name}s/{image_basename}/` lives in `params`, not as a string literal in code.

### Multi-class readiness checklist

- Categories enumerated via `pycocotools.COCO.loadCats(getCatIds())`. **No string literal `"sprinkler"` anywhere in detection or eval code.**
- Outer loop: `for cat in categories: for image in images:`.
- Reference path template lives in params dict, keyed by `category_name`.
- NMS, threshold, score normalization grouped by `category_id`.
- Per-category param overrides supported (`params["per_category"][name] = {...}`), empty by default.
- Metrics enumerate every category from the COCO file (zero-instance classes report as zeros).
- Adding a new class = drop crops at `dataset/images/<newclass>s/<basename>/` + append to `categories` and `annotations` in COCO. Zero code change.

### Final params (locked)

```python
PARAMS = {
    "target_sizes_px": [9, 10, 11, 12, 13, 14, 15, 17, 19, 21, 24, 27, 31, 35, 40, 46, 53, 61],
    "rotations_deg": (0.0,),
    "tau": 0.78,
    "iou_nms": 0.2,
    "color_max_distance": 35.0,
    "sat_max_distance": 15.0,
    "outlier_count_factor": 4.0,
    "outlier_count_min_threshold": 20,
    "use_roi_mask": False,  # API caller opts in for +0.014 F1
    "iou_match": 0.25,
    "ref_path_template": "dataset/images/{category_name}s/{image_basename}",
    "per_category": {},
}
```

### Per-(ref, scale) outlier rejection

After all per-ref candidates are generated, count how many came from each `(ref_idx, template_size)` pair on the page. Drop any combo whose count exceeds `max(outlier_count_min_threshold, outlier_count_factor × median_count)`.

This targets the dominant FP source: a small-scale template against a small ref (e.g. ref 33 px scaled to 10 px) produces dozens of text-glyph matches per page. Page 5 went from 47 FPs at template size 10 to 0 at that combo (real sprinklers are at template sizes 27 / 35) and overall page 5 FPs dropped 59 → 12 with no TP loss. The dynamic threshold protects pages with many real sprinklers concentrated at one template size: page 9 has 142 GT, multiple template sizes produce ~140 candidates each, the median is high, no scale gets dropped.

### ROI mask (optional)

Wired but disabled in the locked PoC config. With ROI on, F1 improves slightly (0.840 → 0.845) at the cost of an extra connected-components pass per page. Left as an API-side toggle: the production caller decides whether to enable it (e.g. via a request parameter).

### Notebook structure (`notebook/poc_detector.ipynb`)

1. Header markdown — goal, dataset facts, latency target.
2. Imports + config — paths from `REPO_ROOT`, `PARAMS`, `RUN_ID`.
3. Load COCO + categories via `pycocotools`. Assert `len(cats) ≥ 1`.
4. Reference loader — reads `dataset/images/sprinklers/<image_basename>/`.
5. Single-page debug cell — image_id=0. Visualize GT (red) vs detections (green). Save to `outputs/debug/<run_id>/page_0.png`.
6. Full-dataset run cell — loop categories × images, time each page, write `outputs/predictions_<run_id>.json`.
7. Metrics cell — IoU=0.25 matching, per-class TP/FP/FN, micro+macro P/R/F1, mean IoU TP, latency, miss list. Write `metrics/metrics_<run_id>.json` and `.md`. Hard-fail if `micro_precision < 0.85` OR `micro_recall < 0.85` OR `max_latency > 10.0`.
8. Failure visualization cell — top 20 FNs and worst FPs to `outputs/failures_<run_id>/`.
9. Multi-class smoke test — injects a fake second category, verifies the outer loop iterates without code change.

## Evaluation / test plan

End-to-end checks:
1. `outputs/predictions_<run_id>.json` exists with > 0 entries.
2. `metrics/metrics_<run_id>.json` and `.md` exist; markdown table matches the eval skill schema.
3. Per-page latency table printed; `max ≤ 10.0s`.
4. `outputs/debug/<run_id>/page_0.png` overlay exists.
5. `outputs/failures_<run_id>/` populated when FN > 0.
6. Reproducibility: rerun produces identical predictions (no RNG).
7. Multi-class smoke: hidden cell injects a fake second category and asserts the outer loop iterates twice without code change.
8. Code-reviewer subagent pass before merge.

## Result

Final headline (see `metrics/metrics_<run_id>.md` for the actual numbers and `notebook/trials.md` for the full iteration history):

- **F1 = 0.840** (P = 0.927, R = 0.768) at IoU=0.25, no ROI
- F1 = 0.845 (P = 0.941, R = 0.766) with ROI on (optional)
- Max latency 8 s/page (under the 10 s budget)
- Precision target (≥0.85) hit. Recall target (≥0.85) **not** hit; ceiling identified at pages 2 and 4 where per-page reference crops do not cover every visual format actually present on the page (page 4 alone is 31 of 107 missed; page 2 is 36 of 107).

## Risks / known limits

- **Per-page reference quality determines ceiling.** Pages whose reference crops do not cover all visual formats present in that plan suffer in recall. Page 4 is the worst (R=0.16 — refs are 47 px, GTs are 12 px, multiple visual formats not in refs).
- **`matchTemplate` is sharply scale-sensitive.** Score drops fast outside ±10 % of the right scale. The locked dense list (`DENSE2`) covers the dataset's GT distribution. Scaling to a new dataset means re-tuning this list.
- **No rotation invariance.** Rotation sweeps were tried and worsened F1 (added FPs faster than recall). If a future dataset has rotated symbols, this is the first knob to revisit.

## Next iterations to try (when picking this back up)

1. **Curated reference bank for pages 2 and 4** specifically — the visual formats currently missed.
2. **Sub-template extraction** — use the inner 50% of each reference as an additional template, for cases where the outer ring is occluded.
3. **Per-template score normalisation** — calibrate `tau` per (ref, size) pair against the score distribution on the page itself.
4. **Cross-page reference pool** with per-ref color/sat statistics still applied. Wired but expensive (~30 min benchmark).
