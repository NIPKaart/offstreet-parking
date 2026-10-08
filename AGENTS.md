# NIPKaart collector agent guidance

This repository is a source collector in the NIPKaart ecosystem. The shared, cross-repository agent workflows live in [NIPKaart/skills](https://github.com/NIPKaart/skills):

- [nipkaart-context](https://github.com/NIPKaart/skills/blob/main/nipkaart-context/SKILL.md): system ownership and authoritative contracts.
- [cross-repo-planning](https://github.com/NIPKaart/skills/blob/main/cross-repo-planning/SKILL.md): verify existing work before creating issues or planning changes.
- [dataset-integration](https://github.com/NIPKaart/skills/blob/main/dataset-integration/SKILL.md): source-to-publication acceptance.
- [collector-review](https://github.com/NIPKaart/skills/blob/main/collector-review/SKILL.md): collector PR review.
- [retro](https://github.com/NIPKaart/skills/blob/main/retro/SKILL.md): evidence-led ecosystem retrospective.

The shared skills repository is private. Only agents with authorized access can load these workflows; links do not install skills or grant access. When access is unavailable, follow the local instructions and accessible contracts instead. Never claim to have used a skill that could not be loaded.

## Local authority

Before editing, inspect this repository's README, pyproject.toml, source adapters, delivery/export implementation, tests and CI. Run the documented local checks relevant to the change.

Collectors retrieve, normalize and deliver source data. NIPKaart/core owns validation, source approval, moderation and publication. Check the **current** producer and core consumer contract together before changing schemas, source identifiers, transport or publication assumptions. Do not claim production acceptance based only on local tests.

Do not duplicate authoritative core contracts or accepted ADRs here. Keep local code-specific conventions in this repository, and reusable cross-repository procedures in NIPKaart/skills.
