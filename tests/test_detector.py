"""Unit tests for the pure detector functions in `notebook/detector.py`.

The detector is otherwise validated end-to-end by the notebook; these tests
cover the geometry / shape primitives where bugs are easiest to introduce
(NMS, IoU, matchTemplate wrapper, ref trimming).

Run with: `pytest tests/`
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebook"))

from detector import (  # noqa: E402
    Candidate,
    _iou,
    _resize_to_target,
    match_template,
    nms,
    trim_near_white_border,
)


# ----- _iou -----------------------------------------------------------------

def test_iou_identical_boxes_is_one():
    assert _iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)


def test_iou_disjoint_boxes_is_zero():
    assert _iou((0, 0, 10, 10), (100, 100, 10, 10)) == 0.0


def test_iou_zero_area_box_is_zero():
    assert _iou((0, 0, 0, 0), (0, 0, 10, 10)) == 0.0


def test_iou_partial_overlap_is_correct():
    # 10x10 boxes at (0,0) and (5,5) → 5x5 intersection, area 25; union 175
    assert _iou((0, 0, 10, 10), (5, 5, 10, 10)) == pytest.approx(25 / 175)


def test_iou_one_inside_other():
    # 10x10 inside 20x20 at the same origin → IoU = 100 / 400 = 0.25
    assert _iou((0, 0, 10, 10), (0, 0, 20, 20)) == pytest.approx(0.25)


# ----- nms ------------------------------------------------------------------

def test_nms_empty_input():
    assert nms([], iou_thresh=0.3) == []


def test_nms_keeps_disjoint_boxes():
    cands = [
        Candidate(0, 0, 10, 10, 0.9),
        Candidate(100, 100, 10, 10, 0.8),
    ]
    kept = nms(cands, iou_thresh=0.3)
    assert len(kept) == 2


def test_nms_suppresses_overlap_keeps_higher_score():
    cands = [
        Candidate(0, 0, 10, 10, 0.7),
        Candidate(2, 2, 10, 10, 0.95),  # heavy overlap, higher score
        Candidate(50, 50, 10, 10, 0.6),
    ]
    kept = nms(cands, iou_thresh=0.3)
    assert len(kept) == 2
    # Higher-score overlapping box wins
    assert kept[0].score == 0.95
    assert any(c.x == 50 and c.y == 50 for c in kept)


def test_nms_threshold_respects_iou_value():
    # Two boxes with IoU exactly 25/175 ≈ 0.143
    cands = [
        Candidate(0, 0, 10, 10, 0.9),
        Candidate(5, 5, 10, 10, 0.8),
    ]
    # threshold above the IoU → keep both
    assert len(nms(cands, iou_thresh=0.2)) == 2
    # threshold below the IoU → suppress
    assert len(nms(cands, iou_thresh=0.1)) == 1


# ----- trim_near_white_border ----------------------------------------------

def test_trim_returns_image_when_all_white():
    white = np.full((20, 20, 3), 255, dtype=np.uint8)
    out = trim_near_white_border(white)
    # All white → trim has no work, returns input
    assert out.shape == white.shape


def test_trim_finds_dark_blob_in_white_border():
    img = np.full((30, 30, 3), 255, dtype=np.uint8)
    img[10:20, 10:20] = 0  # 10x10 black square in the middle
    out = trim_near_white_border(img)
    assert out.shape[:2] == (10, 10)
    # Centre is still black after trim
    assert int(out[5, 5, 0]) == 0


def test_trim_handles_grayscale_input():
    gray = np.full((20, 20), 255, dtype=np.uint8)
    gray[5:15, 5:15] = 0
    out = trim_near_white_border(gray)
    assert out.shape == (10, 10)


def test_trim_uses_threshold():
    # Pixels just below white_thresh should be kept
    img = np.full((30, 30, 3), 250, dtype=np.uint8)
    img[10:20, 10:20] = 240  # below default threshold of 245
    out = trim_near_white_border(img)
    assert out.shape[:2] == (10, 10)


# ----- _resize_to_target ----------------------------------------------------

def test_resize_to_target_long_side_matches():
    img = np.zeros((50, 30), dtype=np.uint8)  # h=50, w=30, long side = 50
    out = _resize_to_target(img, 25)
    # Long side becomes 25
    assert max(out.shape) == 25


def test_resize_to_target_preserves_aspect_ratio_within_rounding():
    img = np.zeros((40, 20), dtype=np.uint8)  # 2:1 aspect
    out = _resize_to_target(img, 20)
    h, w = out.shape
    assert max(h, w) == 20
    # Aspect should be ~2:1 (allow for ±1 px rounding)
    assert abs((h / w) - 2.0) < 0.15


def test_resize_to_target_floors_at_three_pixels():
    img = np.zeros((100, 100), dtype=np.uint8)
    out = _resize_to_target(img, 1)  # would round to 0×0; clipped to 3
    assert out.shape[0] >= 3 and out.shape[1] >= 3


# ----- match_template -------------------------------------------------------

def _structured_template(size: int = 20) -> np.ndarray:
    """Build a 20x20 patch with non-zero variance: filled circle on white.
    Required for TM_CCOEFF_NORMED to behave (uniform templates give NaN/1.0)."""
    tpl = np.full((size, size), 255, dtype=np.uint8)
    cv2.circle(tpl, (size // 2, size // 2), size // 3, 0, thickness=-1)
    return tpl


def test_match_template_finds_self():
    """Template embedded in a known position must score above 0.95."""
    template = _structured_template(20)
    page = np.full((200, 300), 255, dtype=np.uint8)
    # Embed the template at (x=50, y=100)
    page[100:120, 50:70] = template
    cands = match_template(page, template, tau=0.95)
    assert len(cands) >= 1
    # Best candidate is the inserted location
    best = max(cands, key=lambda c: c.score)
    assert best.x == 50 and best.y == 100
    assert best.w == 20 and best.h == 20
    assert best.score >= 0.95


def test_match_template_returns_empty_when_template_too_big():
    page = np.zeros((10, 10), dtype=np.uint8)
    template = np.zeros((20, 20), dtype=np.uint8)
    assert match_template(page, template, tau=0.5) == []


def test_match_template_returns_empty_when_template_too_small():
    page = np.zeros((100, 100), dtype=np.uint8)
    template = np.zeros((2, 2), dtype=np.uint8)
    assert match_template(page, template, tau=0.5) == []


def test_match_template_threshold_filters_weak_matches():
    """Page contains no copy of the template — no peak should cross tau."""
    template = _structured_template(20)
    # Page filled with random uniform noise (no embedded template)
    rng = np.random.default_rng(seed=42)
    page = rng.integers(low=120, high=160, size=(200, 300), dtype=np.uint8)
    cands = match_template(page, template, tau=0.95)
    # Random noise correlates only weakly with a structured template — at
    # tau=0.95 we expect zero or a tiny number of peaks. Allow up to 5 to
    # account for chance high correlations on a 200x300 page.
    assert len(cands) <= 5
