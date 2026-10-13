"""module_hooks registry and the world_reports capability riding on it (#515)."""

from collections.abc import Iterator

import pytest

from src.engine import module_hooks
from src.engine.game_instance import GameInstance
from src.engine.modules import world_reports


@pytest.fixture
def detached_world_reports() -> Iterator[None]:
    removed = module_hooks.unregister_owner(world_reports.MODULE_NAME)
    try:
        yield
    finally:
        for point, handler in removed.items():
            module_hooks.register(point, world_reports.MODULE_NAME, handler)


@pytest.fixture
def scratch_point() -> Iterator[str]:
    point = module_hooks.ROUND_REPORT_READ
    saved = list(module_hooks._HANDLERS[point])
    module_hooks._HANDLERS[point].clear()
    try:
        yield point
    finally:
        module_hooks._HANDLERS[point][:] = saved


def test_unknown_point_and_bad_handlers_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown module hook point"):
        module_hooks.register("round.resett", "x", lambda instance: None)
    with pytest.raises(ValueError, match="owner"):
        module_hooks.register(module_hooks.ROUND_RESET, "", lambda instance: None)
    with pytest.raises(TypeError):
        module_hooks.register(module_hooks.ROUND_RESET, "x", "not callable")


def test_ask_returns_first_answer_or_default_and_reregister_replaces(scratch_point) -> None:
    assert module_hooks.ask(scratch_point, None, "k", default=["d"]) == ["d"]
    module_hooks.register(scratch_point, "a", lambda instance, kind: None)
    module_hooks.register(scratch_point, "b", lambda instance, kind: ["b1"])
    module_hooks.register(scratch_point, "c", lambda instance, kind: ["c"])
    assert module_hooks.ask(scratch_point, None, "k", default=[]) == ["b1"]
    module_hooks.register(scratch_point, "b", lambda instance, kind: ["b2"])
    assert module_hooks.owners(scratch_point) == ("a", "c", "b")
    assert module_hooks.ask(scratch_point, None, "k", default=[]) == ["c"]


def test_world_reports_registers_its_hooks() -> None:
    for point in (module_hooks.ROUND_RESET, module_hooks.ROUND_REPORT_RECORD, module_hooks.ROUND_REPORT_READ):
        assert world_reports.MODULE_NAME in module_hooks.owners(point)


def test_reports_round_trip_through_hooks_and_reset_clears_them() -> None:
    instance = GameInstance(game_key=("web", "hooks-reports", "u"))
    module_hooks.record_round_report(instance, module_hooks.REPORT_OVERREACH, [{"player": "p1"}])
    module_hooks.record_round_report(instance, module_hooks.REPORT_WORLD_EVENTS, [{"event_id": "e"}])
    assert world_reports.last_overreach(instance) == [{"player": "p1"}]
    assert module_hooks.round_report(instance, module_hooks.REPORT_WORLD_EVENTS) == [{"event_id": "e"}]
    assert module_hooks.round_report(instance, "unknown-kind") == []

    instance.reset_round_checks()

    assert module_hooks.round_report(instance, module_hooks.REPORT_OVERREACH) == []
    assert world_reports.last_world_events(instance) == []


def test_without_world_reports_the_round_keeps_working_without_reports(detached_world_reports) -> None:
    instance = GameInstance(game_key=("web", "hooks-detached", "u"))
    world_reports.replace_last_overreach(instance, [{"player": "stale"}])

    module_hooks.record_round_report(instance, module_hooks.REPORT_OVERREACH, [{"player": "p1"}])
    instance.reset_round_checks(prepared=True)

    assert module_hooks.round_report(instance, module_hooks.REPORT_OVERREACH) == []
    assert world_reports.last_overreach(instance) == [{"player": "stale"}]
