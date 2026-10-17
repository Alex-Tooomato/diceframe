from __future__ import annotations

from copy import deepcopy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.adventures import AdventureBundleLoader, AdventureResolver, sync_adventure_catalog
from src.engine.game_instance import GameInstance, GameRegistry
from src.rulesets.registry import RulesetRuntimeRegistry
from src.rulesets.builtin import default_adventure_runtime_requirement
from src.webui.services import adventures


ROOT = Path(__file__).parents[1]
BUILTIN = ROOT / "templates" / "adventures"


def _api(tmp_path: Path) -> SimpleNamespace:
    runtime_dir = tmp_path / "data" / "templates" / "adventures"
    sync_adventure_catalog(BUILTIN, runtime_dir)
    api = SimpleNamespace(
        _adventure_loader=AdventureBundleLoader(runtime_dir),
        _reg=GameRegistry(tmp_path / "data" / "saves"),
    )
    api.dependencies = adventures.AdventureDependencies(
        adventure_loader=api._adventure_loader,
        list_instances=api._reg.list_all,
        load_rule_by_id=lambda _rule_id, _language: None,
        ruleset_registry=RulesetRuntimeRegistry(),
        default_runtime_requirement=default_adventure_runtime_requirement,
    )
    return api


def test_catalog_sync_marks_builtins_and_preserves_custom_directories(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "adventures"
    first = sync_adventure_catalog(BUILTIN, runtime_dir)
    custom = runtime_dir / "my_story"
    custom.mkdir()
    (custom / "manifest.json").write_text("{}", encoding="utf-8")

    second = sync_adventure_catalog(BUILTIN, runtime_dir)

    assert first["copied"] == 1
    assert (runtime_dir / "lanterns_of_greymoor" / ".diceframe-builtin").is_file()
    assert custom.is_dir()
    assert second["updated"] == 0


def test_copy_edit_export_import_and_delete_custom_adventure(tmp_path: Path) -> None:
    api = _api(tmp_path)
    copied = adventures.copy_adventure(api.dependencies, "core:lanterns_of_greymoor", {
        "directory_id": "my_greymoor",
        "adventure_id": "user:my_greymoor",
        "name": "我的灰沼冒险",
        "summary": "从内置包复制后独立维护。",
        "locale": "zh-CN",
    }, "zh-CN")
    assert copied["adventure_id"] == "user:my_greymoor"
    detail = adventures.adventure_detail(
        api.dependencies, "user:my_greymoor", "zh-CN",
    )["adventure"]
    assert detail["custom"] is True
    assert detail["editable"] is True
    files = deepcopy(detail["files"])
    files["manifest.json"]["version"] = "1.1.0"
    files["locales/zh-CN/adventure.json"]["fields"]["tutorial"]["name"] = "灰沼自定义版"

    updated = adventures.update_adventure(
        api.dependencies, "user:my_greymoor", {"files": files}, "zh-CN",
    )
    assert updated["content_digest"] != copied["content_digest"]
    loaded = api._adventure_loader.resolve("user:my_greymoor", "zh-CN")
    assert loaded.manifest.version == "1.1.0"
    assert loaded.adventure["tutorial"]["name"] == "灰沼自定义版"

    filename, payload = adventures.export_adventure(
        api.dependencies, "user:my_greymoor",
    )
    assert filename == "my_greymoor.dfadventure.zip"
    imported_api = _api(tmp_path / "imported")
    imported = adventures.import_adventure(
        imported_api.dependencies, payload, "imported_greymoor",
    )
    assert imported["adventure_id"] == "user:my_greymoor"
    assert imported_api._adventure_loader.resolve(
        "user:my_greymoor", "zh-CN",
    ).adventure["tutorial"]["name"] == "灰沼自定义版"

    assert adventures.delete_adventure(api.dependencies, "user:my_greymoor") == {
        "ok": True, "deleted": "user:my_greymoor",
    }


def test_create_adventure_starts_with_a_valid_editable_package(tmp_path: Path) -> None:
    api = _api(tmp_path)
    created = adventures.create_adventure(api.dependencies, {
        "directory_id": "fog_harbor_case",
        "name": "雾港失踪案",
        "summary": "从一个开场场景开始。",
    }, "zh-CN")
    assert created["adventure_id"] == "user:fog_harbor_case"
    bundle = api._adventure_loader.resolve("user:fog_harbor_case", "zh-CN")
    assert bundle.adventure["start_node_ids"] == ["opening"]
    assert bundle.adventure["nodes"][0]["scene_ref"] == "scene:fog_harbor_case_opening"
    assert bundle.manifest.required_runtime_id == "core:adventure"
    detail = adventures.adventure_detail(
        api.dependencies, "user:fog_harbor_case", "zh-CN",
    )["adventure"]
    assert detail["custom"] is True and detail["editable"] is True


def test_create_adventure_preserves_explicit_runtime_requirement(tmp_path: Path) -> None:
    api = _api(tmp_path)

    adventures.create_adventure(api.dependencies, {
        "directory_id": "external_rules_story",
        "name": "External rules story",
        "required_runtime": {"id": "example:custom", "minimum_version": 3},
    })

    bundle = api._adventure_loader.resolve("user:external_rules_story")
    assert bundle.manifest.required_runtime_id == "example:custom"
    assert bundle.manifest.required_runtime_version == 3


def test_new_adventure_declares_only_locales_with_shipped_translations(tmp_path: Path) -> None:
    api = _api(tmp_path)

    adventures.create_adventure(
        api.dependencies,
        {"directory_id": "english_fallback", "name": "English fallback"},
        "de",
    )

    root = api._adventure_loader.adventures_dir / "english_fallback"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    locales = {path.name for path in (root / "locales").iterdir() if path.is_dir()}
    assert manifest["supported_locales"] == ["zh-CN", "en"]
    assert manifest["default_locale"] == "en"
    assert locales == {"zh-CN", "en"}
    assert api._adventure_loader.resolve("user:english_fallback", "de").locale == "en"


def test_builtin_and_bound_adventures_are_protected(tmp_path: Path) -> None:
    api = _api(tmp_path)
    builtin = adventures.adventure_detail(
        api.dependencies, "core:lanterns_of_greymoor", "zh-CN",
    )["adventure"]
    with pytest.raises(PermissionError, match="built-in"):
        adventures.update_adventure(
            api.dependencies,
            "core:lanterns_of_greymoor",
            {"files": builtin["files"]},
            "zh-CN",
        )
    with pytest.raises(PermissionError, match="built-in"):
        adventures.delete_adventure(
            api.dependencies, "core:lanterns_of_greymoor",
        )

    adventures.copy_adventure(api.dependencies, "core:lanterns_of_greymoor", {
        "directory_id": "bound_story", "adventure_id": "user:bound_story",
    })
    bundle = api._adventure_loader.resolve("user:bound_story", "zh-CN")
    instance = GameInstance(
        game_key=("web", "bound-story", "web_bot"), world_id="greymoor",
    )
    assert instance.bind_adventure(bundle.binding("greymoor"))
    api._reg.register(instance)
    detail = adventures.adventure_detail(
        api.dependencies, "user:bound_story", "zh-CN",
    )["adventure"]
    assert detail["editable"] is False
    assert detail["bound_games"] == ["web|bound-story|web_bot"]
    with pytest.raises(PermissionError, match="bound to a save"):
        adventures.update_adventure(
            api.dependencies,
            "user:bound_story",
            {"files": detail["files"]},
            "zh-CN",
        )
    with pytest.raises(PermissionError, match="bound to a save"):
        adventures.delete_adventure(api.dependencies, "user:bound_story")


def test_import_rejects_core_identity_and_archive_traversal(tmp_path: Path) -> None:
    api = _api(tmp_path)
    _filename, builtin_payload = adventures.export_adventure(
        api.dependencies, "core:lanterns_of_greymoor",
    )
    with pytest.raises(ValueError, match="core namespace"):
        adventures.import_adventure(
            api.dependencies, builtin_payload, "forged_core",
        )


def _resolver_dependencies(api: SimpleNamespace, *, user_dir: Path | None):
    resolver = AdventureResolver.from_directories(BUILTIN, user_dir)
    api.dependencies = replace(
        api.dependencies,
        adventure_loader=resolver,
        adventure_resolver=resolver,
        builtin_adventures_dir=BUILTIN,
    )
    return api.dependencies


def test_custom_authoring_rejects_builtin_only_resolver(tmp_path: Path) -> None:
    api = _api(tmp_path)
    deps = _resolver_dependencies(api, user_dir=None)

    with pytest.raises(ValueError, match="registered user Adventure source"):
        adventures.create_adventure(
            deps, {"directory_id": "user_story", "name": "User story"}, "en",
        )


def test_custom_authoring_initializes_registered_missing_user_source(tmp_path: Path) -> None:
    api = _api(tmp_path)
    user_dir = tmp_path / "data" / "user-adventures"
    deps = _resolver_dependencies(api, user_dir=user_dir)
    assert not user_dir.exists()

    created = adventures.create_adventure(
        deps, {"directory_id": "user_story", "name": "User story"}, "en",
    )

    assert created["adventure_id"] == "user:user_story"
    assert (user_dir / "user_story" / "manifest.json").is_file()
    detail = adventures.adventure_detail(deps, "user:user_story", "en")["adventure"]
    assert detail["custom"] is True
