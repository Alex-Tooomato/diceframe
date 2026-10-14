"""Capture the game projection needed by an asynchronous storyboard job."""

from copy import deepcopy
from typing import Any

from src.engine.modules import narrative_notes


def capture_storyboard_context(instance: Any) -> dict[str, Any]:
    """Copy inputs while the caller owns the run/entry fence.

    The storyboard inference owner applies its public appearance projection
    before making a model request; this snapshot is never a client response.
    """
    return {
        "current_scene": str(narrative_notes.scene(instance) or ""),
        "players": deepcopy(getattr(instance, "players", {}) or {}),
    }
