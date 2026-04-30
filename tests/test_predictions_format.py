"""Regression tests on the latest predictions JSON.

Catches the COCO-format mistakes that `CLAUDE.md` calls out:
- bbox is `[x, y, w, h]` (not `[x1, y1, x2, y2]`); w and h must be > 0.
- `category_id` references a real category in the GT file.
- `image_id` references a real image in the GT file.
- `score` is a number in [0, 1].

Run with: `pytest tests/`
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GT_PATH = REPO_ROOT / "dataset" / "annotations" / "annotations.json"


def _latest_predictions() -> Path | None:
    candidates = sorted((REPO_ROOT / "outputs").glob("predictions_*.json"))
    return candidates[-1] if candidates else None


@pytest.fixture(scope="module")
def gt():
    if not GT_PATH.exists():
        pytest.skip(f"missing GT file: {GT_PATH}")
    return json.loads(GT_PATH.read_text())


@pytest.fixture(scope="module")
def predictions():
    p = _latest_predictions()
    if p is None:
        pytest.skip("no predictions_*.json on disk; run the notebook first")
    return json.loads(p.read_text()), p.name


def test_predictions_is_a_flat_list(predictions):
    preds, name = predictions
    assert isinstance(preds, list), f"{name} must be a flat list per COCO results"


def test_predictions_have_required_keys(predictions):
    preds, _ = predictions
    required = {"image_id", "category_id", "bbox", "score"}
    for p in preds[:200]:  # spot check
        assert required.issubset(p.keys()), f"prediction missing keys: {required - p.keys()}"


def test_bbox_is_xywh_with_positive_size(predictions):
    """bbox is [x, y, w, h] in pixels — w and h must be positive.
    A bbox of [x1, y1, x2, y2] format would yield w=x2 > x1 and h=y2 > y1,
    but typical (x1, y1) pairs are small and (x2, y2) are large, so this
    looks like normal xywh — the better discriminator is that w*h ≈ symbol
    area. We assert positive w/h plus a reasonable upper bound."""
    preds, _ = predictions
    assert preds, "no predictions to validate"
    for p in preds:
        bbox = p["bbox"]
        assert len(bbox) == 4, f"bbox must be 4-tuple, got {bbox}"
        x, y, w, h = bbox
        assert w > 0, f"bbox width must be > 0, got {bbox}"
        assert h > 0, f"bbox height must be > 0, got {bbox}"
        # Sanity: a sprinkler symbol is < 200 px in any dimension on these plans
        assert w < 500 and h < 500, f"bbox suspiciously large: {bbox}"


def test_score_in_unit_interval(predictions):
    preds, _ = predictions
    for p in preds:
        s = p["score"]
        assert 0.0 <= s <= 1.0, f"score outside [0, 1]: {s}"


def test_category_id_matches_gt(gt, predictions):
    preds, _ = predictions
    valid_cat_ids = {c["id"] for c in gt["categories"]}
    for p in preds[:500]:
        assert p["category_id"] in valid_cat_ids, (
            f"prediction category_id={p['category_id']} not in GT {valid_cat_ids}"
        )


def test_image_id_matches_gt(gt, predictions):
    preds, _ = predictions
    valid_image_ids = {i["id"] for i in gt["images"]}
    for p in preds[:500]:
        assert p["image_id"] in valid_image_ids, (
            f"prediction image_id={p['image_id']} not in GT image set"
        )


def test_predictions_use_python_native_numbers(predictions):
    """JSON-serialised predictions should not contain numpy scalars (those
    survive `json.dumps` only because pycocotools tolerates them; but on a
    fresh `json.load(...)` they're regular floats. This test confirms the
    written file is clean Python ints/floats, which is what every consumer
    expects)."""
    preds, _ = predictions
    for p in preds[:50]:
        assert type(p["image_id"]) is int
        assert type(p["category_id"]) is int
        assert type(p["score"]) is float
        for v in p["bbox"]:
            assert type(v) in (int, float)
