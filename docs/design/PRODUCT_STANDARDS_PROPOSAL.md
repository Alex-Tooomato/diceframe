# Product standards and durable advantages

Status: proposal for maintainer discussion, 2026-10-15. This note does not introduce a schema, API, migration, adopted ADR or release promise. Existing [engineering rules](../ENGINEERING_RULES.md), [architecture](../ARCHITECTURE_EN.md) and [accepted ADRs](../adr/README.md) remain authoritative.

## Positioning

Build an extensible, self-hostable game platform where AI helps create and narrate, the server owns game state, and creators can reuse their content across campaigns and supported interfaces. Make this promise visible in complete user journeys, not only in internal abstractions.

Feature count alone is a weak advantage. Friends & Fables already advertises an AI GM, lore, world-building tools, branching quests, multiplayer and tactical 5e combat. AI Dungeon documents automatic summaries and memory retrieval. Foundry documents package identity, dependency and compatibility metadata. These are facts from their own documentation, not a comparative reliability benchmark. The proposed direction below is our inference from that overlap. Sources checked on 2026-10-15: [Friends & Fables](https://fables.gg/), [AI Dungeon memory](https://help.aidungeon.com/faq/the-memory-system), [Foundry module development](https://foundryvtt.com/article/module-development/).

## Standards to make enforceable

| Area | Product promise | Evidence for acceptance |
| --- | --- | --- |
| Content | World, Book, Adventure and package have distinct roles; a title never substitutes for canonical identity | Same-title resources from different sources remain distinct through import, edit, export and game creation; users can see what each game actually references |
| Rules and modes | Capabilities declare supported mechanics, progression and transport access; every advertised restriction is enforced on the server | A Bot marked read-only cannot mutate; absent optional capabilities have safe defaults; missing access/authority dependencies reject unsafe operations |
| AI operations | Models propose operations; validated services authorize and execute them; users can understand progress, cancellation and cost scope | No unconfirmed persistent write; repeated confirmations are idempotent; cancellation preserves reviewable drafts; per-request output budgets are not mislabeled as total spending caps |
| User data | Updates preserve user-owned content and explain incompatibility before modifying it | Old save fixtures, independent databases, failed upgrade recovery and referenced-content preservation pass at supported version boundaries |
| Interface | Common paths stay compact; hidden settings remain discoverable; every unavailable action explains what is missing | Import → review → publish → start works on desktop and phone; main actions fit the viewport; task panels can fold; errors and completion are observable |
| Extensions | A feature has one owner and a public contract; transports and central views compose it | A new ruleset/mode/provider uses a capability, adapter or registry; it does not add concrete mechanics branches throughout generic paths |
| Maintenance | Community contributions carry a bounded maintenance obligation | Core English/Chinese are maintained; community locales follow the existing active/paused and source-review policy with English fallback; no accidental permanent obligation for the core maintainer |

Do not create a parallel universal manifest now. First inventory and reuse ContentRef, package manifests, ruleset capabilities, module hooks and translation policy. Where a new contract is necessary, name its owner, version and failure behavior explicitly. Package compatibility and ownership metadata must represent evidence, not self-certified marketing claims.

For issue #535, the proposed boundary is: access control is essential; rollback and transaction integrity are essential even if economy gameplay is optional. Keep the minimum authoritative contract required by those promises, and separate optional presentation/policy capabilities. A high count of failing tests after removing a module does not by itself prove the whole module should be kernel. Inspect callers and failure modes before changing `KERNEL_MODULES`. Split `table_settings` only with an explicit persisted-slot plan that preserves existing values.

## Advantages worth investing in

1. **Trustworthy long campaigns.** Deterministic rules, recoverable updates, state history and multiplayer privacy let users invest time without constantly repairing AI mistakes. Contract tests, saved fixtures and failure recovery accumulate into an advantage; an assertion of reliability alone does not.
2. **A reusable creator ecosystem.** A creator can draft or import material, correct it, publish a versioned package, and prove it works in a game. Good examples, import diagnostics, source identity, dependency closure and author maintenance are more valuable than adding many disconnected editors. Respect creators' rights and publish only licensed or original fixtures.
3. **One game across interfaces and models.** Web, mobile and Bot clients use the same authoritative game. Replaceable model transports and self-hosting reduce provider dependence, but the experience must survive model changes, disconnects and reconnection. Provider-specific protocol behavior belongs in an adapter; API settings keep the existing provider-reference contract.
4. **A public conformance kit.** Reusable sample packs, validator diagnostics and observable behavioral tests help outside authors produce compatible content. A badge should name the tested version and scope; passing an import parser is not proof of gameplay compatibility. Avoid an expensive marketplace or certification bureaucracy before authors can complete the basic workflow.

The accumulating assets are compatible creator content, extension authors, reproducible campaign fixtures, reliable migrations and user trust. Keep user data portable. Do not depend on lock-in, secret prompts, unsupported claims about model intelligence, or collecting private campaign transcripts by default.

## Suggested order

First stabilize the complete import/play/update paths and provider compatibility issues. Convert repeated UI complaints into shared component behavior, and prioritize failed authority or recovery contracts over additional preview modes. Keep experimental modes explicitly labeled until their restrictions and save behavior are verified.

Then publish a small set of original/licensed example packages and a contributor quickstart: a short adventure, a CoC investigation, a D&D rules-backed encounter, and a minimal extension example. Use the same examples for import, references, permissions, cancellation, replay and update checks; do not maintain a second Markdown list of test filenames.

Finally expand the extension and creator ecosystem around proven contracts. Introduce a new long-term boundary through an ADR; use an ordinary design note for routine implementation. Assess richer modes and distribution services only after their content can complete a validated game journey.

Measure task completion, import blocker clarity, save recovery, denied unauthorized mutations, reference preservation, model compatibility and cost visibility. Define targets before the next milestone, collect a baseline, and report results with the tested scope. No numerical target here is a claim about current performance.
