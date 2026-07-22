# Visible Boundary Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development to implement this plan task-by-task.

**Goal:** Show candidate-declared public boundary tags during bio-first discovery and let the user choose one as shared-ground context without disclosing private required filters.

**Architecture:** Centralize public starter-tag construction in `ResearchSession`, combining a candidate's lifestyle tags and public `boundaries` tuple in stable order. Reuse that method for validation and UI rendering. Never include `required_boundaries`, add persistence, infer health status, or claim verification.

**Tech Stack:** Python 3.12/3.13, pytest, Tkinter, Ruff, mypy, uv, GitHub Actions.

---

### Task 1: Pin the public/private starter boundary

**Files:**
- Modify: `tests/unit/test_session.py`
- Modify: `src/swipe_dating/application/session.py`

- [x] **Step 1: Write the failing public-tag test**

Construct a synthetic candidate whose lifestyle and public-boundary tuples overlap, and whose private `required_boundaries` contains a separate marker. Assert:

```python
assert session.visible_starter_tags("p-visible") == (
    "public_first_meet",
    "coffee",
    "condoms_required",
)
assert "private_required_filter" not in session.visible_starter_tags("p-visible")
```

The list must be stable and deduplicated.

- [x] **Step 2: Run the test and verify RED**

Run: `uv run pytest tests/unit/test_session.py::test_visible_starter_tags_include_public_boundaries_not_private_filters -q`

Expected: FAIL with `AttributeError` because the canonical method does not exist.

- [x] **Step 3: Implement `visible_starter_tags`**

Return the ordered unique combination of:

1. `candidate.lifestyle_tags`;
2. `candidate.boundaries`.

Do not read or return `candidate.required_boundaries`.

- [x] **Step 4: Reuse the method in interest validation**

Replace the inline set construction in `express_interest` with the canonical method. Preserve `shared_ground_not_visible` for every other value.

- [x] **Step 5: Add behavior tests for boundary starter and private filter rejection**

Verify a public candidate boundary can become the starter tag of a synthetic reciprocal match, while the private required-filter marker remains rejected.

- [x] **Step 6: Run the session tests and verify GREEN**

Run: `uv run pytest tests/unit/test_session.py -q`

Expected: PASS.

### Task 2: Render public self-reported boundaries

**Files:**
- Modify: `tests/smoke/test_desktop_import.py`
- Modify: `src/swipe_dating/desktop/app.py`

- [x] **Step 1: Add a failing desktop-helper smoke assertion**

Assert `SwipeDatingDesktop._render_candidate_boundaries` is callable.

- [x] **Step 2: Run the smoke test and verify RED**

Run: `uv run pytest tests/smoke/test_desktop_import.py -q`

Expected: FAIL because the renderer is absent.

- [x] **Step 3: Render candidate-declared boundaries**

Add a compact panel to the candidate card that:

- labels the data synthetic and self-reported;
- lists only `candidate.boundaries`;
- says it is not verified and should be discussed before relying on it;
- says private required filters remain hidden.

- [x] **Step 4: Use the canonical starter-tag list**

Populate the starter radio buttons from `session.visible_starter_tags(candidate.id)` so public boundary tags and lifestyle tags are both selectable.

- [x] **Step 5: Run the focused tests and static checks**

```bash
uv run pytest tests/unit/test_session.py tests/smoke/test_desktop_import.py -q
uv run ruff check src/swipe_dating/application/session.py src/swipe_dating/desktop/app.py tests/unit/test_session.py tests/smoke/test_desktop_import.py
uv run ruff format --check src/swipe_dating/application/session.py src/swipe_dating/desktop/app.py tests/unit/test_session.py tests/smoke/test_desktop_import.py
```

### Task 3: Document, verify, and deploy Loop 5

**Files:**
- Modify: `docs/PARITY_MATRIX.md`
- Modify: `docs/specs/current-objective.md`
- Modify: `docs/superpowers/plans/2026-07-22-consent-state-sequences.md`
- Verify: entire repository

- [x] **Step 1: Document the visible/public distinction**

Point the current objective to this plan, update the discovery parity note, and include the completed Loop 4 checklist marker already present locally.

- [x] **Step 2: Run the complete release gate**

```bash
uv run python -m compileall -q src tests
uv run pytest --cov=swipe_dating --cov-branch --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run swipe-governance
uv run swipe-simulate
uv pip check
git diff --check
```

- [x] **Step 3: Commit and push the slice**

Stage only the two plan files, objective/parity documentation, session/UI changes, and their tests. Commit as `Expose public boundary starter tags`, then push the existing branch.

- [x] **Step 4: Wait for CI and refresh the draft PR**

Wait for Python 3.12 and 3.13 to pass. Refresh the PR with the exact test count, measured coverage, public/private distinction, and unchanged synthetic-only release boundary.
