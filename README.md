# Batatis

Agent-ready environment for the Alberta **Building Codes Challenge** (Built World Tech — Venture Pilots 2026).

We are building an AI tool that helps innovators prepare **complete alternative-solution (variance) applications** and helps Safety Codes Officers review them for **administrative completeness** — not technical correctness.

## Clone and start agents

```bash
git clone https://github.com/simplythatguy/batatis.git
cd batatis
# Optional: refresh Matt Pocock skills
npx skills@latest add mattpocock/skills -a cursor
```

Open the repo in **Cursor**. New agent threads should:

1. Read [`AGENTS.md`](./AGENTS.md) (entrypoint).
2. Follow always-on rules under [`.cursor/rules/`](./.cursor/rules/) (includes **pstack model map** + **review = Opus 5.5**).
3. Install **pstack** plugin once: `/add-plugin pstack` — see [`docs/pstack.md`](./docs/pstack.md).
4. Load skills as tasks demand:
   - `.cursor/skills/batatis-*` — challenge domain / variance / **UI Linear system** / UI Opus pin
   - `.agents/skills/` — Matt Pocock engineering skills (triage, tdd, grill-*, etc.)
5. Use [`evals/fixtures/`](./evals/fixtures/) and [`evals/battle-prompts/`](./evals/battle-prompts/) (incl. `ui-blind/`) to verify understanding.
6. **All quality reviews** of agent outputs use Claude Opus 5.5 (max/xhigh). UI review also Opus 5.5.

Human-oriented brief: [`docs/hackathon-problem-brief.md`](./docs/hackathon-problem-brief.md).  
NBC(AE) acceptable vs alternative process: [`docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`](./docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png).  
Product UI system: [`docs/design-system-linear.md`](./docs/design-system-linear.md).

## Non-negotiables (short)

- Completeness review only — never certify safety/compliance.
- No fabricated code citations; Section C attributions are lookups.
- Do not invent Section D professional evidence.
- Prefer NBC(AE) 2023 **2nd printing**.
- UI → Opus 5.5 implement **and** review; default look = Linear-caliber tokens (no prompt required).

## Product UI kit

Linear-themed shadcn lives in [`apps/web`](./apps/web). Stock imports are `@/components/ui/*`. Colors map in `apps/web/app/globals.css`. Eval colors live in [`docs/design/variables.css`](./docs/design/variables.css).

```bash
cd apps/web && npm install && npm run dev
# open /gallery
node scripts/assert-linear-theme.mjs
```

## Status

Clone-ready **agent environment** (rules, skills, evals, docs) plus a Linear-themed shadcn kit under `apps/web`.
