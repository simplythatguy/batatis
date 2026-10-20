# Batatis

Agent-ready environment for the Alberta **Building Codes Challenge** (Built World Tech — Venture Pilots 2026).

We are building an AI tool that helps innovators prepare **complete alternative-solution (variance) applications** and helps Safety Codes Officers review them for **administrative completeness** — not technical correctness.

## Clone and start agents

```bash
git clone https://github.com/simplythatguy/batatis.git
cd batatis
```

Open the repo in **Cursor**. New agent threads should:

1. Read [`AGENTS.md`](./AGENTS.md) (entrypoint).
2. Follow always-on rules under [`.cursor/rules/`](./.cursor/rules/).
3. Load skills under [`.cursor/skills/`](./.cursor/skills/) as tasks demand:
   - `batatis-hackathon` — domain + pitfalls
   - `batatis-variance-workflow` — product pipeline
   - `batatis-ui-opus` — **all UI work uses Claude Opus 5.5** (highest available Opus 5.5 tier)
4. Use [`evals/fixtures/understanding-checklist.md`](./evals/fixtures/understanding-checklist.md) to verify agents still understand the challenge after skill/rule edits.

Human-oriented brief: [`docs/hackathon-problem-brief.md`](./docs/hackathon-problem-brief.md).  
NBC(AE) acceptable vs alternative process: [`docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`](./docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png).

## Non-negotiables (short)

- Completeness review only — never certify safety/compliance.
- No fabricated code citations; Section C attributions are lookups.
- Do not invent Section D professional evidence.
- Prefer NBC(AE) 2023 **2nd printing**.
- UI → Opus 5.5.

## Status

Clone-ready **agent environment** (rules, skills, evals, docs). Application product code is not the focus of this PR.
