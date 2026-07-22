from __future__ import annotations

import json

import pytest

from swipe_dating.adapters.storage import LocalStateRepository, MemoryStorageAdapter
from swipe_dating.application.session import ResearchSession
from swipe_dating.domain.conversations import MatchStatus
from swipe_dating.domain.discovery import DEFAULT_RANKING_WEIGHTS
from swipe_dating.domain.errors import DomainError
from swipe_dating.domain.relationship_phases import RelationshipPhase

NOW = 1_753_185_600_000


def create_session() -> tuple[ResearchSession, MemoryStorageAdapter]:
    adapter = MemoryStorageAdapter()
    session = ResearchSession(
        repository=LocalStateRepository(adapter),
        clock=lambda: NOW,
        today="2026-07-22",
    )
    return session, adapter


def test_adult_gate_and_discovery_reveal() -> None:
    session, _adapter = create_session()
    with pytest.raises(DomainError, match="adult_only"):
        session.accept_adult_gate("2009-07-22")
    assert session.adult_accepted is False
    session.accept_adult_gate("2000-01-01")
    assert session.adult_accepted is True
    assert session.birth_date == "2000-01-01"

    current = session.current_candidate()
    assert current is not None and current.candidate.id == "p1"
    assert session.reveal_stage("p1") == "bio_first"
    assert session.reveal_candidate("p1", "swipe_right") == "bio_first"
    assert session.reveal_candidate("p1", "inspect_tags") == "photo_revealed"


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


def test_unknown_ranking_dimension_is_rejected() -> None:
    session, _adapter = create_session()
    with pytest.raises(DomainError, match="unknown_ranking_dimension"):
        session.adjust_ranking_weight("attractiveness", 5)


def test_user_can_reset_ranking_weights() -> None:
    session, _adapter = create_session()
    session.adjust_ranking_weight("alignment", 50)

    assert session.reset_ranking_weights() == DEFAULT_RANKING_WEIGHTS
    assert session.ranking_weights == DEFAULT_RANKING_WEIGHTS


def test_match_message_deepen_and_unmatch_are_coordinated_in_memory() -> None:
    session, adapter = create_session()
    session.accept_adult_gate("2000-01-01")
    outcome = session.express_interest("p1", "hiking")
    assert outcome["matched"] is True
    assert session.active_tab == "Matches"
    match_id = str(outcome["match_id"])

    with pytest.raises(DomainError, match="opening_context_required"):
        session.send_message(match_id, "Hello")
    message = session.send_message(match_id, "What trail do you like?", "hiking")
    assert message.shared_ground_tag == "hiking"
    assert session.receive_synthetic_reply(match_id, "I like the river loop.").sender == "candidate"

    pending = session.request_deepen(match_id, actor="local")
    assert pending["kind"] == "request_pending"
    assert session.phase_for(match_id).phase is RelationshipPhase.CASUAL
    accepted = session.respond_to_deepen(match_id, actor="candidate", accept=True)
    assert accepted["kind"] == "deepened"
    session.answer_deepen_prompt(match_id, "communication_style", "I value a pause.")
    assert session.phase_for(match_id).prompt_answers["communication_style"] == ("I value a pause.")

    ended = session.unmatch(match_id)
    assert ended["kind"] == "unmatched"
    assert session.conversations.matches[match_id].status is MatchStatus.UNMATCHED
    assert session.phase_for(match_id).phase is RelationshipPhase.ENDED
    assert not session.phase_for(match_id).prompt_answers

    # Session-only adult, discovery, match, message, and phase state never reaches storage.
    assert adapter.inspect() is None


def test_block_purges_content_and_suppresses_candidate() -> None:
    session, _adapter = create_session()
    session.accept_adult_gate("2000-01-01")
    outcome = session.express_interest("p1", "hiking")
    match_id = str(outcome["match_id"])
    session.send_message(match_id, "Opening", "hiking")
    session.block(match_id)
    match = session.conversations.matches[match_id]
    assert match.status is MatchStatus.BLOCKED
    assert match.content_purged and not match.messages and match.starter_tag is None
    assert all(entry.candidate.id != "p1" for entry in session.discovery_queue())


def test_visible_shared_ground_is_required() -> None:
    session, _adapter = create_session()
    session.accept_adult_gate("2000-01-01")
    with pytest.raises(DomainError, match="shared_ground_not_visible"):
        session.express_interest("p1", "secret_trait")


def test_only_allowlisted_profile_cosmetic_and_safe_tab_state_persists() -> None:
    session, adapter = create_session()
    session.update_profile(display_name="Riley", about="Builder", pronouns="they/them")
    session.select_tab("My Profile")
    session.acquire_or_apply_skin("neon-orbit")
    session.select_tab("Matches")
    session.selected_intents.add("casual_sex")
    session.questionnaire_answers["politics"] = "private"
    session.location_choice = "live_15_minutes"

    raw = json.loads(adapter.inspect())
    assert raw["profile"]["displayName"] == "Riley"
    assert raw["cosmetics"]["selectedSkinId"] == "neon-orbit"
    assert raw["ui"]["lastTab"] == "My Profile"
    assert set(raw) == {"schemaVersion", "savedAt", "profile", "cosmetics", "ui"}


def test_pass_undo_restores_candidate() -> None:
    session, _adapter = create_session()
    session.accept_adult_gate("2000-01-01")
    assert session.pass_candidate("p1")["kind"] == "passed"
    assert session.current_candidate().candidate.id == "p3"  # type: ignore[union-attr]
    outcome = session.undo_last_decision()
    assert outcome["restored_candidate_id"] == "p1"
    assert session.current_candidate().candidate.id == "p1"  # type: ignore[union-attr]
