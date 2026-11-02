"""GM-only per-game GM model routing (user GM / 服务端 GM) routes."""
from aiohttp import web

from src.webui.routes._common import _get_api
from src.webui.viewer import viewer_for


def _denied(request: web.Request) -> web.Response | None:
    inst = _get_api(request).get_game_instance(request.match_info["game_key"])
    if inst is None:
        return web.json_response({"ok": False, "error_code": "game_missing"}, status=404)
    if not viewer_for(request, inst).is_gm:
        return web.json_response({"ok": False, "error": "GM only"}, status=403)
    return None


async def read(request: web.Request) -> web.Response:
    denied = _denied(request)
    if denied is not None:
        return denied
    return web.json_response(_get_api(request).gm_routing_settings(request.match_info["game_key"]))


async def update(request: web.Request) -> web.Response:
    denied = _denied(request)
    if denied is not None:
        return denied
    try:
        body = await request.json()
    except (ValueError, TypeError):
        return web.json_response({"ok": False, "error_code": "invalid_settings"}, status=400)
    result = await _get_api(request).update_gm_routing_settings(
        request.match_info["game_key"], body,
    )
    if result.get("ok"):
        await _broadcast(request)
    return web.json_response(result, status=200 if result.get("ok") else 400)


async def _broadcast(request: web.Request) -> None:
    pool = request.app.get("connection_pool")
    if pool is not None:
        await pool.broadcast(request.match_info["game_key"], {"type": "gm_source_changed"})


def register(app: web.Application) -> None:
    app.router.add_get("/api/games/{game_key}/gm-routing", read)
    app.router.add_put("/api/games/{game_key}/gm-routing", update)
