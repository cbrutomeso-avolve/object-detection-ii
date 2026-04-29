# Object Detection PoC — A Claude Code Best-Practices Walkthrough

This repository is **a teaching artifact**.

It uses a real but small computer-vision problem — *find every sprinkler in a fire sprinkler plan* — as the vehicle to demonstrate how to ship a project end-to-end with Claude Code without the agent going off the rails.

---

## What this repo demonstrates

| Practice | Where to look |
|---|---|
| `CLAUDE.md` as the **living spec** the agent reads at the start of every session | [`CLAUDE.md`](./CLAUDE.md) |
| Domain-specific **skills** instead of dumping rules into a system prompt | [`.claude/skills/object-detection-eval/SKILL.md`](./.claude/skills/object-detection-eval/SKILL.md) |
| **Subagents** for fresh-eyes review uncontaminated by the writing context | [`.claude/agents/code-reviewer.md`](./.claude/agents/code-reviewer.md) |
| **Hooks** that block destructive shell commands and reads on sensitive paths | [`.claude/hooks/`](./.claude/hooks/) + [`.claude/settings.example.json`](./.claude/settings.example.json) |
| **Bootstrap script** so per-machine paths never pollute the repo | [`scripts/init-claude.js`](./scripts/init-claude.js) |
| **Phase-based branching** with Plan Mode → Code Mode discipline | [`CLAUDE.md`](./CLAUDE.md) → "Workflow rules" |
| **Saved feature plans** so the reasoning that led to implementation is reviewable | [`plans/`](./plans/) |
| **Cross-platform** setup (Windows + Linux + macOS) baked in from day one | [`CLAUDE.md`](./CLAUDE.md) → "Environment" |
| **Reproducible accuracy + latency metrics** separated from subjective AI commentary | [`SKILL.md`](./.claude/skills/object-detection-eval/SKILL.md) → "Output format" + "Miss analysis" |
| **Multi-class from day one** — adding a new feature class is a data-only change | [`CLAUDE.md`](./CLAUDE.md) → "Scope" + "Conventions" |

---

## The PoC itself (for context)

Phase 1 tackles **sprinkler detection** in fire sprinkler plans, given:

- A plan image (PNG)
- One or more reference crops of a sprinkler

The detector should find every sprinkler in the plan, tolerating arbitrary rotation, partial occlusion, smudges, color/scale variation, and multiple visual formats per class.

Hard constraints: **open-source only, runs offline, no model training, no paid APIs**.

Full spec lives in [`CLAUDE.md`](./CLAUDE.md).

---

## Quick start

### 1. Prerequisites (OS-level)

| Tool | Version | Used for |
|---|---|---|
| Python | 3.11.x | API + notebook |
| Node.js | 20 LTS | UI + Claude Code bootstrap |
| Git | any modern | source control |

Install:

- **Windows** (PowerShell, [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/)):
  ```powershell
  winget install --id Python.Python.3.11 -e
  winget install --id OpenJS.NodeJS.LTS -e
  winget install --id Git.Git -e
  ```
- **macOS** ([Homebrew](https://brew.sh/)):
  ```bash
  brew install python@3.11 node@20 git
  ```
- **Linux** (Debian / Ubuntu):
  ```bash
  sudo apt update
  sudo apt install -y python3.11 python3.11-venv git
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt install -y nodejs
  ```

Verify with `python --version` (or `python3 --version`), `node --version`, `git --version`.

### 2. Clone and bootstrap Claude Code

```bash
git clone <this-repo> object-detection-ii
cd object-detection-ii
node scripts/init-claude.js
```

That generates `.claude/settings.local.json` from `.claude/settings.example.json`, replacing `$PWD` with the absolute path of `.claude/` on **your** machine. It is per-machine, gitignored, and idempotent — re-run any time the example changes.

### 3. Open in Claude Code and start Phase 1

Your setup ends here. **From this point, Claude Code does the work.**

When you tell the agent to start Phase 1 (e.g. *"start the poc-notebook phase"*), it will, per the rules in [`CLAUDE.md`](./CLAUDE.md) → "Workflow rules" and "Environment":

1. Create the `feat/poc-notebook` branch from `main`.
2. Enter Plan Mode (Explore) and propose an approach before writing code.
3. Create `.venv/`, write `requirements.txt` with pinned versions, install dependencies.
4. Save the approved plan to `plans/poc-notebook.md`.
5. Scaffold the notebook in `notebook/`.
6. Evaluate accuracy and latency, targeting **MAX latency <=10s/page** for the CPU-only OpenCV PoC.
7. End the branch with a `code-reviewer` subagent pass before you decide on merge.

You do **not** run `python -m venv` by hand. That is exactly the point of this repo — the agent reads the spec and executes against it.

#### Optional: activating the venv in your own shell

If you want to poke around outside Claude Code (run a Jupyter cell ad-hoc, debug a script), activate the venv that the agent created:

- **Windows (PowerShell)**: `.\.venv\Scripts\Activate.ps1`
- **Windows (cmd)**: `.venv\Scripts\activate.bat`
- **macOS / Linux**: `source .venv/bin/activate`

---

## Repository layout

```
.
├── README.md                       # you are here
├── CLAUDE.md                       # the spec the agent reads first, every session
├── .gitignore
├── .claude/
│   ├── settings.example.json       # committed, $PWD placeholders
│   ├── settings.local.json         # generated, per-machine (gitignored)
│   ├── hooks/                      # PreToolUse guards (Node scripts)
│   │   ├── block-destruction.js
│   │   └── block-sensitive-read.js
│   ├── skills/                     # domain knowledge the agent loads on demand
│   │   └── object-detection-eval/
│   │       └── SKILL.md
│   └── agents/                     # subagent personas
│       └── code-reviewer.md
├── scripts/
│   └── init-claude.js              # bootstrap settings.local.json from example
├── plans/                          # saved Claude Code plans, one per feature/phase
├── dataset/
│   ├── annotations/
│   │   └── annotations.json        # COCO ground truth
│   ├── images/
│   │   ├── raw/                    # plan PNGs (the images_dir for COCO)
│   │   └── sprinklers/             # per-plan crop store, one folder per image
│   └── pdfs/                       # source PDFs (gitignored)
│       └── convert_pdfs_to_png.py  # PDF→PNG converter (tracked)
├── notebook/                       # Jupyter exploration  (Phase 1)
├── api/                            # FastAPI service       (Phase 2)
├── ui/                             # Next.js + Tailwind    (Phase 3)
├── outputs/                        # detector predictions, keyed by run_id
└── metrics/                        # accuracy + latency results, keyed by run_id
```

---

## Suggested reading order if you are studying this

1. [`CLAUDE.md`](./CLAUDE.md) — the project contract. Notice how it is opinionated, decisive, and short.
2. [`plans/`](./plans/) — how Plan Mode becomes a committed artifact instead of disappearing into chat history.
3. [`.claude/skills/object-detection-eval/SKILL.md`](./.claude/skills/object-detection-eval/SKILL.md) — how a domain skill is shaped: triggers, schema, decision rules, latency targets, and separation of mechanical vs interpretive output.
4. [`.claude/agents/code-reviewer.md`](./.claude/agents/code-reviewer.md) — how a subagent persona is shaped: scope, output format, review focus.
5. [`.claude/settings.example.json`](./.claude/settings.example.json) + [`.claude/hooks/`](./.claude/hooks/) — how guardrails are wired without trusting the agent.
6. [`scripts/init-claude.js`](./scripts/init-claude.js) — how per-machine scaffolding is generated without polluting the repo with absolute paths.

---

## What this repo deliberately is NOT

- **Not a production service.** The detector is PoC-grade by design.
- **Not a model-training project.** No fine-tuning, no GPU, no datasets-at-scale.
- **Not a paid-AI showcase.** Open-source only, offline-only, no API keys.
- **Not Cursor-specific.** The `.claude/` scaffold works in Claude Code CLI, IDE plugins, or any host that respects the convention.

---

## Contributing / extending the PoC

Adding a new feature class (e.g. fire alarm, smoke detector) should be a **data-only** change:

1. Append a new `category` to `dataset/annotations/annotations.json`.
2. Append the corresponding `annotations` entries.
3. Provide one or more reference crops.

That is it. **No code changes** in the detector, the API, or the UI. If you find yourself editing code to add a class, that is a bug — please open an issue describing where the assumption leaked in.

See [`CLAUDE.md`](./CLAUDE.md) → "Scope" and "Conventions" for the full rule.
