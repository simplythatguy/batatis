# Batatis cloneable agent environment

Battle-oriented stack for Alberta Building Codes Challenge agents. **PR #1 is merged** — work from `main` (or a feature branch off it).

## 1. Clone

```bash
git clone https://github.com/simplythatguy/batatis.git
cd batatis
# default branch main is clone-ready
```

## 2. Fresh-clone installs (order matters)

### A. Open in Cursor

Rules under `.cursor/rules/` apply automatically. Read `AGENTS.md` first.

### B. pstack / poteto-mode (plugin — not vendored)

1. In Cursor chat: `/add-plugin pstack` (or install **pstack / poteto** from the plugin marketplace).
2. Confirm committed map exists: `.cursor/rules/pstack-models.mdc` (Opus 5.5 for judgment/review when available).
3. Optional: `/setup-pstack` only to retarget models for your account — **keep review roles on Opus 5.5**.
4. For nontrivial feature/eval/shipping work: `/poteto-mode`.
5. Details: [`docs/pstack.md`](./pstack.md).

If you skip this step, Batatis domain skills still work; poteto-mode / pstack playbooks will not.

### C. Matt Pocock skills (already vendored — refresh optional)

Committed under `.agents/skills/` and symlinked into `.cursor/skills/`, locked by `skills-lock.json`.

On a **fresh machine** you can work immediately. To **refresh** from upstream:

```bash
npx skills@latest add mattpocock/skills -a cursor
```

Domain pointers: `docs/agents/` (`domain.md`, `issue-tracker.md`, `triage-labels.md`).

### D. Batatis challenge + Linear-default UI (committed — no install)

| Piece | Path |
| --- | --- |
| Domain / variance / pitfalls | `.cursor/skills/batatis-hackathon`, `batatis-variance-workflow` |
| UI model pin | `.cursor/skills/batatis-ui-opus` → **Claude Opus 5.5** implement **and** review **when available** |
| Default product look | `.cursor/skills/batatis-ui-linear` + [`docs/design-system-linear.md`](./design-system-linear.md) + [`docs/design/tokens.css`](./design/tokens.css) |
| References | [`docs/design/linear-reference/`](./design/linear-reference/) |

Agents must produce Linear-caliber UI **without** the user saying “Linear.” Simplify ruthlessly; do not drop capabilities; meet the bug-free bar. Prefer Opus 5.5 for UI; if usage is blocked, keep smoke green and treat cheaper reviews as provisional only — never fake an Opus seal.

## 3. Start an agent thread

1. Open the repo in Cursor.
2. Read `AGENTS.md`.
3. Domain: `batatis-hackathon` + `docs/hackathon-problem-brief.md` + diagram.
4. Product flow: `batatis-variance-workflow`.
5. **Any UI:** `batatis-ui-linear` + `batatis-ui-opus` → Opus 5.5 (when available) + tokens.
6. Engineering workflows: Matt Pocock skills via `docs/agents/`.
7. Nontrivial work: `/poteto-mode` after pstack install.
8. **Every quality / UI review:** Opus 5.5 preferred (`claude-opus-5-5-max` when available).

## 4. Prove the env

```text
evals/battle-prompts/           # BT01–BT50 domain suite
evals/battle-prompts/ui-blind/  # UI-B01–B07 feature-only prompts (no look keywords)
evals/ui-artifacts/             # HTML surfaces + smoke.mjs
evals/fixtures/                 # short checklist
```

```bash
node evals/ui-artifacts/smoke.mjs   # must PASS before claiming UI progress
```

Pass bars: domain ≥ 4.0/5 under Opus 5.5 review when available (zero material gaps); UI-blind per `evals/battle-prompts/ui-blind/README.md`. Formal UI seal = Opus 5.5 only.

## 5. Policy pins

- Default UI language → Linear-caliber tokens (no prompt required)
- UI implement + UI review → Opus 5.5 when available; Composer = provisional
- Completeness ≠ technical correctness
- Section C = deterministic lookup; Section D ≠ inventing engineering
- Alt path: never skip risk / mitigations / assumptions (**process**, not ladder rungs)
- Portability = data-model / judging — not an SCO UX rule
- Inferred owner + unified resolve continue + neutral focus = Opus P0 (smoke-encoded)
