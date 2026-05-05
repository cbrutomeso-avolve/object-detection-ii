"""HTTP contract tests for POST /detect.

Expected detections are loaded directly from the validated prediction
files in outputs/ for image_id=0. The tests assert exact bbox match
and near-exact score match (float32→float64 round-trip tolerance).
"""
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from api.main import app

client = TestClient(app)

_ROOT = Path(__file__).parent.parent
_OUTPUTS = _ROOT / "outputs"
_FORM = {"category_name": "sprinkler", "category_id": "0"}

# ROI for image_id=0 from dataset/rois/001_Fire_Sprinkler_Plan_page_001.json
_ROI_XYWH = [68, 125, 2043, 1075]


def _predictions_for(filename: str, image_id: int) -> list[dict]:
    preds = json.loads((_OUTPUTS / filename).read_text())
    return [p for p in preds if p["image_id"] == image_id]


_EXPECTED_NO_ROI = _predictions_for(
    "predictions_2026-05-04_1246_final_no_roi.json", image_id=0
)
_EXPECTED_ROI = _predictions_for(
    "predictions_2026-05-04_1246_final_roi.json", image_id=0
)


def _assert_detections(detections: list[dict], expected: list[dict]) -> None:
    assert len(detections) == len(expected)
    for det, exp in zip(detections, expected):
        assert det["bbox"] == exp["bbox"]
        assert det["score"] == pytest.approx(exp["score"], rel=1e-5)


def test_multi_reference(
    plan_bytes: bytes,
    ref_bytes_1: bytes,
    ref_bytes_2: bytes,
    ref_bytes_3: bytes,
) -> None:
    response = client.post(
        "/detect",
        data=_FORM,
        files=[
            ("plan", ("plan.png", plan_bytes, "image/png")),
            ("references", ("ref1.png", ref_bytes_1, "image/png")),
            ("references", ("ref2.png", ref_bytes_2, "image/png")),
            ("references", ("ref3.png", ref_bytes_3, "image/png")),
        ],
    )
    assert response.status_code == 200
    _assert_detections(response.json()["detections"], _EXPECTED_NO_ROI)


def test_multi_reference_with_roi(
    plan_bytes: bytes,
    ref_bytes_1: bytes,
    ref_bytes_2: bytes,
    ref_bytes_3: bytes,
) -> None:
    response = client.post(
        "/detect",
        data={**_FORM, "roi": json.dumps(_ROI_XYWH)},
        files=[
            ("plan", ("plan.png", plan_bytes, "image/png")),
            ("references", ("ref1.png", ref_bytes_1, "image/png")),
            ("references", ("ref2.png", ref_bytes_2, "image/png")),
            ("references", ("ref3.png", ref_bytes_3, "image/png")),
        ],
    )
    assert response.status_code == 200
    _assert_detections(response.json()["detections"], _EXPECTED_ROI)
