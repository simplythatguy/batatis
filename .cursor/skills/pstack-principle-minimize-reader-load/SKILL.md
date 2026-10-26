---
name: pstack-principle-minimize-reader-load
description: "Apply when reviewing or shaping code that's hard to trace. Count layers between question and answer, and hidden state in the reader's head; collapse one-caller wrappers and shrink mutable scope."
user-invocable: false
---

# pstack-principle-minimize-reader-load

Read `.agents/pstack/ADAPTER.md` from the repository root, then
`.agents/pstack/upstream/skills/principle-minimize-reader-load/SKILL.md`.

Apply the adapter to the upstream method. Resolve its relative links and file
references from the upstream source file's directory, not this wrapper.
