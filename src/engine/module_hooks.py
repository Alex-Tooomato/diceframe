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
# A round adjudication produced a report: handler(instance, kind, items) -> None.
ROUND_REPORT_RECORD = "round.report.record"
# Read the current round's report: handler(instance, kind) -> list | None.
# ``None`` means "not mine"; the first list answer wins.
ROUND_REPORT_READ = "round.report.read"

# Round report kinds produced by round adjudication.
REPORT_OVERREACH = "overreach"
REPORT_WORLD_LEGALITY = "world_legality"
REPORT_WORLD_EVENTS = "world_events"

HOOK_POINTS = frozenset({ROUND_RESET, ROUND_REPORT_RECORD, ROUND_REPORT_READ})

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


def record_round_report(instance: Any, kind: str, items: list) -> None:
    run(ROUND_REPORT_RECORD, instance, kind, items)


def round_report(instance: Any, kind: str) -> list:
    """The current round's ``kind`` report; empty when no module keeps it."""
    answer = ask(ROUND_REPORT_READ, instance, kind, default=[])
    return answer if isinstance(answer, list) else []
