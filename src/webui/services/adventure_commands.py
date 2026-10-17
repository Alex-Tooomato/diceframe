"""Authenticated application commands; gameplay facade only composes this owner."""
from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from collections.abc import Callable, Awaitable
from typing import Any

from src.engine.modules import adventure_runtime_state, economy_state

logger = logging.getLogger('trpg')


@dataclass(frozen=True)
class AdventureCommandDependencies:
    save: Callable[[Any], Awaitable[None]]
    complete: Callable[..., dict] | None
    request_choice: Callable[..., dict] | None
    admission: Callable[[], dict | None]
    binding: Callable[[], Awaitable[dict | None]]
    get_instance: Callable[[Any], Any] | None = None


async def execute(deps: AdventureCommandDependencies, instance: Any, body: dict,
                  actor_uid: str, *, is_gm: bool) -> dict:
    kind = body['type']
    if kind == 'adventure.node.complete' and not is_gm:
        return {'ok': False, 'code': 'GM_ONLY', 'error': '只有 GM 可以确认冒险节点完成'}
    if set(body) - {'type', 'node_id', 'choice_id'}:
        return {'ok': False, 'code': 'INVALID_ADVENTURE_COMMAND', 'error': 'unexpected adventure command field'}
    node_id, choice_id = body.get('node_id'), body.get('choice_id', '')
    if not isinstance(node_id, str) or not node_id.strip() or not isinstance(choice_id, str):
        return {'ok': False, 'code': 'INVALID_ADVENTURE_NODE', 'error': 'node_id and choice_id must be strings'}
    callback = deps.complete if kind == 'adventure.node.complete' else deps.request_choice
    if callback is None:
        return {'ok': False, 'code': 'ADVENTURE_RUNTIME_UNAVAILABLE', 'error': 'Adventure runtime is unavailable'}
    async with instance.authoritative_write() as write_entered, instance._lock:
        if not write_entered:
            return {"ok": False, "error_code": "REWRITE_IN_PROGRESS", "code": "REWRITE_IN_PROGRESS", "error": "historical rewrite is in progress"}
        if deps.get_instance is not None and deps.get_instance(instance.game_key) is not instance:
            return {"ok": False, "error_code": "STALE_RUN", "code": "STALE_RUN", "error": "game run was replaced"}
        error = deps.admission()
        if error:
            return error
        adventure_runtime_state.require_writable(instance)
        error = await deps.binding()
        if error:
            return error
        before = {
            "world_state": deepcopy(instance.world_state),
            "adventure_progress": deepcopy(adventure_runtime_state.progress(instance)),
            "economy": deepcopy(economy_state.state(instance)),
        }
        try:
            if kind == 'adventure.node.complete':
                args = (instance, node_id.strip(), actor_uid, actor_uid)
                result = callback(*args, choice_id=choice_id) if choice_id else callback(*args)
            else:
                result = callback(instance, node_id.strip(), choice_id, actor_uid)
            await deps.save(instance)
        except Exception as exc:
            instance.world_state = before["world_state"]
            adventure_runtime_state.replace_progress(instance, before["adventure_progress"])
            economy_state.replace_state(instance, before["economy"])
            if isinstance(exc, (ValueError, KeyError, TypeError)):
                return {'ok': False, 'code': 'ADVENTURE_NODE_REJECTED', 'error': str(exc)}
            logger.exception('Adventure command failed and was restored')
            return {'ok': False, 'code': 'ADVENTURE_NODE_FAILED', 'error': '冒险结算失败，状态已恢复，请重试'}
    return {'ok': True, 'result': {'adventure_node' if kind == 'adventure.node.complete' else 'adventure_choice_request': result}}
