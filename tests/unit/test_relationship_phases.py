from __future__ import annotations

import pytest

from swipe_dating.domain.errors import DomainError
from swipe_dating.domain.relationship_phases import (
    DEEPEN_PROMPTS,
    RelationshipPhase,
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

MATCH_ID = "match:p1"
AT = 1_753_185_600_000


def deepened():  # type: ignore[no-untyped-def]
    local = request_deepen(
        create_relationship_phase_state(), match_id=MATCH_ID, actor="local", at_ms=AT
    )
    return request_deepen(local.state, match_id=MATCH_ID, actor="candidate", at_ms=AT + 1).state


def answered(prompt_id: str = "communication_style"):  # type: ignore[no-untyped-def]
    return answer_deepen_prompt(
        deepened(),
        match_id=MATCH_ID,
        prompt_id=prompt_id,
        answer="A private answer for this synthetic session.",
        at_ms=AT + 2,
    ).state


def test_one_sided_request_is_pending_and_two_requests_deepen() -> None:
    one = request_deepen(
        create_relationship_phase_state(), match_id=MATCH_ID, actor="local", at_ms=AT
    )
    phase = get_relationship_phase(one.state, MATCH_ID)
    assert one.outcome["kind"] == "request_pending"
    assert phase.phase is RelationshipPhase.CASUAL
    assert phase.local_requested
    assert not phase.candidate_requested

    mutual = request_deepen(one.state, match_id=MATCH_ID, actor="candidate", at_ms=AT + 1)
    assert mutual.outcome["kind"] == "deepened"
    assert get_relationship_phase(mutual.state, MATCH_ID).phase is RelationshipPhase.DEEPENED
    assert len(list_available_deepen_prompts(mutual.state, MATCH_ID)) == len(DEEPEN_PROMPTS)


def test_candidate_first_request_can_be_accepted_locally() -> None:
    incoming = request_deepen(
        create_relationship_phase_state(), match_id=MATCH_ID, actor="candidate", at_ms=AT
    )
    accepted = respond_to_deepen(
        incoming.state, match_id=MATCH_ID, actor="local", accept=True, at_ms=AT + 1
    )
    assert accepted.outcome["kind"] == "deepened"


def test_decline_retains_no_reason_and_withdrawal_is_available() -> None:
    pending = request_deepen(
        create_relationship_phase_state(), match_id=MATCH_ID, actor="local", at_ms=AT
    )
    declined = respond_to_deepen(
        pending.state, match_id=MATCH_ID, actor="candidate", accept=False, at_ms=AT + 1
    )
    phase = get_relationship_phase(declined.state, MATCH_ID)
    assert phase.phase is RelationshipPhase.CASUAL
    assert not phase.local_requested and not phase.candidate_requested
    assert not hasattr(phase, "decline_reason")

    withdrawn = withdraw_deepen_request(
        pending.state, match_id=MATCH_ID, actor="local", at_ms=AT + 1
    )
    assert withdrawn.outcome["kind"] == "request_withdrawn"
    assert not get_relationship_phase(withdrawn.state, MATCH_ID).local_requested


def test_prompts_are_mutually_gated_allowlisted_bounded_and_clearable() -> None:
    with pytest.raises(DomainError, match="mutual_deepen_required"):
        answer_deepen_prompt(
            create_relationship_phase_state(),
            match_id=MATCH_ID,
            prompt_id="communication_style",
            answer="No",
            at_ms=AT,
        )
    with pytest.raises(DomainError, match="unknown_deepen_prompt"):
        answer_deepen_prompt(
            deepened(),
            match_id=MATCH_ID,
            prompt_id="secret_prompt",
            answer="No",
            at_ms=AT,
        )
    with pytest.raises(DomainError, match="answer_too_long"):
        answer_deepen_prompt(
            deepened(),
            match_id=MATCH_ID,
            prompt_id="communication_style",
            answer="x" * 301,
            at_ms=AT,
        )
    saved = answer_deepen_prompt(
        deepened(),
        match_id=MATCH_ID,
        prompt_id="communication_style",
        answer="  I need a pause.  ",
        at_ms=AT,
    )
    assert saved.value.answer == "I need a pause."
    cleared = clear_deepen_prompt_answer(
        saved.state, match_id=MATCH_ID, prompt_id="communication_style", at_ms=AT + 1
    )
    assert not get_relationship_phase(cleared.state, MATCH_ID).prompt_answers


@pytest.mark.parametrize("actor", ["local", "candidate"])
def test_either_participant_can_return_to_casual_and_clear_answers(actor: str) -> None:
    result = return_to_casual(answered(), match_id=MATCH_ID, actor=actor, at_ms=AT + 3)
    phase = get_relationship_phase(result.state, MATCH_ID)
    assert result.outcome["kind"] == "returned_to_casual"
    assert phase.phase is RelationshipPhase.CASUAL
    assert not phase.prompt_answers


@pytest.mark.parametrize("reason", ["unmatched", "blocked"])
def test_match_termination_ends_phase_clears_answers_and_rejects_transitions(
    reason: str,
) -> None:
    ended = terminate_relationship_phase(
        answered("future_boundaries"), match_id=MATCH_ID, reason=reason, at_ms=AT + 3
    )
    phase = get_relationship_phase(ended.state, MATCH_ID)
    assert phase.phase is RelationshipPhase.ENDED
    assert phase.ended_reason == reason
    assert not phase.prompt_answers
    with pytest.raises(DomainError, match="match_phase_ended"):
        request_deepen(ended.state, match_id=MATCH_ID, actor="local", at_ms=AT + 4)
