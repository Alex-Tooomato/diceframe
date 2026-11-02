"""Persisted GM model routing. Only provider references belong in saves.

本局 GM（user GM）可以在服务端共享服务商目录中选择自己的主模型 / 备用模型 /
独立检定模型；user GM 掉线时运行时自动回退服务端全局配置。存档只保存引用与
开关，绝不保存 base_url / api_key（凭据解析唯一出口是
``src.ai_providers.resolve_provider``）。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.ai_providers import is_valid_provider_id
from src.engine.module_state import ModuleStateSpec, get_module_state, register_module_state, set_module_state

MODULE_NAME = "gm_routing"
SCHEMA_VERSION = 1
MODES = ("server", "user")
ROUTE_FIELDS = ("provider_ref", "model")
USER_FIELDS = ("main", "fallback1", "fallback2", "check", "fallback_to_server")


def fresh() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": 0,
        "mode": "server",
        "user": None,
    }


def ensure(raw: Any) -> dict[str, Any]:
    # Unknown or corrupt existing routing is never silently replaced by defaults.
    return raw if isinstance(raw, dict) else fresh()


def validate_route(raw: Any) -> dict[str, Any] | None:
    """一条模型引用：``{"provider_ref": id, "model": name}``；``None`` 表示继承服务端。"""
    if raw is None:
        return None
    if not isinstance(raw, dict) or raw.keys() - set(ROUTE_FIELDS):
        raise ValueError("unsupported GM routing route fields")
    result: dict[str, Any] = {}
    for key in ROUTE_FIELDS:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ValueError(f"invalid GM routing {key}")
        result[key] = value.strip()
    if not is_valid_provider_id(result["provider_ref"]):
        raise ValueError("invalid GM routing provider_ref")
    return result


def validate_user_settings(raw: Any) -> dict[str, Any]:
    """校验 user GM 的模型选择；``None`` 路由 = 该能力继承服务端全局配置。"""
    if raw is None:
        return {"main": None, "fallback1": None, "fallback2": None,
                "check": None, "fallback_to_server": True}
    if not isinstance(raw, dict) or raw.keys() - set(USER_FIELDS):
        raise ValueError("unsupported GM routing fields")
    result = {
        "main": validate_route(raw.get("main")),
        "fallback1": validate_route(raw.get("fallback1")),
        "fallback2": validate_route(raw.get("fallback2")),
        "check": validate_route(raw.get("check")),
        "fallback_to_server": raw.get("fallback_to_server") is not False,
    }
    return result


def settings_state(instance: Any) -> dict[str, Any]:
    slot = get_module_state(instance, MODULE_NAME)
    if (type(slot.get("revision")) is not int or slot["revision"] < 0
            or slot.get("mode") not in MODES):
        raise ValueError("invalid GM routing state")
    validate_user_settings(slot.get("user"))
    return slot


def effective_settings(instance: Any) -> dict[str, Any]:
    """返回本局生效的 user GM 配置（已校验、深拷贝）。"""
    return deepcopy(validate_user_settings(settings_state(instance)["user"]))


def update_settings(instance: Any, raw: Any, *, expected_revision: int) -> int:
    """在调用方 authority gate 内整体替换 GM 路由配置；revision 乐观并发。"""
    mode = raw.get("mode") if isinstance(raw, dict) else None
    if mode not in MODES:
        raise ValueError("invalid GM routing mode")
    user = validate_user_settings(raw.get("user") if isinstance(raw, dict) else None)
    if mode == "user" and user["main"] is None:
        raise ValueError("main_required")
    slot = settings_state(instance)
    if type(expected_revision) is not int or expected_revision != slot["revision"]:
        raise ValueError("GM routing revision changed")
    slot["mode"] = mode
    slot["user"] = user
    slot["revision"] += 1
    return slot["revision"]


def routing_token(instance: Any) -> int | None:
    """生成期快照令牌：路由配置变化即可废弃在飞结果。"""
    try:
        return settings_state(instance)["revision"]
    except ValueError:
        return None


def restore_settings(instance: Any, before: dict[str, Any]) -> None:
    set_module_state(instance, MODULE_NAME, deepcopy(before))


register_module_state(ModuleStateSpec(MODULE_NAME, SCHEMA_VERSION, fresh, ensure))
