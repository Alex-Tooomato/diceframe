"""本局 GM 模型路由（user GM / 服务端 GM）：模块状态、迁移、解析矩阵、
服务边界、稳定错误码、路由权限与创建期 LLM gate 放宽。"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.commands.game_lifecycle import GameLifecycle
from src.commands.round_processor import GmModelNotConfigured, RoundProcessor
from src.engine.game_instance import GameInstance, GameState
from src.engine.modules import gm_routing as gm_routing_state
from src.engine.modules import session_stats
from src.migrations.instance import CURRENT_INSTANCE_SCHEMA_VERSION, migrate_game_state_payload
from src.webui.connection_pool import ConnectionPool
from src.webui.services import turns as turns_service
from src.webui.services.game_lifecycle import GameLifecycleDependencies, _validate_creation_gm_routing
from src.webui.services.gm_routing import GmRoutingDependencies, GmRoutingRuntime, GmRoutingService

from legacy_save_fixtures import legacy_table_payload
from webapi_harness import web_api  # noqa: F401


# --------------------------------------------------------------------- helpers

def table() -> GameInstance:
    inst = GameInstance(game_key=("web", "routing", "bot"), rule_id="freeform_fantasy")
    inst.state = GameState.ACTIVE_ACTION
    inst.round_number = 1
    inst.gm_uid = "gm1"
    inst.put_player("gm1", {"user_id": "gm1", "character_name": "GM",
                            "character_sheet": {"hp": 10, "max_hp": 10}})
    return inst


def config() -> dict:
    return {
        "ai_providers": [
            {"id": "srv", "name": "Server", "base_url": "http://srv.local/v1",
             "api_format": "openai", "models": ["big"],
             "model_capabilities": {"big": "chat"}},
            {"id": "user", "name": "User", "base_url": "http://127.0.0.1:8000/v1",
             "api_format": "openai", "models": ["qwen", "phi", "img"],
             "model_capabilities": {"qwen": "chat", "phi": "chat", "img": "image"}},
        ],
        "llm_provider_ref": "srv", "model": "big", "ai_provider_key_user": "SECRET-KEY",
        "check_model_enabled": True, "check_provider_ref": "srv", "check_model": "big",
    }


def no_server_model_config() -> dict:
    state = config()
    state["llm_provider_ref"] = ""
    state["model"] = ""
    state["check_model_enabled"] = False
    return state


class RecordingClient:
    """记录 provider 链的假客户端；绝不发起网络请求。"""

    instances: list["RecordingClient"] = []

    def __init__(self, *, providers, default, **_kwargs):
        self.providers = list(providers)
        self.default = default
        self.closed = False
        RecordingClient.instances.append(self)

    async def close(self):
        self.closed = True


NO_SERVER_CLIENTS = (None, None, False)


def runtime(state=config(), *, presence=None, server=None, online=False):
    if server is None:
        server = ((SimpleNamespace(name="server-main"), SimpleNamespace(name="server-check"), True)
                  if state.get("llm_provider_ref") else NO_SERVER_CLIENTS)
    rt = GmRoutingRuntime(
        config_state=lambda: state,
        server_clients=lambda: server,
        presence=presence if presence is not None else (lambda _gk, _uid: online),
        client_factory=RecordingClient,
    )
    return rt


def user_settings(**overrides) -> dict:
    settings = {
        "mode": "user",
        "user": {
            "main": {"provider_ref": "user", "model": "qwen"},
            "fallback1": {"provider_ref": "user", "model": "phi"},
            "fallback2": None,
            "check": {"provider_ref": "user", "model": "phi"},
            "fallback_to_server": True,
        },
    }
    settings.update(overrides)
    return settings


@pytest.fixture(autouse=True)
def _fresh_clients():
    RecordingClient.instances = []
    yield
    RecordingClient.instances = []


def apply_settings(inst, settings):
    gm_routing_state.update_settings(
        inst, settings, expected_revision=inst.modules["gm_routing"]["revision"]
    )


# ------------------------------------------------------------ module + save

def test_module_settings_validation_revision_and_main_required():
    inst = table()
    # 新槽位：server 模式、revision 0。
    assert inst.modules["gm_routing"] == {
        "schema_version": 1, "revision": 0, "mode": "server", "user": None,
    }
    with pytest.raises(ValueError):
        gm_routing_state.update_settings(inst, {"mode": "hybrid"}, expected_revision=0)
    with pytest.raises(ValueError):
        # user 模式必须显式选择主模型（不允许"空配置"切到 user）。
        gm_routing_state.update_settings(
            inst, {"mode": "user", "user": None}, expected_revision=0)
    with pytest.raises(ValueError):
        gm_routing_state.update_settings(
            inst, user_settings(), expected_revision=99)  # 乐观并发
    apply_settings(inst, user_settings())
    assert inst.modules["gm_routing"]["revision"] == 1
    assert inst.modules["gm_routing"]["mode"] == "user"
    with pytest.raises(ValueError):
        gm_routing_state.validate_route({"provider_ref": "user"})  # 缺 model
    with pytest.raises(ValueError):
        gm_routing_state.validate_route({"provider_ref": "../x", "model": "m"})


def test_settings_round_trip_keeps_references_only():
    inst = table()
    apply_settings(inst, user_settings())
    restored = GameInstance.from_dict(copy.deepcopy(inst.to_dict()))
    assert gm_routing_state.effective_settings(restored)["main"] == {
        "provider_ref": "user", "model": "qwen"}
    saved = json.dumps(restored.to_dict())
    assert "SECRET-KEY" not in saved
    assert "base_url" not in saved
    assert "api_key" not in saved


def test_v47_migration_materializes_fresh_slot_and_preserves_existing():
    old = legacy_table_payload(copy.deepcopy(table().to_dict()))
    old["instance_schema_version"] = 47
    old["modules"].pop("gm_routing", None)
    migrated = migrate_game_state_payload(old)
    assert migrated["instance_schema_version"] == CURRENT_INSTANCE_SCHEMA_VERSION
    assert migrated["modules"]["gm_routing"] == gm_routing_state.fresh()
    assert migrate_game_state_payload(migrated) == migrated  # 幂等
    preserved = copy.deepcopy(old)
    preserved["modules"]["gm_routing"] = {"schema_version": 1, "revision": 7,
                                          "mode": "user", "user": None}
    assert (migrate_game_state_payload(preserved)["modules"]["gm_routing"]
            == preserved["modules"]["gm_routing"])
    future = copy.deepcopy(old)
    future["modules"]["gm_routing"] = {"schema_version": 99, "future": [1]}
    assert (migrate_game_state_payload(future)["modules"]["gm_routing"]
            == future["modules"]["gm_routing"])


# ------------------------------------------------------- resolution matrix

def test_server_mode_passes_server_clients_through_without_ownership():
    inst = table()
    server_main, server_check = SimpleNamespace(), SimpleNamespace()
    rt = runtime(server=(server_main, server_check, True))
    generation = rt.begin(inst)
    assert generation.source == "server"
    assert generation.llm_client is server_main
    assert generation.check_llm_client is server_check
    assert generation.owns_clients is False
    import asyncio
    asyncio.run(generation.close())  # 透传客户端绝不被路由层关闭
    assert RecordingClient.instances == []


def test_online_user_gm_builds_provider_chain_with_server_fallback():
    inst = table()
    apply_settings(inst, user_settings())
    generation = runtime(online=True).begin(inst)
    assert generation.source == "user"
    assert generation.owns_clients is True
    (main_client,) = RecordingClient.instances[:1]
    assert [(p.provider_name, p.model_name, p.fallback) for p in main_client.providers] == [
        ("user", "qwen", False),   # user 主模型
        ("user", "phi", True),     # user 备用
        ("srv", "big", True),      # 服务端兜底
    ]
    assert main_client.default == "user"
    # 独立检定模型：user 检定链 + 服务端检定兜底。
    check_client = RecordingClient.instances[1]
    assert [(p.provider_name, p.model_name) for p in check_client.providers] == [
        ("user", "phi"), ("srv", "big")]
    assert generation.check_model_enabled is True


def test_offline_user_gm_falls_back_to_server_with_reason():
    inst = table()
    apply_settings(inst, user_settings())
    session_stats.replace_started_at(inst, "")  # 无宽限窗
    rt = runtime(online=False)
    generation = rt.begin(inst)
    assert generation.source == "server"
    assert generation.reason == "gm_offline"
    view = rt.project(inst)
    assert view["effective"]["source"] == "server"
    assert view["effective"]["user_gm_online"] is False
    assert view["mode"] == "user"


def test_creation_grace_window_counts_as_online():
    inst = table()
    apply_settings(inst, user_settings())
    session_stats.replace_started_at(
        inst, datetime.now(timezone.utc).isoformat())
    assert runtime(online=False).begin(inst).source == "user"
    stale = datetime.now(timezone.utc) - timedelta(seconds=600)
    session_stats.replace_started_at(inst, stale.isoformat())
    assert runtime(online=False).begin(inst).source == "server"


def test_presence_probe_uses_game_key_and_gm_uid():
    inst = table()
    apply_settings(inst, user_settings())
    seen = []

    def probe(game_key, uid):
        seen.append((game_key, uid))
        return uid == "gm1"

    session_stats.replace_started_at(inst, "")
    generation = runtime(presence=probe).begin(inst)
    assert generation.source == "user"
    assert seen == [("web|routing|bot", "gm1")]


def test_broken_user_main_with_server_ready_falls_back():
    inst = table()
    apply_settings(inst, user_settings(user={
        "main": {"provider_ref": "user", "model": "gone"},
        "fallback1": None, "fallback2": None, "check": None,
        "fallback_to_server": True,
    }))
    rt = runtime(online=True)
    generation = rt.begin(inst)
    assert generation.source == "server"
    assert generation.reason == "main_model_missing"


def test_no_available_model_reports_model_unavailable():
    inst = table()
    apply_settings(inst, user_settings())
    session_stats.replace_started_at(inst, "")
    # user GM 离线 + 服务端无主模型 → model_unavailable（触发稳定错误码）。
    rt = runtime(no_server_model_config(), online=False)
    assert rt.begin(inst).reason == "model_unavailable"
    # fallback_to_server=False 且 user 主模型失效 → 同样不可用。
    broken = user_settings(user={
        "main": {"provider_ref": "user", "model": "gone"},
        "fallback1": None, "fallback2": None, "check": None,
        "fallback_to_server": False,
    })
    apply_settings(inst, broken)
    assert runtime(online=True).begin(inst).reason == "model_unavailable"


def test_check_inherits_main_when_unset():
    inst = table()
    apply_settings(inst, user_settings(user={
        "main": {"provider_ref": "user", "model": "qwen"},
        "fallback1": None, "fallback2": None, "check": None,
        "fallback_to_server": False,
    }))
    generation = runtime(online=True).begin(inst)
    assert generation.source == "user"
    assert generation.check_llm_client is None
    assert generation.check_model_enabled is False
    assert runtime(online=True).project(inst)["effective"]["check_mode"] == "main"


def test_project_exposes_resolution_without_credentials():
    inst = table()
    apply_settings(inst, user_settings())
    projection = runtime(online=True).project(inst)
    assert projection["ok"] is True
    assert projection["revision"] == 1
    assert projection["effective"]["main"]["model"] == "qwen"
    assert projection["application"]["provider_ref"] == "srv"
    dumped = json.dumps(projection)
    assert "SECRET-KEY" not in dumped
    assert "base_url" not in dumped
    assert "api_key" not in dumped


def test_validate_settings_rejects_unresolvable_user_main():
    rt = runtime()
    rt.validate_settings(user_settings())
    rt.validate_settings({"mode": "server", "user": None})
    with pytest.raises(ValueError, match="main_required"):
        rt.validate_settings({"mode": "user", "user": None})
    with pytest.raises(ValueError, match="provider_missing"):
        rt.validate_settings(user_settings(user={
            "main": {"provider_ref": "ghost", "model": "m"},
            "fallback1": None, "fallback2": None, "check": None,
            "fallback_to_server": True}))
    with pytest.raises(ValueError, match="model_not_chat"):
        rt.validate_settings(user_settings(user={
            "main": {"provider_ref": "user", "model": "img"},
            "fallback1": None, "fallback2": None, "check": None,
            "fallback_to_server": True}))
    with pytest.raises(ValueError, match="invalid_mode"):
        rt.validate_settings({"mode": "hybrid"})


# ----------------------------------------------------------- service update

@pytest.mark.asyncio
async def test_service_update_enforces_revision_and_rolls_back_save_failure():
    inst = table()
    saved = []

    async def save(_inst):
        saved.append(True)

    async def fail_save(_inst):
        raise OSError("disk full")

    service = GmRoutingService(GmRoutingDependencies(lambda _k: inst, save), runtime())
    result = await service.update("g", {"settings": user_settings(), "expected_revision": 0})
    assert result["ok"] is True
    assert inst.modules["gm_routing"]["mode"] == "user"
    assert saved == [True]
    # 过期 revision 拒绝。
    assert (await service.update("g", {"settings": user_settings(), "expected_revision": 0})
            )["error_code"] == "invalid_or_stale_settings"
    # 未知字段 / 非法载荷拒绝。
    assert (await service.update("g", {"settings": user_settings(), "extra": 1})
            )["error_code"] == "invalid_settings"
    assert (await service.update("g", {"settings": {"mode": "user", "user": None},
                                       "expected_revision": 1})
            )["error_code"] == "invalid_or_stale_settings"
    # 保存失败回滚到写前状态。
    failing = GmRoutingService(GmRoutingDependencies(lambda _k: inst, fail_save), runtime())
    before = copy.deepcopy(inst.modules["gm_routing"])
    with pytest.raises(OSError):
        await failing.update("g", {"settings": {"mode": "server", "user": None},
                                   "expected_revision": 1})
    assert inst.modules["gm_routing"] == before
    assert GmRoutingService(GmRoutingDependencies(lambda _k: None, save), runtime()).read(
        "missing")["error_code"] == "game_missing"


# ------------------------------------------------- pipeline failure surface

@pytest.mark.asyncio
async def test_round_processor_raises_stable_error_when_no_model_available():
    inst = table()
    apply_settings(inst, user_settings())
    session_stats.replace_started_at(inst, "")
    processor = object.__new__(RoundProcessor)
    processor.llm_client = SimpleNamespace(name="server-main")
    processor.set_gm_routing_runtime(runtime(no_server_model_config(), online=False))
    with pytest.raises(GmModelNotConfigured) as excinfo:
        await processor._begin_gm_generation(inst)
    assert excinfo.value.error_code == "GM_MODEL_NOT_CONFIGURED"
    assert excinfo.value.rolled_back is None
    assert "user GM" in str(excinfo.value)


@pytest.mark.asyncio
async def test_background_gm_client_yields_none_instead_of_raising():
    import asyncio
    inst = table()
    apply_settings(inst, user_settings())
    session_stats.replace_started_at(inst, "")
    processor = object.__new__(RoundProcessor)
    server_main = SimpleNamespace(name="server-main")
    processor.llm_client = server_main
    # 后台任务（摘要/分镜）不允许抛配置错误：服务端可用时回退服务端。
    processor.set_gm_routing_runtime(runtime(online=False))
    async with processor._background_gm_client(inst) as client:
        assert client is server_main
    # 服务端也不可用 → yield None（调用方跳过该后台任务），不 raise。
    processor.set_gm_routing_runtime(runtime(no_server_model_config(), online=False))
    async with processor._background_gm_client(inst) as client:
        assert client is None
    # 临时 user 客户端在退出时关闭。
    processor.set_gm_routing_runtime(runtime(online=True))
    async with processor._background_gm_client(inst) as client:
        assert isinstance(client, RecordingClient)
        assert not client.closed
        user_client = client
    assert user_client.closed is True
    await asyncio.sleep(0)


def test_lifecycle_begin_passes_creation_assumption():
    inst = table()
    apply_settings(inst, user_settings())
    # 创建期：presence 判 GM 离线（无 SSE、started_at 未写），但创建请求
    # 由 user GM 本人发起 → assume_user_online 必须直达 user 路由。
    session_stats.replace_started_at(inst, "")
    assert runtime(online=False).begin(
        inst, assume_user_online=True).source == "user"
    lifecycle = object.__new__(GameLifecycle)
    lifecycle.llm_client = SimpleNamespace()

    class Spy:
        def __init__(self):
            self.kwargs = None

        def begin(self, _inst, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(source="user", close=lambda: None)

    spy = Spy()
    lifecycle._gm_routing = spy
    lifecycle._begin_gm_generation(inst, assume_user_online=True)
    assert spy.kwargs == {"assume_user_online": True}


def test_turns_result_is_recoverable_409_with_stable_code():
    result = turns_service._gm_model_config_result(table())
    assert result["status"] == 409
    payload = result["payload"]
    assert payload["ok"] is False
    assert payload["error_code"] == "GM_MODEL_NOT_CONFIGURED"
    assert payload["advanced"] is False  # 行动保留，user GM 修复后可重试
    assert "user GM" in payload["error"]


# ---------------------------------------------------------------- routes

@pytest.mark.asyncio
async def test_gm_routing_routes_require_gm_and_update_broadcasts(web_api):
    api, _, registry, _, _ = web_api
    inst = table()
    registry.register(inst)
    api._config_state.update(config())

    @web.middleware
    async def identity(request, handler):
        request["user_id"] = request.headers.get("User", "")
        request["owner_authenticated"] = False
        return await handler(request)

    from src.webui.routes.gm_routing import register
    app = web.Application(middlewares=[identity])
    app["api"] = api
    register(app)
    base = "/api/games/web%7Crouting%7Cbot/gm-routing"
    async with TestClient(TestServer(app)) as client:
        # 非 GM 与未认证：403；不存在的对局：404。
        assert (await client.get(base, headers={"User": "stranger"})).status == 403
        assert (await client.get(base)).status == 403
        assert (await client.get("/api/games/web%7Cnone%7Cbot/gm-routing",
                                 headers={"User": "gm1"})).status == 404
        response = await client.get(base, headers={"User": "gm1"})
        assert response.status == 200
        view = await response.json()
        assert view["mode"] == "server"
        assert "SECRET-KEY" not in json.dumps(view)
        # 切到 user 模式：校验通过 + revision 前进。
        response = await client.put(base, headers={"User": "gm1"}, json={
            "expected_revision": 0, "settings": user_settings()})
        assert response.status == 200
        updated = await response.json()
        assert updated["mode"] == "user"
        assert updated["revision"] == 1
        # 非法载荷 / 过期 revision → 400。
        assert (await client.put(base, headers={"User": "gm1"}, json={
            "expected_revision": 0, "settings": user_settings()})).status == 400
        assert (await client.put(base, headers={"User": "gm1"}, json={
            "expected_revision": 1, "settings": {"mode": "user", "user": None}
        })).status == 400
        assert (await client.put(base, headers={"User": "gm1"}, data="{")).status == 400


# ------------------------------------------------------- presence plumbing

def test_connection_pool_is_online_tracks_per_game_user():
    pool = ConnectionPool()

    class Resp:
        pass

    resp = Resp()
    pool.add("g", "gm1", resp)
    assert pool.is_online("g", "gm1") is True
    assert pool.is_online("g", "gm2") is False
    assert pool.is_online("other", "gm1") is False
    pool.remove("g", "gm1", resp)
    assert pool.is_online("g", "gm1") is False


# ------------------------------------------------------------ creation gate

def lifecycle_dependencies(*, llm_error=None, validator=None):
    def required(name):
        return SimpleNamespace(__name__=name)

    return GameLifecycleDependencies(
        registry=required("registry"),
        handler=required("handler"),
        rulesets=required("rulesets"),
        lorebook=None,
        worlds_dir=None,
        rules_dir=SimpleNamespace(),
        parse_game_key=lambda key: tuple(key.split("|")),
        llm_configuration_error=lambda _lang: llm_error,
        load_rule_by_id=lambda *_a, **_k: None,
        resolve_adventure_binding=lambda *_a, **_k: {},
        resolve_default_scene_image=lambda *_a, **_k: {},
        materialize_scene_image=lambda image: dict(image or {}),
        validate_map_background=lambda bg: dict(bg or {}),
        create_player=None,
        cleanup_orphan_game_templates=lambda _wid: 0,
        refresh_lorebook_index=lambda _wid: None,
        project_rule_id=lambda _inst: "",
        clean_public_narration=lambda text: text,
        validate_gm_routing=validator,
    )


def test_creation_gm_routing_validation_maps_runtime_reasons():
    dependencies = lifecycle_dependencies(
        validator=lambda raw: ({"ok": False, "error_code": "INVALID_GM_ROUTING",
                                "error": "所选模型不在服务商目录中"}
                               if raw and raw.get("mode") == "user" and raw["user"]["main"]["model"] == "gone"
                               else None))
    assert _validate_creation_gm_routing(dependencies, None) is None
    assert _validate_creation_gm_routing(dependencies, user_settings()) is None
    error = _validate_creation_gm_routing(dependencies, user_settings(user={
        "main": {"provider_ref": "user", "model": "gone"},
        "fallback1": None, "fallback2": None, "check": None,
        "fallback_to_server": True}))
    assert error["error_code"] == "INVALID_GM_ROUTING"


def test_creation_gm_routing_minimal_shape_rejects_unknown_mode_without_runtime():
    dependencies = lifecycle_dependencies()  # 未注入运行时校验器（旧测试上下文）
    assert _validate_creation_gm_routing(dependencies, None) is None
    assert _validate_creation_gm_routing(dependencies, user_settings()) is None
    # 无运行时注入时仍有不依赖能力模块的字面白名单兜底。
    error = _validate_creation_gm_routing(dependencies, {"mode": "hybrid"})
    assert error["error_code"] == "INVALID_GM_ROUTING"
    error = _validate_creation_gm_routing(dependencies, ["mode"])
    assert error["error_code"] == "INVALID_GM_ROUTING"


def test_runtime_apply_creation_settings_writes_fresh_slot():
    inst = table()
    runtime().apply_creation_settings(inst, user_settings())
    assert inst.modules["gm_routing"]["mode"] == "user"
    assert inst.modules["gm_routing"]["revision"] == 1
    assert gm_routing_state.effective_settings(inst)["main"]["model"] == "qwen"
    with pytest.raises(ValueError):
        runtime().apply_creation_settings(inst, {"mode": "user", "user": None})


@pytest.mark.asyncio
async def test_create_game_gate_bypassed_only_by_resolvable_user_gm():
    from src.webui.services.game_lifecycle import create_game

    llm_error = {"ok": False, "error_code": "llm_not_configured",
                 "error": "尚未配置主模型"}
    gate_kept = lifecycle_dependencies(
        llm_error=llm_error, validator=lambda _raw: None)
    result = await create_game(gate_kept, "world", players=[{"name": "p"}])
    assert result["error_code"] == "llm_not_configured"

    # user GM 模式通过校验 → 放宽服务端 gate；随后 world_id 预检失败证明
    # 执行流已经越过 LLM gate。
    bypassed = lifecycle_dependencies(
        llm_error=llm_error, validator=lambda _raw: None)
    result = await create_game(
        bypassed, "", players=[{"name": "p"}], gm_routing=user_settings())
    assert result.get("error") == "非法 world_id"

    # server 模式 / 无 gm_routing：gate 不放宽。
    server_mode = lifecycle_dependencies(
        llm_error=llm_error, validator=lambda _raw: None)
    result = await create_game(
        server_mode, "world", players=[{"name": "p"}],
        gm_routing={"mode": "server", "user": None})
    assert result["error_code"] == "llm_not_configured"

    # 载荷非法：在任何 gate 之前拒绝。
    invalid = lifecycle_dependencies(
        llm_error=llm_error,
        validator=lambda _raw: {"ok": False, "error_code": "INVALID_GM_ROUTING",
                                "error": "GM 路由配置无效"})
    result = await create_game(invalid, "world", players=[{"name": "p"}],
                               gm_routing={"mode": "hybrid"})
    assert result["error_code"] == "INVALID_GM_ROUTING"


@pytest.mark.asyncio
async def test_web_api_validates_creation_payload_with_routing_runtime(web_api):
    api, _, _, _, _ = web_api
    api._config_state.update(config())
    # 有效 user 主模型：通过。
    assert api._validate_creation_gm_routing(user_settings()) is None
    assert api._validate_creation_gm_routing(None) is None
    # 主模型不在目录 / 非对话模型 / 缺主模型：给出可操作错误码。
    for bad, fragment in (
        (user_settings(user={"main": {"provider_ref": "user", "model": "gone"},
                             "fallback1": None, "fallback2": None, "check": None,
                             "fallback_to_server": True}), "不在服务商目录"),
        (user_settings(user={"main": {"provider_ref": "user", "model": "img"},
                             "fallback1": None, "fallback2": None, "check": None,
                             "fallback_to_server": True}), "不支持对话"),
        ({"mode": "user", "user": None}, "必须选择主模型"),
    ):
        error = api._validate_creation_gm_routing(bad)
        assert error["error_code"] == "INVALID_GM_ROUTING"
        assert fragment in error["error"]
