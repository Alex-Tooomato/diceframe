"""认证路由 handler：登录、当前用户信息和登录记录。"""

from __future__ import annotations

import logging

from aiohttp import web

from src.webui.login_audit import LOGIN_AUDIT_KEY


logger = logging.getLogger("trpg")
ACCESS_PASSWORD_CONFIGURED_KEY = web.RequestKey("access_password_configured", bool)


async def api_login(request: web.Request) -> web.Response:
    builder_authenticated = bool(request.get("builder_authenticated", False))
    owner_authenticated = bool(request.get("owner_authenticated", False))
    success = (
        not request.get(ACCESS_PASSWORD_CONFIGURED_KEY, False)
        or owner_authenticated
        or builder_authenticated
    )
    # 无密码服务器人人等同 owner；有密码时报告实际命中的角色，前端据此
    # 隐藏管理入口（后端仍按路径拒绝，前端只是不再展示进不去的页面）。
    role = (
        "owner"
        if owner_authenticated or not request.get(ACCESS_PASSWORD_CONFIGURED_KEY, False)
        else "builder"
    ) if success else ""
    audit = request.app.get(LOGIN_AUDIT_KEY)
    if audit:
        try:
            audit.record(request.remote or "unknown", success)
        except Exception:
            # 审计落盘失败不能把用户锁在登录页外，服务日志仍会保留异常。
            logger.exception("登录记录写入失败")
    if not success:
        return web.json_response(
            {"ok": False, "error": "密码错误"},
            status=401,
            headers={"Cache-Control": "no-store"},
        )
    return web.json_response(
        {"ok": True, "role": role},
        headers={"Cache-Control": "no-store"},
    )


async def api_login_history(request: web.Request) -> web.Response:
    audit = request.app.get(LOGIN_AUDIT_KEY)
    return web.json_response(
        {
            "entries": audit.recent(50) if audit else [],
            "max_entries": audit.max_entries if audit else 0,
        },
        headers={"Cache-Control": "no-store"},
    )


async def api_me(request: web.Request) -> web.Response:
    mgr = request.app.get("session_manager")
    token = request.get("session_token")
    name = mgr.get_name(token) if mgr and token else ""
    role = ""
    if request.get("owner_authenticated", False) or not request.get(
        ACCESS_PASSWORD_CONFIGURED_KEY, False
    ):
        role = "owner"
    elif request.get("builder_authenticated", False):
        role = "builder"
    return web.json_response(
        {"user_id": request.get("user_id", ""), "name": name, "role": role}
    )


def register_auth(app: web.Application) -> None:
    app.router.add_post("/api/login", api_login)
    app.router.add_get("/api/login-history", api_login_history)
    app.router.add_get("/api/me", api_me)
