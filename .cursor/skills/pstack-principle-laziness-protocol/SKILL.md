---
name: pstack-principle-laziness-protocol
description: "Apply when refactoring, evaluating diff size, or tempted to add abstractions, layers, or signal threading. Bias toward deletion and the smallest change that solves the problem."
user-invocable: false
---

# pstack-principle-laziness-protocol

Read `.agents/pstack/ADAPTER.md` from the repository root, then
`.agents/pstack/upstream/skills/principle-laziness-protocol/SKILL.md`.

Apply the adapter to the upstream method. Resolve its relative links and file
references from the upstream source file's directory, not this wrapper.
