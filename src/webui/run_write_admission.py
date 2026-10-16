"""Transport admission for frozen/ended runs, including legacy direct writers."""
from aiohttp import web

from src.engine.game_state import GameState


@web.middleware
async def run_write_admission(request, handler):
    key = request.match_info.get('game_key')
    api = request.app.get('api')
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'} or not key or api is None:
        return await handler(request)
    # The feature service owns its privileged freeze lifecycle and permissions.
    if request.match_info.route.resource.canonical.startswith('/api/games/{game_key}/run-story'):
        return await handler(request)
    instance = api.get_game_instance(key)
    if instance is None:
        return await handler(request)
    # Ticket issuance authorizes a role-filtered read stream; it never mutates
    # game state. Frozen archives must remain subscribable after reconnect.
    if request.method == 'POST' and request.match_info.route.resource.canonical == '/api/games/{game_key}/sse-ticket':
        return await handler(request)
    # Explicit archive delivery/credential revocation may continue; they do not
    # rewrite settled characters or story. No reset/restart exception: preserve
    # the original archive and create a separate game to carry characters.
    if request.method == 'DELETE' and request.path.endswith('/seat-token'):
        return await handler(request)
    async with instance.authoritative_write() as entered:
        if not entered:
            return web.json_response({'ok': False, 'error_code': 'RUN_ENDED' if instance.state == GameState.ENDED else 'RUN_READ_ONLY',
                                      'error': '本局已结团或正在准备结团，只能查看 / This run is read-only'}, status=409)
        return await handler(request)
