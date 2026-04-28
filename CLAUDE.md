# Project: Object Detection PoC

## Goal
Given an image and ONE OR MORE reference crops of a feature,
detect ALL instances of that feature in the plan. The same conceptual
feature may have multiple visual formats.

## Scope (current and future)
- Phase 1 (now): sprinkler only.
- Future: additional feature classes (fire alarm, smoke detector, etc.). The codebase, schemas, API, and UI MUST be built multi-class from day one. Adding a new class should be a data-only change: add the category to the COCO file + provide reference crops. No code changes.

## Object variability the detector MUST tolerate
- Arbitrary rotation
- Partial occlusion (something on top of the object)
- Smudges, stains, or partial overprinting
- Different colors than the reference
- Different scales but same shape
- Multiple visual formats per feature class

## Hard constraints
- Open-source only. No paid APIs. No API keys. Must run offline.
- No model training. PoC scope.

## Stack (locked)
- Python 3.11
- FastAPI + Pydantic v2 + uvicorn for the API
- Next.js 14 + Tailwind for the UI
- Jupyter for the notebook
- Detector library: TBD during the Explore step of each phase, must
  satisfy the hard constraints. OpenCV is a strong candidate.

## Dataset

Layout:
- `dataset/annotations/annotations.json` — ground truth in COCO format
  (images, annotations, categories).
- `dataset/images/raw/` — original plan images. This is the
  **images_dir**: the folder against which COCO `file_name` is resolved.
  In the JSON, `file_name` is always the basename (e.g.
  `001_Fire_Sprinkler_Plan_page_001.png`), never a path. Code that
  loads an image MUST prepend `dataset/images/raw/`.
- `dataset/images/sprinklers/<image_basename>/` — per-plan sprinkler
  crops. One subfolder per image in `raw/`, named after the basename
  without extension. Use it for inspecting matches, curating the
  reference set, or any per-plan label-store work. Each subfolder
  ships with a `.gitkeep` so the structure survives a fresh clone.

Conventions:
- `image_id` in annotations references `images[].id` in the same COCO
  file. Bounding boxes are `[x, y, w, h]` in pixels (COCO convention).
- Phase 1 ships with one category: `sprinkler` (id=0). Adding a class
  later = append to `categories` and `annotations`. Nothing else —
  no path renames, no schema changes, no code changes.

## Environment
- Always work inside a project venv at `./.venv`. Cross-platform (Windows, Linux, macOS).
- Python binary: use `python` on Windows, `python3` on Linux/macOS. If `python3.11`
  is available, prefer it explicitly to lock the version.
- If `.venv` does not exist, create it and install from `requirements.txt`:
  - Windows (PowerShell):
    `python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt`
  - Windows (cmd):
    `python -m venv .venv && .venv\Scripts\activate.bat && pip install -r requirements.txt`
  - Linux / macOS (bash/zsh):
    `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- After activation, always invoke tools via the venv (`python`, `pip`, `uvicorn`,
  `pytest`, `ruff`, `black`) — never the system Python.
- New dependency? Append it to `requirements.txt` with a pinned version
  AND install it. Never `pip install` without updating the file.
- Use forward slashes in repo paths (`dataset/images/...`). They work on all
  three OSes from Python and from modern shells (PowerShell, bash, zsh).
- Line endings: enforced repo-wide via `.gitattributes`. All text files are
  LF in the working copy AND the repo, regardless of each contributor's
  local `core.autocrlf` setting. Binaries (PNG / JPG / PDF / etc.) are
  marked explicitly so git never tries to "fix" their line endings.

## Workflow rules
- ONE branch per phase. Never code on main.
  Branch naming: `feat/<phase>` (e.g. `feat/poc-notebook`, `feat/api`,
  `feat/ui`).
- The FIRST action of every phase is to create the branch from main:
  - bash / zsh / PowerShell 7+:
    `git checkout main && git pull && git checkout -b feat/<phase>`
  - PowerShell 5.1 (default on Windows 10/11):
    `git checkout main; git pull; git checkout -b feat/<phase>`
- Every phase starts in Plan Mode (Explore) before any code is written.
  The plan does not need its own branch.
- Each branch ends with a code-reviewer subagent pass (local quality
  review, see `.claude/agents/code-reviewer.md`) before the user
  decides to merge.

## Conventions
- Type hints everywhere. ruff + black. pytest.
- Predictions follow the COCO results schema documented in the
  poc-runner skill.
- NEVER hardcode "sprinkler" in detection logic. The category is
  data-driven: read from the COCO file or from the API request.
  This is what makes future classes a data-only change.

## Avoid
- Reading raw PDFs in tools — convert to PNG first.
- Storing user-uploaded plans on disk past the request lifecycle.
- Running scripts outside the venv.