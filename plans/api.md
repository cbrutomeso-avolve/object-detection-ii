# Plan: Expose Sprinkler Detector as a FastAPI Endpoint

## Context

The PoC detector (`notebook/detector.py`) runs offline on CPU and returns a list of `Candidate` dataclasses. It has no HTTP interface. This phase wraps it in a FastAPI service so external clients can POST a plan image plus reference crops and get back detections in the COCO results schema. The notebook is a frozen artifact — only imported, never modified.

---

## Todo List

### 0. Branch setup
- [ ] Create branch `feat/api` from `main`

---

### 1. Install new dependencies
- [ ] Add to `requirements.txt` and install in `.venv`:
  - `fastapi==0.115.12`
  - `uvicorn==0.34.2`
  - `python-multipart==0.0.20` (required by FastAPI for file/form uploads)
  - `httpx==0.28.1` (drives `starlette.testclient.TestClient`)

---

### 2. Pydantic schemas — `api/schemas.py`

Create two models:

```
Detection
  bbox: list[float]   # [x, y, w, h] — matches COCO results bbox field exactly
  score: float        # confidence in [0, 1]

DetectResponse
  category_id:   int
  category_name: str
  detections:    list[Detection]
```

No `image_id` in `Detection` — the plan is uploaded per-request, no persistent ID exists. The bbox + score fields mirror the COCO prediction schema exactly; the envelope adds the category context required for a multi-class API.

---

### 3. FastAPI app — `api/main.py`

#### Endpoint: `POST /detect`

**Multipart form fields:**

| Field           | Type                | Required | Notes                                          |
|-----------------|---------------------|----------|------------------------------------------------|
| `plan`          | `UploadFile`        | yes      | PNG/JPG plan image                            |
| `references`    | `list[UploadFile]`  | yes      | One or more reference crop images             |
| `category_name` | `str` (Form)        | yes      | E.g. `"sprinkler"` — never hardcoded          |
| `category_id`   | `int` (Form)        | yes      | Matches the COCO category id                  |
| `roi`           | `str` (Form)        | no       | JSON-encoded `[x, y, w, h]` bounding box      |

**Processing steps:**
1. Decode `plan` bytes → numpy BGR array via `cv2.imdecode`
2. Decode each `references[i]` bytes → numpy BGR array; collect into `list[np.ndarray]`
3. If `roi` is provided: parse JSON `[x, y, w, h]` → build a binary mask (black image, white filled rect), set `use_roi_mask=True`
4. Import and call `notebook.detector.detect()` with hardcoded defaults matching the notebook's best run:
   - `target_sizes_px = [9, 15, 25, 40, 57]`
   - `tau = 0.5`
   - `iou_nms = 0.3`
   - `rotations_deg = (0.0,)`
5. Convert each `Candidate(x, y, w, h, score)` → `Detection(bbox=[x,y,w,h], score=score)`
6. Return `DetectResponse(category_id=..., category_name=..., detections=[...])`

**Error handling at system boundaries only:**
- `400` if any upload cannot be decoded as an image
- `422` (automatic from FastAPI) for missing or malformed form fields
- `400` if `roi` JSON is not a list of 4 numbers

---

### 4. Three pytests — `tests/test_api.py`

All three use `starlette.testclient.TestClient` (synchronous, no running server needed). They test the **HTTP contract only** — response status, JSON shape, field types/ranges — not detection quality.

**Shared fixtures (in `tests/conftest.py`):**

```
plan_path_1    → dataset/images/raw/001_Fire_Sprinkler_Plan_page_001.png
ref_1a         → dataset/images/sprinklers/001_Fire_Sprinkler_Plan_page_001/sprinkler_1.png
ref_1b         → dataset/images/sprinklers/001_Fire_Sprinkler_Plan_page_001/sprinkler_2.png
ref_1c         → dataset/images/sprinklers/001_Fire_Sprinkler_Plan_page_001/sprinkler_3.png
```

**Test 1 — single reference:**
- POST plan + `sprinkler_1.png`, `category_name="sprinkler"`, `category_id=0`, no ROI
- Assert: 200, response is `DetectResponse`, `category_id == 0`, `category_name == "sprinkler"`, `detections` is a list, each detection has `bbox` (4 floats) and `score` in [0, 1]

**Test 2 — multi-reference (two or more):**
- POST plan + `[sprinkler_1.png, sprinkler_2.png, sprinkler_3.png]`, `category_name="sprinkler"`, `category_id=0`, no ROI
- Same schema assertions as Test 1; additionally assert `len(detections) >= 0` (schema, not quality)

**Test 3 — ROI:**
- POST plan + `sprinkler_1.png`, `category_name="sprinkler"`, `category_id=0`, `roi=[0, 0, 500, 500]`
- Assert: 200, valid `DetectResponse` shape, every detection's `bbox[0] >= 0` and `bbox[1] >= 0` (detections are within the image)

---

### 5. Save the plan
- [ ] Write this plan to `plans/api.md` on the `feat/api` branch

---

## Critical files

| Path | Role |
|------|------|
| `notebook/detector.py` | Frozen detector — import only, never edit |
| `api/main.py` | FastAPI app + endpoint (to create) |
| `api/schemas.py` | Pydantic v2 schemas (to create) |
| `tests/test_api.py` | 3 HTTP contract tests (to create) |
| `tests/conftest.py` | Shared fixtures (to create) |
| `requirements.txt` | Add 4 new dependencies |
| `dataset/images/raw/001_Fire_Sprinkler_Plan_page_001.png` | Test fixture — plan |
| `dataset/images/sprinklers/001_Fire_Sprinkler_Plan_page_001/sprinkler_1.png` | Test fixture — ref crop |

---

## Verification

```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# Smoke-test the endpoint manually
uvicorn api.main:app --reload
# In another shell: POST with curl or httpx REPL

# Run the 3 new tests
pytest tests/test_api.py -v

# Full suite — no regressions
pytest tests/ -v
```
