"""Bilateral, reversible, match-scoped Deepen Connection state machine."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from swipe_dating.domain.errors import DomainError
from swipe_dating.domain.models import (
    TransitionResult,
    ValueResult,
    frozen_mapping,
    frozen_outcome,
    iso_from_ms,
)


class RelationshipPhase(StrEnum):
    CASUAL = "casual"
    DEEPENED = "deepened"
    ENDED = "ended"


class TransitionOutcome(StrEnum):
    NONE = "none"
    REQUESTED = "requested"
    DEEPENED = "deepened"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    RETURNED_TO_CASUAL = "returned_to_casual"
    ENDED = "ended"


@dataclass(frozen=True, slots=True)
class DeepenPrompt:
    id: str
    category: str
    prompt: str


DEEPEN_PROMPTS: Final = (
    DeepenPrompt(
        "communication_style",
        "communication",
        "What helps you feel heard during a difficult conversation?",
    ),
    DeepenPrompt(
        "relationship_direction",
        "relationship_goals",
        "What kind of connection would you be open to exploring over time?",
    ),
    DeepenPrompt(
        "time_and_energy",
        "availability",
        "What amount of time and communication feels sustainable for you?",
    ),
    DeepenPrompt(
        "values_in_practice",
        "values",
        "Which values matter most in how a relationship is treated day to day?",
    ),
    DeepenPrompt(
        "future_boundaries",
        "boundaries",
        "Which boundaries would need to stay clear if this connection became more serious?",
    ),
)

PROMPT_IDS: Final = frozenset(prompt.id for prompt in DEEPEN_PROMPTS)


@dataclass(frozen=True, slots=True)
class MatchPhase:
    match_id: str
    phase: RelationshipPhase = RelationshipPhase.CASUAL
    local_requested: bool = False
    candidate_requested: bool = False
    prompt_answers: Mapping[str, str] = frozen_mapping()
    last_outcome: TransitionOutcome = TransitionOutcome.NONE
    deepened_at: str | None = None
    ended_at: str | None = None
    ended_reason: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "prompt_answers", frozen_mapping(self.prompt_answers))


@dataclass(frozen=True, slots=True)
class RelationshipPhaseState:
    by_match_id: Mapping[str, MatchPhase]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_match_id", frozen_mapping(self.by_match_id))


@dataclass(frozen=True, slots=True)
class PromptAnswer:
    prompt_id: str
    answer: str


def create_relationship_phase_state() -> RelationshipPhaseState:
    return RelationshipPhaseState({})


def get_relationship_phase(state: RelationshipPhaseState, match_id: str) -> MatchPhase:
    return state.by_match_id.get(match_id, _create_match_phase(match_id))


def request_deepen(
    state: RelationshipPhaseState,
    *,
    match_id: str,
    actor: str = "local",
    at_ms: int | float | None = None,
) -> TransitionResult[RelationshipPhaseState]:
    _assert_actor(actor)
    current = _require_active_phase(get_relationship_phase(state, match_id))
    if current.phase is RelationshipPhase.DEEPENED:
        return TransitionResult(state, frozen_outcome(kind="already_deepened", match_id=match_id))
    at = _to_iso(at_ms)
    next_phase = replace(
        current,
        local_requested=True if actor == "local" else current.local_requested,
        candidate_requested=True if actor == "candidate" else current.candidate_requested,
        last_outcome=TransitionOutcome.REQUESTED,
        updated_at=at,
    )
    if next_phase.local_requested and next_phase.candidate_requested:
        next_phase = replace(
            next_phase,
            phase=RelationshipPhase.DEEPENED,
            last_outcome=TransitionOutcome.DEEPENED,
            deepened_at=at,
        )
    next_state = _replace_phase(state, match_id, next_phase)
    return TransitionResult(
        next_state,
        frozen_outcome(
            kind=(
                "deepened" if next_phase.phase is RelationshipPhase.DEEPENED else "request_pending"
            ),
            match_id=match_id,
            phase=next_phase.phase.value,
        ),
    )


def respond_to_deepen(
    state: RelationshipPhaseState,
    *,
    match_id: str,
    actor: str = "candidate",
    accept: bool,
    at_ms: int | float | None = None,
) -> TransitionResult[RelationshipPhaseState]:
    _assert_actor(actor)
    if not isinstance(accept, bool):
        raise DomainError("acceptance_required")
    current = _require_active_phase(get_relationship_phase(state, match_id))
    if accept:
        return request_deepen(state, match_id=match_id, actor=actor, at_ms=at_ms)
    next_phase = replace(
        current,
        phase=RelationshipPhase.CASUAL,
        local_requested=False,
        candidate_requested=False,
        deepened_at=None,
        prompt_answers={},
        last_outcome=TransitionOutcome.DECLINED,
        updated_at=_to_iso(at_ms),
    )
    return TransitionResult(
        _replace_phase(state, match_id, next_phase),
        frozen_outcome(kind="declined", match_id=match_id, phase=next_phase.phase.value),
    )


def withdraw_deepen_request(
    state: RelationshipPhaseState,
    *,
    match_id: str,
    actor: str = "local",
    at_ms: int | float | None = None,
) -> TransitionResult[RelationshipPhaseState]:
    _assert_actor(actor)
    current = _require_active_phase(get_relationship_phase(state, match_id))
    if current.phase is RelationshipPhase.DEEPENED:
        raise DomainError("already_deepened_use_return_to_casual")
    next_phase = replace(
        current,
        local_requested=False if actor == "local" else current.local_requested,
        candidate_requested=False if actor == "candidate" else current.candidate_requested,
        last_outcome=TransitionOutcome.WITHDRAWN,
        updated_at=_to_iso(at_ms),
    )
    return TransitionResult(
        _replace_phase(state, match_id, next_phase),
        frozen_outcome(kind="request_withdrawn", match_id=match_id),
    )


def return_to_casual(
    state: RelationshipPhaseState,
    *,
    match_id: str,
    actor: str = "local",
    at_ms: int | float | None = None,
) -> TransitionResult[RelationshipPhaseState]:
    _assert_actor(actor)
    current = _require_active_phase(get_relationship_phase(state, match_id))
    if current.phase is not RelationshipPhase.DEEPENED:
        return TransitionResult(state, frozen_outcome(kind="already_casual", match_id=match_id))
    next_phase = replace(
        current,
        phase=RelationshipPhase.CASUAL,
        local_requested=False,
        candidate_requested=False,
        deepened_at=None,
        prompt_answers={},
        last_outcome=TransitionOutcome.RETURNED_TO_CASUAL,
        updated_at=_to_iso(at_ms),
    )
    return TransitionResult(
        _replace_phase(state, match_id, next_phase),
        frozen_outcome(kind="returned_to_casual", match_id=match_id, actor=actor),
    )


def answer_deepen_prompt(
    state: RelationshipPhaseState,
    *,
    match_id: str,
    prompt_id: str,
    answer: str,
    at_ms: int | float | None = None,
) -> ValueResult[RelationshipPhaseState, PromptAnswer]:
    current = _require_active_phase(get_relationship_phase(state, match_id))
    if current.phase is not RelationshipPhase.DEEPENED:
        raise DomainError("mutual_deepen_required")
    if prompt_id not in PROMPT_IDS:
        raise DomainError("unknown_deepen_prompt")
    normalized = _normalize_answer(answer)
    next_phase = replace(
        current,
        prompt_answers={**current.prompt_answers, prompt_id: normalized},
        updated_at=_to_iso(at_ms),
    )
    return ValueResult(
        _replace_phase(state, match_id, next_phase), PromptAnswer(prompt_id, normalized)
    )


def clear_deepen_prompt_answer(
    state: RelationshipPhaseState,
    *,
    match_id: str,
    prompt_id: str,
    at_ms: int | float | None = None,
) -> TransitionResult[RelationshipPhaseState]:
    current = _require_active_phase(get_relationship_phase(state, match_id))
    if prompt_id not in PROMPT_IDS:
        raise DomainError("unknown_deepen_prompt")
    answers = dict(current.prompt_answers)
    answers.pop(prompt_id, None)
    next_phase = replace(current, prompt_answers=answers, updated_at=_to_iso(at_ms))
    return TransitionResult(
        _replace_phase(state, match_id, next_phase),
        frozen_outcome(kind="answer_cleared", match_id=match_id, prompt_id=prompt_id),
    )


def terminate_relationship_phase(
    state: RelationshipPhaseState,
    *,
    match_id: str,
    reason: str,
    at_ms: int | float | None = None,
) -> TransitionResult[RelationshipPhaseState]:
    if reason not in {"unmatched", "blocked"}:
        raise DomainError("invalid_termination_reason")
    current = get_relationship_phase(state, match_id)
    at = _to_iso(at_ms)
    next_phase = replace(
        current,
        phase=RelationshipPhase.ENDED,
        local_requested=False,
        candidate_requested=False,
        deepened_at=None,
        prompt_answers={},
        ended_reason=reason,
        ended_at=at,
        last_outcome=TransitionOutcome.ENDED,
        updated_at=at,
    )
    return TransitionResult(
        _replace_phase(state, match_id, next_phase),
        frozen_outcome(kind="phase_ended", match_id=match_id, reason=reason),
    )


def list_available_deepen_prompts(
    state: RelationshipPhaseState, match_id: str
) -> tuple[DeepenPrompt, ...]:
    current = get_relationship_phase(state, match_id)
    return DEEPEN_PROMPTS if current.phase is RelationshipPhase.DEEPENED else ()


def _create_match_phase(match_id: str) -> MatchPhase:
    if not match_id or not isinstance(match_id, str):
        raise DomainError("match_id_required")
    return MatchPhase(match_id=match_id)


def _replace_phase(
    state: RelationshipPhaseState, match_id: str, phase: MatchPhase
) -> RelationshipPhaseState:
    return RelationshipPhaseState({**state.by_match_id, match_id: phase})


def _require_active_phase(phase: MatchPhase) -> MatchPhase:
    if phase.phase is RelationshipPhase.ENDED:
        raise DomainError("match_phase_ended")
    return phase


def _assert_actor(actor: str) -> None:
    if actor not in {"local", "candidate"}:
        raise DomainError("invalid_actor")


def _normalize_answer(value: str) -> str:
    answer = value.strip() if isinstance(value, str) else ""
    if not answer:
        raise DomainError("answer_required")
    if len(answer) > 300:
        raise DomainError("answer_too_long")
    return answer


def _to_iso(at_ms: int | float | None) -> str:
    return iso_from_ms(time.time() * 1_000 if at_ms is None else at_ms)
