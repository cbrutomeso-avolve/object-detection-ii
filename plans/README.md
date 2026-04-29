# Feature Plans

Claude Code saves the approved Plan Mode output here before implementing a
feature or phase.

Plans are committed artifacts. They explain why the implementation exists,
what trade-offs were accepted, and how the branch should be evaluated. This
keeps the reasoning reviewable after the chat scrolls away.

## Naming

Use one file per feature or phase:

- `plans/poc-notebook.md`
- `plans/api.md`
- `plans/ui.md`
- `plans/<feature-name>.md`

The file name should match the branch feature name when possible. For a branch
`feat/poc-notebook`, use `plans/poc-notebook.md`.

## Required Sections

Each plan should include:

- Goal: what user-visible or reviewer-visible outcome this branch delivers.
- Scope: what is included and what is explicitly out of scope.
- Constraints: relevant project rules from `CLAUDE.md`, skills, hooks, or
  external requirements.
- Approach: the intended implementation path and key trade-offs.
- Evaluation / test plan: how the branch will be checked before handoff.
- Risks: known failure modes, uncertainty, and what would trigger a rethink.

For detector work, the evaluation section must mention both accuracy metrics
and latency. Quality metrics have priority; latency is a secondary target.
The CPU-only PoC target is **MAX latency <=10 seconds/page**, but changes made
only for speed must not reduce precision/recall unless the user explicitly
accepts that trade-off.
