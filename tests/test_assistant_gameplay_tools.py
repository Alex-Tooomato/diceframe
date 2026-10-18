from types import SimpleNamespace

import pytest

from src.webui.services.assistant_gameplay_tools import GameplayToolDependencies, gameplay_tools
from src.engine.participant_view import resolve_viewer


class _Game:
    run_id = "run-1"
    state = "active_action"
    players = {"alice": {"character_name": "Alice"}}

    def __init__(self):
        self.progress = {"active_nodes": ["opening"]}

    def get_character_sheet(self, uid):
        return {"ruleset_revision": 3, "hp": 8}


def _fixture():
    game = _Game()
    viewers = {"alice": SimpleNamespace(is_member=True, is_gm=False, uid="alice"),
               "gm": SimpleNamespace(is_member=True, is_gm=True, uid="gm")}
    recovery = SimpleNamespace(
        get=lambda key, viewer: {"ok": True, "revision": 4, "sources": []},
        mutate=lambda key, viewer, action, body: {"ok": True, "body": body},
    )
    deps = GameplayToolDependencies(
        get_game=lambda key: game if key == "game" else None,
        viewer_for=lambda instance, owner: viewers[owner],
        recovery=recovery,
        complete_adventure_node=lambda *args, **kwargs: {"ok": True},
    )
    return game, viewers, recovery, gameplay_tools(deps)


def test_gameplay_tools_are_importable_and_expose_authoritative_operations():
    _game, _viewers, _recovery, tools = _fixture()
    names = {tool.name for tool in tools}
    assert {"get_gameplay_status", "request_adventure_choice", "complete_adventure_node",
            "mutate_resource_recovery"}.issubset(names)


def test_gm_operation_rejects_non_gm_before_handler():
    _game, _viewers, _recovery, tools = _fixture()
    tool = next(item for item in tools if item.name == "complete_adventure_node")
    with pytest.raises(PermissionError, match="GM"):
        tool.guard({"game_key": "game", "run_id": "run-1", "node_id": "opening"}, "alice")


def test_recovery_guard_changes_when_authoritative_revision_changes():
    _game, _viewers, recovery, tools = _fixture()
    tool = next(item for item in tools if item.name == "mutate_resource_recovery")
    args = {"game_key": "game", "run_id": "run-1", "action": "request", "expected_revision": 4}
    first = tool.guard(args, "alice")
    recovery.get = lambda key, viewer: {"ok": True, "revision": 5, "sources": []}
    assert first != tool.guard(args, "alice")


@pytest.mark.asyncio
async def test_recovery_write_generates_operation_id_and_preserves_run_revision():
    _game, _viewers, _recovery, tools = _fixture()
    tool = next(item for item in tools if item.name == "mutate_resource_recovery")
    result = await tool.handler({"game_key": "game", "run_id": "run-1", "action": "request",
                                 "expected_revision": 4, "payload": {"kind": "overnight"}}, "alice")
    assert result["body"]["run_id"] == "run-1"
    assert result["body"]["expected_revision"] == 4
    assert len(result["body"]["operation_id"]) == 32


@pytest.mark.asyncio
async def test_recovery_payload_cannot_replace_authority_fields():
    _game, _viewers, _recovery, tools = _fixture()
    tool = next(item for item in tools if item.name == "mutate_resource_recovery")
    with pytest.raises(ValueError, match="reserved fields"):
        await tool.handler({"game_key": "game", "run_id": "run-1", "action": "request",
                            "expected_revision": 4,
                            "payload": {"run_id": "forged", "kind": "overnight"}}, "alice")


@pytest.mark.asyncio
async def test_real_adventure_command_adapter_enforces_gm_and_run_fences(tmp_path):
    from src.engine.modules import adventure_runtime_state
    from src.webui.services import adventure_commands, adventure_runtime
    from tests.test_adventure_choices import installed_choice

    runtime_deps, game = installed_choice(tmp_path)
    game.gm_uid = "gm"
    async def save(_instance):
        return None
    async def binding():
        return None
    command_deps = adventure_commands.AdventureCommandDependencies(
        save=save,
        admission=lambda: None,
        binding=binding,
        complete=lambda target, node, recipient, actor, choice_id="": adventure_runtime.complete_adventure_node(
            runtime_deps, target, node, choice_id=choice_id),
        request_choice=lambda target, node, choice, actor: adventure_runtime.request_adventure_choice(
            runtime_deps, target, node, choice, actor),
    )

    async def command(instance, body, actor, is_gm):
        return await adventure_commands.execute(command_deps, instance, body, actor, is_gm=is_gm)

    deps = GameplayToolDependencies(
        get_game=lambda key: game,
        viewer_for=lambda instance, owner: resolve_viewer(
            instance, user_id=owner, owner_authenticated=False, player_preview=False),
        adventure_command=command,
    )
    tools = gameplay_tools(deps)
    complete = next(tool for tool in tools if tool.name == "complete_adventure_node")
    args = {"game_key": "game", "run_id": game.run_id, "node_id": "gate", "choice_id": "bridge_route"}
    with pytest.raises(PermissionError):
        complete.guard(args, "alice")
    with pytest.raises(ValueError, match="stale"):
        await complete.handler({**args, "run_id": "other"}, "gm")

    result = await complete.handler(args, "gm")
    assert result["ok"]
    assert adventure_runtime_state.progress(game)["active_nodes"] == ["bridge"]
    # A second dispatch cannot duplicate the completed node or any outcome.
    second = await complete.handler(args, "gm")
    assert not second["ok"]
