# Discovery Ranking Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a laptop R&D user transparently tune and reset the five approved discovery-ranking dimensions while keeping every displayed percentage bounded and totaling exactly 100.

**Architecture:** Keep eligibility and scoring inside the existing discovery domain, add a three-operation session controller (`normalized_ranking_weights`, `adjust_ranking_weight`, and `reset_ranking_weights`), and render those operations through the existing Tkinter Discover tab. Ranking choices remain session-only and do not add storage, API, identity, location, billing, or real-user behavior.

**Tech Stack:** Python 3.12/3.13, pytest, Hypothesis, Tkinter, Ruff, mypy, uv, GitHub Actions.

---

### Task 1: Guarantee bounded exact-100 normalization

**Files:**
- Modify: `tests/unit/test_discovery.py`
- Modify: `tests/property/test_domain_properties.py`
- Modify: `src/swipe_dating/domain/discovery.py`

- [x] **Step 1: Write the failing rounding regression test**

Add this behavior test to `tests/unit/test_discovery.py`:

```python
def test_weights_remain_bounded_when_earlier_dimensions_round_up() -> None:
    assert normalize_ranking_weights(
        {"intent": 0, "boundaries": 0, "lifestyle": 10, "alignment": 70, "distance": 0}
    ) == {
        "intent": 0,
        "boundaries": 0,
        "lifestyle": 13,
        "alignment": 87,
        "distance": 0,
    }
```

- [x] **Step 2: Run the regression test and verify RED**

Run: `uv run pytest tests/unit/test_discovery.py::test_weights_remain_bounded_when_earlier_dimensions_round_up -q`

Expected: FAIL because the current independent-rounding algorithm returns alignment `88` and distance `-1`.

- [x] **Step 3: Replace independent rounding with stable largest-remainder allocation**

Replace the rounding body of `normalize_ranking_weights` in `src/swipe_dating/domain/discovery.py` with:

```python
    exact = {key: weights[key] / total * 100 for key in RANKING_DIMENSIONS}
    normalized = {key: math.floor(exact[key]) for key in RANKING_DIMENSIONS}
    remaining = 100 - sum(normalized.values())
    allocation_order = sorted(
        enumerate(RANKING_DIMENSIONS),
        key=lambda item: (
            -(exact[item[1]] - normalized[item[1]]),
            item[0],
        ),
    )
    for _index, key in allocation_order[:remaining]:
        normalized[key] += 1
    return normalized
```

This preserves the pinned integer behavior vector, guarantees every output is between 0 and 100, totals exactly 100, and uses dimension order as the deterministic tie-breaker.

- [x] **Step 4: Run the regression test and verify GREEN**

Run: `uv run pytest tests/unit/test_discovery.py::test_weights_remain_bounded_when_earlier_dimensions_round_up -q`

Expected: PASS.

- [x] **Step 5: Strengthen the existing property invariant**

Extend `test_normalized_weights_always_total_one_hundred` in `tests/property/test_domain_properties.py`:

```python
    normalized = normalize_ranking_weights(values)
    assert sum(normalized.values()) == 100
    assert all(0 <= value <= 100 for value in normalized.values())
```

- [x] **Step 6: Run domain normalization tests**

Run: `uv run pytest tests/unit/test_discovery.py tests/property/test_domain_properties.py -q`

Expected: PASS.

- [x] **Step 7: Commit the bounded normalizer**

```bash
git add src/swipe_dating/domain/discovery.py tests/unit/test_discovery.py tests/property/test_domain_properties.py
git commit -m "Keep discovery weights bounded"
```

### Task 2: Add the minimal session ranking controller

**Files:**
- Modify: `tests/unit/test_session.py`
- Modify: `src/swipe_dating/application/session.py`

- [x] **Step 1: Write the failing re-ranking behavior test**

Add this public-interface test to `tests/unit/test_session.py`:

```python
def test_user_can_reweight_discovery_and_change_the_top_candidate() -> None:
    session, _adapter = create_session()
    for dimension in ("intent", "boundaries", "lifestyle", "distance"):
        session.adjust_ranking_weight(dimension, -1_000)
    session.adjust_ranking_weight("alignment", 1_000)

    assert session.normalized_ranking_weights() == {
        "intent": 0,
        "boundaries": 0,
        "lifestyle": 0,
        "alignment": 100,
        "distance": 0,
    }
    assert session.current_candidate().candidate.id == "p3"  # type: ignore[union-attr]
```

- [x] **Step 2: Run the session test and verify RED**

Run: `uv run pytest tests/unit/test_session.py::test_user_can_reweight_discovery_and_change_the_top_candidate -q`

Expected: FAIL because `adjust_ranking_weight` does not exist.

- [x] **Step 3: Implement adjust and normalized readout**

Import `normalize_ranking_weights` in `src/swipe_dating/application/session.py`, then add:

```python
    def normalized_ranking_weights(self) -> Mapping[str, int]:
        return normalize_ranking_weights(self.ranking_weights)

    def adjust_ranking_weight(self, dimension: str, delta: int) -> Mapping[str, int]:
        current = self.ranking_weights[dimension]
        self.ranking_weights[dimension] = max(0, min(100, current + delta))
        return self.normalized_ranking_weights()
```

- [x] **Step 4: Run the session test and verify GREEN**

Run: `uv run pytest tests/unit/test_session.py::test_user_can_reweight_discovery_and_change_the_top_candidate -q`

Expected: PASS.

- [x] **Step 5: Write the failing unknown-dimension test**

```python
def test_unknown_ranking_dimension_is_rejected() -> None:
    session, _adapter = create_session()
    with pytest.raises(DomainError, match="unknown_ranking_dimension"):
        session.adjust_ranking_weight("attractiveness", 5)
```

- [x] **Step 6: Run the unknown-dimension test and verify RED**

Run: `uv run pytest tests/unit/test_session.py::test_unknown_ranking_dimension_is_rejected -q`

Expected: FAIL with `KeyError`.

- [x] **Step 7: Fail closed with the domain vocabulary**

Update `adjust_ranking_weight`:

```python
        try:
            current = self.ranking_weights[dimension]
        except KeyError as error:
            raise DomainError("unknown_ranking_dimension") from error
```

- [x] **Step 8: Run the unknown-dimension test and verify GREEN**

Run: `uv run pytest tests/unit/test_session.py::test_unknown_ranking_dimension_is_rejected -q`

Expected: PASS.

- [x] **Step 9: Write the failing reset behavior test**

```python
def test_user_can_reset_ranking_weights() -> None:
    session, _adapter = create_session()
    session.adjust_ranking_weight("alignment", 50)

    assert session.reset_ranking_weights() == DEFAULT_RANKING_WEIGHTS
    assert session.ranking_weights == DEFAULT_RANKING_WEIGHTS
```

Import `DEFAULT_RANKING_WEIGHTS` into the test module.

- [x] **Step 10: Run the reset test and verify RED**

Run: `uv run pytest tests/unit/test_session.py::test_user_can_reset_ranking_weights -q`

Expected: FAIL because `reset_ranking_weights` does not exist.

- [x] **Step 11: Implement reset**

```python
    def reset_ranking_weights(self) -> Mapping[str, int]:
        self.ranking_weights = dict(DEFAULT_RANKING_WEIGHTS)
        return self.normalized_ranking_weights()
```

- [x] **Step 12: Run the session unit tests**

Run: `uv run pytest tests/unit/test_session.py -q`

Expected: PASS.

### Task 3: Expose the controls in the laptop Discover tab

**Files:**
- Modify: `src/swipe_dating/desktop/app.py`
- Modify: `docs/PARITY_MATRIX.md`
- Modify: `docs/specs/current-objective.md`

- [x] **Step 1: Import the approved dimension order**

Add `RANKING_DIMENSIONS` to the existing discovery imports in `src/swipe_dating/desktop/app.py`.

- [x] **Step 2: Render one compact algorithm card**

In `_render_discover`, between intent/boundary settings and proximity simulation, add:

```python
        algorithm = self._card("Choose your algorithm")
        self._text(
            algorithm,
            "Tune only intent, boundaries, lifestyle, alignment, and distance. Values are normalized to 100% for this session; protected traits, purchases, and popularity are excluded.",
            color=MUTED,
            wrap=940,
        ).pack(anchor="w", pady=(0, 8))
        normalized_weights = self.session.normalized_ranking_weights()
        for dimension in RANKING_DIMENSIONS:
            row = tk.Frame(algorithm, bg=PANEL, padx=12, pady=8)
            row.pack(fill="x", pady=3)
            self._text(
                row,
                self._label(dimension),
                bg=PANEL,
                weight="bold",
            ).pack(side="left")
            self._button(
                row,
                "+5",
                lambda key=dimension: self._adjust_ranking_weight(key, 5),
            ).pack(side="right")
            self._text(
                row,
                f"{normalized_weights[dimension]}%",
                bg=PANEL,
                color=MINT,
                weight="bold",
            ).pack(side="right", padx=10)
            self._button(
                row,
                "−5",
                lambda key=dimension: self._adjust_ranking_weight(key, -5),
            ).pack(side="right")
        self._button(algorithm, "Reset weights", self._reset_ranking_weights).pack(
            anchor="w", pady=(8, 0)
        )
```

- [x] **Step 3: Add thin callbacks**

Add these methods beside the other discovery callbacks:

```python
    def _adjust_ranking_weight(self, dimension: str, delta: int) -> None:
        self.session.adjust_ranking_weight(dimension, delta)
        self._render_active_tab()

    def _reset_ranking_weights(self) -> None:
        self.session.reset_ranking_weights()
        self._render_active_tab()
```

- [x] **Step 4: Document the bounded interactive parity**

In `docs/PARITY_MATRIX.md`, replace the discovery status with:

```markdown
| `rnd-discovery` | `domain/discovery.py` | Verified, including bounded interactive ranking controls |
```

In `docs/specs/current-objective.md`, replace the single plan line with:

```markdown
**Rebuild plan:** [2026-07-22-python-rnd-rebuild.md](../superpowers/plans/2026-07-22-python-rnd-rebuild.md)

**Current loop:** [2026-07-22-discovery-ranking-controls.md](../superpowers/plans/2026-07-22-discovery-ranking-controls.md)
```

Keep the existing production blockers unchanged.

- [x] **Step 5: Format and run the focused checks**

Run:

```bash
uv run ruff format src/swipe_dating/domain/discovery.py src/swipe_dating/application/session.py src/swipe_dating/desktop/app.py tests/unit/test_discovery.py tests/property/test_domain_properties.py tests/unit/test_session.py
uv run pytest tests/unit/test_discovery.py tests/property/test_domain_properties.py tests/unit/test_session.py tests/smoke/test_desktop_import.py -q
uv run ruff check src/swipe_dating/domain/discovery.py src/swipe_dating/application/session.py src/swipe_dating/desktop/app.py tests/unit/test_discovery.py tests/property/test_domain_properties.py tests/unit/test_session.py
uv run mypy src
```

Expected: all commands exit 0.

- [x] **Step 6: Commit the complete control slice**

```bash
git add src/swipe_dating/application/session.py src/swipe_dating/desktop/app.py tests/unit/test_session.py docs/PARITY_MATRIX.md docs/specs/current-objective.md docs/superpowers/plans/2026-07-22-discovery-ranking-controls.md
git commit -m "Add user-controlled discovery weights"
```

### Task 4: Verify and deploy the slice to the draft PR

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run the full verification gate sequentially**

Run:

```bash
uv run python -m compileall -q src tests
uv run pytest --cov=swipe_dating --cov-branch --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run swipe-governance
uv run swipe-simulate
uv pip check
git diff --check HEAD~2
git status --short --branch
```

Expected: every command exits 0, the simulator remains labeled synthetic-only, and the branch contains only the two intended commits.

- [ ] **Step 2: Push the current feature branch**

Run: `git push -u origin agent/python-rnd-rebuild`

Expected: the existing draft pull request updates without changing `main`.

- [ ] **Step 3: Wait for GitHub Actions**

Run: `gh pr checks 1 --watch --interval 10`

Expected: Python 3.12 and Python 3.13 verification jobs both pass.

- [ ] **Step 4: Record the loop result**

Report the feature behavior, test count, full verification evidence, commit hashes, branch, and draft PR URL. Leave the broader continuing-development goal active for the next narrow loop.
