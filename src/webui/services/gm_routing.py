"""本局 GM 模型路由（user GM / 服务端 GM）的运行时解析与持久化服务。

职责边界（对照 AISeatRuntime 模式）：

- 凭据解析唯一出口仍是 ``src.ai_providers.resolve_provider``；本模块只消费
  服务端共享服务商目录的引用，绝不新建内联地址/密钥字段，也绝不把凭据写进存档。
- user GM 的 presence 判定来自 SSE 连接池（``is_online``）+ 建局后的短宽限窗，
  不引入第二套心跳；掉线解析期直接回退服务端配置，不在调用期猜测换模型。
- 生成期临时客户端用完即关（``GmGeneration.close``）；服务端默认客户端由
  composition 管理生命周期，这里只透传引用、绝不关闭。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.ai_providers import resolve_provider
from src.engine.modules import gm_routing
from src.engine.modules import progression_state, session_stats
from src.llm.client import LLMClient, ProviderConfig
from src.network_proxy import effective_proxy_url
from src.webui.services._common import _GAME_KEY_SEP

# 建局后的宽限窗：纯 AI 桌建局即自动推进首轮，此时 GM 的 SSE 可能尚未建立。
_CREATION_GRACE_SECONDS = 180


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_activity(raw: Any) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


@dataclass
class GmGeneration:
    """一次 GM 生成（叙事 / 检定规划 / 改写）使用的有效客户端集合。"""

    llm_client: Any
    check_llm_client: Any | None
    check_model_enabled: bool
    source: str  # "user" | "server"
    reason: str  # "" 或回退原因码（gm_offline / provider_missing / model_unavailable ...）
    owns_clients: bool = False

    async def close(self) -> None:
        if self.owns_clients:
            for client in (self.llm_client, self.check_llm_client):
                closer = getattr(client, "close", None)
                if closer is not None:
                    await closer()


class GmRoutingRuntime:
    """Live config resolver for per-game GM model routing, injected at composition."""

    def __init__(
        self,
        *,
        config_state: Callable[[], dict],
        server_clients: Callable[[], tuple[Any, Any | None, bool]],
        presence: Callable[[str, str], bool] | None = None,
        client_factory: Callable = LLMClient,
    ):
        self._config_state = config_state
        self._server_clients = server_clients
        self._presence = presence
        self._client_factory = client_factory

    # ------------------------------------------------------------------ helpers

    def set_presence_probe(self, probe: Callable[[str, str], bool] | None) -> None:
        """应用层注入 SSE presence 探针；配置热重载换 WebAPI 后重绑。"""
        self._presence = probe

    def _config(self) -> dict:
        return self._config_state() or {}

    def _provider_entry(self, config: dict, ref: str) -> dict | None:
        return next(
            (p for p in config.get("ai_providers", [])
             if isinstance(p, dict) and p.get("id") == ref),
            None,
        )

    def _resolve_route(self, config: dict, route: dict | None) -> tuple[dict, dict | None]:
        """解析一条 {provider_ref, model} 引用；返回 (view, connection)。"""
        if route is None:
            return {"ready": False, "reason": "inherit"}, None
        ref, model = route["provider_ref"], route["model"]
        entry = self._provider_entry(config, ref)
        connection = resolve_provider(config, ref)
        reason = ""
        if not entry or not connection:
            reason = "provider_missing"
        elif not connection["base_url"]:
            reason = "provider_unconfigured"
        elif not model:
            reason = "model_required"
        elif entry.get("models") and model not in entry["models"]:
            reason = "model_missing"
        elif entry.get("model_capabilities", {}).get(model, "chat") != "chat":
            reason = "model_not_chat"
        view = {"ready": not reason, "reason": reason, "provider_ref": ref,
                "provider_name": entry.get("name", ref) if entry else ref, "model": model}
        return view, connection

    def _server_main_ready(self, config: dict) -> bool:
        """服务端主模型配置可解析（构建兜底 provider 链用）。"""
        connection = resolve_provider(config, str(config.get("llm_provider_ref") or ""))
        return bool(connection and connection["base_url"] and str(config.get("model") or ""))

    def _server_check_route(self, config: dict) -> dict | None:
        if not config.get("check_model_enabled"):
            return None
        ref = str(config.get("check_provider_ref") or "")
        model = str(config.get("check_model") or "")
        if not ref or not model:
            return None
        return {"provider_ref": ref, "model": model}

    def user_gm_online(self, instance: Any) -> bool:
        gm_uid = str(getattr(instance, "gm_uid", "") or "")
        if not gm_uid:
            return False
        game_key = _GAME_KEY_SEP.join(str(part) for part in instance.game_key)
        if self._presence is not None and self._presence(game_key, gm_uid):
            return True
        started = _parse_activity(session_stats.started_at(instance))
        return bool(started and _now() - started <= timedelta(seconds=_CREATION_GRACE_SECONDS))

    # ------------------------------------------------------------------ resolve

    def _resolve_view(
        self, instance: Any, *, assume_user_online: bool = False
    ) -> dict[str, Any]:
        """解析本局当前生效的 GM 路由视图；不构建客户端，供 project/begin 共用。

        ``assume_user_online``：创建期由生命周期层显式声明"创建请求正由 user GM
        本人发起"，跳过 presence 判定（此时 GM 席位与 SSE 连接都尚未建立）。
        """
        config = self._config()
        view: dict[str, Any] = {
            "source": "server",
            "reason": "",
            "mode": "server",
            "user": None,
            "user_gm_online": False,
            "main": None,
            "fallbacks": [],
            "check": None,
            "check_mode": "main",  # main | dedicated | server
        }
        try:
            slot = gm_routing.settings_state(instance)
            view["mode"] = slot["mode"]
            view["user"] = gm_routing.validate_user_settings(slot["user"])
            revision = slot["revision"]
        except ValueError:
            view["reason"] = "unsupported_settings"
            return view
        view["revision"] = revision
        if view["mode"] != "user":
            return view

        view["user_gm_online"] = (
            True if assume_user_online else self.user_gm_online(instance)
        )
        user = view["user"] or {}
        if not view["user_gm_online"]:
            view["reason"] = "gm_offline"
            return view
        main_view, _conn = self._resolve_route(config, user.get("main"))
        if not main_view["ready"]:
            # user 主模型不可解析：有服务端客户端在位（fallback_to_server）即可
            # 用服务端补位。服务端可用性以 composition 注入的真实客户端为准，
            # 而不是 live 配置——配置热重载间隙里客户端仍然可用。
            view["reason"] = f"main_{main_view['reason']}" if main_view["reason"] != "inherit" else "main_missing"
            if not (user.get("fallback_to_server", True) and self._server_clients()[0] is not None):
                view["reason"] = "model_unavailable"
            return view
        view["source"] = "user"
        view["main"] = {"provider_ref": main_view["provider_ref"],
                        "provider_name": main_view["provider_name"],
                        "model": main_view["model"]}
        for key in ("fallback1", "fallback2"):
            route = user.get(key)
            if not route:
                continue
            fallback_view, _conn = self._resolve_route(config, route)
            view["fallbacks"].append({"slot": key, "ready": fallback_view["ready"],
                                      "reason": fallback_view["reason"],
                                      "provider_ref": fallback_view["provider_ref"],
                                      "provider_name": fallback_view["provider_name"],
                                      "model": fallback_view["model"]})
        check_route = user.get("check")
        if check_route is None:
            view["check_mode"] = "main"
        else:
            check_view, _conn = self._resolve_route(config, check_route)
            view["check_mode"] = "dedicated"
            view["check"] = {"ready": check_view["ready"], "reason": check_view["reason"],
                             "provider_ref": check_view["provider_ref"],
                             "provider_name": check_view["provider_name"],
                             "model": check_view["model"]}
        return view

    def _build_client(self, config: dict, providers: list[ProviderConfig], default: str) -> LLMClient | None:
        if not providers:
            return None
        return self._client_factory(
            providers=providers, default=default,
            proxy_url=effective_proxy_url(
                bool(config.get("proxy_enabled")), str(config.get("proxy_url") or "")),
            request_timeout_seconds=float(config.get("model_request_timeout_seconds", 120)),
        )

    def _provider_config(self, config: dict, route: dict, *, fallback: bool = False) -> ProviderConfig | None:
        connection = resolve_provider(config, route["provider_ref"])
        if not connection or not connection["base_url"]:
            return None
        return ProviderConfig(
            provider_name=route["provider_ref"], base_url=connection["base_url"],
            api_key=connection["api_key"], api_format=connection["api_format"],
            model_name=route["model"], fallback=fallback,
        )

    def begin(self, instance: Any, *, assume_user_online: bool = False) -> GmGeneration:
        """解析本局这一刻应使用的 GM 客户端；临时客户端由调用方负责 close。"""
        config = self._config()
        view = self._resolve_view(instance, assume_user_online=assume_user_online)
        server_llm, server_check, server_check_enabled = self._server_clients()

        if view["source"] != "user":
            reason = view["reason"]
            if server_llm is None:
                # 服务端没有可用主模型客户端（composition 未构建）才是不可恢复。
                reason = "model_unavailable"
            elif reason == "unsupported_settings":
                reason = ""  # 旧/损坏槽位按服务端默认路由执行，不阻断对局
            return GmGeneration(server_llm, server_check, server_check_enabled,
                                "server", reason)

        user = view["user"] or {}
        providers: list[ProviderConfig] = []
        main_route = user["main"]
        main_config = self._provider_config(config, main_route)
        if main_config is not None:
            providers.append(main_config)
        for key in ("fallback1", "fallback2"):
            route = user.get(key)
            if not route:
                continue
            route_config = self._provider_config(config, route, fallback=True)
            if route_config is not None:
                providers.append(route_config)
        if user.get("fallback_to_server", True) and self._server_main_ready(config):
            server_route = {"provider_ref": str(config.get("llm_provider_ref") or ""),
                            "model": str(config.get("model") or "")}
            server_config = self._provider_config(config, server_route, fallback=True)
            if server_config is not None and all(
                    p.provider_name != server_config.provider_name or p.model_name != server_config.model_name
                    for p in providers):
                providers.append(server_config)

        llm_client = self._build_client(config, providers, providers[0].provider_name)
        if llm_client is None:  # 防御：主模型解析与构建间发生配置变化
            return GmGeneration(server_llm, server_check, server_check_enabled,
                                "server", "" if server_llm is not None else "model_unavailable")

        check_client: LLMClient | None = None
        check_enabled = False
        if view["check_mode"] == "dedicated":
            check_route = user["check"]
            check_providers: list[ProviderConfig] = []
            check_config = self._provider_config(config, check_route)
            if check_config is not None:
                check_providers.append(check_config)
            if user.get("fallback_to_server", True):
                server_check_route = self._server_check_route(config)
                if server_check_route:
                    server_check_config = self._provider_config(config, server_check_route, fallback=True)
                    if server_check_config is not None and all(
                            p.provider_name != server_check_config.provider_name
                            or p.model_name != server_check_config.model_name
                            for p in check_providers):
                        check_providers.append(server_check_config)
            if check_providers:
                # user 检定模型不可解析时按链路降级（服务端检定 → 主模型），
                # 不让显式配置失效变成硬错误；降级原因已在 view["check"] 里。
                check_client = self._build_client(
                    config, check_providers, check_providers[0].provider_name)
                check_enabled = check_client is not None
        return GmGeneration(llm_client, check_client, check_enabled,
                            "user", "", owns_clients=True)

    # ------------------------------------------------------------------ project

    def project(self, instance: Any) -> dict[str, Any]:
        config = self._config()
        try:
            slot = gm_routing.settings_state(instance)
            revision = slot["revision"]
            mode = slot["mode"]
            user = gm_routing.validate_user_settings(slot["user"])
        except ValueError:
            revision, mode, user = 0, "server", gm_routing.validate_user_settings(None)
        view = self._resolve_view(instance)
        providers = []
        for entry in config.get("ai_providers", []):
            if not isinstance(entry, dict):
                continue
            models = [m for m in entry.get("models", [])
                      if entry.get("model_capabilities", {}).get(m, "chat") == "chat"]
            providers.append({"id": entry["id"], "name": entry.get("name", entry["id"]), "models": models})
        return {
            "ok": True,
            "revision": revision,
            "mode": mode,
            "user": deepcopy(user),
            "effective": {
                "source": view["source"],
                "reason": view["reason"],
                "user_gm_online": view["user_gm_online"],
                "main": view["main"],
                "fallbacks": view["fallbacks"],
                "check_mode": view["check_mode"],
                "check": view["check"],
            },
            "providers": providers,
            "application": {
                "provider_ref": str(config.get("llm_provider_ref") or ""),
                "model": str(config.get("model") or ""),
                "check_model_enabled": bool(config.get("check_model_enabled")),
                "check_provider_ref": str(config.get("check_provider_ref") or ""),
                "check_model": str(config.get("check_model") or ""),
            },
        }

    def validate_settings(self, raw: Any) -> None:
        """保存/创建前的完整解析校验：mode=user 时主模型必须可解析。

        不依赖具体对局实例——创建期（对局尚不存在）与存量更新共用同一套规则。
        """
        mode = raw.get("mode") if isinstance(raw, dict) else None
        if mode not in gm_routing.MODES:
            raise ValueError("invalid_mode")
        user = gm_routing.validate_user_settings(raw.get("user") if isinstance(raw, dict) else None)
        if mode == "user":
            if user["main"] is None:
                raise ValueError("main_required")
            main_view, _conn = self._resolve_route(self._config(), user["main"])
            if not main_view["ready"]:
                raise ValueError(main_view["reason"])

    def validate_selection(self, instance: Any, raw: Any) -> None:
        """保存前的完整解析校验（见 :meth:`validate_settings`）。"""
        del instance  # 路由解析只读 live 配置，与具体对局无关
        self.validate_settings(raw)

    def apply_creation_settings(self, instance: Any, settings: dict[str, Any]) -> None:
        """创建事务内把开局选择写入路由槽位（revision 从 fresh 的 0 起步）。

        由 GameLifecycleDependencies.apply_gm_routing 注入调用——核心创建流程
        通过钩子使用本能力，不直接 import 能力模块（shrink-only 基线）。
        """
        self.validate_settings(settings)
        gm_routing.update_settings(instance, settings, expected_revision=0)


@dataclass(frozen=True)
class GmRoutingDependencies:
    get_instance: Callable[[str], Any | None]
    save_instance: Callable[[Any], Awaitable[None]]


class GmRoutingService:
    """GM-only 路由读写服务：authority gate + 乐观并发 + 保存失败回滚。"""

    def __init__(self, dependencies: GmRoutingDependencies, runtime: GmRoutingRuntime):
        self._dependencies = dependencies
        self.runtime = runtime

    def read(self, game_key: str) -> dict:
        inst = self._dependencies.get_instance(game_key)
        return self.runtime.project(inst) if inst else {"ok": False, "error_code": "game_missing"}

    async def update(self, game_key: str, body: Any) -> dict:
        inst = self._dependencies.get_instance(game_key)
        if inst is None:
            return {"ok": False, "error_code": "game_missing"}
        if not isinstance(body, dict) or body.keys() - {"settings", "expected_revision"}:
            return {"ok": False, "error_code": "invalid_settings"}
        settings = body.get("settings")
        try:
            async with inst.authoritative_write() as entered:
                if not entered:
                    return {"ok": False, "error_code": "game_busy"}
                self.runtime.validate_selection(inst, settings)
                before = deepcopy(gm_routing.settings_state(inst))
                gm_routing.update_settings(
                    inst, settings, expected_revision=body.get("expected_revision"))
                try:
                    await self._dependencies.save_instance(inst)
                except BaseException:
                    gm_routing.restore_settings(inst, before)
                    raise
        except ValueError:
            return {"ok": False, "error_code": "invalid_or_stale_settings"}
        return self.runtime.project(inst)
