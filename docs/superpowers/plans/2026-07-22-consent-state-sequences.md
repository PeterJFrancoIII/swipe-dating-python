# Consent State Sequence Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use systematic debugging for every minimized counterexample.

**Goal:** Exercise conversation and Deepen Connection consent invariants across randomized action sequences without expanding the app or changing production authorization.

**Architecture:** Add one property-test module that drives the existing immutable domain state machines through valid and invalid sequences. Check invariants after every action, including reciprocity, opening context, message sequencing, block purge, suppression, bilateral deepening, answer gating, reversibility, termination, and match scoping. Change production code only if Hypothesis finds a reproducible domain defect.

**Tech Stack:** Python 3.12/3.13, pytest, Hypothesis, Ruff, mypy, uv, GitHub Actions.

---

### Task 1: Randomize conversation sequences

**Files:**
- Create: `tests/property/test_consent_state_sequences.py`

- [x] **Step 1: Define a bounded action strategy**

Generate lists of up to 40 actions from:

- pass;
- unilateral interest;
- reciprocal interest;
- undo;
- local message;
- synthetic candidate reply;
- meetup proposal;
- unmatch;
- block.

Every new decision uses a fresh synthetic candidate ID. All timestamps are deterministic integers derived from the step number.

- [x] **Step 2: Drive the public conversation API**

Use only public transition functions. When no applicable match exists, leave the state unchanged. For meetup attempts before both sides have messaged, assert `meetup_requires_two_way_conversation` instead of swallowing the failure.

- [x] **Step 3: Check invariants after every action**

Assert:

- a match always has a reciprocal, match-creating decision;
- decision and visible message IDs are unique;
- every visible message sequence is below the state's next sequence;
- the first local message carries the original starter tag and later local messages do not;
- block purges messages and starter context, marks content purged, and suppresses the candidate;
- every current decision, match, and blocked candidate appears in suppression;
- an ended match cannot accept another direct message.

- [x] **Step 4: Run the conversation property test**

Run: `uv run pytest tests/property/test_consent_state_sequences.py -k conversation -q`

Expected: PASS, or a minimized action list that is investigated before any fix.

### Task 2: Randomize Deepen Connection sequences

**Files:**
- Modify: `tests/property/test_consent_state_sequences.py`

- [x] **Step 1: Define phase actions**

Generate lists of up to 50 actions from:

- local or candidate request/accept;
- local or candidate decline;
- local or candidate withdrawal;
- local or candidate return to casual;
- answer or clear a deeper prompt;
- terminate for unmatch or block;
- start operations on a fresh synthetic match ID.

- [x] **Step 2: Apply active and fail-closed transitions**

Assert the documented error for operations attempted after termination, for prompt answers while casual, and for request withdrawal while already deepened.

- [x] **Step 3: Check invariants across every touched match**

Assert:

- deepened always means both participants opted in;
- prompt answers exist only while deepened;
- casual never retains deeper answers;
- return, decline, unmatch, and block clear request/answer state as specified;
- ended state records an allowed reason, has no requests or answers, and exposes no deeper prompts;
- each match ID evolves independently.

- [x] **Step 4: Run the phase property test**

Run: `uv run pytest tests/property/test_consent_state_sequences.py -k relationship -q`

Expected: PASS, or a minimized counterexample that is investigated systematically.

### Task 3: Verify and deploy Loop 4

**Files:**
- Modify: `docs/specs/current-objective.md`
- Verify: entire repository

- [x] **Step 1: Point the current objective to this hardening loop**

Do not alter the product scope, persistence allowlist, API surface, or release state.

- [x] **Step 2: Run the focused test and static gate**

```bash
uv run pytest tests/property/test_consent_state_sequences.py -q
uv run ruff check tests/property/test_consent_state_sequences.py
uv run ruff format --check tests/property/test_consent_state_sequences.py
```

- [x] **Step 3: Run the complete release gate**

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

- [x] **Step 4: Commit, push, and wait for both GitHub lanes**

```bash
git add docs/specs/current-objective.md docs/superpowers/plans/2026-07-22-consent-state-sequences.md tests/property/test_consent_state_sequences.py
git commit -m "Harden consent state sequences"
git push
gh pr checks 1 --watch --interval 10
```

Refresh the draft PR with the exact test count, measured coverage, and the fact that this loop adds test depth without product or storage expansion.
