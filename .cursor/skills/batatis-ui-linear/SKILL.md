---
name: batatis-ui-linear
description: Default Batatis product UI/UX system. Always produce Linear-caliber, ruthlessly simplified interfaces (no feature loss) without the user needing to say Linear. Use for any applicant, SCO, intake, ranking, Section C, export, or product chrome work. Pair with batatis-ui-opus (Claude Opus 5.5 for implementation AND review).
---

# Batatis UI — Linear-default system

## Mandate (always on for product UI)

Agents **always** ship spectacular, simplified product UI matching this system’s spacing, colors, texture, type, components, and color discipline — **without** the prompt saying “make it Linear.”

- **Simplify ruthlessly; never drop capabilities.** Collapse chrome, not features.
- **Bug-free bar:** interactive states work; labels match actions; no dead controls; keyboard focus visible; empty/error/loading states exist where data can be missing.
- **Model:** Claude Opus 5.5 (highest available tier) for **all UI implementation and all UI review** — see `../batatis-ui-opus/SKILL.md`.

Reference screenshots (study before inventing patterns): `../../../docs/design/linear-reference/`.  
Tokens to copy: `../../../docs/design/tokens.css`.  
Human doc: `../../../docs/design-system-linear.md`.

## Visual language (encode these; do not substitute)

| Pillar | Rule |
| --- | --- |
| Surfaces | Charcoal layers: `--bg-app` → sidebar → panel → elevated. Depth from **value shifts**, not heavy shadows. |
| Borders | **1px** thin, low-contrast (`--border-subtle` / `--border-default`). Prefer border + layer over card shadow. |
| Type | Inter / Linear-like sans (`--font-sans`). Hierarchy via **weight + color**, not huge size jumps. |
| Grid | **8px** spacing scale (`--space-*`). Density with air: compact rows, generous padding. |
| Color | **Sparse functional color** only (status, labels, selection accent). No decorative purple gradients / glow fest. |
| Radii | Small consistent (`4–8px`). Pills are soft rectangles, not candy `rounded-full` blobs unless a true chip. |
| Layout | Default **sidebar + main**; lists often **three-pane** (nav / list / detail). Main content in a rounded panel with thin border. |
| Cards | Avoid clutter cards. Separate with whitespace + hairline dividers. Cards only when they are the interaction container. |
| Icons | Thin-stroke (~1.5px), monochrome nav + utility icons in sidebar/header; color only when status/meaning. Text-only nav is a soft fail vs reference. |
| Status | Small **status dots** + muted text (success / warning / danger / progress). |
| Code vs AI | Retrieved code in mono `cite-block`; AI explainers in `.ai-explain` muted prose — **visually distinct**. |

## Layout patterns

1. **App shell** — `.app-shell` + `.sidebar` + `.main-panel`.
2. **List + detail** — middle list pane + right detail (inbox / SCO review).
3. **Grouped rows** — section headers with count; single-line issue-style rows (id · status · title · meta).
4. **Tables** — hairline headers, uppercase micro labels, no zebra stripes.
5. **Toolbars** — pill filters left; ghost icon actions right.
6. **Forms** — quiet inputs on `--bg-input`; confidence hints under fields; never silently fill required fields.

## Product surfaces (capabilities stay; chrome simplifies)

| Surface | Must remain possible | UI pattern |
| --- | --- | --- |
| Intake | A–B fields, confidence, clarifying Qs, assumptions labeled | Form + gap banner; sidebar project nav |
| Article ranking | Ranked candidates, benchmark acceptable, confirm/reject | Grouped list rows + detail pane |
| Section C | Deterministic attributions table + per-article explainer | Table; code cite ≠ AI explain |
| SCO review | Citations, gaps, explanations; admin only | Three-pane; gap list; never “complies/safe” |
| Export | PDF preview + completeness gate | Preview panel + checklist of missing process fields |

## Attribution (do not regress BT12)

- Applicant UX rules ≠ SCO UX rules ≠ portability.
- Portability = data-model / judging — **not** an SCO chrome rule.

## Process ≠ evidence (do not regress BT20)

UI may show risk / mitigations / assumptions as **required process fields** on the alt path. Do not label them as evidence-ladder rungs.

## Anti-patterns (fail the blind UI bar)

- Generic dashboard card grids, purple-glow AI chrome, cream/serif marketing skins.
- Mentioning brand names in copy as a substitute for tokens.
- Dropping Section D planner, risk fields, or SCO gap review to “look simpler.”
- Mixing retrieved NBC text into AI narrative styling.
- Silent required-field fills; missing empty/error states; non-working buttons.

## Implementation checklist

1. Load `docs/design/tokens.css` (or equivalent CSS variables).
2. Match shell: sidebar + main panel, thin borders, charcoal layers.
3. Use pills, status dots, hairline tables/rows.
4. Keep every product capability reachable in ≤2 clicks from the surface’s primary job.
5. Self-review against `docs/design/linear-reference/` + bug bar before handoff.
6. UI review agent must use Opus 5.5 and score against `evals/battle-prompts/ui-blind/README.md` pass bar.
