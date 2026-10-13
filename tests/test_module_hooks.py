"""module_hooks registry and the world_reports capability riding on it (#515)."""

from collections.abc import Iterator

import pytest

from src.engine import module_hooks
from src.engine.game_instance import GameInstance
from src.engine.health import health_payload, mark_health_event, record_health_event
from src.engine.modules import health, lorebook_runtime, round_presentation, world_reports


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


@pytest.fixture
def detached_round_presentation() -> Iterator[None]:
    removed = module_hooks.unregister_owner(round_presentation.MODULE_NAME)
    try:
        yield
    finally:
        for point, handler in removed.items():
            module_hooks.register(point, round_presentation.MODULE_NAME, handler)


def test_round_presentation_round_trips_through_game_instance() -> None:
    instance = GameInstance(game_key=("web", "hooks-presentation", "u"))
    instance.set_quick_actions(["look", " ", "run"])
    instance.add_gm_directive({"id": "d1"})
    instance.add_gm_directive({"id": "d2"})
    instance.record_combat_result({"hit": True})
    instance.set_state_update_recap({"hp": 1})
    instance.set_token_budget_bump(100, 200)

    assert round_presentation.quick_actions(instance) == ["look", "run"]
    assert module_hooks.round_report_value(instance, module_hooks.REPORT_STATE_UPDATE) == {"hp": 1}
    instance.consume_gm_directives({"d1"})
    assert round_presentation.gm_directives(instance) == [{"id": "d2"}]

    instance.begin_round_processing()
    assert round_presentation.pending_combat_results(instance) == []
    assert round_presentation.last_token_budget_bump(instance) is None
    assert round_presentation.quick_actions(instance) == ["look", "run"]


def test_without_round_presentation_the_extras_are_dropped(detached_round_presentation) -> None:
    instance = GameInstance(game_key=("web", "hooks-presentation-off", "u"))
    instance.set_quick_actions(["look"])
    instance.add_gm_directive({"id": "d1"})
    instance.record_combat_result({"hit": True})
    instance.set_state_update_recap({"hp": 1})
    instance.consume_gm_directives({"d1"})
    instance.begin_round_processing()

    assert module_hooks.round_report(instance, module_hooks.REPORT_QUICK_ACTIONS) == []
    assert module_hooks.round_report(instance, module_hooks.REPORT_GM_DIRECTIVES) == []
    assert module_hooks.round_report_value(instance, module_hooks.REPORT_STATE_UPDATE) is None
    assert round_presentation.quick_actions(instance) == []


def test_lorebook_timers_tick_at_round_begin_and_clear_on_reset() -> None:
    instance = GameInstance(game_key=("web", "hooks-lorebook", "u"))
    # Pre-v2 timer shape, which the tick still supports.
    lorebook_runtime.timers(instance).update({"e1": {"remaining": 2}, "e2": {"remaining": 1}})

    instance.begin_round_processing()

    assert lorebook_runtime.timers(instance) == {"e1": {"remaining": 1}}
    assert module_hooks.round_report_value(instance, module_hooks.REPORT_LOREBOOK_TIMERS) is lorebook_runtime.timers(instance)
    module_hooks.run(module_hooks.INSTANCE_RESET, instance)
    assert lorebook_runtime.timers(instance) == {}


def test_without_lorebook_runtime_entries_have_no_timers() -> None:
    removed = module_hooks.unregister_owner(lorebook_runtime.MODULE_NAME)
    try:
        instance = GameInstance(game_key=("web", "hooks-lorebook-off", "u"))
        lorebook_runtime.timers(instance).update({"e1": {"remaining": 2}})
        instance.begin_round_processing()
        module_hooks.run(module_hooks.INSTANCE_RESET_PREFLIGHT, instance)

        assert module_hooks.round_report_value(instance, module_hooks.REPORT_LOREBOOK_TIMERS) is None
        assert lorebook_runtime.timers(instance) == {"e1": {"remaining": 2}}
    finally:
        for point, handler in removed.items():
            module_hooks.register(point, lorebook_runtime.MODULE_NAME, handler)


def test_health_events_round_trip_and_reset() -> None:
    instance = GameInstance(game_key=("web", "hooks-health", "u"))
    event = record_health_event(instance, "llm", "TIMEOUT", "error", "LLM timed out")
    assert health.health_events(instance) == [event]
    assert health.health_status(instance)["llm"] == "error"
    assert mark_health_event(instance, event["id"], resolved=True)
    assert health_payload(instance)["events"] == []

    module_hooks.run(module_hooks.INSTANCE_RESET, instance)
    assert health.health_events(instance) == [] and health.health_status(instance) == {}


def test_without_health_events_are_not_kept() -> None:
    removed = module_hooks.unregister_owner(health.MODULE_NAME)
    try:
        instance = GameInstance(game_key=("web", "hooks-health-off", "u"))
        event = record_health_event(instance, "llm", "TIMEOUT", "error", "LLM timed out")
        assert event["code"] == "TIMEOUT"
        assert not mark_health_event(instance, event["id"], resolved=True)
        assert health_payload(instance) == {"ok": True, "status": {}, "events": [], "total": 0}
        assert health.health_events(instance) == []
    finally:
        for point, handler in removed.items():
            module_hooks.register(point, health.MODULE_NAME, handler)
