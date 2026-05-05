import json
import sys
from pathlib import Path
from typing import Annotated

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).parent.parent / "notebook"))
from detector import Candidate, detect  # noqa: E402

from api.schemas import DetectResponse, Detection

app = FastAPI(title="Object Detection API")

# Params mirror the notebook's final tuned values (see notebook/poc_detector.ipynb).
# Two sets because ROI runs benefit from lower tau / tighter NMS.
_TARGET_SIZES = [9, 10, 11, 12, 13, 14, 15, 17, 19, 21, 24, 27, 31, 35, 40, 46, 53, 61]
_ROTATIONS = (0.0,)
_DOWNSAMPLE_THRESHOLD = 17

_PARAMS_NO_ROI = dict(
    tau=0.78,
    iou_nms=0.2,
    color_max_distance=35.0,
    sat_max_distance=15.0,
    outlier_count_factor=4.0,
    outlier_count_min_threshold=20,
)
_PARAMS_ROI = dict(
    tau=0.685,
    iou_nms=0.1,
    color_max_distance=35.0,
    sat_max_distance=30.0,
    outlier_count_factor=2.5,
    outlier_count_min_threshold=20,
)


def _decode_image(data: bytes, field: str) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail=f"{field}: cannot decode as image")
    return img


def _build_roi_mask(roi_str: str, h: int, w: int) -> np.ndarray:
    try:
        coords = json.loads(roi_str)
        if not (isinstance(coords, list) and len(coords) == 4):
            raise ValueError
        x, y, rw, rh = (int(v) for v in coords)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="roi must be a JSON array [x, y, w, h]")
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask, (x, y), (x + rw, y + rh), 255, thickness=-1)
    return mask


@app.post("/detect", response_model=DetectResponse)
async def detect_endpoint(
    plan: Annotated[UploadFile, File()],
    references: Annotated[list[UploadFile], File()],
    category_name: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
    roi: Annotated[str | None, Form()] = None,
) -> DetectResponse:
    plan_bgr = _decode_image(await plan.read(), "plan")
    refs_bgr = [
        _decode_image(await ref.read(), f"references[{i}]")
        for i, ref in enumerate(references)
    ]

    h, w = plan_bgr.shape[:2]
    use_roi = bool(roi)
    roi_mask = _build_roi_mask(roi, h, w) if use_roi else None
    params = _PARAMS_ROI if use_roi else _PARAMS_NO_ROI

    candidates: list[Candidate] = detect(
        plan_bgr,
        refs_bgr,
        target_sizes_px=_TARGET_SIZES,
        rotations_deg=_ROTATIONS,
        downsample_size_threshold_px=_DOWNSAMPLE_THRESHOLD,
        use_roi_mask=use_roi,
        roi_mask=roi_mask,
        **params,
    )

    detections = [
        Detection(bbox=[float(c.x), float(c.y), float(c.w), float(c.h)], score=c.score)
        for c in candidates
    ]
    return DetectResponse(
        category_id=category_id,
        category_name=category_name,
        detections=detections,
    )
