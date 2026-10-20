# Batatis — agent entrypoint

Alberta **Building Codes Challenge** (Built World Tech — Venture Pilots 2026).

## Agent skills

### Issue tracker

GitHub Issues for `simplythatguy/batatis` via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` + `docs/adr/` + challenge brief. See `docs/agents/domain.md`.

### Stack skills

- **Batatis challenge:** `.cursor/skills/batatis-*` (hackathon, variance-workflow, ui-opus, **ui-linear**).
- **Matt Pocock engineering:** `.agents/skills/` (also symlinked under `.cursor/skills/`). Reinstall with `npx skills@latest add mattpocock/skills -a cursor`.
- **pstack / poteto-mode:** Cursor plugin (not vendored). See `docs/pstack.md`. Review/judgment roles pinned to Opus 5.5 in `.cursor/rules/pstack-models.mdc` when available.

## What we are building

An AI tool that helps innovators prepare a **complete, code-referenced alternative solution (variance) application** (Safety Codes Variance Template Part 1, Sections **A–D**) and helps Safety Codes Officers (**SCOs**) review for **administrative completeness** — **not** technical correctness.

Pipeline: **Intake → Code identification → Supplemental case-building**.

Official NBC(AE) process fork (acceptable vs alternative): [`docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`](./docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png). Batatis targets the **alternative / variance** branch (SSRIA template); still detect when the user is on the acceptable-solution path.

## Before you code

1. Read `.cursor/skills/batatis-hackathon/SKILL.md` (domain + pitfalls + NBC(AE) fork).
2. For product flow work, read `.cursor/skills/batatis-variance-workflow/SKILL.md`.
3. For any UI / frontend / visual work: read `.cursor/skills/batatis-ui-linear/SKILL.md` + `.cursor/skills/batatis-ui-opus/SKILL.md`. **Default product look** = Linear-caliber system (`docs/design-system-linear.md`, `docs/design/tokens.css`). Primary CTAs are **neutral grey** (not indigo fill); focus rings neutral (never indigo); inferred owner + unified resolve continue are Opus P0. Prefer **Claude Opus 5.5** for UI implement **and** formal UI review when available (Composer is provisional — do not fake a seal). Simplify ruthlessly without dropping capabilities; meet the bug-free bar + `evals/ui-artifacts/smoke.mjs`.
4. Run understanding checks in `evals/fixtures/understanding-checklist.md` when changing skills/rules. Domain adversarial: `evals/battle-prompts/` (BT01–BT50). Blind UI: `evals/battle-prompts/ui-blind/` (UI-B01–B07). Clone walkthrough: `docs/env-guide.md`.

Always-on domain rule: `.cursor/rules/batatis-hackathon.mdc`. UI globs: `.cursor/rules/batatis-ui-opus.mdc`, `.cursor/rules/batatis-ui-linear.mdc`.

Human brief: `docs/hackathon-problem-brief.md`.

## Non-negotiables

- Never claim the design complies or is safe; flag missing administrative items.
- Never fabricate code article numbers; prefer uncertainty + clarifying questions.
- Section C objective/function/intent = **deterministic lookup** after article identification.
- Do not author Section D professional evidence; recommend what evidence must address and when an engineer is required.
- On the **alternative** fork: do **not** skip risk assessment, mitigating measures, or assumptions/limits.
- Prefer **NBC – 2023 Alberta Edition, 2nd printing** citations first.
- Keep the data model portable across 430+ Alberta jurisdictions.
