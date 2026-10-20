# Batatis — agent entrypoint

Alberta **Building Codes Challenge** (Built World Tech — Venture Pilots 2026).

## What we are building

An AI tool that helps innovators prepare a **complete, code-referenced alternative solution (variance) application** (Safety Codes Variance Template Part 1, Sections **A–D**) and helps Safety Codes Officers (**SCOs**) review for **administrative completeness** — **not** technical correctness.

Pipeline: **Intake → Code identification → Supplemental case-building**.

## Before you code

1. Read `.cursor/skills/batatis-hackathon/SKILL.md` (domain + pitfalls).
2. For product flow work, read `.cursor/skills/batatis-variance-workflow/SKILL.md`.
3. For any UI / frontend / visual work, read `.cursor/skills/batatis-ui-opus/SKILL.md` and use **Claude Opus 5.5** (highest available Opus 5.5 tier).
4. Run understanding checks in `evals/fixtures/understanding-checklist.md` when changing skills/rules.

Always-on rules: `.cursor/rules/batatis-hackathon.mdc`, `.cursor/rules/batatis-ui-opus.mdc`.

Human brief (Context store / mirrored): `docs/hackathon-problem-brief.md`.

## Non-negotiables

- Never claim the design complies or is safe; flag missing administrative items.
- Never fabricate code article numbers; prefer uncertainty + clarifying questions.
- Section C objective/function/intent = **deterministic lookup** after article identification.
- Do not author Section D professional evidence; recommend what evidence must address and when an engineer is required.
- Prefer **NBC – 2023 Alberta Edition, 2nd printing** citations first.
- Keep the data model portable across 430+ Alberta jurisdictions.
