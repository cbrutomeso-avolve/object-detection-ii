# Plan: Phase 3 — Next.js 14 UI for Object Detection PoC

## Context
Phases 1 (OpenCV detector) and 2 (FastAPI `/detect` endpoint) are complete and merged to `main`.
Phase 3 builds the interactive UI so users can upload a plan, define reference crops by dragging
on the image, optionally draw an ROI, select a feature class, and see detection bounding boxes
overlaid on the plan — all without touching the API directly.

## Scope
- UI lives in `ui/` (Next.js 14 + TypeScript + Tailwind, App Router)
- API extended with `GET /categories` (reads COCO annotations) + CORS for localhost:3000
- Single page: upload → drag crops → optional ROI → detect → view bboxes
- Playwright E2E test verifies the happy path end-to-end

## Approach

### API additions (`api/main.py`, `api/schemas.py`)
- `CORSMiddleware` allowing `http://localhost:3000`
- `GET /categories` reads `dataset/annotations/annotations.json`, returns `[{id, name}]`
- Adding a new class = append to COCO file, no code changes

### UI architecture
- `lib/api.ts` — typed API client (`fetchCategories`, `runDetect`)
- `lib/extractCrop.ts` — canvas-based crop blob extraction
- `hooks/useCanvasInteraction.ts` — mouse drag handler with scale correction
- Components: `PlanUploader`, `PlanCanvas`, `BboxOverlay`, `CategorySelector`, `DrawModeToggle`, `CropList`
- `app/page.tsx` — root page, all shared state

### Canvas interactions
Two drag modes (toggle buttons):
- **Crop** (default): drag selects a region → extracted as PNG blob → appended to references list
- **ROI**: drag sets a single bounding rect → sent as `roi=[x,y,w,h]` to API

Scale correction: canvas events are in CSS pixels; multiply by
`naturalWidth/clientWidth` before using as image-pixel values.

### Bbox overlay
Detections rendered as `<div data-testid="bbox">` with percentage CSS positioning
(not drawn on canvas) so Playwright can count them.

## Verification
1. `pytest tests/` — all tests pass including `test_categories.py`
2. `npm run build` inside `ui/` — no TypeScript errors
3. `npx playwright test` — `detect.spec.ts` passes (bbox count > 0)
