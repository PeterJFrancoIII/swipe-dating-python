from __future__ import annotations

from pathlib import Path

from swipe_dating.desktop.app import SwipeDatingDesktop, default_state_path, main


def test_desktop_module_imports_without_opening_a_window() -> None:
    assert SwipeDatingDesktop.__name__ == "SwipeDatingDesktop"
    assert callable(SwipeDatingDesktop._render_candidate_boundaries)
    assert callable(SwipeDatingDesktop._render_profile_readiness)
    assert callable(main)
    assert default_state_path().name == "local-state.json"
    assert isinstance(default_state_path(), Path)
