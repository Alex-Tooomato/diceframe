"""Lifecycle hooks capability modules register to join the core game flow (#515).

The core flow calls a hook point; it never names the module behind it.  A
point with no registered handler is a no-op (``run``) or answers with the
caller's default (``ask``), so deleting a capability module leaves a playable
game that only lacks that capability.

Hook points are a closed set: registering an unknown point is an error, so a
typo cannot silently detach a module.  Handlers run in registration order.
This registry must not import GameInstance or any concrete module.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# reset_round_checks: handler(instance) -> None.  Clear round-scoped state.
ROUND_RESET = "round.reset"
# begin_round_processing: handler(instance) -> None.  Drop the previous
# round's short-lived presentation state.
ROUND_PROCESSING_BEGIN = "round.processing.begin"
# Before an in-place reset touches anything: handler(instance) -> None.
# Raise to refuse (e.g. an unsupported slot schema); nothing has changed yet.
INSTANCE_RESET_PREFLIGHT = "instance.reset.preflight"
# In-place game reset: handler(instance) -> None.  Clear run-scoped state.
INSTANCE_RESET = "instance.reset"
# Store module-held state by kind: handler(instance, kind, value) -> None.
STATE_RECORD = "module.state.record"
# Read module-held state by kind: handler(instance, kind) -> value | None.
# ``None`` means "not mine / nothing stored"; the first other answer wins.
STATE_READ = "module.state.read"

# State kinds.  List-valued unless noted; the owning module answers for its kinds.
OVERREACH = "overreach"
WORLD_LEGALITY = "world_legality"
WORLD_EVENTS = "world_events"
QUICK_ACTIONS = "quick_actions"
GM_DIRECTIVES = "gm_directives"
COMBAT_RESULTS = "combat_results"
STATE_UPDATE = "state_update"  # dict | None
TOKEN_BUDGET_BUMP = "token_budget_bump"  # dict | None
# Live Lorebook timer dict (entry id -> timer); callers may mutate it.
LOREBOOK_TIMERS = "lorebook_timers"  # dict | None
# GM-visible degradation events and per-component status (not round-scoped).
HEALTH_EVENTS = "health_events"
HEALTH_STATUS = "health_status"  # dict | None
# Check reveal records (check id -> record).
CHECK_REVEALS = "check_reveals"  # dict | None
# Room away-control policy; read with ``ask(STATE_READ, ..., default=...)``.
AWAY_CONTROL_POLICY = "away_control_policy"  # str | None
# Live private messages (uid -> list) and public table talk; callers may mutate.
PRIVATE_LOG = "private_log"  # dict | None
TABLE_TALK = "table_talk"

HOOK_POINTS = frozenset({
    ROUND_RESET, ROUND_PROCESSING_BEGIN, INSTANCE_RESET_PREFLIGHT, INSTANCE_RESET,
    STATE_RECORD, STATE_READ,
})

Handler = Callable[..., Any]
_HANDLERS: dict[str, list[tuple[str, Handler]]] = {point: [] for point in HOOK_POINTS}


def register(point: str, owner: str, handler: Handler) -> None:
    """Register ``handler`` for ``point`` on behalf of module ``owner``.

    Re-registering the same owner on the same point replaces its handler.
    """
    if point not in HOOK_POINTS:
        raise ValueError(f"unknown module hook point: {point!r}")
    if not owner:
        raise ValueError("module hook requires an owner")
    if not callable(handler):
        raise TypeError("module hook handler must be callable")
    handlers = _HANDLERS[point]
    handlers[:] = [(name, fn) for name, fn in handlers if name != owner]
    handlers.append((owner, handler))


def unregister_owner(owner: str) -> dict[str, Handler]:
    """Detach every handler of ``owner``; returns them by point for re-registration."""
    removed: dict[str, Handler] = {}
    for point, handlers in _HANDLERS.items():
        for name, fn in handlers:
            if name == owner:
                removed[point] = fn
        handlers[:] = [(name, fn) for name, fn in handlers if name != owner]
    return removed


def owners(point: str) -> tuple[str, ...]:
    return tuple(name for name, _ in _HANDLERS[point])


def run(point: str, *args: Any) -> None:
    """Call every handler for ``point``."""
    for _, handler in tuple(_HANDLERS[point]):
        handler(*args)


def ask(point: str, *args: Any, default: Any) -> Any:
    """Return the first non-``None`` handler answer, or ``default``."""
    for _, handler in tuple(_HANDLERS[point]):
        answer = handler(*args)
        if answer is not None:
            return answer
    return default


def record(instance: Any, kind: str, value: Any) -> None:
    """Store ``kind``; dropped when no module keeps it."""
    run(STATE_RECORD, instance, kind, value)


def read(instance: Any, kind: str) -> list:
    """List-valued state of ``kind``; empty when no module keeps it."""
    answer = ask(STATE_READ, instance, kind, default=[])
    return answer if isinstance(answer, list) else []


def read_value(instance: Any, kind: str) -> dict | None:
    """Dict-valued state of ``kind``; ``None`` when absent or no module keeps it."""
    answer = ask(STATE_READ, instance, kind, default=None)
    return answer if isinstance(answer, dict) else None
