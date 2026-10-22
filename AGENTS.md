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

- **Batatis challenge:** `.cursor/skills/batatis-*` (hackathon, variance-workflow, ui-opus, **ui-linear**, **ui-minimalist**).
- **Matt Pocock engineering:** `.agents/skills/` (also symlinked under `.cursor/skills/`). Reinstall with `npx skills@latest add mattpocock/skills -a cursor`.
- **pstack / poteto-mode:** Cursor plugin (not vendored). See `docs/pstack.md`. Review/judgment roles pinned to Opus 5.5 in `.cursor/rules/pstack-models.mdc`.

## What we are building

An AI tool that helps innovators prepare a **complete, code-referenced alternative solution (variance) application** (Safety Codes Variance Template Part 1, Sections **A–D**) and helps Safety Codes Officers (**SCOs**) review for **administrative completeness** — **not** technical correctness.

Pipeline: **Intake → Code identification → Supplemental case-building**.

Official NBC(AE) process fork (acceptable vs alternative): [`docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`](./docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png). Batatis targets the **alternative / variance** branch (SSRIA template); still detect when the user is on the acceptable-solution path.

## Before you code

1. Read `.cursor/skills/batatis-hackathon/SKILL.md` (domain + pitfalls + NBC(AE) fork).
2. For product flow work, read `.cursor/skills/batatis-variance-workflow/SKILL.md`.
3. For any UI / frontend / visual work: read `.cursor/skills/batatis-ui-linear/SKILL.md` (P0 rules) + `.cursor/skills/batatis-ui-opus/SKILL.md` + `.cursor/skills/batatis-ui-minimalist/SKILL.md` (how much goes on screen: icons before words, visuals over sentences, obvious questions as a label + control with help on demand, icon + count metadata). **Default product look** = the calm system (user decision 2026-10-20): `docs/design-system-calm.md`, contract `docs/design/calm-flow-prototype.html`, code `web/src/calm/`. It replaces the Linear look (`docs/design-system-linear.md` is history); the P0 rules still hold. Since 2026-10-22 it is **light mode with section colours and minimal text** (visuals over sentences); see the Tokens section. Primary CTAs stay **neutral** (near-black fill, never indigo). Use **Claude Opus 5.5** for UI implement **and** formal UI review (Composer is provisional). Simplify ruthlessly without dropping capabilities; meet the bug-free bar + `evals/ui-artifacts/smoke.mjs`.
4. Run understanding checks in `evals/fixtures/understanding-checklist.md` when changing skills/rules. Blind UI prompts: `evals/battle-prompts/ui-blind/`.

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
