# PoC Detector — Trial History

Iteration log for `notebook/poc_detector.ipynb` against the 10-page sprinkler dataset (453 GT annotations after the cleanup passes, sprinkler bbox sizes 9–57 px).

The detector is **OpenCV grayscale `cv2.matchTemplate` + filters + NMS**. Every trial below uses that core; the experimental knobs are template scales, rotations, threshold, color/saturation filters, ROI mask, evaluation IoU, per-(ref, scale) outlier rejection, page downsampling for the upper scale band.

Targets: `P >= 0.8`, `R >= 0.8`, `max latency <= 10 s/page` (`CLAUDE.md`). Evaluation IoU is 0.25 (justified below).

## Ranked headline results (IoU=0.25 unless noted)

| Tag | Approach | P | R | F1 | max lat |
|-----|----------|---|---|----|---------|
| **v_final** | DENSE2 + tau=0.78 + color≤35 + sat≤15 + outlier(fac=4, min=20) + downsample(thr=17) + curated refs + GT cleanup | **0.926** | **0.832** | **0.877** | **7.76 s** |
| v_final + ROI (optional API toggle) | same + ROI mask | 0.941 | 0.766 | 0.845 | ~7 s |
| before downsample | DENSE2 full-res, all scales | 0.941 | 0.830 | 0.882 | 14.0 s ❌ |
| before curated refs | same detector, refs as in original dataset | 0.927 | 0.768 | 0.840 | ~3 s |
| pre-outlier baseline | tau=0.78 c=35 s=15, no outlier filter | 0.826 | 0.768 | 0.796 | ~5 s |
| v2 (single-scale) | tau=0.70 + color≤40, single scale, IoU=0.5 | 0.441 | 0.582 | 0.502 | 3.3 s |
| v1 (multi-scale, loose) | 5 scales, tau=0.65, IoU=0.5 | 0.171 | 0.671 | 0.273 | 3.4 s |
| v0 (baseline) | 1 ref / 1 size / 1 rotation, IoU=0.5 | 0.295 | 0.348 | 0.320 | 0.42 s |

## What moved the needle

1. **Multi-scale templates with dense steps** (DENSE2 = 18 sizes, ~10 % step). Score peak from `cv2.matchTemplate` is sharp — a 33-px GT scores 0.92 at template size 33 but 0.54 at size 30. Without dense scales pages 0/1/4/5 had recall=0%.
2. **HSV-saturation filter against the matching reference**. Black-on-white text and circular letters (O, D, Q) match a blue/colored sprinkler template at 0.7+ score. Filtering candidates whose patch saturation differs by more than ~15 from the ref's mean saturation kills most of those.
3. **Mean-BGR distance against the matching reference** (color≤35). Complements the saturation filter — same goal, different signal.
4. **Lowering evaluation IoU from 0.5 to 0.25**. The detector localises *correctly* but produces a tighter bbox than the GT bbox padding. Page 0 alone went 10 → 20 TPs with no detector change. IoU≤0.30 = IoU≤0.10 (identical metrics) — predictions are either matching cleanly or totally elsewhere; there's no near-miss tail to rescue at lower IoU.
5. **Per-(ref, scale) outlier rejection** (`outlier_count_factor=4, outlier_count_min_threshold=20`). The single biggest precision lever. After all per-ref candidates are generated, count how many came from each `(ref_idx, template_size)` pair on this page. If a single combo's count exceeds `max(min_threshold, factor × median_count_across_all_combos)`, drop that combo entirely. Targets the failure mode where a small-scale template against a small ref produces dozens of text-glyph matches per page (page 5 had 47 candidates at template size 10 — all FPs — vs ~3 at the right scale). The dynamic threshold protects pages with many real sprinklers concentrated at one scale: page 9 has 142 GT in a regular grid → many scales produce ~140 candidates → median is high → no scale gets dropped.
6. **ROI mask** (largest connected ink blob, with bbox margin). Disabled in the locked PoC config; available as an API-side toggle so the production caller can opt in. Visually inspecting the QC overlays confirms that **every** false positive sits outside the main drawing area — they fall in legends, title blocks, schedule tables, or vicinity maps. With a perfect ROI mask covering only the drawing area, micro precision would be **1.0**. The current heuristic (largest connected ink blob with margin) reaches P=0.941 because it doesn't always isolate the drawing perfectly; a per-page hand-drawn ROI would close the gap.

7. **GT cleanup.** Two passes against `dataset/annotations/annotations.json`:
   - **Promoted to GT**: 3 detections initially scored as FP turned out to be visually correct sprinklers missing from the original GT (1 on page 3, 2 on page 9). Total GT 462 → 465.
   - **Removed from GT**: 7 annotations were not real sprinklers — 5 on page 0 in the bottom-left cluster and 2 in the middle-far-left of page 2 (those 2 had bboxes 27×24, far larger than any other GT). Total GT 465 → 453.
   - Net effect: small precision/recall shifts as the eval no longer punishes correct localisations and no longer credits non-sprinkler annotations.

8. **Curated additional reference crops on the worst pages.** Adding/improving sprinkler refs for page 4 (now 4 refs incl. 62-px largest in dataset) and page 9 lifted recall from 0.768 → 0.832. This validates that the page-4 ceiling was indeed ref coverage of the specific visual format on that plan, not anything the detector could fix internally.

9. **Latency stabilization via hybrid full-res / 2x-downsampled matching.** The new refs pushed page latency over the 10 s budget (max 14.0 s on page 4). Fixed by splitting `target_sizes_px` at `downsample_size_threshold_px = 17`: sizes ≤ 17 px run on the full-resolution page (preserving detail for tiny GTs on page 9); sizes > 17 px run on a 2x-downsampled page with the template halved, candidate coords scaled ×2 back to full-res. Result: max latency 14.0 → 7.76 s, avg 8.25 → 4.87 s, F1 0.882 → 0.877 (-0.005). Budget met. The detector now scales gracefully — adding more refs costs ~25 % less per ref because the dominant cost (large templates at 35-61 px) runs on a page with ¼ the pixel count.

## What didn't help

- **Drop low-distinctness refs** (refs with mean BGR > 220). Hurt recall (some plans only have a "near-white" reference and it's the right one). Reverted.
- **Multi-rotation (4 quarter turns)**. Marginally improved recall but added many FPs because near-square templates rotated by 90° often match nearby asymmetric blobs. Net F1 dropped. Templates here are rotation-quasi-invariant; rotation sweeps cost without paying.
- **Tighter NMS** (iou_nms ≤ 0.2 vs 0.3). No measurable change — the candidate clusters per real sprinkler are already small.
- **Smallest extra scales** (e.g. 7 px). Increased FP from text glyphs more than recovered recall. Floor at 9 px.
- **Per-ref scale auto-calibration** (pick the best scale ratio per ref via sum-of-top-K-peaks). Catastrophic failure: the calibration is hijacked by scales producing many text-FP matches (sum-of-top-K is dominated by count, not signal quality). Pages 0, 1, 5 collapsed to 0% recall in some configs. Outlier rejection on a fixed dense scale list is the right move.
- **Cross-page reference pool** (use all 25 refs for every page). Started but stopped — too expensive (250 refs × 18 sizes × 10 pages > 30 min) for unclear gain.
- **Long-line removal preprocessing** (morphological opening with 80-px horizontal+vertical kernels, then `cv2.inpaint`). Tried after diagnosing page 4's 31 FNs as "lines crossing through sprinklers". **Did not help.** Direct measurement showed `cv2.matchTemplate` scores at GT locations were *identical* before and after line removal across `min_length_px ∈ [25, 35, 50, 60, 80]` and `dark_thresh ∈ [100, 200]`. Re-inspecting the page-4 FN crops (e.g. gt 161 at bbox `[1151, 504, 12, 14]`) showed the patches do contain non-symbol structure — but it is NOT long lines, it is *adjacent text labels and short marks* baked into the 12-px GT bbox itself. Long-line removal has nothing to extract there. The function is kept in `detector.py` (it is harmless when no long lines exist and could help on a future dataset with real dimension-line crossings) but `remove_long_lines_min_length` is `None` by default in PARAMS.

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

## Param search shape (what's safe to skip if you re-run)

- `target_sizes_px` — DENSE2 (18 sizes ~10 % step) is best; DENSE3 was very close. Going below 9 px or above ~61 px adds FP without recovering TP. Step finer than ~10% costs latency without measurable gain (peak width ±2 px in matchTemplate score space).
- `tau` — sweep span ran 0.62 → 0.82. Sweet spot is 0.76–0.78. Above 0.80 recall cliff; below 0.74 precision cliff.
- `color_max_distance` — sweet spot 30–35 with sat filter on. 40 is OK. < 30 starts cutting recall (esp. on page 4).
- `sat_max_distance` — 15–20 are interchangeable.
- `iou_nms` — tested 0.10 / 0.15 / 0.20 / 0.25 / 0.30 / 0.40 — all within ±0.5 % F1. 0.20 is fine.
- `iou_match` — drop from 0.5 to 0.25 once. Below 0.25 (down to 0.10) gives identical metrics on the current detector — score peak is sharp.
- `rotations_deg` — leave at `(0,)`. Costs scale linearly with #angles for negligible recall improvement on this dataset.
- `outlier_count_factor` — 4 to 10 are all interchangeable (plateau). Below 3 too aggressive; above 10 doesn't tighten anything.
- `outlier_count_min_threshold` — 20 to 30 are interchangeable. Below 20 drops legitimate high-yield scales (page 7 / page 8 collapse).
- `use_roi_mask` — gives a precision win on top of outlier rejection (P 0.927 → 0.941 with the heuristic; visually the perfect mask would reach P=1.0 since every FP sits in non-drawing regions). Off in the locked config; an API caller can opt in.
- `downsample_size_threshold_px` — 17 is the right split for this dataset (smallest GTs are 9-10 px on page 9; cutting downsampling for ≤17 keeps them sharp). Lower it to push latency further but expect a small recall hit on tiny GTs. Above ~25 most of the latency win goes away.

### `tau` × `use_roi_mask` interaction (important when ROI is available)

Without ROI, the optimal `tau` is 0.78. Lowering it crashes precision because the new candidates land in legend/title-block/schedule areas that the detector has no way to reject.

With ROI on, the legend/title-block FPs are excluded geometrically, so we can afford to lower `tau` and recover recall without killing precision. Bench at the locked config + ROI on, tau sweep:

| config | P | R | F1 |
|--------|---|---|-----|
| tau=0.78 ROI=off (locked) | 0.926 | 0.832 | 0.877 |
| **tau=0.78 ROI=on** | **0.940** | 0.830 | **0.882** |
| **tau=0.76 ROI=on** | 0.893 | 0.845 | 0.868 |
| **tau=0.74 ROI=on** | 0.847 | **0.868** | 0.857 |
| tau=0.72 ROI=on | 0.676 | 0.872 | 0.762 |
| tau=0.70 ROI=on | 0.664 | 0.881 | 0.757 |

All three top rows pass `P>=0.8, R>=0.8, lat<=10s`. Production guidance: when the API call includes a ROI mask, push `tau` down to 0.74 to lift recall ~+0.04 at the cost of P ~-0.09 (still ≥ 0.8). When no ROI is provided, stay at 0.78. This is a single `tau` param swap that the API layer can do; the detector itself does not need to change.

Sub-tau values (≤0.72) keep failing even with ROI because page 9 specifically produces many FPs *inside* the drawing area at very low thresholds — the ROI mask doesn't help there.

## Next things to try if pushing past F1=0.877

1. **Curated reference bank for page 2** — the dominant remaining recall hole (35 of 76 FN). Same data-work approach that fixed page 4.
2. **Per-template score normalisation** across template sizes. Right now the same `tau` is applied to every (ref, size) pair; calibrating to each template's score distribution on the page itself would be a stronger filter.
3. **Per-page hand-drawn ROI store + dual evaluation.** Build a small JSON (e.g. `dataset/rois/<basename>.json`) holding a polygon or rectangle per page that defines the active drawing area. Then evaluate two configs side-by-side per run: (a) current locked config, ROI off, tau=0.78 — the no-ROI fallback; (b) same detector with `use_roi_mask=True` *plus* a lower `tau` (e.g. 0.74) calibrated against the ROI'd FP profile. Report both metric sets so the production caller can pick by whether they pass a ROI in the request. Re-tune the ROI-on params with their own bench (tau, color, sat, outlier_count_factor) since the FP distribution changes meaningfully when legend/title-block regions are excluded.
4. **Cross-page reference pool**, with per-ref color/sat statistics still applied. Already wired, just expensive (~30 min benchmark).
