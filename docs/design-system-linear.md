# Batatis design system (Linear-default)

Default product look for all Batatis UI. Agents apply this **without** being asked to “make it Linear.”

| Resource | Path |
| --- | --- |
| Tokens (copy into apps) | [`docs/design/tokens.css`](./design/tokens.css) |
| Reference screenshots | [`docs/design/linear-reference/`](./design/linear-reference/) |
| Skill | [`.cursor/skills/batatis-ui-linear/SKILL.md`](../.cursor/skills/batatis-ui-linear/SKILL.md) |
| Rule (UI globs) | [`.cursor/rules/batatis-ui-linear.mdc`](../.cursor/rules/batatis-ui-linear.mdc) |
| Model pin | Claude Opus 5.5 — [`.cursor/skills/batatis-ui-opus/SKILL.md`](../.cursor/skills/batatis-ui-opus/SKILL.md) |

## Principles

1. **Charcoal layers** — near-black app chrome; slightly lighter sidebar/panels; elevated surfaces via value, not drop shadows.
2. **Thin borders** — 1px low-contrast separators; main workspace is a rounded panel with a hairline edge.
3. **Inter-like sans** — hierarchy from weight + muted greys, not oversized display type.
4. **8px grid** — density with air: compact rows, consistent padding.
5. **Sparse functional color** — green / amber / red / accent blue only for status, selection, labels.
6. **Sidebar + main** (and list+detail when reviewing) — tool chrome, not marketing dashboards.
7. **No clutter cards** — prefer rows, tables, and whitespace.
8. **Simplify ruthlessly, keep every capability** — intake, ranking, Section C, SCO gaps, export, alt-path process fields remain reachable.
9. **Bug-free** — focus rings, working actions, empty/error/loading, distinct retrieved-code vs AI explanation.

## Token map (summary)

| Role | Token | Approx |
| --- | --- | --- |
| App bg | `--bg-app` | `#080808` |
| Sidebar | `--bg-sidebar` | `#0c0c0d` |
| Panel | `--bg-panel` | `#0f0f10` |
| Elevated | `--bg-elevated` | `#141415` |
| Primary text | `--text-primary` | `#eeeeef` |
| Secondary | `--text-secondary` | `#8a8a8e` |
| Border | `--border-subtle` | `rgba(255,255,255,0.06)` |
| Accent / focus | `--accent` / `--border-focus` | `#5e6ad2` |
| Success / warn / danger | `--status-*` | green / amber / red |

## Reference index

| File | Pattern to steal |
| --- | --- |
| `01-pulse.jpg` | Feed rows, filter pills, status + avatar + timestamp meta |
| `02-inbox-detail.jpg` | Three-pane inbox / detail / activity |
| `03-my-issues.jpg` | Grouped issue rows, status icons, label pills |
| `04-initiatives.jpg` | Tree table, health dots |
| `05-projects-roadmap.jpg` | Timeline chrome, pill view switcher |
| `06-agent-insights.jpg` | Metric strip + chart + table without heavy cards |
| `07-project-overview.jpg` | Property pills under title, quiet docs list |
| `08-issue-detail-assistant.jpg` | Issue body + floating agent panel |
| `09-reviews-diff.jpg` | Review list + diff pane (green/red functional color) |
| `10-agent-tasks-board.jpg` | Board columns, quiet task tiles |

## Blind UI evals

Product-feature-only prompts (must **not** mention this brand/system): `evals/battle-prompts/ui-blind/`.  
Artifacts: `evals/ui-artifacts/`.
