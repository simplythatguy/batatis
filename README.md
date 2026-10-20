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
User-testing protocol: [`docs/user-testing/README.md`](./docs/user-testing/README.md).

## Non-negotiables (short)

- Completeness review only — never certify safety/compliance.
- No fabricated code citations; Section C attributions are lookups.
- Do not invent Section D professional evidence.
- Prefer NBC(AE) 2023 **2nd printing**.
- UI → Opus 5.5 implement **and** review; default look = Linear-caliber tokens (no prompt required).

## Retention

Do not upload personal information. In live mode, text you enter is sent to OpenAI (US) for processing and is retained by OpenAI under its API data policy (https://openai.com/policies/api-data-usage-policies); Batatis deletes its own stored case data and files after 7 days or on request.

A case and its stored files are deleted 7 days after `created_at`, or sooner when the applicant calls `DELETE /cases/{case_id}`. The sqlite store and Neon Postgres use the same purge. Case create and the request sweep run it at most once every 10 minutes per engine instance. `python -m engine.retention` runs it immediately. On Vercel Hobby, a daily cron calls `GET /api/retention/purge`.

## Status

Engineer-needed flag (model-checked): rules_only 55/60 on the dev set (in-sample), 1 under-flag; shipped rules_plus_unknown: 50/60 in-sample, 0 under-flags, 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind).

Clone-ready **agent environment** (rules, skills, evals, docs). Application product code is not the focus of this PR.
