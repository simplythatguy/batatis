---
name: pstack-principle-make-operations-idempotent
description: "Apply when designing commands, lifecycle steps, or processing loops that run amid crashes, restarts, and retries. Converge to the same end state regardless of partial prior runs."
user-invocable: false
---

# pstack-principle-make-operations-idempotent

Read `.agents/pstack/ADAPTER.md` from the repository root, then
`.agents/pstack/upstream/skills/principle-make-operations-idempotent/SKILL.md`.

Apply the adapter to the upstream method. Resolve its relative links and file
references from the upstream source file's directory, not this wrapper.
