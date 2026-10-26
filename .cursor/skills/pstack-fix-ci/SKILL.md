---
name: pstack-fix-ci
description: Find failing PR checks, inspect logs or external check links, and apply focused fixes
---

# pstack-fix-ci

Read `.agents/pstack/ADAPTER.md` from the repository root, then
`.agents/pstack/upstream/skills/fix-ci/SKILL.md`.

Apply the adapter to the upstream method. Resolve its relative links and file
references from the upstream source file's directory, not this wrapper.
