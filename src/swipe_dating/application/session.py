"""Laptop-session coordinator that preserves the R&D persistence boundary."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import replace

from swipe_dating.adapters.storage import LocalStateRepository
from swipe_dating.domain.adult import is_adult_on
from swipe_dating.domain.conversations import (
    ConversationState,
    Message,
    block_conversation,
    create_conversation_state,
    get_suppressed_candidate_ids,
    receive_synthetic_reply,
    record_interest,
    record_pass,
    send_message,
    undo_last_decision,
    unmatch_conversation,
)
from swipe_dating.domain.discovery import (
    DEFAULT_RANKING_WEIGHTS,
    DiscoveryProfile,
    RankedCandidate,
    advance_profile_reveal,
    evaluate_discovery_candidate,
    rank_discovery_candidates,
)
from swipe_dating.domain.errors import DomainError
from swipe_dating.domain.local_state import LocalCosmetics, LocalProfile, LocalState, LocalUi
from swipe_dating.domain.proximity import (
    ProximityDecision,
    ProximityDisclosure,
    decide_proximity_event,
)
from swipe_dating.domain.relationship_phases import (
    DeepenPrompt,
    MatchPhase,
    PromptAnswer,
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
from swipe_dating.fixtures import LOCAL_VIEWER, SKIN_ITEMS, SYNTHETIC_PROFILES

APP_TABS = ("Discover", "Matches", "My Profile", "Preferences", "Skin Shop", "Matched Map")


class ResearchSession:
    """Orchestrate one synthetic session; persist only approved presentation fields."""

    def __init__(
        self,
        *,
        repository: LocalStateRepository,
        clock: Callable[[], int] | None = None,
        today: str = "2026-07-22",
        profiles: tuple[DiscoveryProfile, ...] = SYNTHETIC_PROFILES,
    ) -> None:
        self.repository = repository
        self.clock = clock if clock is not None else lambda: int(time.time() * 1_000)
        self.today = today
        loaded = repository.load()
        self.local_state = loaded.state
        self.storage_recovered = loaded.recovered
        self.storage_reason = loaded.reason
        self.saved_at = loaded.saved_at
        self.active_tab = self.local_state.ui.last_tab

        self.adult_accepted = False
        self.birth_date = ""
        self.get_fkd_enabled = False
        self.proximity_disclosure = ProximityDisclosure.PROMPT_BEFORE_SHARING
        self.location_choice = "none"

        self.immediate_intent = LOCAL_VIEWER.immediate_intent
        self.relational_openness = LOCAL_VIEWER.relational_openness
        self.required_boundaries = set(LOCAL_VIEWER.required_boundaries)
        self.ranking_weights = dict(DEFAULT_RANKING_WEIGHTS)
        self.reveal_stages: dict[str, str] = {}

        self.selected_intents: set[str] = {"dating"}
        self.selected_genders: set[str] = set()
        self.questionnaire_answers: dict[str, str] = {}

        self.conversations: ConversationState = create_conversation_state()
        self.relationship_phases: RelationshipPhaseState = create_relationship_phase_state()
        self._profiles = tuple(profiles)
        self._profiles_by_id = {profile.id: profile for profile in self._profiles}

    def accept_adult_gate(self, birth_date: str) -> None:
        if not is_adult_on(birth_date, self.today):
            raise DomainError("adult_only")
        self.birth_date = birth_date
        self.adult_accepted = True

    def viewer(self) -> DiscoveryProfile:
        boundaries = tuple(
            boundary for boundary in LOCAL_VIEWER.boundaries if boundary in self.required_boundaries
        )
        extras = tuple(sorted(self.required_boundaries.difference(LOCAL_VIEWER.boundaries)))
        selected_boundaries = (*boundaries, *extras)
        return replace(
            LOCAL_VIEWER,
            immediate_intent=self.immediate_intent,
            relational_openness=self.relational_openness,
            boundaries=selected_boundaries,
            required_boundaries=selected_boundaries,
        )

    def discovery_queue(self) -> tuple[RankedCandidate, ...]:
        suppressed = set(get_suppressed_candidate_ids(self.conversations))
        return tuple(
            entry
            for entry in rank_discovery_candidates(
                self.viewer(), self._profiles, self.ranking_weights
            )
            if entry.candidate.id not in suppressed
        )

    def current_candidate(self) -> RankedCandidate | None:
        queue = self.discovery_queue()
        return queue[0] if queue else None

    def reveal_stage(self, candidate_id: str) -> str:
        candidate = self._candidate(candidate_id)
        initial = evaluate_discovery_candidate(
            self.viewer(), candidate, self.ranking_weights
        ).reveal_stage
        return self.reveal_stages.get(candidate_id, initial)

    def reveal_candidate(self, candidate_id: str, interaction: str) -> str:
        stage = advance_profile_reveal(self.reveal_stage(candidate_id), interaction)
        self.reveal_stages[candidate_id] = stage
        return stage

    def pass_candidate(self, candidate_id: str) -> Mapping[str, object]:
        self._require_adult()
        result = record_pass(self.conversations, candidate_id=candidate_id, at_ms=self.clock())
        self.conversations = result.state
        return result.outcome

    def express_interest(self, candidate_id: str, starter_tag: str) -> Mapping[str, object]:
        self._require_adult()
        candidate = self._candidate(candidate_id)
        visible_tags = {*candidate.lifestyle_tags, *candidate.boundaries}
        if starter_tag not in visible_tags:
            raise DomainError("shared_ground_not_visible")
        result = record_interest(
            self.conversations,
            candidate=candidate,
            starter_tag=starter_tag,
            reciprocal_like=candidate.synthetic_reciprocal_like,
            at_ms=self.clock(),
        )
        self.conversations = result.state
        if result.outcome.get("matched") is True:
            self.active_tab = "Matches"
        return result.outcome

    def undo_last_decision(self) -> Mapping[str, object]:
        result = undo_last_decision(self.conversations)
        self.conversations = result.state
        if result.outcome.get("restored_candidate_id"):
            self.active_tab = "Discover"
        return result.outcome

    def send_message(
        self, match_id: str, text: str, shared_ground_tag: str | None = None
    ) -> Message:
        self._require_adult()
        result = send_message(
            self.conversations,
            match_id=match_id,
            text=text,
            shared_ground_tag=shared_ground_tag,
            at_ms=self.clock(),
        )
        self.conversations = result.state
        return result.value

    def receive_synthetic_reply(self, match_id: str, text: str) -> Message:
        self._require_adult()
        result = receive_synthetic_reply(
            self.conversations, match_id=match_id, text=text, at_ms=self.clock()
        )
        self.conversations = result.state
        return result.value

    def unmatch(self, match_id: str) -> Mapping[str, object]:
        conversation = unmatch_conversation(
            self.conversations, match_id=match_id, at_ms=self.clock()
        )
        phase = terminate_relationship_phase(
            self.relationship_phases,
            match_id=match_id,
            reason="unmatched",
            at_ms=self.clock(),
        )
        self.conversations = conversation.state
        self.relationship_phases = phase.state
        return conversation.outcome

    def block(self, match_id: str) -> Mapping[str, object]:
        conversation = block_conversation(self.conversations, match_id=match_id, at_ms=self.clock())
        phase = terminate_relationship_phase(
            self.relationship_phases,
            match_id=match_id,
            reason="blocked",
            at_ms=self.clock(),
        )
        self.conversations = conversation.state
        self.relationship_phases = phase.state
        return conversation.outcome

    def phase_for(self, match_id: str) -> MatchPhase:
        return get_relationship_phase(self.relationship_phases, match_id)

    def available_deepen_prompts(self, match_id: str) -> tuple[DeepenPrompt, ...]:
        return list_available_deepen_prompts(self.relationship_phases, match_id)

    def request_deepen(self, match_id: str, *, actor: str = "local") -> Mapping[str, object]:
        result = request_deepen(
            self.relationship_phases,
            match_id=match_id,
            actor=actor,
            at_ms=self.clock(),
        )
        self.relationship_phases = result.state
        return result.outcome

    def respond_to_deepen(self, match_id: str, *, actor: str, accept: bool) -> Mapping[str, object]:
        result = respond_to_deepen(
            self.relationship_phases,
            match_id=match_id,
            actor=actor,
            accept=accept,
            at_ms=self.clock(),
        )
        self.relationship_phases = result.state
        return result.outcome

    def withdraw_deepen(self, match_id: str, *, actor: str = "local") -> Mapping[str, object]:
        result = withdraw_deepen_request(
            self.relationship_phases,
            match_id=match_id,
            actor=actor,
            at_ms=self.clock(),
        )
        self.relationship_phases = result.state
        return result.outcome

    def return_to_casual(self, match_id: str, *, actor: str = "local") -> Mapping[str, object]:
        result = return_to_casual(
            self.relationship_phases,
            match_id=match_id,
            actor=actor,
            at_ms=self.clock(),
        )
        self.relationship_phases = result.state
        return result.outcome

    def answer_deepen_prompt(self, match_id: str, prompt_id: str, answer: str) -> PromptAnswer:
        result = answer_deepen_prompt(
            self.relationship_phases,
            match_id=match_id,
            prompt_id=prompt_id,
            answer=answer,
            at_ms=self.clock(),
        )
        self.relationship_phases = result.state
        return result.value

    def clear_deepen_answer(self, match_id: str, prompt_id: str) -> Mapping[str, object]:
        result = clear_deepen_prompt_answer(
            self.relationship_phases,
            match_id=match_id,
            prompt_id=prompt_id,
            at_ms=self.clock(),
        )
        self.relationship_phases = result.state
        return result.outcome

    def update_profile(
        self,
        *,
        display_name: str,
        about: str,
        pronouns: str,
    ) -> LocalState:
        self.local_state = replace(
            self.local_state,
            profile=LocalProfile(display_name, about, pronouns),
        )
        return self._persist()

    def set_haptics(self, enabled: bool) -> LocalState:
        self.local_state = replace(
            self.local_state,
            ui=replace(self.local_state.ui, haptics_enabled=bool(enabled)),
        )
        return self._persist()

    def select_tab(self, tab: str) -> LocalState:
        if tab not in APP_TABS:
            raise DomainError("unknown_tab")
        self.active_tab = tab
        if tab != "Matches":
            self.local_state = replace(
                self.local_state,
                ui=LocalUi(self.local_state.ui.haptics_enabled, tab),
            )
            return self._persist()
        return self.local_state

    def acquire_or_apply_skin(self, skin_id: str) -> LocalState:
        known = {item[0] for item in SKIN_ITEMS}
        if skin_id not in known:
            raise DomainError("unknown_skin")
        owned = tuple(dict.fromkeys((*self.local_state.cosmetics.owned_skin_ids, skin_id)))
        self.local_state = replace(
            self.local_state,
            cosmetics=LocalCosmetics(owned, skin_id),
        )
        return self._persist()

    def reset_saved_profile(self) -> LocalState:
        self.local_state = self.repository.clear()
        self.active_tab = "Discover"
        return self.local_state

    def export_saved_profile(self) -> str:
        return self.repository.export_text()

    def simulate_proximity(self) -> ProximityDecision:
        return decide_proximity_event(
            adult_credential_valid=self.adult_accepted,
            disclosure=(
                self.proximity_disclosure if self.get_fkd_enabled else ProximityDisclosure.OFF
            ),
            independently_compatible=True,
        )

    def _persist(self) -> LocalState:
        saved = self.repository.save(self.local_state, now_ms=self.clock())
        self.local_state = saved.state
        self.saved_at = saved.saved_at
        return self.local_state

    def _candidate(self, candidate_id: str) -> DiscoveryProfile:
        try:
            return self._profiles_by_id[candidate_id]
        except KeyError as error:
            raise DomainError("candidate_not_found") from error

    def _require_adult(self) -> None:
        if not self.adult_accepted:
            raise DomainError("adult_gate_required")
