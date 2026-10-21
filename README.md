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

## Status

Engineer-needed flag. At measured source `d479e82`, the shipped facts-only `rules_plus_unknown` agreed with model gold on 50/60 text-only dev cases (0 no outputs, 27 unknowns) and 8/11 model-constructed no-ground-truth (no-gt) cases (PR #26; 8 no outputs, 3 unknowns). Unshipped `rules_only` had 55/60 dev agreement and 1 under-flag.

Both shipped sets had 0 under-flags, defined only as gold yes to system no. The three no-gt gold-yes cases (`ngt-101`, `ngt-102`, `ngt-103`) abstained; these are misses, not correct answers. Zero under-flags on dev is by design because it never answered no. All current cases are in-sample, model-checked, not human-verified. Neither model gold nor the receipt's self-check is independent expert validation.

These counts do not establish applicability, equivalence, professional approval or safety, or validate the full Case/API/export flow. They apply only to `d479e82`, not this document branch, newer source, a deployment or a final release. Historical shipped-variant results remain 7/8 blind pre-fix and 4/8 post-fix (no longer blind); neither was rerun for this receipt. Source: [Data Nerd receipt `d75e7ff`](https://github.com/simplythatguy/batatis/blob/d75e7ff0fabb89a2d3f23792ceba8ce116536b35/evals_dev/section_d_flag/RESULTS.md).

Clone-ready **agent environment** (rules, skills, evals, docs). Application product code is not the focus of this PR.
