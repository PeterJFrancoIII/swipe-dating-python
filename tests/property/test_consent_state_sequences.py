from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from swipe_dating.domain.conversations import (
    CandidateSnapshot,
    ConversationState,
    MatchStatus,
    block_conversation,
    create_conversation_state,
    get_suppressed_candidate_ids,
    receive_synthetic_reply,
    record_interest,
    record_pass,
    send_meetup_proposal,
    send_message,
    undo_last_decision,
    unmatch_conversation,
)
from swipe_dating.domain.errors import DomainError
from swipe_dating.domain.relationship_phases import (
    DEEPEN_PROMPTS,
    MatchPhase,
    RelationshipPhase,
    RelationshipPhaseState,
    answer_deepen_prompt,
    clear_deepen_prompt_answer,
    create_relationship_phase_state,
    get_relationship_phase,
    list_available_deepen_prompts,
    request_deepen,
    respond_to_deepen,
    return_to_casual,
    terminate_relationship_phase,
    withdraw_deepen_request,
)

CONVERSATION_ACTIONS = (
    "pass",
    "pending_interest",
    "reciprocal_interest",
    "undo",
    "local_message",
    "candidate_reply",
    "meetup",
    "unmatch",
    "block",
)

RELATIONSHIP_ACTIONS = (
    "local_request",
    "candidate_request",
    "local_accept",
    "candidate_accept",
    "local_decline",
    "candidate_decline",
    "local_withdraw",
    "candidate_withdraw",
    "local_return",
    "candidate_return",
    "answer",
    "clear_answer",
    "terminate_unmatched",
    "terminate_blocked",
    "new_match",
)


@settings(max_examples=100, deadline=None)
@given(st.lists(st.sampled_from(CONVERSATION_ACTIONS), min_size=1, max_size=40))
def test_conversation_state_machine_preserves_consent_invariants(
    actions: list[str],
) -> None:
    state = create_conversation_state()
    next_candidate = 1

    for step, action in enumerate(actions, start=1):
        matches = tuple(state.matches.values())
        active_matches = tuple(match for match in matches if match.status is MatchStatus.ACTIVE)

        if action == "pass":
            candidate_id = f"candidate-{next_candidate}"
            next_candidate += 1
            state = record_pass(state, candidate_id=candidate_id, at_ms=step).state
        elif action in {"pending_interest", "reciprocal_interest"}:
            candidate_id = f"candidate-{next_candidate}"
            next_candidate += 1
            state = record_interest(
                state,
                candidate=CandidateSnapshot(candidate_id),
                starter_tag="hiking",
                reciprocal_like=action == "reciprocal_interest",
                at_ms=step,
            ).state
        elif action == "undo":
            state = undo_last_decision(state).state
        elif action == "local_message" and active_matches:
            match = active_matches[-1]
            local_messages = tuple(
                message for message in match.messages if message.sender == "local"
            )
            state = send_message(
                state,
                match_id=match.id,
                text=f"Local message {step}",
                shared_ground_tag=match.starter_tag if not local_messages else None,
                at_ms=step,
            ).state
        elif action == "candidate_reply" and active_matches:
            state = receive_synthetic_reply(
                state,
                match_id=active_matches[-1].id,
                text=f"Candidate reply {step}",
                at_ms=step,
            ).state
        elif action == "meetup" and active_matches:
            match = active_matches[-1]
            senders = {message.sender for message in match.messages}
            if {"local", "candidate"}.issubset(senders):
                state = send_meetup_proposal(
                    state,
                    match_id=match.id,
                    suggestion_id="coffee_public",
                    at_ms=step,
                ).state
            else:
                with pytest.raises(DomainError, match="meetup_requires_two_way_conversation"):
                    send_meetup_proposal(
                        state,
                        match_id=match.id,
                        suggestion_id="coffee_public",
                        at_ms=step,
                    )
        elif action == "unmatch" and matches:
            state = unmatch_conversation(state, match_id=matches[-1].id, at_ms=step).state
        elif action == "block" and matches:
            state = block_conversation(state, match_id=matches[-1].id, at_ms=step).state

        _assert_conversation_invariants(state)
        assert state.next_event_sequence == next_candidate


def _assert_conversation_invariants(state: ConversationState) -> None:
    decisions = state.decisions
    matches = tuple(state.matches.values())
    decision_ids = tuple(decision.id for decision in decisions)
    assert len(decision_ids) == len(set(decision_ids))

    match_creating_candidates = {
        decision.candidate_id for decision in decisions if decision.creates_match
    }
    suppressed = set(get_suppressed_candidate_ids(state))
    visible_message_ids: list[str] = []

    for decision in decisions:
        assert decision.candidate_id in suppressed
    for match in matches:
        assert match.candidate.id in match_creating_candidates
        assert match.candidate.id in suppressed
        local_messages = tuple(message for message in match.messages if message.sender == "local")
        if local_messages:
            assert local_messages[0].shared_ground_tag == match.starter_tag
            assert all(message.shared_ground_tag is None for message in local_messages[1:])
        visible_message_ids.extend(message.id for message in match.messages)

        if match.status is MatchStatus.BLOCKED:
            assert match.content_purged is True
            assert match.messages == ()
            assert match.starter_tag is None
            assert match.candidate.id in state.blocked_candidate_ids
        elif match.status is not MatchStatus.ACTIVE:
            with pytest.raises(DomainError, match="match_not_active"):
                send_message(state, match_id=match.id, text="No", at_ms=0)

    assert len(visible_message_ids) == len(set(visible_message_ids))
    for message_id in visible_message_ids:
        sequence = int(message_id.removeprefix("message-"))
        assert 1 <= sequence < state.next_message_sequence
    assert set(state.blocked_candidate_ids).issubset(suppressed)


@settings(max_examples=100, deadline=None)
@given(st.lists(st.sampled_from(RELATIONSHIP_ACTIONS), min_size=1, max_size=50))
def test_relationship_state_machine_preserves_bilateral_consent_invariants(
    actions: list[str],
) -> None:
    state = create_relationship_phase_state()
    match_number = 1
    match_id = f"match-{match_number}"

    for step, action in enumerate(actions, start=1):
        before_other_matches = dict(state.by_match_id)
        if action == "new_match":
            match_number += 1
            match_id = f"match-{match_number}"
        else:
            state = _apply_relationship_action(state, match_id, action, step)

        for other_match_id, previous in before_other_matches.items():
            if other_match_id != match_id:
                assert state.by_match_id[other_match_id] == previous
        _assert_relationship_invariants(state)
        _assert_match_phase(get_relationship_phase(state, match_id), state)


def _apply_relationship_action(
    state: RelationshipPhaseState, match_id: str, action: str, step: int
) -> RelationshipPhaseState:
    if action.endswith(("request", "accept")):
        result = _apply_request_or_accept(state, match_id, action, step)
    elif action.endswith("decline"):
        result = _apply_decline(state, match_id, action, step)
    elif action.endswith("withdraw"):
        result = _apply_withdraw(state, match_id, action, step)
    elif action.endswith("return"):
        result = _apply_return(state, match_id, action, step)
    elif action == "answer":
        result = _apply_answer(state, match_id, step)
    elif action == "clear_answer":
        result = _apply_clear_answer(state, match_id, step)
    elif action.startswith("terminate_"):
        reason = "unmatched" if action.endswith("unmatched") else "blocked"
        result = terminate_relationship_phase(
            state, match_id=match_id, reason=reason, at_ms=step
        ).state
    else:
        raise AssertionError(f"unknown generated relationship action: {action}")
    return result


def _apply_request_or_accept(
    state: RelationshipPhaseState, match_id: str, action: str, step: int
) -> RelationshipPhaseState:
    actor = _actor(action)
    if get_relationship_phase(state, match_id).phase is RelationshipPhase.ENDED:
        with pytest.raises(DomainError, match="match_phase_ended"):
            request_deepen(state, match_id=match_id, actor=actor, at_ms=step)
        return state
    if action.endswith("accept"):
        return respond_to_deepen(
            state, match_id=match_id, actor=actor, accept=True, at_ms=step
        ).state
    return request_deepen(state, match_id=match_id, actor=actor, at_ms=step).state


def _apply_decline(
    state: RelationshipPhaseState, match_id: str, action: str, step: int
) -> RelationshipPhaseState:
    actor = _actor(action)
    if get_relationship_phase(state, match_id).phase is RelationshipPhase.ENDED:
        with pytest.raises(DomainError, match="match_phase_ended"):
            respond_to_deepen(state, match_id=match_id, actor=actor, accept=False, at_ms=step)
        return state
    return respond_to_deepen(state, match_id=match_id, actor=actor, accept=False, at_ms=step).state


def _apply_withdraw(
    state: RelationshipPhaseState, match_id: str, action: str, step: int
) -> RelationshipPhaseState:
    actor = _actor(action)
    phase = get_relationship_phase(state, match_id).phase
    error = (
        "match_phase_ended"
        if phase is RelationshipPhase.ENDED
        else "already_deepened_use_return_to_casual"
        if phase is RelationshipPhase.DEEPENED
        else None
    )
    if error:
        with pytest.raises(DomainError, match=error):
            withdraw_deepen_request(state, match_id=match_id, actor=actor, at_ms=step)
        return state
    return withdraw_deepen_request(state, match_id=match_id, actor=actor, at_ms=step).state


def _apply_return(
    state: RelationshipPhaseState, match_id: str, action: str, step: int
) -> RelationshipPhaseState:
    actor = _actor(action)
    if get_relationship_phase(state, match_id).phase is RelationshipPhase.ENDED:
        with pytest.raises(DomainError, match="match_phase_ended"):
            return_to_casual(state, match_id=match_id, actor=actor, at_ms=step)
        return state
    return return_to_casual(state, match_id=match_id, actor=actor, at_ms=step).state


def _apply_answer(
    state: RelationshipPhaseState, match_id: str, step: int
) -> RelationshipPhaseState:
    phase = get_relationship_phase(state, match_id).phase
    error = (
        "match_phase_ended"
        if phase is RelationshipPhase.ENDED
        else "mutual_deepen_required"
        if phase is RelationshipPhase.CASUAL
        else None
    )
    if error:
        with pytest.raises(DomainError, match=error):
            answer_deepen_prompt(
                state,
                match_id=match_id,
                prompt_id="communication_style",
                answer="Clear communication",
                at_ms=step,
            )
        return state
    return answer_deepen_prompt(
        state,
        match_id=match_id,
        prompt_id="communication_style",
        answer="Clear communication",
        at_ms=step,
    ).state


def _apply_clear_answer(
    state: RelationshipPhaseState, match_id: str, step: int
) -> RelationshipPhaseState:
    if get_relationship_phase(state, match_id).phase is RelationshipPhase.ENDED:
        with pytest.raises(DomainError, match="match_phase_ended"):
            clear_deepen_prompt_answer(
                state,
                match_id=match_id,
                prompt_id="communication_style",
                at_ms=step,
            )
        return state
    return clear_deepen_prompt_answer(
        state,
        match_id=match_id,
        prompt_id="communication_style",
        at_ms=step,
    ).state


def _actor(action: str) -> str:
    return "local" if action.startswith("local") else "candidate"


def _assert_relationship_invariants(state: RelationshipPhaseState) -> None:
    for phase in state.by_match_id.values():
        _assert_match_phase(phase, state)


def _assert_match_phase(phase: MatchPhase, state: RelationshipPhaseState) -> None:
    available_prompts = list_available_deepen_prompts(state, phase.match_id)
    if phase.phase is RelationshipPhase.DEEPENED:
        assert phase.local_requested and phase.candidate_requested
        assert phase.deepened_at is not None
        assert available_prompts == DEEPEN_PROMPTS
    elif phase.phase is RelationshipPhase.CASUAL:
        assert not (phase.local_requested and phase.candidate_requested)
        assert phase.prompt_answers == {}
        assert phase.deepened_at is None
        assert available_prompts == ()
    else:
        assert phase.local_requested is False
        assert phase.candidate_requested is False
        assert phase.prompt_answers == {}
        assert phase.deepened_at is None
        assert phase.ended_at is not None
        assert phase.ended_reason in {"unmatched", "blocked"}
        assert available_prompts == ()

    if phase.prompt_answers:
        assert phase.phase is RelationshipPhase.DEEPENED
        assert set(phase.prompt_answers).issubset({prompt.id for prompt in DEEPEN_PROMPTS})
        assert all(answer == answer.strip() for answer in phase.prompt_answers.values())
        assert all(1 <= len(answer) <= 300 for answer in phase.prompt_answers.values())
