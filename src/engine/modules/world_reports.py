"""Round-scoped world adjudication reports; reset retains the existing reports.

The core flow reaches this module only through ``module_hooks`` (round reset,
report record / read), so removing it drops the reports and nothing else.
"""

from __future__ import annotations

from typing import Any

from src.engine import module_hooks
from src.engine.module_state import ModuleStateSpec, get_module_state, register_module_state

MODULE_NAME = "world_reports"
SCHEMA_VERSION = 1


def fresh() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "last_overreach": [],
        "last_world_legality": [],
        "last_world_events": [],
    }


def ensure(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return fresh()
    if raw.get("schema_version") != SCHEMA_VERSION:
        return raw
    for key in ("last_overreach", "last_world_legality", "last_world_events"):
        if not isinstance(raw.get(key), list):
            raw[key] = []
    return raw


def last_overreach(instance: Any) -> list:
    return get_module_state(instance, MODULE_NAME)["last_overreach"]


def replace_last_overreach(instance: Any, value: Any) -> None:
    get_module_state(instance, MODULE_NAME)["last_overreach"] = value if isinstance(value, list) else []


def last_world_legality(instance: Any) -> list:
    return get_module_state(instance, MODULE_NAME)["last_world_legality"]


def replace_last_world_legality(instance: Any, value: Any) -> None:
    get_module_state(instance, MODULE_NAME)["last_world_legality"] = value if isinstance(value, list) else []


def last_world_events(instance: Any) -> list:
    return get_module_state(instance, MODULE_NAME)["last_world_events"]


def replace_last_world_events(instance: Any, value: Any) -> None:
    get_module_state(instance, MODULE_NAME)["last_world_events"] = value if isinstance(value, list) else []


_REPORTS = {
    module_hooks.REPORT_OVERREACH: "last_overreach",
    module_hooks.REPORT_WORLD_LEGALITY: "last_world_legality",
    module_hooks.REPORT_WORLD_EVENTS: "last_world_events",
}


def clear_round(instance: Any) -> None:
    for key in _REPORTS.values():
        get_module_state(instance, MODULE_NAME)[key].clear()


def record_report(instance: Any, kind: str, items: Any) -> None:
    key = _REPORTS.get(kind)
    if key is not None:
        get_module_state(instance, MODULE_NAME)[key] = list(items) if isinstance(items, list) else []


def read_report(instance: Any, kind: str) -> list | None:
    key = _REPORTS.get(kind)
    return None if key is None else get_module_state(instance, MODULE_NAME)[key]


SPEC = ModuleStateSpec(name=MODULE_NAME, schema_version=SCHEMA_VERSION, fresh=fresh, ensure=ensure)
register_module_state(SPEC)
module_hooks.register(module_hooks.ROUND_RESET, MODULE_NAME, clear_round)
module_hooks.register(module_hooks.ROUND_REPORT_RECORD, MODULE_NAME, record_report)
module_hooks.register(module_hooks.ROUND_REPORT_READ, MODULE_NAME, read_report)
