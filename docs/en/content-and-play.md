# Content, characters and play

English | [简体中文](../zh/content-and-play.md)

This guide covers the content and play workflows in the current application. See [application updates](updates.md) before upgrading an existing installation.

## Worlds, lorebooks, rules and adventures

| Content | Purpose |
|---|---|
| World | The setting and identity of a game, its background, default rules and associated lorebooks |
| Lorebook | Detailed NPC, place, item, faction and background knowledge retrieved for the GM as needed |
| Rules | The authoritative check, character and combat capabilities; translated names do not change them |
| Adventure | A versioned story graph with scenes, objectives, branches and optional encounters |
| Content pack | An installable source containing adventures and reusable resources |

A short world description is a setting summary, not its complete knowledge base. Lorebooks supply the detail. Installing a pack does not inject all its resources into every model request.

Use **Content library** to browse worlds, adventures and lorebooks. World cards offer starting a game and managing its lorebooks. The world gallery also offers preview and **Clone world**; cloning creates an editable personal world.

During game creation, choose a template, custom world or AI-generated draft. The compact view keeps the common choices visible; expandable settings retain language, seed, additional background and game-specific lorebook selection. Choosing books for this game changes only its bindings. Editing a shared source book can affect other games that reference it; use a personal copy when you need independent content.

Standard free play uses normal GM narration. Adventure mode follows the selected adventure and its supported rules. Compatibility is checked by the server; a D&D 2014 module is not silently converted to D&D 2024.

## Install or create an adventure

1. Open **Content packs** from the library. Choose online content or a local `.dfplugin` file.
2. Preview installation effects and resolve blocking errors. Confirm installation and check the resulting status or error message.
3. Open a pack's details, choose an adventure and select **Use this adventure**.
4. Review the world, rules, lorebooks and characters, then start the game.

Use **Adventure packages** to create an original adventure, generate an AI draft, import a native package, import a script/external module, or organize existing text. Saved games pin the adventure's identity, version and digest. Updates, disable and uninstall are blocked when they would break those bindings; inspect the affected saves instead of deleting package files.

## Import a script, PDF or external module

The import page accepts UTF-8 Markdown/TXT, Foundry Adventure export JSON, unencrypted Fantasy Grounds XML/`.mod`, and PDFs with a text layer. It reads local data into a draft. It does not execute module scripts, install an entire Foundry system, read arbitrary LevelDB collections or fetch external attachments. Scanned PDFs need OCR before import.

1. Choose the file and parse it. Inspect extracted chapters, scenes, GM notes, resources and references.
2. Correct the draft and its visibility. Imported content starts GM-only; make material public deliberately.
3. Resolve errors. An unresolved NPC, location or encounter reference blocks publication unless you explicitly keep it as prose.
4. Validate again after editing. Review the publication checklist and confirmation; the page explains why **Publish as adventure** is unavailable.
5. Publish the validated draft, then use that adventure to create a game.

Numbers in external prose remain reference material. Import does not turn monster statistics, spells, rewards or house rules into executable mechanics.

**AI organize draft** is optional. It uses the configured main model, sends the draft text to that provider and consumes tokens. Confirm the usage notice before starting. The progress bar reports completed processing steps, not a guaranteed duration. Canceling or closing the import dialog stops pending work, but completed calls may still be billed. Review the generated result and explicitly adopt it; failed, canceled or unadopted results do not replace your edited draft. Validate and confirm publication afterward.

## Adventure branches and secrets

The GM sees the full adventure; players receive only its public projection. Native exclusive choices can collect player proposals and require GM confirmation before committing one branch. The server checks the current run and state, preventing stale proposals from advancing another run.

The text marker `@choice label -> scene_id` defines a graph connection. Several unconditional connections can open together; this marker alone does not declare a native exclusive-choice group. Configure the structured choice in the adventure editor when that behavior is needed.

## Character cards, invitations and AI seats

**Character card library** stores reusable cards; **This game's characters** manages participants in the active game. Applying a card to a character that has already acted requires GM authority. The reusable card and a character's current game state serve different purposes.

On the play page, use **Invite players** beneath the party list. Share the actual invitation URL and let the player open it. Players do not need to extract or type `web|room|host` from a link. Invitations and seat credentials follow the server's access policy; a bare legacy player ID is not a credential. If an old link no longer authenticates, the GM should issue a new invitation.

AI-hosted seats and companions use the same server action and rules boundaries as human players. Their policy belongs to the game and survives saving/loading; narration cannot independently grant private information or bypass resource costs.

## Checks and combat

Available check modes depend on the selected rules and GM policy. CoC Push is a linked follow-up to an eligible failed check, not an unrestricted reroll. Required GM consent and its consequences remain attached to that check.

In D&D 2024 authoritative combat, available spells depend on the character's prepared/granted spells, resources and current trigger. A level 2+ Paladin gains **Divine Smite** through Paladin's Smite. It becomes available after a qualifying melee hit while the bonus action and a spell slot or free use remain available. It is not an always-available attack button. Long Rest restores the class's free use. This follows the supported 2024 rules, not the 2014 version of Smite.

The Lite rules and custom rules expose only the actions their runtime declares. Missing spell mechanics are not inferred from a class name. See [rules and dice](rules-and-dice.md) and the [automation coverage](../rulesets/dnd2024/AUTOMATION_COVERAGE.md) for the implemented boundary.

## DF Agent and recovery

The owner's DF Agent can search documentation, inspect game/content state and prepare drafts. Model-directed writes require the application's review and confirmation flow and remain subject to the owning service's permissions. Ordinary player pages do not expose the owner agent. Read the proposed changes before confirming; AI operations use the configured provider and may consume tokens.

Operations use the live tool catalog and current application state. Help is retrieved only when needed through `search_documentation`, using this installed version's bundled English or Simplified Chinese instructions. Development checkouts use their current local files. Moving remote manuals and older unversioned indexes do not describe the Agent's available actions or enter every conversation automatically.

On phones, **Game tools** groups character information, scene maps and the party; the GM workspace retains its own top entry. The compact character status strip also opens the character drawer. These replace the duplicate floating navigation buttons.

Lorebook operation history supports reviewing and recovering supported changes. Recovery is owner-private and validates its plan before applying it. It does not replace an upgrade backup: preserve the complete `data/` directory before changing program versions.
