# Batatis — agent entrypoint

Alberta **Building Codes Challenge** (Built World Tech — Venture Pilots 2026).

## Git and environments (user decisions 2026-10-22 and 2026-10-24)

GitHub has one permanent branch, `main` (production). Each batch of work happens on a short-lived branch that becomes a pull request into `main`; GitHub deletes the branch after it merges. `dev` is retired. **Vercel deploys only `main`; preview deployments are disabled.** Locally the app runs on port `3000` (web) and `8000` (engine) only. Full rules: [`docs/agents/git-workflow.md`](./docs/agents/git-workflow.md).

- Flow: **branch from the latest `main`** → **verify locally** (`scripts/verify.sh`) → **open or update the pull request** (`scripts/land.sh`) → the user tests it locally and merges it.
- Every pull request into `main` uses the [plain-language format and update steps](./docs/agents/git-workflow.md#pull-request-descriptions): **New features added**, **Improvements**, **Bug Fixes**. This format takes precedence over generic PR-writing skills; children return their notes to the parent through task output.
- Agents opening or updating a PR must include a screen-recorded demo **if and only if the PR includes visual changes**. Follow the [PR demo requirement](./docs/agents/git-workflow.md#screen-recorded-demos) for recording, inspection, and linking the evidence.
- Never push to `main`, never merge a pull request unless the user asks, never force-push, never delete `main`, never recreate `dev`. Children never push; the parent opens the pull request. Run `scripts/install-git-hooks.sh` in a new clone.
- Push only verified work. Local verification is required even when GitHub Actions runs. Pull requests into `main` run CI; only a merge into `main` triggers Vercel.
- To catch a branch up with `main`, merge `origin/main` into it (`scripts/land.sh` does this). Never rebase a branch that is already on GitHub.
- Ports: `scripts/local-app.sh status|start|stop|wait`. If 3000 or 8000 is busy, wait for the owner. Never pick another port; stop what you start.

## Subagent communication (user decision 2026-10-23)

- Subagents report progress, questions, findings and handoffs only in their own task output and final result. The parent handles all coordination.
- Subagents must never send messages to any other thread or agent, including the parent and siblings. This applies to thread-send tools, attachment sends, native agent messaging and CLI/RPC equivalents.
- Automatic delivery of a task's completion result to its parent is allowed. Include this boundary in every subagent brief.

## Agent skills

### Issue tracker

GitHub Issues for `simplythatguy/batatis` via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` + `docs/adr/` + challenge brief. See `docs/agents/domain.md`.

### Stack skills

- **Project workflow:** For substantive work, read `.agents/pstack/ADAPTER.md`, select the relevant method, and use the tracked source. Pstack is included in every clone through the `pstack-*` skills in `.agents/skills/`, `.claude/skills/`, and `.cursor/skills/`; no global plugin installation is required. Simple answers and small edits stay direct.
- **Batatis challenge:** `.cursor/skills/batatis-*` (hackathon, variance-workflow, ui-opus, **ui-linear**, **ui-minimalist**).
- **Matt Pocock engineering:** `.agents/skills/` (also symlinked under `.cursor/skills/`). Reinstall with `npx skills@latest add mattpocock/skills -a cursor`.
- **README and diagrams:** `.agents/skills/prettyme` (also symlinked under `.cursor/skills/` and `.claude/skills/`), from [prettyme.md](https://github.com/simplythatguy/prettyme.md). Use it for any README or diagram work: Claude writes, and GPT-6.1-Sol only draws. Update with `npx skills@latest add simplythatguy/prettyme.md -a cursor -a claude-code -y`.
- **pstack / poteto-mode:** [Open Pstack](https://github.com/ericlitman/open-pstack), pinned in `.agents/pstack/upstream/`. Use `pstack-poteto-mode` for the full workflow or select a focused `pstack-*` skill. See `docs/pstack.md`. All delegated roles use **GPT-6.1-Sol at max** under the user decision of 2026-10-23; `.cursor/rules/pstack-models.mdc` carries the portable role map.

## What we are building

An AI tool that helps innovators prepare a **complete, code-referenced alternative solution (variance) application** (Safety Codes Variance Template Part 1, Sections **A–D**) and helps Safety Codes Officers (**SCOs**) review for **administrative completeness** — **not** technical correctness.

Pipeline: **Intake → Code identification → Supplemental case-building**.

Official NBC(AE) process fork (acceptable vs alternative): [`docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`](./docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png). Batatis targets the **alternative / variance** branch (SSRIA template); still detect when the user is on the acceptable-solution path.

## Before you code

1. Read `.cursor/skills/batatis-hackathon/SKILL.md` (domain + pitfalls + NBC(AE) fork).
2. For product flow work, read `.cursor/skills/batatis-variance-workflow/SKILL.md`.
3. For any UI / frontend / visual work: read `.cursor/skills/batatis-ui-linear/SKILL.md` (P0 rules) + `.cursor/skills/batatis-ui-opus/SKILL.md` + `.cursor/skills/batatis-ui-minimalist/SKILL.md` (how much goes on screen: icons before words, visuals over sentences, obvious questions as a label + control with help on demand, short renamable titles, icon + count metadata). **Default product look** = the calm system (user decision 2026-10-20): `docs/design-system-calm.md`, contract `docs/design/calm-flow-prototype.html`, code `web/src/calm/`. It replaces the Linear look (`docs/design-system-linear.md` is history); the P0 rules still hold. Since 2026-10-22 it is **light mode and minimal text** (visuals over sentences), and since the user's later correction **monotone: colour only identifies** where you are or tells crowded items apart, never decorates; see the Tokens section. Primary CTAs stay **neutral** (near-black fill, never indigo). Use **GPT-6.1-Sol at max** for UI implementation **and** independent UI review (user override, 2026-10-23). Simplify ruthlessly without dropping capabilities; meet the bug-free bar + `evals/ui-artifacts/smoke.mjs`.
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
