---
name: pstack-arena
description: "Spawn N parallel candidates at the same task, pick a base, graft the strongest parts of the losers into it. Use for /arena, 'arena this', 'throw it in the arena', or when one attempt at a non-trivial artifact would lock in the wrong shape."
---

# pstack-arena

Read `.agents/pstack/ADAPTER.md` from the repository root, then
`.agents/pstack/upstream/skills/arena/SKILL.md`.

Apply the adapter to the upstream method. Resolve its relative links and file
references from the upstream source file's directory, not this wrapper.
