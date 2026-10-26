---
name: pstack-deslop
description: Remove AI-generated code slop and clean up code style
---

# pstack-deslop

Read `.agents/pstack/ADAPTER.md` from the repository root, then
`.agents/pstack/upstream/skills/deslop/SKILL.md`.

Apply the adapter to the upstream method. Resolve its relative links and file
references from the upstream source file's directory, not this wrapper.
