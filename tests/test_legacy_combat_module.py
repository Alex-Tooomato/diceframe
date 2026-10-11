"""Combat turn view (derived, read-only) and the stored combat_enemies slot."""

from copy import deepcopy
from dataclasses import fields
from types import SimpleNamespace

import pytest

import src.rulesets.dnd2024  # noqa: F401  (registers the D&D combat view projector)
from src.engine.game_instance import GameInstance
from src.engine.module_state import ModuleStateError
from src.engine.modules import legacy_combat as module
from src.engine.modules import ruleset_runtime
from src.migrations.instance import (
    CURRENT_INSTANCE_SCHEMA_VERSION, _migrate_v32_to_v33, _migrate_v41_to_v42,
    migrate_game_state_payload,
)

DND_RUNTIME = "core:dnd2024"
VIEW_FIELDS = ("combat_state", "combat_active", "initiative_order", "initiative_current")
NEUTRAL = {"combat_state": "none", "combat_active": False, "initiative_order": [], "initiative_current": 0}
ENEMIES = [{"name": "guard", "hp": 12}]
LEGACY_VALUES = {
    "combat_active": True,
    "combat_enemies": deepcopy(ENEMIES),
    "combat_state": "active",
    "initiative_order": ["u1", "guard"],
    "initiative_current": 1,
}


def new_instance(**kwargs):
    return GameInstance(game_key=("test", "legacy-combat", "bot"), **kwargs)


def bind_dnd_combat(instance, combat=None):
    """Bind the D&D runtime and give it an encounter authority (test fixture)."""
    ruleset_runtime.replace_binding(instance, {
        "id": DND_RUNTIME, "version": 1, "content_version": "test", "state_schema_version": 1,
    })
    state = {"state_schema_version": 1}
    if combat is not None:
        state["combat"] = combat
    ruleset_runtime.replace_state(instance, state)
    return instance


ACTIVE_COMBAT = {"status": "active", "initiative": ["player:u1", "enemy:goblin"], "turn_index": 1}


# ---------- derived view --------------------------------------------------


def test_unbound_instance_reads_the_neutral_view_without_materializing_slots():
    instance = SimpleNamespace(modules={})
    for name, expected in NEUTRAL.items():
        assert getattr(module, name)(instance) == expected
    assert module.view(instance) == NEUTRAL
    assert instance.modules == {}


@pytest.mark.parametrize("runtime_id", ["core:unknown", "", "core:coc7"])
def test_runtime_without_projector_is_neutral_even_with_stored_combat(runtime_id):
    instance = new_instance()
    ruleset_runtime.replace_binding(instance, {"id": runtime_id} if runtime_id else {})
    ruleset_runtime.replace_state(instance, {"combat": dict(ACTIVE_COMBAT)})
    assert module.view(instance) == NEUTRAL


@pytest.mark.parametrize("status,expected_state", [
    ("active", "active"), ("ended", "none"), ("none", "none"), (None, "none"),
])
def test_dnd_view_projects_ruleset_authority_without_writing(status, expected_state):
    instance = bind_dnd_combat(new_instance(), {"status": status, "initiative": ["player:u1"], "turn_index": "2"})
    before = deepcopy(instance.modules)
    authority = ruleset_runtime.state(instance)["combat"]
    assert module.combat_state(instance) == expected_state
    assert module.combat_active(instance) is (status == "active")
    assert module.initiative_order(instance) == ["player:u1"]
    assert module.initiative_order(instance) is not authority["initiative"]
    assert module.initiative_current(instance) == 2
    assert instance.modules == before
    assert ruleset_runtime.state(instance)["combat"] is authority


@pytest.mark.parametrize("combat", [None, "corrupt", {}, {"turn_index": "x", "initiative": None}])
def test_dnd_view_without_a_usable_encounter_is_neutral(combat):
    instance = bind_dnd_combat(new_instance(), combat)
    assert module.view(instance) == NEUTRAL


def test_view_returns_fresh_lists_not_live_storage():
    instance = bind_dnd_combat(new_instance(), deepcopy(ACTIVE_COMBAT))
    order = module.initiative_order(instance)
    order.append("intruder")
    module.view(instance)["initiative_order"].clear()
    assert module.initiative_order(instance) == ACTIVE_COMBAT["initiative"]
    assert ruleset_runtime.state(instance)["combat"]["initiative"] == ACTIVE_COMBAT["initiative"]


def test_view_follows_authority_changes_immediately():
    instance = bind_dnd_combat(new_instance(), deepcopy(ACTIVE_COMBAT))
    assert module.combat_state(instance) == "active"
    ruleset_runtime.state(instance)["combat"]["status"] = "ended"
    assert module.combat_state(instance) == "none"
    assert module.combat_active(instance) is False


def test_view_ignores_the_legacy_combat_slot_entirely():
    instance = bind_dnd_combat(new_instance(), deepcopy(ACTIVE_COMBAT))
    instance.modules[module.MODULE_NAME] = {"schema_version": 99, "opaque": True}
    assert module.combat_state(instance) == "active"
    assert instance.modules[module.MODULE_NAME] == {"schema_version": 99, "opaque": True}


# ---------- projector registry --------------------------------------------


def test_projector_registry_resolves_by_bound_runtime_and_normalizes(monkeypatch):
    monkeypatch.setattr(module, "_PROJECTORS", dict(module._PROJECTORS))
    calls = []

    def projector(instance):
        calls.append(instance)
        return {"combat_state": "active", "combat_active": 1, "initiative_order": ("a",), "initiative_current": True}

    module.register_combat_projector(" test:runtime ", projector)
    assert module.combat_projector_for("test:runtime") is projector
    instance = new_instance()
    ruleset_runtime.replace_binding(instance, {"id": "test:runtime"})
    # Bool is not an int turn index; tuples are copied into a fresh list.
    assert module.view(instance) == {
        "combat_state": "active", "combat_active": True, "initiative_order": ["a"], "initiative_current": 0,
    }
    assert calls == [instance]
    module.register_combat_projector("test:runtime", lambda instance: None)
    assert module.view(instance) == NEUTRAL


@pytest.mark.parametrize("runtime_id", ["", "  ", None])
def test_projector_registry_rejects_blank_runtime_ids(runtime_id):
    with pytest.raises(ValueError, match="runtime id"):
        module.register_combat_projector(runtime_id, lambda instance: None)


def test_projector_registry_rejects_non_callables():
    with pytest.raises(TypeError):
        module.register_combat_projector("test:runtime", "not callable")


def test_dnd_runtime_registers_its_projector_on_import():
    from src.rulesets.dnd2024.runtime import Dnd2024Runtime, project_combat_view

    assert module.combat_projector_for(Dnd2024Runtime.runtime_id) is project_combat_view


def test_bound_dnd_instance_reports_view_after_import_only(tmp_path):
    """A fresh interpreter that only imports the runtime package projects D&D combat."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = (
        "import src.rulesets.dnd2024\n"
        "from src.engine.game_instance import GameInstance\n"
        "from src.engine.modules import legacy_combat, ruleset_runtime\n"
        "i = GameInstance(game_key=('t','v','b'))\n"
        "ruleset_runtime.replace_binding(i, {'id': 'core:dnd2024'})\n"
        "ruleset_runtime.replace_state(i, {'combat': {'status': 'active', 'initiative': ['x'], 'turn_index': 0}})\n"
        "import sys\n"
        "assert 'src.rulesets.dnd2024.combat.engine' in sys.modules\n"
        "print(legacy_combat.combat_state(i), legacy_combat.initiative_order(i))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=root, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "active ['x']"


# ---------- stored slot (schema 2: combat_enemies only) -------------------


def test_fresh_slot_holds_only_enemies():
    assert module.fresh() == {"schema_version": 2, "combat_enemies": []}
    instance = new_instance()
    assert instance.modules[module.MODULE_NAME] == module.fresh()


@pytest.mark.parametrize("value", [None, {}, "x", 3])
def test_ensure_repairs_invalid_enemies(value):
    raw = {"schema_version": 2, "combat_enemies": value}
    assert module.ensure(raw) is raw
    assert raw == {"schema_version": 2, "combat_enemies": []}


@pytest.mark.parametrize("raw", [None, [], 12, "bad"])
def test_missing_or_malformed_slots_materialize_defaults(raw):
    instance = new_instance(modules={module.MODULE_NAME: raw})
    assert instance.modules[module.MODULE_NAME] == module.fresh()
    assert module.ensure(raw) == module.fresh()
    assert module.ensure({"schema_version": 2}) == module.fresh()


def test_enemy_list_contents_are_preserved():
    raw = {"schema_version": 2, "combat_enemies": [None, 4, "opaque", {"hp": 1}]}
    enemies = raw["combat_enemies"]
    assert module.ensure(raw) is raw
    assert raw["combat_enemies"] is enemies


@pytest.mark.parametrize("raw", [{"schema_version": 1, **LEGACY_VALUES}, {"schema_version": 99, "opaque": [1]}])
def test_non_current_slot_is_preserved_and_access_fails_closed(raw):
    raw = deepcopy(raw)
    assert module.ensure(raw) is raw
    instance = new_instance(modules={module.MODULE_NAME: raw})
    before = deepcopy(instance.modules)
    with pytest.raises(ModuleStateError):
        module.combat_enemies(instance)
    with pytest.raises(ModuleStateError):
        module.replace_combat_enemies(instance, [])
    with pytest.raises(ModuleStateError, match="unsupported legacy_combat module schema"):
        module.require_writable(instance)
    assert instance.modules == before
    encoded = instance.to_dict()
    assert encoded["modules"][module.MODULE_NAME] == raw


def test_future_instance_version_is_rejected():
    with pytest.raises(ValueError, match="unsupported game instance schema"):
        GameInstance.from_dict({"instance_schema_version": CURRENT_INSTANCE_SCHEMA_VERSION + 1})


def test_enemies_use_live_slot_and_roundtrip_has_one_storage_owner():
    instance = new_instance()
    other = new_instance()
    module.replace_combat_enemies(instance, deepcopy(ENEMIES))
    slot = instance.modules[module.MODULE_NAME]
    assert slot is not other.modules[module.MODULE_NAME]
    assert not LEGACY_VALUES.keys() & {item.name for item in fields(instance)}
    assert not LEGACY_VALUES.keys() & vars(instance).keys()
    assert module.combat_enemies(instance) is slot["combat_enemies"]
    assert module.combat_enemies(instance) is not module.combat_enemies(other)
    module.combat_enemies(instance)[0]["hp"] -= 3
    encoded = instance.to_dict()
    assert not LEGACY_VALUES.keys() & encoded.keys()
    assert encoded["modules"][module.MODULE_NAME] == {"schema_version": 2, "combat_enemies": [{"name": "guard", "hp": 9}]}
    restored = GameInstance.from_dict(deepcopy(encoded))
    assert restored.modules[module.MODULE_NAME] == slot
    instance.replace_persisted_state_from(restored)
    assert instance.modules[module.MODULE_NAME] == slot


def test_retired_combat_facades_are_not_game_instance_attributes():
    instance = new_instance()
    for key in LEGACY_VALUES:
        assert not hasattr(GameInstance, key)
        assert not hasattr(instance, key)
        with pytest.raises(AttributeError, match="was removed"):
            setattr(instance, key, LEGACY_VALUES[key])
    for name in ("begin_combat", "end_combat"):
        assert not hasattr(GameInstance, name)
    for name in ("begin", "end", "project_from_ruleset", "restore_from_transaction",
                 *(f"replace_{field}" for field in VIEW_FIELDS)):
        assert not hasattr(module, name)
    assert instance.modules[module.MODULE_NAME] == module.fresh()


# ---------- restore / reset -----------------------------------------------


def test_entity_restore_only_touches_enemies_and_deepcopies():
    instance = bind_dnd_combat(new_instance(), deepcopy(ACTIVE_COMBAT))
    module.replace_combat_enemies(instance, deepcopy(ENEMIES))
    authority = deepcopy(ruleset_runtime.state(instance))
    snapshot = {
        "combat_enemies": [{"hp": 7}], "combat_state": "none",
        "combat_active": False, "initiative_order": [], "initiative_current": 0,
    }
    module.restore_from_entity_snapshot(instance, snapshot)
    assert module.combat_enemies(instance) == [{"hp": 7}]
    assert module.combat_enemies(instance) is not snapshot["combat_enemies"]
    module.combat_enemies(instance)[0]["hp"] = 1
    assert snapshot["combat_enemies"][0]["hp"] == 7
    # The stored turn keys of the snapshot are informational; authority wins.
    assert module.combat_state(instance) == "active"
    assert ruleset_runtime.state(instance) == authority
    assert instance.modules[module.MODULE_NAME] == {"schema_version": 2, "combat_enemies": [{"hp": 1}]}


def test_entity_restore_defaults_enemies_to_empty():
    instance = new_instance()
    module.replace_combat_enemies(instance, deepcopy(ENEMIES))
    module.restore_from_entity_snapshot(instance, {})
    assert instance.modules[module.MODULE_NAME] == module.fresh()


def test_transaction_restore_takes_view_from_restored_ruleset_state():
    instance = bind_dnd_combat(new_instance(), deepcopy(ACTIVE_COMBAT))
    instance.players = {}
    module.replace_combat_enemies(instance, deepcopy(ENEMIES))
    snapshot = {
        "ruleset_state": {"state_schema_version": 1, "combat": {"status": "ended", "initiative": [], "turn_index": 0}},
        "event_ledger": [],
        "players": {},
        # Stale stored copies in the snapshot must not override authority.
        "combat_state": "active", "combat_active": True,
        "initiative_order": ["stale"], "initiative_current": 5,
    }
    instance.restore_ruleset_transaction(snapshot)
    assert module.view(instance) == NEUTRAL
    assert module.combat_enemies(instance) == ENEMIES
    snapshot["ruleset_state"]["combat"] = deepcopy(ACTIVE_COMBAT)
    snapshot["combat_state"] = "none"
    instance.restore_ruleset_transaction(snapshot)
    assert module.combat_state(instance) == "active"
    assert module.initiative_order(instance) == ACTIVE_COMBAT["initiative"]


@pytest.mark.asyncio
async def test_reset_clears_enemies_preserving_list_identity_and_view_turns_neutral():
    instance = bind_dnd_combat(new_instance(), deepcopy(ACTIVE_COMBAT))
    module.replace_combat_enemies(instance, deepcopy(ENEMIES))
    enemies = module.combat_enemies(instance)
    await instance.reset()
    assert instance.modules[module.MODULE_NAME] == module.fresh()
    assert module.combat_enemies(instance) is enemies
    assert module.view(instance) == NEUTRAL


# ---------- migrations ----------------------------------------------------


def test_v32_payload_migrates_through_to_enemies_only_slot():
    original = {"instance_schema_version": 32, **deepcopy(LEGACY_VALUES), "opaque": {"items": [1]}}
    before = deepcopy(original)
    migrated = migrate_game_state_payload(original)
    assert original == before
    assert migrated["instance_schema_version"] == CURRENT_INSTANCE_SCHEMA_VERSION
    assert migrated["modules"][module.MODULE_NAME] == {"schema_version": 2, "combat_enemies": ENEMIES}
    assert not LEGACY_VALUES.keys() & migrated.keys()
    assert migrate_game_state_payload(migrated) == migrated
    step = _migrate_v32_to_v33(deepcopy(original))
    assert _migrate_v32_to_v33(deepcopy(step)) == step
    migrated["modules"][module.MODULE_NAME]["combat_enemies"][0]["hp"] = 1
    assert original == before


def v41_payload(slot, **extra):
    modules = {} if slot is None else {module.MODULE_NAME: slot}
    return {"game_key": ["test", "legacy-combat", "bot"], "state": "waiting",
            "instance_schema_version": 41, "modules": modules, **extra}


def test_v41_to_v42_strips_stored_turn_copies_and_keeps_enemies():
    original = v41_payload({"schema_version": 1, **deepcopy(LEGACY_VALUES)})
    before = deepcopy(original)
    migrated = migrate_game_state_payload(original)
    assert original == before
    assert migrated["instance_schema_version"] == 42 == CURRENT_INSTANCE_SCHEMA_VERSION
    assert migrated["modules"][module.MODULE_NAME] == {"schema_version": 2, "combat_enemies": ENEMIES}
    assert migrate_game_state_payload(migrated) == migrated
    step = _migrate_v41_to_v42(deepcopy(original))
    assert _migrate_v41_to_v42(deepcopy(step)) == step


@pytest.mark.parametrize("slot,expected", [
    (None, {"schema_version": 2, "combat_enemies": []}),
    ("corrupt", {"schema_version": 2, "combat_enemies": []}),
    ({"schema_version": 1}, {"schema_version": 2, "combat_enemies": []}),
    ({"schema_version": 1, "combat_enemies": {"bad": 1}}, {"schema_version": 2, "combat_enemies": []}),
    ({"schema_version": 2, "combat_enemies": [1]}, {"schema_version": 2, "combat_enemies": [1]}),
    ({"schema_version": 99, "opaque": [1]}, {"schema_version": 99, "opaque": [1]}),
])
def test_v41_to_v42_slot_shapes(slot, expected):
    migrated = migrate_game_state_payload(v41_payload(deepcopy(slot)))
    assert migrated["modules"][module.MODULE_NAME] == expected


def test_v41_dnd_save_with_active_stored_combat_reads_view_from_ruleset_state():
    ruleset_slot = {
        "schema_version": 1,
        "binding": {"id": DND_RUNTIME, "version": 1, "content_version": "test", "state_schema_version": 1},
        "state": {"state_schema_version": 1, "combat": {"status": "active", "initiative": ["player:u9"], "turn_index": 0}},
        "event_ledger": [],
    }
    # The stored copies disagree with the authority on purpose.
    payload = v41_payload({"schema_version": 1, **deepcopy(LEGACY_VALUES)})
    payload["modules"]["ruleset_runtime"] = ruleset_slot
    restored = GameInstance.from_dict(payload)
    assert restored.modules[module.MODULE_NAME] == {"schema_version": 2, "combat_enemies": ENEMIES}
    assert module.view(restored) == {
        "combat_state": "active", "combat_active": True,
        "initiative_order": ["player:u9"], "initiative_current": 0,
    }


def test_v41_non_dnd_save_with_active_stored_combat_reads_neutral():
    restored = GameInstance.from_dict(v41_payload({"schema_version": 1, **deepcopy(LEGACY_VALUES)}))
    assert module.view(restored) == NEUTRAL
    assert module.combat_enemies(restored) == ENEMIES
