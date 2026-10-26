---
name: pstack-principle-separate-before-serializing-shared-state
description: "Apply when concurrent actors might write to the same file, branch, key, or state object. Eliminate the sharing first; serialize structurally only when one shared writer is a real invariant."
user-invocable: false
---

# pstack-principle-separate-before-serializing-shared-state

Read `.agents/pstack/ADAPTER.md` from the repository root, then
`.agents/pstack/upstream/skills/principle-separate-before-serializing-shared-state/SKILL.md`.

Apply the adapter to the upstream method. Resolve its relative links and file
references from the upstream source file's directory, not this wrapper.
