I want to expose the sprinkler detector as an API. The service receives a fire sprinkler plan image and one or more reference crops for a single class, and returns the detections.

The detector logic already lives in notebook/detector.py. The notebook is a frozen PoC artifact — do not modify it or its imports.

The request must cleanly express "one feature class, many references" — the class is a parameter, not hardcoded. It must also accept an optional ROI to restrict the search to a region of the plan. The response must follow the same prediction schema we already use to evaluate against the COCO ground truth.

Mirror the notebook's tuned `PARAMS` / `PARAMS_ROI` dicts exactly — do not invent defaults. Note that the params differ between the ROI and no-ROI cases, and that `downsample_size_threshold_px` is critical for latency. The ROI field is a JSON `[x, y, w, h]`; the detector filters by candidate center, not bbox boundary.

Add 2 pytests that exercise the API endpoint itself (not the detector logic), end-to-end: (1) multi-reference with no ROI, (2) multi-reference with the dataset ROI for `image_id=0`. For both, load the expected detections directly from `outputs/predictions_2026-05-04_1246_final_{no_roi,roi}.json` filtering for `image_id=0`, and assert exact bbox + near-exact score match against the API response. The ROI `[x, y, w, h]` for image_id=0 lives in `dataset/rois/001_Fire_Sprinkler_Plan_page_001.json`. The pytest is about the HTTP contract — valid response shape, deterministic output, and ROI geometry; detector quality is already evaluated in the notebook.

Output the plan as a todo list, no code yet.
