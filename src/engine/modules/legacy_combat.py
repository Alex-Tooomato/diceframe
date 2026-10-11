"""Read-only combat turn view plus the retired generic ``combat_enemies`` slot.

The four turn fields ``combat_state`` / ``combat_active`` /
``initiative_order`` / ``initiative_current`` are NOT stored. They are derived
on every read from the bound ruleset's own encounter authority through a
projector the ruleset registers with :func:`register_combat_projector`
(D&D 2024 projects ``ruleset_state["combat"]``). A game whose runtime has no
registered projector (unbound, generic rulesets, unknown runtime ids) reads the
neutral view: ``"none"`` / ``False`` / ``[]`` / ``0``.

``src/engine`` must not import ``src/rulesets``; the registry is the seam.
Projectors are resolved through :func:`ruleset_runtime.bound_runtime_id`, a
read that never materializes or repairs a module slot.

The persisted slot (schema 2) only holds ``combat_enemies``. No production
code appends to it any more; it is restored by round entity snapshots and
cleared on reset until it is retired.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from src.engine.module_state import (
    ModuleStateError, ModuleStateSpec, get_module_state, register_module_state,
)
from src.engine.modules import ruleset_runtime

MODULE_NAME = "legacy_combat"
SCHEMA_VERSION = 2

CombatProjector = Callable[[Any], "Mapping[str, Any] | None"]

_PROJECTORS: dict[str, CombatProjector] = {}


def register_combat_projector(runtime_id: str, projector: CombatProjector) -> None:
    """Register the combat view projector for one ruleset runtime id.

    ``projector(instance)`` returns a mapping with any of the four view keys,
    or ``None`` for the neutral view. Re-registering a runtime id replaces it.
    """
    normalized = str(runtime_id or "").strip()
    if not normalized:
        raise ValueError("combat projector requires a runtime id")
    if not callable(projector):
        raise TypeError("combat projector must be callable")
    _PROJECTORS[normalized] = projector


def combat_projector_for(runtime_id: str) -> CombatProjector | None:
    return _PROJECTORS.get(str(runtime_id or "").strip())


def neutral_view() -> dict[str, Any]:
    return {
        "combat_state": "none",
        "combat_active": False,
        "initiative_order": [],
        "initiative_current": 0,
    }


def view(instance: Any) -> dict[str, Any]:
    """Return a fresh copy of the derived combat view (never live storage)."""
    projector = combat_projector_for(ruleset_runtime.bound_runtime_id(instance))
    raw = projector(instance) if projector is not None else None
    result = neutral_view()
    if not isinstance(raw, Mapping):
        return result
    state = raw.get("combat_state")
    result["combat_state"] = state if isinstance(state, str) and state else "none"
    result["combat_active"] = bool(raw.get("combat_active"))
    order = raw.get("initiative_order")
    result["initiative_order"] = deepcopy(list(order)) if isinstance(order, (list, tuple)) else []
    current = raw.get("initiative_current")
    result["initiative_current"] = current if type(current) is int else 0
    return result


def combat_state(instance: Any) -> str:
    return view(instance)["combat_state"]


def combat_active(instance: Any) -> bool:
    return view(instance)["combat_active"]


def initiative_order(instance: Any) -> list[Any]:
    return view(instance)["initiative_order"]


def initiative_current(instance: Any) -> int:
    return view(instance)["initiative_current"]


def fresh() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "combat_enemies": []}


def ensure(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return fresh()
    if raw.get("schema_version") != SCHEMA_VERSION:
        return raw
    if not isinstance(raw.get("combat_enemies"), list):
        raw["combat_enemies"] = []
    return raw


def require_writable(instance: Any) -> None:
    """Read-only transaction preflight; never repair or materialize a slot."""
    modules = getattr(instance, "modules", None)
    if not isinstance(modules, dict):
        raise ModuleStateError("instance has no module state container")
    slot = modules.get(MODULE_NAME)
    if not isinstance(slot, dict):
        return
    if slot.get("schema_version") != SCHEMA_VERSION:
        raise ModuleStateError(f"unsupported legacy_combat module schema: {slot.get('schema_version')!r}")


def combat_enemies(instance: Any) -> list:
    return get_module_state(instance, MODULE_NAME)["combat_enemies"]


def replace_combat_enemies(instance: Any, value: list) -> None:
    get_module_state(instance, MODULE_NAME)["combat_enemies"] = value


def restore_from_entity_snapshot(instance: Any, snapshot: dict[str, Any]) -> None:
    """Restore only the stored enemies; the turn view follows its authority."""
    require_writable(instance)
    state = get_module_state(instance, MODULE_NAME)
    state["combat_enemies"] = deepcopy(snapshot.get("combat_enemies") or [])


def reset(instance: Any) -> None:
    require_writable(instance)
    get_module_state(instance, MODULE_NAME)["combat_enemies"].clear()


SPEC = ModuleStateSpec(name=MODULE_NAME, schema_version=SCHEMA_VERSION, fresh=fresh, ensure=ensure)
register_module_state(SPEC)
