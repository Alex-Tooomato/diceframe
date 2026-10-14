"""Agent authoring capability pack over canonical content-owner boundaries."""
from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

from src.webui.services.assistant_agent import AgentTool, _digest
from src.webui.services.assistant_agent_application import obj, string
from src.webui.services.assistant_content import _has_private_markers


@dataclass(frozen=True)
class AuthoringDependencies:
    list_worlds: Callable
    update_world: Callable
    list_book_entries: Callable
    save_book_entry: Callable
    list_cards: Callable
    update_card: Callable
    adventure_detail: Callable
    get_rule: Callable
    write_entries_with_recovery: Callable | None = None
    write_world_with_recovery: Callable | None = None
    write_card_with_recovery: Callable | None = None
    world_snapshot: Callable | None = None
    card_snapshot: Callable | None = None


def authoring_tools(deps: AuthoringDependencies) -> tuple[AgentTool, ...]:
    def world(world_id):
        row = next((w for w in deps.list_worlds().get("worlds", []) if w.get("id") == world_id), None)
        if not row:
            raise ValueError("World does not exist")
        return row

    def card(card_id):
        row = next((c for c in deps.list_cards().get("cards", []) if c.get("id") == card_id), None)
        if not row:
            raise ValueError("Character card does not exist")
        return row

    def book_entries(book_id):
        result = deps.list_book_entries(book_id)
        if result.get("ok") is False:
            raise ValueError("Lorebook does not exist")
        return result.get("entries", [])

    async def read(args, owner):
        kind, identity = args["kind"], args["id"]
        if kind == "world":
            return {"ok": True, "world": world(identity)}
        if kind == "lorebook":
            return {"ok": True, "entries": book_entries(identity)}
        if kind == "character_template":
            return {"ok": True, "card": card(identity)}
        if kind == "adventure":
            return deps.adventure_detail(identity)
        return deps.get_rule(identity)

    async def edit_world(args, owner):
        current = world(args["world_id"])
        if _has_private_markers(args["description"]):
            raise ValueError("World descriptions cannot contain private material")
        if deps.write_world_with_recovery is not None:
            return deps.write_world_with_recovery(owner, args['world_id'], {
                'name': args['name'], 'description': args['description'],
                'language': args.get('language') or current.get('language') or 'zh-CN'})
        return deps.update_world(args["world_id"], args["name"], args["description"], args.get("language") or current.get("language") or "zh-CN")

    async def write_entries(args, owner):
        existing = {e["id"]: e for e in book_entries(args["book_id"])}
        prepared = []
        seen = set()
        # Validate the complete batch before the first write.
        for entry in args["entries"]:
            identity = entry.get("id")
            if identity and identity not in existing:
                raise ValueError("Entry ID does not exist in the selected book; omit it to create")
            if identity and identity in seen:
                raise ValueError("Duplicate entry update")
            seen.add(identity)
            public = entry.get("visibility") == "public" if "visibility" in entry else "*" in existing.get(identity, {}).get("visible_to", [])
            if public and _has_private_markers(entry["content"]):
                raise ValueError("A public entry cannot contain private markers")
            row = {key: deepcopy(value) for key, value in entry.items() if key != "visibility"}
            row["id"] = identity or f"agent_entry_{uuid.uuid4().hex}"
            # Preserve an existing entry's audience unless the user explicitly
            # confirms a visibility change. New entries fail closed to GM.
            if "visibility" in entry or not identity:
                row["visible_to"] = ["*"] if public else []
            prepared.append(row)
        if deps.write_entries_with_recovery is not None:
            return deps.write_entries_with_recovery(owner, args['book_id'], prepared)
        results = []
        for row in prepared:
            try:
                result = deps.save_book_entry(args["book_id"], row)
            except (ValueError, OSError) as exc:
                result = {"ok": False, "error": str(exc)}
            results.append({"id": row["id"], **result})
            if result.get("ok") is not True:
                return {"ok": False, "partial": len(results) > 1, "results": results,
                        "error": "Some entries could not be saved; inspect results before planning again"}
        return {"ok": True, "results": results, "navigation": {"route": "lorebook", "query": {"book": args["book_id"]}}}

    async def edit_card(args, owner):
        card(args["card_id"])
        patch = {key: value for key, value in args.items() if key != "card_id"}
        if any(_has_private_markers(str(value)) for value in patch.values()):
            raise ValueError("Character public fields cannot contain private material")
        if deps.write_card_with_recovery is not None:
            return deps.write_card_with_recovery(owner, args['card_id'], patch)
        # This service rejects professional-card legacy updates. No mechanics
        # fields are offered by the agent schema.
        return deps.update_card(args["card_id"], patch)

    entry = obj({"id": string(), "name": string(minimum=1), "content": string(16000, minimum=1),
        "type": string(30, ("npc", "location", "item", "event", "puzzle", "faction", "spell", "class", "other")),
        "keywords": {"type": "array", "items": string(100), "maxItems": 20},
        "visibility": string(20, ("public", "gm"))}, ("name", "content"))
    return (
        AgentTool("read_content", "Read an existing world, book, character, adventure or rule", obj({
            "kind": string(30, ("world", "lorebook", "character_template", "adventure", "rule")), "id": string(minimum=1)}, ("kind", "id")), read),
        AgentTool("edit_world", "Update the name and public setting of your world", obj({"world_id": string(minimum=1),
            "name": string(minimum=1), "description": string(16000), "language": string(16, ("zh-CN", "en", "de", "ja", "ru"))},
            ("world_id", "name", "description")), edit_world, mutation=True,
            guard=lambda args, owner: _digest(deps.world_snapshot(args['world_id']) if deps.world_snapshot else world(args["world_id"])),
            preview=lambda args, owner: {"target_name": world(args["world_id"])["name"], "changes": args}),
        AgentTool("write_lorebook_entries", "Add or update reviewed lorebook entries, with explicit public or GM visibility", obj({
            "book_id": string(minimum=1), "entries": {"type": "array", "minItems": 1, "maxItems": 16, "items": entry}},
            ("book_id", "entries")), write_entries, mutation=True,
            guard=lambda args, owner: _digest(book_entries(args["book_id"])),
            preview=lambda args, owner: {"target_name": str((deps.list_book_entries(args["book_id"]).get("book") or {}).get("name") or args["book_id"]),
                "entries": args["entries"]}),
        AgentTool("edit_character_card", "Edit a reusable character's public narrative fields", obj({"card_id": string(minimum=1),
            "character_name": string(minimum=1), "background": string(16000), "race": string(),
            "class": string()}, ("card_id", "character_name")), edit_card, mutation=True,
            guard=lambda args, owner: _digest(deps.card_snapshot(args['card_id']) if deps.card_snapshot else card(args["card_id"])),
            preview=lambda args, owner: {"target_name": card(args["card_id"])["character_name"], "changes": args}),
    )
