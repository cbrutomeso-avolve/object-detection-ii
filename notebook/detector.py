"""Pure detector functions for the object-detection PoC.

Class-agnostic by design: the caller passes references and parameters; the
detector returns bounding-box candidates with no category awareness. The
notebook orchestrates per-class loops and writes COCO-format predictions.

Pipeline (final, after iteration documented in `notebook/trials.md`):
1. Grayscale `cv2.matchTemplate` (TM_CCOEFF_NORMED) at a dense list of target
   sizes — sprinkler symbols span ~9–57 px across plans and the score peak
   is sharp (~10% step needed to not miss the right scale).
2. Multi-reference union; ROI mask filters candidates outside the largest
   connected ink region (excludes legend / title block / vicinity map).
3. Mean-BGR distance + HSV-saturation filters reject black-on-white text
   matches against colored references.
4. Greedy NMS for deduplication.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np


@dataclass(frozen=True)
class Candidate:
    x: int
    y: int
    w: int
    h: int
    score: float


def trim_near_white_border(image: np.ndarray, white_thresh: int = 245) -> np.ndarray:
    """Crop to the tight bounding box of non-near-white pixels."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    mask = gray < white_thresh
    if not mask.any():
        return image
    ys, xs = np.where(mask)
    return image[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _rotate_expand(image: np.ndarray, angle_deg: float) -> np.ndarray:
    if angle_deg == 0.0:
        return image
    h, w = image.shape[:2]
    center = (w / 2.0, h / 2.0)
    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    new_w = int(round(h * sin + w * cos))
    new_h = int(round(h * cos + w * sin))
    M[0, 2] += new_w / 2.0 - center[0]
    M[1, 2] += new_h / 2.0 - center[1]
    return cv2.warpAffine(image, M, (new_w, new_h), borderValue=255)


def _resize_to_target(image: np.ndarray, target_size_px: int) -> np.ndarray:
    h, w = image.shape[:2]
    long_side = max(h, w)
    if long_side < 4:
        return image
    s = target_size_px / long_side
    new_w = max(3, int(round(w * s)))
    new_h = max(3, int(round(h * s)))
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix0, iy0 = max(ax, bx), max(ay, by)
    ix1, iy1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def nms(candidates: list[Candidate], iou_thresh: float) -> list[Candidate]:
    """Greedy non-max suppression. Class-agnostic; group by class before calling."""
    items = sorted(candidates, key=lambda c: c.score, reverse=True)
    kept: list[Candidate] = []
    for c in items:
        cb = (c.x, c.y, c.w, c.h)
        if all(_iou(cb, (k.x, k.y, k.w, k.h)) < iou_thresh for k in kept):
            kept.append(c)
    return kept


def match_template(
    page_gray: np.ndarray,
    template_gray: np.ndarray,
    tau: float,
) -> list[Candidate]:
    H, W = page_gray.shape
    th, tw = template_gray.shape
    if th >= H or tw >= W or th < 3 or tw < 3:
        return []
    scores = cv2.matchTemplate(page_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    kernel = np.ones((max(3, th), max(3, tw)), np.uint8)
    local_max = cv2.dilate(scores, kernel)
    peaks = (scores >= local_max - 1e-6) & (scores >= tau)
    ys, xs = np.where(peaks)
    if len(ys) == 0:
        return []
    return [
        Candidate(x=int(x), y=int(y), w=int(tw), h=int(th), score=float(scores[y, x]))
        for x, y in zip(xs, ys)
    ]


def _patch_mean_bgr(page_bgr: np.ndarray, cand: Candidate) -> np.ndarray | None:
    H, W = page_bgr.shape[:2]
    x0, y0 = max(0, cand.x), max(0, cand.y)
    x1, y1 = min(W, cand.x + cand.w), min(H, cand.y + cand.h)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return page_bgr[y0:y1, x0:x1].mean(axis=(0, 1))


def _patch_mean_sat(page_hsv: np.ndarray, cand: Candidate) -> float | None:
    H, W = page_hsv.shape[:2]
    x0, y0 = max(0, cand.x), max(0, cand.y)
    x1, y1 = min(W, cand.x + cand.w), min(H, cand.y + cand.h)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return float(page_hsv[y0:y1, x0:x1, 1].mean())


def _ref_mean_sat(ref_bgr: np.ndarray) -> float:
    if ref_bgr.ndim != 3:
        return 0.0
    return float(cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2HSV)[..., 1].mean())


def _drop_low_distinctness_refs(refs: list[np.ndarray], min_dark_per_channel: int) -> list[np.ndarray]:
    """Drop refs whose trimmed mean BGR is above the threshold in every channel
    (mostly white = matches anything = low signal). Returns at least one ref to
    avoid an empty list."""
    kept = []
    for r in refs:
        trimmed = trim_near_white_border(r)
        if trimmed.ndim != 3:
            kept.append(r)
            continue
        m = trimmed.mean(axis=(0, 1))
        if not all(c >= min_dark_per_channel for c in m):
            kept.append(r)
    return kept if kept else refs[:1]


def remove_long_lines(
    page_bgr: np.ndarray,
    *,
    min_length_px: int = 80,
    dark_thresh: int = 100,
    inpaint_radius: int = 3,
) -> np.ndarray:
    """Detect long horizontal and vertical dark lines (dimension marks, pipes,
    table borders) and inpaint them out of the page.

    Sprinkler symbols (max ~57 px in this dataset) are shorter than
    `min_length_px=80` so the morphological opening with line kernels never
    catches them — only true dimension/pipe lines are extracted. Without this
    step, lines crossing a sprinkler perturb the patch and drop
    `cv2.matchTemplate(TM_CCOEFF_NORMED)` scores from ~0.85 to ~0.3, well
    below tau, causing systematic false negatives in light-region zones of
    architectural plans.
    """
    gray = cv2.cvtColor(page_bgr, cv2.COLOR_BGR2GRAY) if page_bgr.ndim == 3 else page_bgr
    _, dark = cv2.threshold(gray, dark_thresh, 255, cv2.THRESH_BINARY_INV)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_length_px, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_length_px))
    h_lines = cv2.morphologyEx(dark, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(dark, cv2.MORPH_OPEN, v_kernel)
    line_mask = cv2.dilate(cv2.bitwise_or(h_lines, v_lines), np.ones((3, 3), np.uint8))
    if line_mask.sum() == 0:
        return page_bgr
    return cv2.inpaint(page_bgr, line_mask, inpaint_radius, cv2.INPAINT_TELEA)


def compute_drawing_roi(
    page_bgr: np.ndarray,
    *,
    edge_low: int = 50,
    edge_high: int = 150,
    dilate_kernel: int = 25,
    min_area_frac: float = 0.05,
) -> np.ndarray:
    """Heuristic ROI: keep only the largest connected blob of structural ink.

    A plan's drawing area is one big connected ink region (walls, dimension
    lines, etc.). Title block, legend, vicinity map are smaller separate
    regions surrounded by white. Connected-components on a generously
    dilated edge map separates them; the biggest component is the drawing.

    Returns a uint8 mask (0/255) the same H×W as `page_bgr`. Components below
    `min_area_frac` of the page area are also kept to be permissive — we'd
    rather include a slightly smaller drawing than miss real sprinklers.
    """
    gray = cv2.cvtColor(page_bgr, cv2.COLOR_BGR2GRAY) if page_bgr.ndim == 3 else page_bgr
    edges = cv2.Canny(gray, edge_low, edge_high)
    kernel = np.ones((dilate_kernel, dilate_kernel), np.uint8)
    dilated = cv2.dilate(edges, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dilated, connectivity=8)
    if n <= 1:
        return np.full(gray.shape, 255, np.uint8)
    page_area = gray.shape[0] * gray.shape[1]
    sizes = stats[1:, cv2.CC_STAT_AREA]
    biggest = int(np.argmax(sizes)) + 1
    mask = (labels == biggest).astype(np.uint8) * 255
    # Take bounding box of biggest blob and grow by ~3% margin
    x = stats[biggest, cv2.CC_STAT_LEFT]
    y = stats[biggest, cv2.CC_STAT_TOP]
    w = stats[biggest, cv2.CC_STAT_WIDTH]
    h = stats[biggest, cv2.CC_STAT_HEIGHT]
    margin = int(0.03 * max(gray.shape))
    x0 = max(0, x - margin)
    y0 = max(0, y - margin)
    x1 = min(gray.shape[1], x + w + margin)
    y1 = min(gray.shape[0], y + h + margin)
    bbox_mask = np.zeros_like(mask)
    bbox_mask[y0:y1, x0:x1] = 255
    return bbox_mask


def _candidate_in_mask(mask: np.ndarray, cand: Candidate) -> bool:
    cy = cand.y + cand.h // 2
    cx = cand.x + cand.w // 2
    H, W = mask.shape[:2]
    if 0 <= cy < H and 0 <= cx < W:
        return bool(mask[cy, cx])
    return False


def find_best_scale_ratio(
    page_gray: np.ndarray,
    ref_gray: np.ndarray,
    candidate_ratios: Sequence[float],
    tau: float,
    top_k: int = 10,
) -> float:
    """Coarse-scan per-(page, ref) to pick the scale ratio that produces the
    strongest top-K peaks. The detector then runs a fine sweep around the
    winning ratio. This adapts the template scale to each page's actual
    symbol size without hardcoded per-page tuning."""
    ref_long = max(ref_gray.shape)
    best_ratio = candidate_ratios[len(candidate_ratios) // 2]
    best_metric = -1.0
    for ratio in candidate_ratios:
        size = int(round(ref_long * ratio))
        if size < 4:
            continue
        tpl = _resize_to_target(ref_gray, size)
        if tpl.shape[0] < 3 or tpl.shape[1] < 3:
            continue
        if tpl.shape[0] >= page_gray.shape[0] or tpl.shape[1] >= page_gray.shape[1]:
            continue
        scores = cv2.matchTemplate(page_gray, tpl, cv2.TM_CCOEFF_NORMED)
        kernel = np.ones((max(3, tpl.shape[0]), max(3, tpl.shape[1])), np.uint8)
        local_max = cv2.dilate(scores, kernel)
        peaks = (scores >= local_max - 1e-6) & (scores >= tau)
        peak_scores = scores[peaks]
        if peak_scores.size < 3:
            continue
        k = min(top_k, peak_scores.size)
        top = np.partition(peak_scores, -k)[-k:]
        metric = float(top.sum())
        if metric > best_metric:
            best_metric = metric
            best_ratio = ratio
    return best_ratio


def detect(
    page_bgr: np.ndarray,
    references_bgr: list[np.ndarray],
    *,
    target_sizes_px: Sequence[int] | None = None,
    target_size_coarse_ratios: Sequence[float] | None = None,
    target_size_fine_steps: Sequence[float] = (0.85, 0.93, 1.0, 1.08, 1.17),
    tau: float,
    iou_nms: float,
    rotations_deg: Sequence[float] = (0.0,),
    color_max_distance: float | None = None,
    sat_max_distance: float | None = None,
    drop_light_refs_thresh: int | None = None,
    use_roi_mask: bool = False,
    roi_mask: np.ndarray | None = None,
    outlier_count_factor: float | None = None,
    outlier_count_min_threshold: int = 20,
    remove_long_lines_min_length: int | None = None,
    downsample_size_threshold_px: int | None = None,
) -> list[Candidate]:
    """Grayscale matchTemplate at one or more target sizes, multi-reference
    union, greedy NMS.

    `target_sizes_px` lists the absolute longest-side template sizes to try.
    Sprinkler symbols span ~9–57 px across plans, so a small geometric list
    covers the range without exploding cost.

    `rotations_deg` defaults to a single 0° pass — extend only if recall
    demands it; each extra angle multiplies the per-page cost.

    `color_max_distance` filters candidates whose mean BGR is further than
    this from the matching reference's mean BGR. Cheap discriminator that
    rejects black-on-white text matches against a colored reference.

    `sat_max_distance` filters candidates whose patch saturation differs
    from the reference's mean saturation by more than this. Catches text
    matches against colored refs (text is low-sat, blue ref is high-sat).

    `drop_light_refs_thresh` drops refs whose trimmed mean BGR is at or
    above this in every channel (e.g. 220 = mostly white, low signal).

    `downsample_size_threshold_px` enables a hybrid full-res / 2x-downsampled
    matching strategy that keeps per-page latency stable as more refs are
    added. Templates with `size <= threshold` run on the full-resolution
    page (preserving detail for tiny sprinklers); templates with
    `size > threshold` run on a 2x-downsampled page with the template also
    halved. Match coordinates from the downsampled pass are scaled by 2
    back to full-res. Recommended threshold = 17. `None` (default) keeps
    everything full-res.
    """
    if (target_sizes_px is None) == (target_size_coarse_ratios is None):
        raise ValueError("specify exactly one of target_sizes_px or target_size_coarse_ratios")
    if remove_long_lines_min_length is not None:
        page_bgr = remove_long_lines(page_bgr, min_length_px=remove_long_lines_min_length)
    refs = list(references_bgr)
    if drop_light_refs_thresh is not None:
        refs = _drop_low_distinctness_refs(refs, drop_light_refs_thresh)

    page_gray = cv2.cvtColor(page_bgr, cv2.COLOR_BGR2GRAY) if page_bgr.ndim == 3 else page_bgr
    page_hsv = cv2.cvtColor(page_bgr, cv2.COLOR_BGR2HSV) if (page_bgr.ndim == 3 and sat_max_distance is not None) else None
    if downsample_size_threshold_px is not None:
        H, W = page_gray.shape
        page_gray_small = cv2.resize(page_gray, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    else:
        page_gray_small = None
    cands_with_origin: list[tuple[Candidate, int, int]] = []  # (cand, ref_idx, template_long_side_px)
    for ref_idx, ref in enumerate(refs):
        trimmed = trim_near_white_border(ref)
        ref_gray = cv2.cvtColor(trimmed, cv2.COLOR_BGR2GRAY) if trimmed.ndim == 3 else trimmed
        ref_color = trimmed.mean(axis=(0, 1)) if (trimmed.ndim == 3 and color_max_distance is not None) else None
        ref_sat = _ref_mean_sat(trimmed) if (sat_max_distance is not None) else None
        if target_size_coarse_ratios is not None:
            ref_long = max(ref_gray.shape)
            best_ratio = find_best_scale_ratio(page_gray, ref_gray, target_size_coarse_ratios, tau=tau)
            sizes_for_ref = [max(8, int(round(ref_long * best_ratio * f))) for f in target_size_fine_steps]
        else:
            sizes_for_ref = list(target_sizes_px)
        for size in sizes_for_ref:
            use_downsampled = (
                downsample_size_threshold_px is not None
                and size > downsample_size_threshold_px
                and page_gray_small is not None
            )
            tpl_size = size // 2 if use_downsampled else size
            ref_resized = _resize_to_target(ref_gray, tpl_size)
            for angle in rotations_deg:
                tpl = _rotate_expand(ref_resized, angle)
                if tpl.shape[0] < 3 or tpl.shape[1] < 3:
                    continue
                if use_downsampled:
                    cands_raw = match_template(page_gray_small, tpl, tau=tau)
                    cands = [Candidate(c.x * 2, c.y * 2, c.w * 2, c.h * 2, c.score) for c in cands_raw]
                else:
                    cands = match_template(page_gray, tpl, tau=tau)
                if ref_color is not None:
                    cands = [
                        c for c in cands
                        if (m := _patch_mean_bgr(page_bgr, c)) is not None
                        and float(np.linalg.norm(m - ref_color)) <= color_max_distance
                    ]
                if ref_sat is not None and page_hsv is not None:
                    cands = [
                        c for c in cands
                        if (s := _patch_mean_sat(page_hsv, c)) is not None
                        and abs(s - ref_sat) <= sat_max_distance
                    ]
                tpl_long = max(tpl.shape[:2])
                cands_with_origin.extend((c, ref_idx, tpl_long) for c in cands)
    if not cands_with_origin:
        return []
    if outlier_count_factor is not None:
        from collections import Counter
        counts = Counter((rid, sz) for _, rid, sz in cands_with_origin)
        sorted_counts = sorted(counts.values())
        median_count = sorted_counts[len(sorted_counts) // 2]
        threshold = max(outlier_count_min_threshold, int(median_count * outlier_count_factor))
        cands_with_origin = [t for t in cands_with_origin if counts[(t[1], t[2])] <= threshold]
        if not cands_with_origin:
            return []
    all_cands = [t[0] for t in cands_with_origin]
    if use_roi_mask:
        mask = roi_mask if roi_mask is not None else compute_drawing_roi(page_bgr)
        all_cands = [c for c in all_cands if _candidate_in_mask(mask, c)]
        if not all_cands:
            return []
    return nms(all_cands, iou_thresh=iou_nms)
