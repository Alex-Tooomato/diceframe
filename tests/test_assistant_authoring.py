import pytest

from src.webui.services.assistant_authoring import AuthoringDependencies, authoring_tools


def tools(entries, save):
    return {tool.name: tool for tool in authoring_tools(AuthoringDependencies(
        list_worlds=lambda: {"worlds": []}, update_world=lambda *a: {},
        list_book_entries=lambda book: {"ok": True, "entries": entries}, save_book_entry=save,
        list_cards=lambda: {"cards": []}, update_card=lambda *a: {},
        adventure_detail=lambda *a: {}, get_rule=lambda *a: {},
    ))}


@pytest.mark.asyncio
async def test_book_entry_writes_cannot_guess_existing_ids_or_publish_private_markers():
    writes = []
    def save(book, row):
        writes.append((book, row))
        return {"ok": True}
    writer = tools([{"id": "known", "name": "Old"}], save)["write_lorebook_entries"]
    with pytest.raises(ValueError, match="exist"):
        await writer.handler({"book_id": "book", "entries": [{"id": "guessed", "name": "Name", "content": "Text"}]}, "owner")
    with pytest.raises(ValueError, match="private"):
        await writer.handler({"book_id": "book", "entries": [{"name": "Note", "content": "GM: A hidden trap", "visibility": "public"}]}, "owner")
    assert writes == []
    assert writer.mutation
    result = await writer.handler({"book_id": "book", "entries": [
        {"name": "Public", "content": "Harbor", "visibility": "public"},
        {"name": "Hidden", "content": "GM: A hidden trap"}]}, "owner")
    assert result["ok"]
    assert writes[0][1]["visible_to"] == ["*"]
    assert writes[1][1]["visible_to"] == []


@pytest.mark.asyncio
async def test_book_batch_reports_partial_results_and_does_not_hide_owner_failure():
    count = [0]
    def save(book, row):
        count[0] += 1
        return {"ok": count[0] == 1, "error": "cannot save"}
    writer = tools([], save)["write_lorebook_entries"]
    result = await writer.handler({"book_id": "b", "entries": [
        {"name": "One", "content": "First"}, {"name": "Two", "content": "Second"}]}, "owner")
    assert not result["ok"] and result["partial"] and len(result["results"]) == 2


@pytest.mark.asyncio
async def test_existing_public_entry_cannot_receive_gm_text_without_visibility_change():
    writes = []
    writer = tools([{"id": "public", "visible_to": ["*"]}], lambda *args: writes.append(args))["write_lorebook_entries"]
    with pytest.raises(ValueError, match="private"):
        await writer.handler({"book_id": "b", "entries": [{"id": "public", "name": "Note", "content": "GM: Hidden trap"}]}, "owner")
    assert not writes
