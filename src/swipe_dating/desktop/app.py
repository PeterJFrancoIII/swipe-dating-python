"""Runnable Tkinter recreation of the synthetic Swipe Dating research app."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import tkinter as tk
    from tkinter import messagebox

    _TK_AVAILABLE: bool
else:
    try:
        import tkinter as tk
        from tkinter import messagebox

        _TK_AVAILABLE = True
    except ModuleNotFoundError:
        tk = cast(Any, None)
        messagebox = cast(Any, None)
        _TK_AVAILABLE = False

from swipe_dating.adapters.storage import JsonFileStorageAdapter, LocalStateRepository
from swipe_dating.application.session import APP_TABS, ResearchSession
from swipe_dating.domain.conversations import (
    MatchStatus,
    build_starter_suggestions,
    list_matches,
)
from swipe_dating.domain.discovery import (
    BOUNDARY_TAGS,
    IMMEDIATE_INTENTS,
    RANKING_DIMENSIONS,
    RELATIONAL_OPENNESS,
)
from swipe_dating.domain.errors import DomainError
from swipe_dating.domain.location_grants import LocationMode
from swipe_dating.domain.preferences import (
    GENDER_DISCOVERY_CATEGORIES,
    LOOKING_FOR_MODES,
)
from swipe_dating.domain.proximity import ProximityDisclosure
from swipe_dating.domain.relationship_phases import RelationshipPhase
from swipe_dating.fixtures import (
    QUESTIONNAIRE,
    SKIN_ITEMS,
)

BACKGROUND = "#11141a"
PANEL = "#191d24"
CARD = "#242936"
TEXT = "#f7f8fa"
MUTED = "#aeb5c1"
PINK = "#ff6d9e"
MINT = "#69e7c3"
AMBER = "#ffb45c"
DANGER = "#ff735f"
BORDER = "#454c58"


def default_state_path() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "SwipeDatingRND" / "local-state.json"


class SwipeDatingDesktop:
    """Thin UI adapter; all product decisions remain in ResearchSession/domain code."""

    def __init__(self, root: tk.Tk, session: ResearchSession) -> None:
        if not _TK_AVAILABLE:
            raise RuntimeError(
                "Tkinter is unavailable in this Python build. Install the matching python-tk "
                "system package or use a Python distribution that includes Tk."
            )
        self.root = root
        self.session = session
        self.root.title("Swipe Dating — Python R&D")
        self.root.geometry("1100x780")
        self.root.minsize(820, 640)
        self.root.configure(bg=BACKGROUND)
        self._body: tk.Frame | None = None
        self._canvas: tk.Canvas | None = None
        self._nav_buttons: dict[str, tk.Button] = {}
        self._starter_by_candidate: dict[str, str] = {}
        self._export_preview = ""
        self._dynamic_variables: list[tk.Variable] = []
        self._show_adult_gate()

    def _show_adult_gate(self) -> None:
        self._clear(self.root)
        outer = tk.Frame(self.root, bg=BACKGROUND)
        outer.pack(expand=True, fill="both")
        card = tk.Frame(
            outer, bg=PANEL, padx=42, pady=38, highlightbackground=BORDER, highlightthickness=1
        )
        card.place(relx=0.5, rely=0.5, anchor="center", width=560)
        self._text(card, "Swipe Dating — Python R&D", size=28, weight="bold").pack(anchor="w")
        self._text(card, "ADULTS 18+ ONLY", color=AMBER, size=13, weight="bold").pack(
            anchor="w", pady=(8, 20)
        )
        self._text(
            card,
            "Enter an exact birth date. There is no parental-consent bypass. The date and gate result stay in memory for this session and are never written to the local profile file.",
            color=MUTED,
            wrap=470,
        ).pack(anchor="w", pady=(0, 18))
        birth_date = tk.StringVar(value="2000-01-01")
        entry = tk.Entry(card, textvariable=birth_date, font=("Helvetica Neue", 17), relief="flat")
        entry.pack(fill="x", ipady=10)
        entry.focus_set()

        def continue_to_app() -> None:
            try:
                self.session.accept_adult_gate(birth_date.get())
            except DomainError:
                messagebox.showerror(
                    "Adults only", "You must be at least 18 years old to continue."
                )
                return
            self._show_shell()

        self._button(card, "Continue", continue_to_app, primary=True).pack(fill="x", pady=(16, 16))
        storage = (
            "Saved profile data was invalid and safely reset."
            if self.session.storage_recovered
            else "Approved local profile fields are ready."
        )
        self._text(card, storage, color=MINT, size=11).pack(anchor="w")
        entry.bind("<Return>", lambda _event: continue_to_app())

    def _show_shell(self) -> None:
        self._clear(self.root)
        header = tk.Frame(self.root, bg=PANEL, padx=24, pady=14)
        header.pack(fill="x")
        display_name = self.session.local_state.profile.display_name
        title = f"Swipe R&D · {display_name}" if display_name else "Swipe R&D"
        self._text(header, title, size=22, weight="bold").pack(side="left")
        self._text(header, "PYTHON · SYNTHETIC ONLY", color=MINT, size=10, weight="bold").pack(
            side="right", pady=8
        )

        nav = tk.Frame(self.root, bg=BACKGROUND, padx=18, pady=10)
        nav.pack(fill="x")
        self._nav_buttons.clear()
        for tab in APP_TABS:
            button = self._button(
                nav, self._tab_label(tab), lambda value=tab: self._navigate(value)
            )
            button.pack(side="left", padx=3)
            self._nav_buttons[tab] = button

        host = tk.Frame(self.root, bg=BACKGROUND)
        host.pack(expand=True, fill="both")
        canvas = tk.Canvas(host, bg=BACKGROUND, highlightthickness=0)
        scrollbar = tk.Scrollbar(host, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=BACKGROUND, padx=28, pady=16)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", expand=True, fill="both")
        scrollbar.pack(side="right", fill="y")
        body.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )
        canvas.bind_all(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
        )
        self._body = body
        self._canvas = canvas
        self._render_active_tab()

    def _navigate(self, tab: str) -> None:
        self.session.select_tab(tab)
        self._render_active_tab()

    def _render_active_tab(self) -> None:
        if self._body is None:
            return
        self._clear(self._body)
        self._dynamic_variables.clear()
        for tab, button in self._nav_buttons.items():
            button.configure(
                bg=PINK if tab == self.session.active_tab else PANEL,
                fg=BACKGROUND if tab == self.session.active_tab else TEXT,
            )
        renderers: dict[str, Callable[[], None]] = {
            "Discover": self._render_discover,
            "Matches": self._render_matches,
            "My Profile": self._render_profile,
            "Preferences": self._render_preferences,
            "Skin Shop": self._render_skin_shop,
            "Matched Map": self._render_matched_map,
        }
        renderers[self.session.active_tab]()
        if self._canvas is not None:
            self._canvas.yview_moveto(0)

    def _render_discover(self) -> None:
        settings = self._card("Intent-driven discovery")
        self._text(
            settings,
            "Immediate desire and relational openness are separate. Required boundaries exclude before scoring, and all controls remain session-only.",
            color=MUTED,
            wrap=940,
        ).pack(anchor="w", pady=(0, 12))
        controls = tk.Frame(settings, bg=CARD)
        controls.pack(fill="x")
        self._text(controls, "Right now", color=MUTED, size=11).grid(row=0, column=0, sticky="w")
        immediate = tk.StringVar(value=self.session.immediate_intent)
        self._dynamic_variables.append(immediate)
        tk.OptionMenu(
            controls,
            immediate,
            *IMMEDIATE_INTENTS,
            command=lambda value: self._set_discovery_choice("immediate", str(value)),
        ).grid(row=1, column=0, sticky="ew", padx=(0, 12))
        self._text(controls, "Could become", color=MUTED, size=11).grid(row=0, column=1, sticky="w")
        openness = tk.StringVar(value=self.session.relational_openness)
        self._dynamic_variables.append(openness)
        tk.OptionMenu(
            controls,
            openness,
            *RELATIONAL_OPENNESS,
            command=lambda value: self._set_discovery_choice("openness", str(value)),
        ).grid(row=1, column=1, sticky="ew")
        controls.columnconfigure((0, 1), weight=1)

        boundary_row = tk.Frame(settings, bg=CARD)
        boundary_row.pack(fill="x", pady=(14, 4))
        self._text(boundary_row, "Required boundaries", weight="bold").pack(anchor="w")
        for boundary in BOUNDARY_TAGS:
            selected = tk.BooleanVar(value=boundary in self.session.required_boundaries)
            self._dynamic_variables.append(selected)
            check = tk.Checkbutton(
                boundary_row,
                text=self._label(boundary),
                variable=selected,
                command=lambda tag=boundary, value=selected: self._toggle_boundary(
                    tag, value.get()
                ),
                bg=CARD,
                fg=TEXT,
                selectcolor=PANEL,
                activebackground=CARD,
                activeforeground=TEXT,
            )
            check.pack(side="left", padx=(0, 8), pady=4)

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

        proximity = self._card("Get fk’d — proximity simulation")
        self._text(
            proximity,
            "Off by default with identical privacy defaults for every gender. This screen does not scan Bluetooth or share a profile.",
            color=MUTED,
            wrap=940,
        ).pack(anchor="w")
        proximity_enabled = tk.BooleanVar(value=self.session.get_fkd_enabled)
        self._dynamic_variables.append(proximity_enabled)
        tk.Checkbutton(
            proximity,
            text="Enable synthetic decision model",
            variable=proximity_enabled,
            command=lambda: setattr(self.session, "get_fkd_enabled", proximity_enabled.get()),
            bg=CARD,
            fg=TEXT,
            selectcolor=PANEL,
            activebackground=CARD,
            activeforeground=TEXT,
        ).pack(anchor="w", pady=8)
        disclosure = tk.StringVar(value=self.session.proximity_disclosure.value)
        self._dynamic_variables.append(disclosure)
        tk.OptionMenu(
            proximity,
            disclosure,
            ProximityDisclosure.PROMPT_BEFORE_SHARING.value,
            ProximityDisclosure.AUTO_SHARE_COMPATIBLE.value,
            command=lambda value: setattr(
                self.session, "proximity_disclosure", ProximityDisclosure(str(value))
            ),
        ).pack(anchor="w")
        self._button(proximity, "Simulate nearby adult", self._simulate_proximity).pack(
            anchor="w", pady=(10, 0)
        )

        current = self.session.current_candidate()
        candidate_card = self._card("Candidate queue")
        if current is None:
            self._text(
                candidate_card,
                "No eligible synthetic profiles remain. Undo the latest pass or pending interest to restore it.",
                color=MUTED,
                wrap=900,
            ).pack(anchor="w")
            self._button(candidate_card, "Undo latest decision", self._undo).pack(
                anchor="w", pady=(12, 0)
            )
            return

        candidate = current.candidate
        self._text(
            candidate_card,
            f"{candidate.display_name} · {candidate.age_band}",
            size=28,
            weight="bold",
        ).pack(anchor="w")
        self._text(
            candidate_card,
            f"SYNTHETIC · score {current.result.score}/100 · {self._label(candidate.immediate_intent)} · {self._label(candidate.relational_openness)}",
            color=MINT,
            size=11,
            weight="bold",
        ).pack(anchor="w", pady=(3, 12))
        self._text(candidate_card, candidate.about, wrap=900, size=16).pack(anchor="w")
        stage = self.session.reveal_stage(candidate.id)
        visual_text = (
            "Synthetic visual placeholder revealed — no real photograph is loaded."
            if stage == "photo_revealed"
            else "BIO FIRST · Visual placeholder remains hidden until a non-visual inspection."
        )
        self._text(
            candidate_card,
            visual_text,
            color=PINK if stage == "photo_revealed" else AMBER,
            weight="bold",
            wrap=900,
        ).pack(anchor="w", pady=12)
        inspect_row = tk.Frame(candidate_card, bg=CARD)
        inspect_row.pack(fill="x")
        for interaction, label in (
            ("read_bio", "I read the bio"),
            ("inspect_tags", "Inspect tags"),
            ("view_explanation", "View score explanation"),
        ):
            self._button(
                inspect_row,
                label,
                lambda value=interaction, candidate_id=candidate.id: self._reveal(
                    candidate_id, value
                ),
            ).pack(side="left", padx=(0, 8))
        explanation = " · ".join(
            f"{item.key} {item.component}% × {item.weight}%" for item in current.result.explanation
        )
        self._text(candidate_card, explanation, color=MUTED, size=10, wrap=920).pack(
            anchor="w", pady=(12, 8)
        )
        self._text(
            candidate_card,
            "Choose visible shared ground before expressing interest:",
            weight="bold",
        ).pack(anchor="w")
        starter = tk.StringVar(value=self._starter_by_candidate.get(candidate.id, ""))
        self._dynamic_variables.append(starter)
        tags = tk.Frame(candidate_card, bg=CARD)
        tags.pack(fill="x", pady=6)
        for tag in candidate.lifestyle_tags:
            tk.Radiobutton(
                tags,
                text=self._label(tag),
                value=tag,
                variable=starter,
                command=lambda cid=candidate.id, value=starter: (
                    self._starter_by_candidate.__setitem__(cid, value.get())
                ),
                bg=CARD,
                fg=TEXT,
                selectcolor=PANEL,
                activebackground=CARD,
                activeforeground=TEXT,
            ).pack(side="left", padx=(0, 8))
        actions = tk.Frame(candidate_card, bg=CARD)
        actions.pack(fill="x", pady=(8, 0))
        self._button(
            actions,
            "Interested — synthetic",
            lambda: self._interest(candidate.id),
            primary=True,
        ).pack(side="left", padx=(0, 8))
        self._button(actions, "Pass", lambda: self._pass(candidate.id)).pack(side="left")
        self._button(actions, "Undo latest", self._undo).pack(side="right")

    def _render_matches(self) -> None:
        heading = self._card("Matches and conversations")
        self._text(
            heading,
            "Session-only synthetic fixtures. No network delivery, E2EE, read receipts, push, screenshots controls, or real counterpart action is represented here.",
            color=AMBER,
            wrap=940,
        ).pack(anchor="w")
        matches = list_matches(self.session.conversations)
        if not matches:
            self._text(heading, "No synthetic matches yet.", color=MUTED).pack(
                anchor="w", pady=(12, 0)
            )
            self._button(heading, "Return to Discover", lambda: self._navigate("Discover")).pack(
                anchor="w", pady=(12, 0)
            )
            return
        for match in matches:
            card = self._card(f"{match.candidate.display_name} · {self._label(match.status.value)}")
            self._text(card, "SYNTHETIC MATCH", color=MINT, size=10, weight="bold").pack(anchor="w")
            if match.content_purged:
                self._text(
                    card,
                    "Conversation content and shared-ground context were purged after block.",
                    color=AMBER,
                    wrap=900,
                ).pack(anchor="w", pady=10)
            else:
                if match.starter_tag:
                    self._text(
                        card,
                        f"Shared ground: {self._label(match.starter_tag)}",
                        color=MINT,
                        weight="bold",
                    ).pack(anchor="w", pady=(4, 8))
                if not match.messages:
                    self._text(card, "No messages yet.", color=MUTED).pack(anchor="w")
                for message in match.messages:
                    sender = (
                        match.candidate.display_name if message.sender == "candidate" else "You"
                    )
                    color = MUTED if message.sender == "candidate" else TEXT
                    self._text(card, f"{sender}: {message.body}", color=color, wrap=900).pack(
                        anchor="w", pady=3
                    )
                if match.status is MatchStatus.ACTIVE:
                    local_messages = [
                        message for message in match.messages if message.sender == "local"
                    ]
                    if not local_messages:
                        self._text(
                            card,
                            "Choose a shared-ground opening. The app never sends automatically.",
                            weight="bold",
                        ).pack(anchor="w", pady=(12, 6))
                        for suggestion in build_starter_suggestions(match):
                            self._button(
                                card,
                                suggestion,
                                lambda text=suggestion, match_id=match.id: self._send_opening(
                                    match_id, text
                                ),
                            ).pack(fill="x", pady=3)
                    else:
                        composer = tk.Text(card, height=3, wrap="word", font=("Helvetica Neue", 12))
                        composer.pack(fill="x", pady=(12, 6))
                        row = tk.Frame(card, bg=CARD)
                        row.pack(fill="x")
                        self._button(
                            row,
                            "Send local message",
                            lambda match_id=match.id, widget=composer: self._send_free(
                                match_id, widget
                            ),
                            primary=True,
                        ).pack(side="left", padx=(0, 8))
                        self._button(
                            row,
                            "Receive synthetic reply",
                            lambda match_id=match.id: self._receive_reply(match_id),
                        ).pack(side="left")
            self._render_deepen_panel(card, match.id)
            actions = tk.Frame(card, bg=CARD)
            actions.pack(fill="x", pady=(14, 0))
            if match.status is MatchStatus.ACTIVE:
                self._button(
                    actions,
                    "Unmatch",
                    lambda match_id=match.id: self._unmatch(match_id),
                    danger=True,
                ).pack(side="left", padx=(0, 8))
            if match.status is not MatchStatus.BLOCKED:
                self._button(
                    actions,
                    "Block and purge",
                    lambda match_id=match.id: self._block(match_id),
                    danger=True,
                ).pack(side="left")

    def _render_deepen_panel(self, parent: tk.Widget, match_id: str) -> None:
        phase = self.session.phase_for(match_id)
        panel = tk.Frame(parent, bg=PANEL, padx=14, pady=14)
        panel.pack(fill="x", pady=(16, 0))
        self._text(panel, "Deepen Connection", size=18, weight="bold", bg=PANEL).pack(anchor="w")
        if phase.phase is RelationshipPhase.ENDED:
            self._text(
                panel,
                "This relationship phase ended with the match. Deeper answers were cleared.",
                color=MUTED,
                bg=PANEL,
                wrap=880,
            ).pack(anchor="w", pady=(6, 0))
            return
        if phase.phase is RelationshipPhase.DEEPENED:
            self._text(
                panel,
                "MUTUAL · SYNTHETIC. This is not consent to sex, exclusivity, media, location, or a meeting.",
                color=MINT,
                weight="bold",
                bg=PANEL,
                wrap=880,
            ).pack(anchor="w", pady=6)
            for prompt in self.session.available_deepen_prompts(match_id):
                self._text(
                    panel,
                    prompt.prompt,
                    bg=PANEL,
                    weight="bold",
                    wrap=880,
                ).pack(anchor="w", pady=(10, 3))
                answer = tk.Text(panel, height=3, wrap="word", font=("Helvetica Neue", 11))
                answer.insert("1.0", phase.prompt_answers.get(prompt.id, ""))
                answer.pack(fill="x")
                row = tk.Frame(panel, bg=PANEL)
                row.pack(fill="x", pady=(5, 0))
                self._button(
                    row,
                    "Save for this session",
                    lambda prompt_id=prompt.id, widget=answer: self._save_prompt(
                        match_id, prompt_id, widget
                    ),
                    primary=True,
                ).pack(side="left", padx=(0, 6))
                self._button(
                    row,
                    "Clear",
                    lambda prompt_id=prompt.id: self._clear_prompt(match_id, prompt_id),
                ).pack(side="left")
            self._button(
                panel,
                "Return this match to casual",
                lambda: self._relationship_action(
                    lambda: self.session.return_to_casual(match_id),
                    "Returned to casual; deeper answers were cleared.",
                ),
                danger=True,
            ).pack(anchor="w", pady=(14, 0))
            return

        self._text(
            panel,
            "A reversible, match-specific transition. It never activates from messages, time, a meetup, location, purchases, or inference.",
            color=MUTED,
            bg=PANEL,
            wrap=880,
        ).pack(anchor="w", pady=6)
        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill="x")
        actions: tuple[tuple[str, Callable[[], object]], ...]
        if phase.local_requested and not phase.candidate_requested:
            self._text(
                panel,
                "Your request is pending synthetic reciprocal consent.",
                color=PINK,
                bg=PANEL,
                weight="bold",
            ).pack(anchor="w", pady=5)
            actions = (
                (
                    "Simulate accept",
                    lambda: self.session.respond_to_deepen(
                        match_id, actor="candidate", accept=True
                    ),
                ),
                (
                    "Simulate decline",
                    lambda: self.session.respond_to_deepen(
                        match_id, actor="candidate", accept=False
                    ),
                ),
                ("Withdraw", lambda: self.session.withdraw_deepen(match_id)),
            )
        elif phase.candidate_requested and not phase.local_requested:
            self._text(
                panel,
                "Synthetic counterpart requested a deeper phase.",
                color=PINK,
                bg=PANEL,
                weight="bold",
            ).pack(anchor="w", pady=5)
            actions = (
                (
                    "Accept",
                    lambda: self.session.respond_to_deepen(match_id, actor="local", accept=True),
                ),
                (
                    "Decline",
                    lambda: self.session.respond_to_deepen(match_id, actor="local", accept=False),
                ),
            )
        else:
            actions = (
                ("Ask to deepen", lambda: self.session.request_deepen(match_id, actor="local")),
                (
                    "Simulate incoming request",
                    lambda: self.session.request_deepen(match_id, actor="candidate"),
                ),
            )
        for index, (label, action) in enumerate(actions):
            self._button(
                row,
                label,
                lambda operation=action: self._relationship_action(
                    operation, "Relationship-phase state updated — synthetic."
                ),
                primary=index == 0,
            ).pack(side="left", padx=(0, 7))

    def _render_profile(self) -> None:
        card = self._card("My local R&D profile")
        self._text(
            card,
            "Only these presentation fields, mock cosmetics, haptics, and a safe last tab are written locally. The file is unencrypted.",
            color=MUTED,
            wrap=940,
        ).pack(anchor="w", pady=(0, 12))
        state = self.session.local_state
        display_name = self._field(card, "Display name", state.profile.display_name)
        pronouns = self._field(card, "Pronouns (optional)", state.profile.pronouns)
        self._text(card, "About", weight="bold").pack(anchor="w", pady=(10, 4))
        about = tk.Text(card, height=6, wrap="word", font=("Helvetica Neue", 12))
        about.insert("1.0", state.profile.about)
        about.pack(fill="x")

        def save_profile() -> None:
            self.session.update_profile(
                display_name=display_name.get(),
                about=about.get("1.0", "end").strip(),
                pronouns=pronouns.get(),
            )
            messagebox.showinfo("Saved", "Approved local profile fields were saved.")
            self._show_shell()

        self._button(card, "Save approved fields", save_profile, primary=True).pack(
            anchor="w", pady=(12, 0)
        )
        settings = self._card("Local settings and persistence boundary")
        haptics = tk.BooleanVar(value=state.ui.haptics_enabled)
        self._dynamic_variables.append(haptics)
        tk.Checkbutton(
            settings,
            text="Haptic feedback preference (does not enable Bluetooth)",
            variable=haptics,
            command=lambda: self.session.set_haptics(haptics.get()),
            bg=CARD,
            fg=TEXT,
            selectcolor=PANEL,
            activebackground=CARD,
            activeforeground=TEXT,
        ).pack(anchor="w")
        self._text(
            settings,
            "Excluded: birth date, adult gate, intent, boundaries, ranking, questionnaire answers, decisions, likes, matches, messages, phases, deeper answers, blocks, proximity, location, identifiers, keys, payments, and the Matches tab.",
            color=AMBER,
            wrap=930,
        ).pack(anchor="w", pady=10)
        row = tk.Frame(settings, bg=CARD)
        row.pack(fill="x")
        self._button(row, "View redacted export", self._show_export).pack(side="left", padx=(0, 8))
        self._button(row, "Reset saved profile", self._reset_profile, danger=True).pack(side="left")
        if self._export_preview:
            export = tk.Text(settings, height=10, wrap="word", font=("Menlo", 10))
            export.insert("1.0", self._export_preview)
            export.configure(state="disabled")
            export.pack(fill="x", pady=(12, 0))

    def _render_preferences(self) -> None:
        looking = self._card("Looking For")
        self._text(
            looking,
            "Private, session-only intent controls. Another person is never told why they were excluded.",
            color=MUTED,
            wrap=930,
        ).pack(anchor="w")
        self._checkbox_grid(looking, LOOKING_FOR_MODES, self.session.selected_intents)
        show = self._card("Show me")
        self._text(
            show,
            "Private feed eligibility only; gender is never a score multiplier.",
            color=MUTED,
        ).pack(anchor="w")
        self._checkbox_grid(show, GENDER_DISCOVERY_CATEGORIES, self.session.selected_genders)
        questionnaire = self._card("Alignment questionnaire")
        self._text(
            questionnaire,
            "Answers stay in memory. Purchases and protected traits never affect rank.",
            color=MUTED,
        ).pack(anchor="w", pady=(0, 8))
        for question_id, prompt, options in QUESTIONNAIRE:
            self._text(questionnaire, prompt, weight="bold", wrap=900).pack(
                anchor="w", pady=(10, 3)
            )
            value = tk.StringVar(value=self.session.questionnaire_answers.get(question_id, ""))
            self._dynamic_variables.append(value)
            row = tk.Frame(questionnaire, bg=CARD)
            row.pack(fill="x")
            for option in options:
                tk.Radiobutton(
                    row,
                    text=option,
                    variable=value,
                    value=option,
                    command=lambda qid=question_id, selected=value: (
                        self.session.questionnaire_answers.__setitem__(qid, selected.get())
                    ),
                    bg=CARD,
                    fg=TEXT,
                    selectcolor=PANEL,
                    activebackground=CARD,
                    activeforeground=TEXT,
                ).pack(side="left", padx=(0, 8))

    def _render_skin_shop(self) -> None:
        card = self._card("Skin Shop — mock catalog")
        self._text(
            card,
            "Synthetic ownership only. No charge occurs, and cosmetics never change dating reach, rank, matching, messaging, phase access, reports, or safety access.",
            color=MUTED,
            wrap=930,
        ).pack(anchor="w", pady=(0, 10))
        owned = set(self.session.local_state.cosmetics.owned_skin_ids)
        selected = self.session.local_state.cosmetics.selected_skin_id
        for skin_id, title, kind, price in SKIN_ITEMS:
            item = tk.Frame(card, bg=PANEL, padx=14, pady=12)
            item.pack(fill="x", pady=5)
            self._text(item, title, bg=PANEL, size=16, weight="bold").pack(side="left")
            self._text(item, f"{kind} · {price}", bg=PANEL, color=MUTED).pack(side="left", padx=14)
            label = (
                "Applied" if selected == skin_id else "Apply" if skin_id in owned else "Get mock"
            )
            self._button(
                item,
                label,
                lambda value=skin_id: self._skin(value),
                primary=selected != skin_id,
            ).pack(side="right")

    def _render_matched_map(self) -> None:
        card = self._card("Matched Map — consent model only")
        self._text(
            card,
            "No map tiles, coordinates, device permissions, background service, or network transport are active. Matching and Deepen Connection never share location automatically.",
            color=AMBER,
            wrap=930,
        ).pack(anchor="w", pady=(0, 12))
        self._text(
            card,
            "Choose a match-scoped grant type to inspect the decision copy. Precise modes still require a second confirmation in the domain model.",
            color=MUTED,
            wrap=930,
        ).pack(anchor="w")
        choice = tk.StringVar(value=self.session.location_choice)
        self._dynamic_variables.append(choice)
        options = tuple(mode.value for mode in LocationMode)
        tk.OptionMenu(
            card,
            choice,
            *options,
            command=lambda value: setattr(self.session, "location_choice", str(value)),
        ).pack(anchor="w", pady=10)
        self._button(
            card,
            "Review synthetic choice",
            lambda: messagebox.showinfo(
                "No location shared",
                f"Selected: {self._label(self.session.location_choice)}. This laptop build collected and transmitted no coordinates.",
            ),
        ).pack(anchor="w")

    def _set_discovery_choice(self, kind: str, value: str) -> None:
        if kind == "immediate":
            self.session.immediate_intent = value
        else:
            self.session.relational_openness = value
        self._render_active_tab()

    def _toggle_boundary(self, boundary: str, selected: bool) -> None:
        if selected:
            self.session.required_boundaries.add(boundary)
        else:
            self.session.required_boundaries.discard(boundary)
        self._render_active_tab()

    def _adjust_ranking_weight(self, dimension: str, delta: int) -> None:
        self.session.adjust_ranking_weight(dimension, delta)
        self._render_active_tab()

    def _reset_ranking_weights(self) -> None:
        self.session.reset_ranking_weights()
        self._render_active_tab()

    def _simulate_proximity(self) -> None:
        decision = self.session.simulate_proximity()
        copy = {
            "suppress": "No nearby event. The feature is off or eligibility is unavailable.",
            "buzz_only": "A generic synthetic buzz would occur, with no profile disclosure.",
            "buzz_and_prompt": "A synthetic buzz would occur. The profile stays hidden until separate approval.",
            "buzz_and_share_scoped_capability": "A short-lived synthetic capability would be considered; no Bluetooth is active.",
        }[decision.value]
        messagebox.showinfo("Synthetic proximity decision", copy)

    def _reveal(self, candidate_id: str, interaction: str) -> None:
        self.session.reveal_candidate(candidate_id, interaction)
        self._render_active_tab()

    def _interest(self, candidate_id: str) -> None:
        starter = self._starter_by_candidate.get(candidate_id, "")
        try:
            outcome = self.session.express_interest(candidate_id, starter)
        except DomainError as error:
            self._show_domain_error(error)
            return
        if outcome.get("matched") is True:
            messagebox.showinfo(
                "It’s a match — synthetic",
                "The fixture simulated reciprocal interest. No real participant action or authentication occurred.",
            )
        else:
            messagebox.showinfo(
                "Interest pending — synthetic",
                "One-sided interest created no match. Authenticated reciprocity would still be required in a real system.",
            )
        self._render_active_tab()

    def _pass(self, candidate_id: str) -> None:
        self.session.pass_candidate(candidate_id)
        self._render_active_tab()

    def _undo(self) -> None:
        outcome = self.session.undo_last_decision()
        if outcome["kind"] == "match_requires_unmatch":
            messagebox.showinfo(
                "Unmatch required", "An established match cannot be undone as a swipe."
            )
        self._render_active_tab()

    def _send_opening(self, match_id: str, text: str) -> None:
        match = self.session.conversations.matches[match_id]
        try:
            self.session.send_message(match_id, text, match.starter_tag)
        except DomainError as error:
            self._show_domain_error(error)
            return
        self._render_active_tab()

    def _send_free(self, match_id: str, widget: tk.Text) -> None:
        try:
            self.session.send_message(match_id, widget.get("1.0", "end").strip())
        except DomainError as error:
            self._show_domain_error(error)
            return
        self._render_active_tab()

    def _receive_reply(self, match_id: str) -> None:
        try:
            self.session.receive_synthetic_reply(
                match_id, "This is a deterministic synthetic reply for the local research session."
            )
        except DomainError as error:
            self._show_domain_error(error)
            return
        self._render_active_tab()

    def _unmatch(self, match_id: str) -> None:
        if messagebox.askyesno("Unmatch?", "Sending will stop immediately."):
            self.session.unmatch(match_id)
            self._render_active_tab()

    def _block(self, match_id: str) -> None:
        if messagebox.askyesno(
            "Block and purge?",
            "Visible messages and shared-ground context will be purged, and rediscovery suppressed.",
        ):
            self.session.block(match_id)
            self._render_active_tab()

    def _relationship_action(self, action: Callable[[], object], success: str) -> None:
        try:
            action()
        except DomainError as error:
            self._show_domain_error(error)
            return
        messagebox.showinfo("Synthetic phase update", success)
        self._render_active_tab()

    def _save_prompt(self, match_id: str, prompt_id: str, widget: tk.Text) -> None:
        try:
            self.session.answer_deepen_prompt(match_id, prompt_id, widget.get("1.0", "end").strip())
        except DomainError as error:
            self._show_domain_error(error)
            return
        self._render_active_tab()

    def _clear_prompt(self, match_id: str, prompt_id: str) -> None:
        try:
            self.session.clear_deepen_answer(match_id, prompt_id)
        except DomainError as error:
            self._show_domain_error(error)
            return
        self._render_active_tab()

    def _show_export(self) -> None:
        self._export_preview = self.session.export_saved_profile()
        self._render_active_tab()

    def _reset_profile(self) -> None:
        if messagebox.askyesno(
            "Reset saved profile?", "Only approved local fields and mock cosmetics will be removed."
        ):
            self.session.reset_saved_profile()
            self._export_preview = ""
            self._show_shell()

    def _skin(self, skin_id: str) -> None:
        self.session.acquire_or_apply_skin(skin_id)
        self._render_active_tab()

    def _checkbox_grid(
        self, parent: tk.Widget, values: tuple[str, ...], selected_values: set[str]
    ) -> None:
        grid = tk.Frame(parent, bg=CARD)
        grid.pack(fill="x", pady=8)
        for index, value in enumerate(values):
            selected = tk.BooleanVar(value=value in selected_values)
            self._dynamic_variables.append(selected)
            tk.Checkbutton(
                grid,
                text=self._label(value),
                variable=selected,
                command=lambda item=value, state=selected: self._toggle_set(
                    selected_values, item, state.get()
                ),
                bg=CARD,
                fg=TEXT,
                selectcolor=PANEL,
                activebackground=CARD,
                activeforeground=TEXT,
            ).grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 18), pady=3)

    @staticmethod
    def _toggle_set(values: set[str], item: str, selected: bool) -> None:
        if selected:
            values.add(item)
        else:
            values.discard(item)

    def _card(self, title: str) -> tk.Frame:
        if self._body is None:
            raise RuntimeError("desktop shell is not ready")
        card = tk.Frame(
            self._body,
            bg=CARD,
            padx=20,
            pady=18,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        card.pack(fill="x", pady=(0, 14))
        self._text(card, title, size=20, weight="bold").pack(anchor="w", pady=(0, 8))
        return card

    def _field(self, parent: tk.Widget, label: str, value: str) -> tk.Entry:
        self._text(parent, label, weight="bold").pack(anchor="w", pady=(8, 4))
        entry = tk.Entry(parent, font=("Helvetica Neue", 13), relief="flat")
        entry.insert(0, value)
        entry.pack(fill="x", ipady=8)
        return entry

    @staticmethod
    def _text(
        parent: tk.Widget,
        value: str,
        *,
        color: str = TEXT,
        size: int = 13,
        weight: str = "normal",
        wrap: int | None = None,
        bg: str = CARD,
    ) -> tk.Label:
        return tk.Label(
            parent,
            text=value,
            bg=bg,
            fg=color,
            font=("Helvetica Neue", size, weight),
            justify="left",
            anchor="w",
            wraplength=wrap or 0,
        )

    @staticmethod
    def _button(
        parent: tk.Widget,
        label: str,
        command: Callable[[], object],
        *,
        primary: bool = False,
        danger: bool = False,
    ) -> tk.Button:
        color = DANGER if danger else PINK if primary else PANEL
        foreground = BACKGROUND if primary or danger else TEXT
        return tk.Button(
            parent,
            text=label,
            command=command,
            bg=color,
            fg=foreground,
            activebackground=color,
            activeforeground=foreground,
            relief="flat",
            padx=13,
            pady=8,
            font=("Helvetica Neue", 11, "bold"),
            cursor="hand2",
        )

    @staticmethod
    def _label(value: object) -> str:
        return str(value).replace("_", " ")

    @staticmethod
    def _tab_label(value: str) -> str:
        return {
            "My Profile": "Profile",
            "Preferences": "Prefs",
            "Skin Shop": "Skins",
            "Matched Map": "Map",
        }.get(value, value)

    @staticmethod
    def _clear(widget: tk.Misc) -> None:
        for child in widget.winfo_children():
            child.destroy()

    @staticmethod
    def _show_domain_error(error: DomainError) -> None:
        messages = {
            "shared_ground_not_visible": "Choose one of the visible shared-ground tags first.",
            "opening_context_required": "The first message must use the selected shared-ground context.",
            "message_required": "Enter a message first.",
            "message_too_long": "Messages are limited to 500 characters.",
            "answer_required": "Enter an answer first.",
            "answer_too_long": "Deeper answers are limited to 300 characters.",
            "match_not_active": "This match is no longer active.",
        }
        messagebox.showerror("Action unavailable", messages.get(error.code, error.code))


def main() -> None:
    if not _TK_AVAILABLE:
        raise SystemExit(
            "Tkinter is unavailable. Install the matching python-tk system package or run with "
            "a Python distribution that includes Tk."
        )
    repository = LocalStateRepository(JsonFileStorageAdapter(default_state_path()))
    session = ResearchSession(repository=repository)
    root = tk.Tk()
    SwipeDatingDesktop(root, session)
    root.mainloop()


if __name__ == "__main__":
    main()
