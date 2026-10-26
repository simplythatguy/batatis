# Architecture decision records

`AGENTS.md` and `docs/agents/domain.md` point here. This is a single-context repo: system-wide decisions live in this directory.

One decision per file, numbered in order: `0001-short-slug.md`, `0002-short-slug.md`, and so on. The body is a short paragraph — the context, what was decided, and why. Add a status line, the options that were turned down, or the consequences only when a later reader needs them. The format is in `.cursor/skills/domain-modeling/ADR-FORMAT.md`.

Record a decision when it is hard to reverse, surprising without the context, and the result of a real trade-off. The domain-modeling skill adds a file when a decision of that kind is actually made.

[0001](0001-vite-web-canonical.md) records that `web/` is the canonical frontend. [0002](0002-use-what-the-applicant-gave.md) records that intake uses what the applicant already gave and asks only what is missing or unclear. Other choices for the current build are written in [`docs/research/2026-10-20-vision/2-week-build.md`](../research/2026-10-20-vision/2-week-build.md), under "Architecture: reuse first" and "Decisions settled on 2026-10-20". Copy one into this directory when it meets the bar above.
