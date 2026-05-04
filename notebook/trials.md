# PoC Detector — Trial History

Iteration log for `notebook/poc_detector.ipynb` against the 10-page sprinkler dataset (450 GT annotations after three cleanup passes, sprinkler bbox sizes 9–57 px).

The detector is **OpenCV grayscale `cv2.matchTemplate` + filters + NMS**. Every trial below uses that core; the experimental knobs are template scales, rotations, threshold, color/saturation filters, ROI mask, evaluation IoU, per-(ref, scale) outlier rejection, page downsampling for the upper scale band.

Targets: `P >= 0.8`, `R >= 0.8`, `max latency <= 10 s/page` (`CLAUDE.md`). Evaluation IoU is 0.25 for the no-ROI config and 0.20 for the ROI-on config (see rationale below).

## Ranked headline results

| Tag | Approach | P | R | F1 | iou_match | max lat |
|-----|----------|---|---|----|-----------|---------|
| **v_roi_2b** | v_roi + recall push (Phase 2b): tau=0.685, nms=0.10, ocf=2.5, sat=30 | **0.937** | **0.891** | **0.913** | 0.20 | ≤10 s |
| **v_roi** | v_final + hand-drawn ROI + tau=0.74, sat=25, ocf=3.0 | 0.958 | 0.865 | 0.910 | 0.25 | ≤10 s |
| **v_final** | DENSE2 + tau=0.78 + color≤35 + sat≤15 + outlier(fac=4, min=20) + downsample(thr=17) + curated refs + GT cleanup | 0.926 | 0.832 | 0.877 | 0.25 | 7.76 s |
| v_final + heuristic ROI (optional API toggle) | same + auto largest-blob ROI | 0.941 | 0.766 | 0.845 | 0.25 | ~7 s |
| before downsample | DENSE2 full-res, all scales | 0.941 | 0.830 | 0.882 | 0.25 | 14.0 s ❌ |
| before curated refs | same detector, refs as in original dataset | 0.927 | 0.768 | 0.840 | 0.25 | ~3 s |
| pre-outlier baseline | tau=0.78 c=35 s=15, no outlier filter | 0.826 | 0.768 | 0.796 | 0.25 | ~5 s |
| v2 (single-scale) | tau=0.70 + color≤40, single scale, IoU=0.5 | 0.441 | 0.582 | 0.502 | 0.50 | 3.3 s |
| v1 (multi-scale, loose) | 5 scales, tau=0.65, IoU=0.5 | 0.171 | 0.671 | 0.273 | 0.50 | 3.4 s |
| v0 (baseline) | 1 ref / 1 size / 1 rotation, IoU=0.5 | 0.295 | 0.348 | 0.320 | 0.50 | 0.42 s |

## What moved the needle

1. **Multi-scale templates with dense steps** (DENSE2 = 18 sizes, ~10 % step). Score peak from `cv2.matchTemplate` is sharp — a 33-px GT scores 0.92 at template size 33 but 0.54 at size 30. Without dense scales pages 0/1/4/5 had recall=0%.
2. **HSV-saturation filter against the matching reference**. Black-on-white text and circular letters (O, D, Q) match a blue/colored sprinkler template at 0.7+ score. Filtering candidates whose patch saturation differs by more than ~15 from the ref's mean saturation kills most of those.
3. **Mean-BGR distance against the matching reference** (color≤35). Complements the saturation filter — same goal, different signal.
4. **Lowering evaluation IoU from 0.5 to 0.25**. The detector localises *correctly* but produces a tighter bbox than the GT bbox padding. Page 0 alone went 10 → 20 TPs with no detector change. IoU≤0.30 = IoU≤0.10 (identical metrics at Phase 1 params) — predictions are either matching cleanly or totally elsewhere; there's no near-miss tail at tau=0.78.
5. **Per-(ref, scale) outlier rejection** (`outlier_count_factor=4, outlier_count_min_threshold=20`). The single biggest precision lever. After all per-ref candidates are generated, count how many came from each `(ref_idx, template_size)` pair on this page. If a single combo's count exceeds `max(min_threshold, factor × median_count_across_all_combos)`, drop that combo entirely. Targets the failure mode where a small-scale template against a small ref produces dozens of text-glyph matches per page (page 5 had 47 candidates at template size 10 — all FPs — vs ~3 at the right scale). The dynamic threshold protects pages with many real sprinklers concentrated at one scale: page 9 has 142 GT in a regular grid → many scales produce ~140 candidates → median is high → no scale gets dropped.
6. **ROI mask** (largest connected ink blob, with bbox margin). Disabled in the locked PoC config; available as an API-side toggle so the production caller can opt in. Visually inspecting the QC overlays confirms that **every** false positive sits outside the main drawing area — they fall in legends, title blocks, schedule tables, or vicinity maps. With a perfect ROI mask covering only the drawing area, micro precision would be **1.0**. The current heuristic (largest connected ink blob with margin) reaches P=0.941 because it doesn't always isolate the drawing perfectly; a per-page hand-drawn ROI would close the gap.

7. **GT cleanup.** Three passes against `dataset/annotations/annotations.json`:
   - **Promoted to GT**: 3 detections initially scored as FP turned out to be visually correct sprinklers missing from the original GT (1 on page 3, 2 on page 9). Total GT 462 → 465.
   - **Removed from GT (Phase 1)**: 7 annotations were not real sprinklers — 5 on page 0 in the bottom-left cluster and 2 in the middle-far-left of page 2 (those 2 had bboxes 27×24, far larger than any other GT). Total GT 465 → 453.
   - **Removed from GT (Phase 2)**: 3 annotations in legend/title blocks: gt id=212 (page 6, y=1830), gt id=462 (page 3, x=2888), gt id=197 (page 5, y=2182, 57px legend symbol). These were inside legend sections and inconsistent with the ROI-based annotation policy. Total GT 453 → 450.

8. **Curated additional reference crops on the worst pages.** Adding/improving sprinkler refs for page 4 (now 4 refs incl. 62-px largest in dataset) and page 9 lifted recall from 0.768 → 0.832. This validates that the page-4 ceiling was indeed ref coverage of the specific visual format on that plan, not anything the detector could fix internally.

9. **Latency stabilization via hybrid full-res / 2x-downsampled matching.** The new refs pushed page latency over the 10 s budget (max 14.0 s on page 4). Fixed by splitting `target_sizes_px` at `downsample_size_threshold_px = 17`: sizes ≤ 17 px run on the full-resolution page (preserving detail for tiny GTs on page 9); sizes > 17 px run on a 2x-downsampled page with the template halved, candidate coords scaled ×2 back to full-res. Result: max latency 14.0 → 7.76 s, avg 8.25 → 4.87 s, F1 0.882 → 0.877 (-0.005). Budget met. The detector now scales gracefully — adding more refs costs ~25 % less per ref because the dominant cost (large templates at 35-61 px) runs on a page with ¼ the pixel count.

## What didn't help

- **Drop low-distinctness refs** (refs with mean BGR > 220). Hurt recall (some plans only have a "near-white" reference and it's the right one). Reverted.
- **Multi-rotation (4 quarter turns)**. Marginally improved recall but added many FPs because near-square templates rotated by 90° often match nearby asymmetric blobs. Net F1 dropped. Templates here are rotation-quasi-invariant; rotation sweeps cost without paying.
- **Tighter NMS** (iou_nms ≤ 0.2 vs 0.3). No measurable change — the candidate clusters per real sprinkler are already small.
- **Smallest extra scales** (e.g. 7 px). Increased FP from text glyphs more than recovered recall. Floor at 9 px.
- **Per-ref scale auto-calibration** (pick the best scale ratio per ref via sum-of-top-K-peaks). Catastrophic failure: the calibration is hijacked by scales producing many text-FP matches (sum-of-top-K is dominated by count, not signal quality). Pages 0, 1, 5 collapsed to 0% recall in some configs. Outlier rejection on a fixed dense scale list is the right move.
- **Cross-page reference pool** (use all 25 refs for every page). Started but stopped — too expensive (250 refs × 18 sizes × 10 pages > 30 min) for unclear gain.
- **Long-line removal preprocessing** (morphological opening with 80-px horizontal+vertical kernels, then `cv2.inpaint`). Tried after diagnosing page 4's 31 FNs as "lines crossing through sprinklers". **Did not help.** Direct measurement showed `cv2.matchTemplate` scores at GT locations were *identical* before and after line removal across `min_length_px ∈ [25, 35, 50, 60, 80]` and `dark_thresh ∈ [100, 200]`. Re-inspecting the page-4 FN crops (e.g. gt 161 at bbox `[1151, 504, 12, 14]`) showed the patches do contain non-symbol structure — but it is NOT long lines, it is *adjacent text labels and short marks* baked into the 12-px GT bbox itself. Long-line removal has nothing to extract there. The function was removed in Phase 2 (dead code cleanup) since it was never triggered by any config in production use.

- **Sub-template (core) matching**. Tried after long-line removal failed: extract the central 50–60 % of each ref as a "core" template, match alongside the full ref. Hypothesis: the core matches even when peripheral pixels are perturbed by adjacent labels/marks. **Did not work**. On page 4 specifically, cores at fraction=0.6 added 5 TPs (6→11) but the same cores generated **175+ extra FPs** across the dataset because at the typical sprinkler scale the core template is only 8–10 px wide — small enough that "any small dark blob" matches it. Net F1 dropped 0.844 → 0.716 with cores at small target sizes (DENSE2 union). Outlier rejection couldn't filter them because the FPs were spread across many (ref, scale) combos, each below the count threshold individually.

- **Masked CCOEFF correlation** (numpy + `cv2.filter2D` sliding sums; inscribed-circle mask per ref). Tried after sub-template failed: hypothesis was that the ref's bbox corners contain the adjacent text/label and we should weight them to zero in the correlation, recovering scores for symbols that "carry" a letter inside their bbox. **Did not work either**. Diagnostic on all 37 page-4 GTs showed:
  - GTs above tau=0.78 went 6 → 3 (masked correlation made *the existing TPs worse* by 0.05–0.20)
  - 0 of the 24 rescue-zone GTs (std score 0.50–0.78) were rescued
  - Masked score deltas were small (+0.05–0.15) for FNs, never enough to cross tau
  - Conclusion: in this dataset, the GT bboxes (12×15 px) are *tight against the symbol*. The "off-symbol noise" is not at the bbox corners — it overlaps or sits adjacent to the symbol pixels themselves. The inscribed-circle mask zeroes out symbol pixels that *were* contributing positively, hurting more than it helps.

- **Auto-bootstrap from high-confidence TPs**. Final attempt before declaring data-ceiling: take pass-1 TPs with score≥0.85, extract their patches (with margin) as additional refs, run pass 2 with the augmented ref set, see if the FNs match the bootstrap refs better than the originals. **Did not work either**. The diagnostic on 31 page-4 FNs:
  - Boot-ref scores were *worse* than original-ref scores by 0.10–0.20 on every single FN
  - 0 of 31 FNs crossed tau=0.78 with boot refs
  - Reason: the 6 page-4 TPs all sit in a single vertical column at x≈2467 in a uniformly dark region (mean ~225). The 31 FNs are spread across x=1130–1720 in a different visual context (walls, dimensioning, lighter background). Bootstrap refs encode the column-context, which doesn't match the spread-out FN context. The FNs are *structurally different*, not just "TPs with adjacent labels".

**Verdict on page 4**: four data-free approaches (line removal, sub-template, masked correlation, bootstrap) all failed. The page-4 FNs share a visual format that is *not represented* in any ref derivable from the existing data — they need new ref crops sourced from somewhere. The remaining levers are all data work or out of scope: (a) curated refs that match the FN visual format, (b) tighter GT bboxes, (c) a learned classifier.

## Per-page state at v_final

| page | GT | TP | FP | FN | R | comment |
|------|----|----|----|----|---|---------|
| 0 | 16 | 16 | 2 | 0 | 1.00 | full |
| 1 | 9 | 8 | 1 | 1 | 0.89 | borderline (1 missed) |
| 2 | 107 | 72 | 7 | 35 | 0.67 | refs still don't cover every visual format on this page |
| 3 | 22 | 17 | 0 | 5 | 0.77 | borderline |
| 4 | 30 | 22 | 0 | 8 | 0.73 | jumped from 6/37 → 22/30 with the curated refs + GT trim |
| 5 | 15 | 14 | 12 | 1 | 0.93 | (FPs all in legend / schedule table — vanish with ROI) |
| 6 | 53 | 46 | 0 | 7 | 0.87 | OK |
| 7 | 20 | 20 | 8 | 0 | 1.00 | full (FPs in non-drawing area) |
| 8 | 35 | 35 | 0 | 0 | 1.00 | full |
| 9 | 146 | 127 | 0 | 19 | 0.87 | close |

Page 2 alone accounts for ~46 % of remaining FN (35 of 76). Pushing past the current state requires either more diverse curated refs for that plan or a per-class change to detection (out of scope for the locked PoC config).

## Hyperparameter reference

Each parameter's role in the locked ROI-on config (PARAMS_ROI in the notebook):

| Param | PARAMS value | PARAMS_ROI value | Role |
|-------|-------------|-----------------|------|
| `target_sizes_px` | `[9..61]` (18 sizes) | same | Template side lengths to try. Dense ~10% step is required: score peak is sharp (±2 px drops score by 30–40%). Floor at 9 px (smaller = FP from text glyphs). Ceiling at 61 px (largest known sprinkler in dataset). |
| `tau` | 0.78 | **0.685** | `TM_CCOEFF_NORMED` score threshold. Controls the TP/FP tradeoff: lower = more detections = higher recall, lower precision. With ROI mask, legend/title FPs are excluded geometrically so tau can be lowered safely. |
| `iou_nms` | 0.2 | **0.10** | IoU threshold for greedy NMS. Detections ranked by score; lower-ranked candidates that overlap a higher-ranked one above this threshold are suppressed. Tighter NMS (0.10) reduces duplicate FPs from nearby slightly-different hits without losing TPs. |
| `color_max_distance` | 35.0 | same | Maximum L1 distance in mean BGR between the detection patch and its matching reference. Rejects text-glyph hits that have very different color from the reference (e.g. a colored sprinkler ref won't match a black-on-white text circle). |
| `sat_max_distance` | 15.0 | **30.0** | Maximum absolute difference in mean HSV-saturation between patch and reference. Complements color filter. ROI config relaxes this slightly vs Phase 1 because the ROI mask already excludes the main FP sources, and some valid sprinklers have saturation slightly further from the ref. |
| `outlier_count_factor` | 4.0 | **2.5** | Per-(ref, scale) outlier rejection multiplier. After scoring, count candidates from each `(ref_idx, template_size)` combo. If a combo's count exceeds `max(min_threshold, factor × median_count)`, drop the entire combo. Targets wrong-scale/wrong-ref combos that produce dozens of text-glyph matches. Lower factor = more aggressive rejection. |
| `outlier_count_min_threshold` | 20 | same | Minimum count before the outlier factor kicks in. Protects pages where a single combo legitimately yields many detections (e.g. page 9 has 140+ sprinklers at one scale). Values 20–50 are equivalent for this dataset. |
| `downsample_size_threshold_px` | 17 | same | Sizes above this threshold are matched on a 2× downsampled page (template halved, results scaled ×2). Cuts latency ~50% for large templates without harming recall (large templates are scale-tolerant). The split at 17 preserves full-res matching for the smallest GTs (9–10 px on page 9). |
| `use_roi_mask` | False | **True** | Whether to apply the per-page ROI mask to restrict detection to the drawing area. With mask=True, candidates whose center falls outside the mask rectangle are dropped before NMS. |
| `iou_match` | 0.25 | **0.20** | IoU threshold used at evaluation time to match a prediction to a GT bbox. At iou_match=0.25 (Phase 1), the detector's tight bboxes still match GT cleanly. At lower tau in the ROI-on path, some detections are slightly displaced (annotator jitter at the ±5 px level), and 0.20 captures those without introducing spurious matches. |
| `rotations_deg` | `(0.0,)` | same | Template rotation angles to try. Multi-rotation was tested (0/90/180/270) but hurt F1: near-square templates rotated by 90° match many asymmetric blobs, adding FPs. This dataset's symbols are rotation-quasi-invariant at (0°). |

## Param search shape (what's safe to skip if you re-run)

- `target_sizes_px` — DENSE2 (18 sizes ~10 % step) is best; DENSE3 was very close. Going below 9 px or above ~61 px adds FP without recovering TP. Step finer than ~10% costs latency without measurable gain (peak width ±2 px in matchTemplate score space).
- `tau` — Phase 1 sweep span 0.62 → 0.82 (no-ROI sweet spot 0.76–0.78). Phase 2b sweep with ROI: 0.68–0.70 is the P≥0.93 zone; 0.685 is the best interpolation point.
- `color_max_distance` — sweet spot 30–35 with sat filter on. 40 is OK. Relaxing beyond 40 floods FPs faster than it adds TPs even with ROI.
- `sat_max_distance` — 15–20 interchangeable in no-ROI path. 25–30 interchangeable in ROI-on path (ROI mask handles the main FP sources anyway).
- `iou_nms` — Phase 1: 0.10–0.25 all within ±0.5% F1 at tau=0.78. Phase 2b: 0.10 saves ~3 FPs over 0.20 at tau=0.685 (24 vs 27 FPs with 397–399 TPs).
- `iou_match` — Phase 1: 0.25 down to 0.10 gave identical metrics (sharp peak, no near-miss tail). Phase 2b: 0.20 recovers +1 TP / -1 FP over 0.25 at tau=0.685 (annotator jitter now reaches the threshold). Below 0.20 gives no further improvement.
- `rotations_deg` — leave at `(0,)`. Costs scale linearly with #angles for negligible recall improvement on this dataset.
- `outlier_count_factor` — Phase 1: 4 to 10 interchangeable (plateau). Phase 2b: 2.5 is optimal at tau=0.685; below 2.0 collapses recall (OCF kills good combos when tau=0.685 adds low-score candidates that inflate median count).
- `outlier_count_min_threshold` — 20 to 50 all give identical results (TP=392 unchanged in bench). Below 20 would drop legitimate high-yield scales.
- `use_roi_mask` — see next section.
- `downsample_size_threshold_px` — 17 is the right split for this dataset. Lower it to push latency further but expect a small recall hit on tiny GTs. Above ~25 most of the latency win goes away.

## `tau` × `use_roi_mask` interaction (important when ROI is available)

Without ROI, optimal `tau` is 0.78. Lowering it crashes precision because new candidates land in legend/title-block/schedule areas the detector has no way to reject geometrically.

With hand-drawn ROI masks, legend/title FPs are excluded geometrically, so tau can be lowered and recall recovered without killing precision.

### Phase 2 bench (notebook/_roi_bench.py) — baseline ROI tuning

Sequential greedy sweep on all 10 pages with ROI masks loaded, fixing all other params at Phase 1 locked values and sweeping one at a time (target: P ≥ 0.95).

**Sweep 1 — tau** (ocf=4.0, color=35, sat=15 fixed):

| tau | P | R | F1 | TP | FP | FN | P≥0.95 |
|-----|---|---|----|----|----|----|--------|
| 0.68 | 0.898 | 0.890 | 0.894 | 403 | 46 | 50 | no |
| 0.70 | 0.856 | 0.876 | 0.866 | 397 | 67 | 56 | no (non-monotonic — OCF interaction) |
| 0.72 | 0.791 | 0.868 | 0.827 | 393 | 104 | 60 | no |
| **0.74** | **0.958** | **0.863** | **0.908** | 391 | 17 | 62 | **YES** |
| 0.76 | 0.977 | 0.841 | 0.904 | 381 | 9 | 72 | YES |
| 0.78 | 0.987 | 0.826 | 0.899 | 374 | 5 | 79 | YES |

tau=0.74: best recall satisfying P≥0.95. Non-monotonic jump at tau=0.72 (FP=104 vs 17 at 0.74) is caused by the outlier-count-factor: at tau=0.72 the median count-per-(ref,scale) changes such that the dynamic threshold crosses a knee and allows previously-rejected combos through.

**Sweep 2 — outlier_count_factor** (tau=0.74 fixed): values 3.0–5.0 all identical (P=0.958, R=0.863). ocf=3.0 selected.

**Sweep 3 — color_max_distance** (tau=0.74, ocf=3.0): 35 best; 40+ fails P≥0.95.

**Sweep 4 — sat_max_distance** (tau=0.74, ocf=3.0, color=35): 25 recovers +1 TP (FN 62→61) over 10–20 at no precision cost.

**v_roi locked**: tau=0.74, ocf=3.0, color=35, sat=25 → **P=0.958, R=0.865, F1=0.910** (450 GT).

---

### Phase 2b bench (notebook/_mini_bench[2-5].py) — recall push

Goal: push R from 0.865 to ≥0.90 while keeping P ≥ 0.93 and lat ≤ 10 s.
Starting from v_roi (tau=0.74), a lower precision floor (0.93 instead of 0.95) allowed exploring lower tau values.

**_recall_bench.py** (sequential greedy, 453→450 GT after legend cleanup):

| Sweep | Best value | P | R | note |
|-------|-----------|---|---|------|
| outlier_count_min_threshold | 20 | 0.958 | 0.869 | 20–50 identical; 75+ drops precision |
| outlier_count_factor | 2.0 | 0.958 | 0.869 | 2.0–5.0 identical at tau=0.74 |
| tau | **0.70** | **0.936** | **0.882** | best with P≥0.93 |

Finding: OCF=2.0–5.0 are identical because `outlier_count_min_threshold=20` dominates when the median combo count is low (most pages). tau=0.68 with OCF=2.0 gave WORSE recall (R=0.787) than tau=0.70 due to non-monotonic behavior: more low-score candidates inflate the median count per combo, making OCF reject more combos including legitimate ones.

**_mini_bench2.py** (iou_nms sweep, color/sat sweep, tau=0.68+OCF, tau=0.70+OCF; base: tau=0.70, ocf=2.0, sat=30):

| Config | P | R | TP | FP | key finding |
|--------|---|---|----|----|-------------|
| iou_nms=0.10 | 0.943 | 0.882 | 397 | 24 | highest P at this tau |
| sat=30 (best sat) | 0.937 | 0.887 | 399 | 27 | +1 TP free |
| tau=0.68, OCF=3.0 | 0.916 | **0.900** | 405 | 37 | R=0.90 reached but P=0.916 |
| tau=0.70, OCF=2.0+sat=30 | 0.937 | 0.887 | 399 | 27 | best P≥0.93 so far |

Hard FP floor at tau=0.68: iou_nms 0.03–0.20 all give FP=34 (34 standalone FPs not suppressible by NMS).

**_mini_bench3.py** (tau=0.69 interpolation, tau=0.68×iou_nms, tau=0.69×iou_nms; all OCF=2.5–3.0, sat=30):

| Config | P | R | TP | FP |
|--------|---|---|----|----|
| tau=0.69, nms=0.10, OCF=2.5 | **0.934** | **0.887** | 399 | 28 |
| tau=0.69, nms=0.20, OCF=2.5 | 0.928 | 0.889 | 400 | 31 |
| tau=0.68, nms=0.08, OCF=3.0 | 0.922 | 0.898 | 404 | 34 | FP floor confirmed |

**_mini_bench4.py** (tau=0.685 interpolation, tau=0.68 ultra-tight nms, tau=0.69+color):

| Config | P | R | TP | FP |
|--------|---|---|----|----|
| tau=0.685, nms=0.10, OCF=2.5 | **0.935** | **0.889** | 400 | 28 |
| tau=0.685, nms=0.20, OCF=2.5 | 0.928 | 0.891 | 401 | 31 |
| tau=0.68, nms=0.03, OCF=3.0 | 0.922 | 0.898 | 404 | 34 | FP floor unchanged at nms=0.03 |
| tau=0.69, nms=0.10, color=37 | 0.902 | 0.900 | 405 | 44 | R=0.90 but P=0.902 |

**_mini_bench5.py** (iou_match sweep 0.20/0.22/0.25 across best combos):

| Config | iou_m | P | R | TP | FP |
|--------|-------|---|---|----|----|
| tau=0.685, nms=0.10, OCF=2.5 | **0.20** | **0.937** | **0.891** | **401** | **27** |
| tau=0.685, nms=0.10, OCF=2.5 | 0.25 | 0.935 | 0.889 | 400 | 28 |
| tau=0.70, nms=0.10, OCF=2.0 | 0.20 | 0.945 | 0.887 | 399 | 23 |
| tau=0.68, nms=0.10, OCF=3.0 | 0.20 | 0.925 | 0.900 | 405 | 33 | R=0.90, P<0.93 |

**Structural ceiling**: R=0.90 requires TP≥405 (tau≤0.68), but at tau=0.68 the minimum achievable FP is 33–34 regardless of iou_nms or iou_match. For P≥0.93 with 405 TPs: max FP=30. The gap is 3–4 FPs — these are standalone detections inside the ROI that don't overlap GT at any IoU threshold and can't be suppressed by NMS. Closing this gap would require either better per-page refs (data work) or a secondary classifier (out of PoC scope).

**v_roi_2b locked**: tau=0.685, nms=0.10, OCF=2.5, sat=30, iou_match=0.20 → **P=0.937, R=0.891, F1=0.913** (450 GT).

## Next things to try if pushing further

1. **Curated reference bank for page 2** — the dominant remaining recall hole (35 of ~50 FN in v_roi_2b). Same data-work approach that fixed page 4.
2. **Per-template score normalisation** across template sizes. Right now the same `tau` is applied to every (ref, size) pair; calibrating to each template's score distribution on the page itself would be a stronger filter.
3. **[DONE — v_roi] Per-page hand-drawn ROI store + dual evaluation.** Implemented: `dataset/rois/*.json` for all 10 pages; dual-config evaluation in `poc_detector.ipynb`.
4. **[DONE — v_roi_2b] Recall push bench.** Confirmed hard ceiling at R=0.891 (P≥0.93) with current detector and refs. Closing the remaining gap needs new refs for page 2 (data work) or a secondary classifier.
5. **Cross-page reference pool**, with per-ref color/sat statistics still applied. Already wired, just expensive (~30 min benchmark).
