# Documentation map

Start here when developing or using DiceFrame. The source in the checked-out revision and its architecture documents describe current behavior. A plan or archived handoff does not override them.

## Current contracts

- Architecture: [English](ARCHITECTURE_EN.md) · [简体中文](ARCHITECTURE_CN.md)
- [Engineering rules](ENGINEERING_RULES.md): ownership, authority, data, extensions and contract testing
- [Accepted architecture decisions](adr/README.md): why durable boundaries were chosen
- Content: [Adventure bundle](adventures/ADVENTURE_BUNDLE_EN.md), [lorebook adapter](LOREBOOK_ADAPTER_GUIDE.md), [content synchronization](content-sync/CONTRACT.md)
- Plugin development: [English](plugins/EXTENDING_EN.md) · [简体中文](plugins/EXTENDING_CN.md)

## User guides

| Topic | English | 简体中文 |
| --- | --- | --- |
| Content and play, including DF Agent | [Guide](en/content-and-play.md) | [指南](zh/content-and-play.md) |
| Updates and recovery | [Guide](en/updates.md) | [指南](zh/updates.md) |
| Rules and dice | [Guide](en/rules-and-dice.md) | [指南](zh/rules-and-dice.md) |
| Direct connections | [Guide](en/direct-connect.md) | [指南](zh/direct-connect.md) |
| Translation maintenance | [Policy](en/translations.md) | [政策](zh/translations.md) |
| Lorebook management | [Guide](LOREBOOK_USER_GUIDE_EN.md) | [指南](LOREBOOK_USER_GUIDE_CN.md) |

## Design and history

`design/` contains scoped design notes and implementation contracts. Read each note's status before treating a planned feature as implemented. [DF Agent](design/DF_AGENT_IMPLEMENTATION.md) describes the current agent protocol; [product standards proposal](design/PRODUCT_STANDARDS_PROPOSAL.md) is a proposal for discussion, not an adopted new API or release commitment.

[Archived plans and handoffs](archive/README.md) preserve historical decisions and unfinished inventories. Their branch names, PR ordering and test counts are historical. Temporary review reports, local paths, approval drafts and execution logs belong outside the published documentation; report their outcomes in the working conversation.

When a change lands, update its user guide and affected contract. Keep a durable decision in an ADR, keep a proposal explicitly marked as a proposal, and archive superseded execution plans. Do not maintain a second manual catalog of test names or copy session transcripts into `docs/`.
