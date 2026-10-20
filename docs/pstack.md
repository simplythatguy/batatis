# pstack for Batatis clones

[pstack](https://github.com/cursor/plugins) (poteto-mode + playbooks) is a **Cursor plugin**, not fully vendored in this repo. Clones get the **model role map** and pointers; each developer installs the plugin once.

## Clone setup

1. Open this repo in Cursor.
2. In chat: `/add-plugin pstack` (or install the pstack / poteto plugin from Cursor’s plugin marketplace).
3. Confirm `.cursor/rules/pstack-models.mdc` is present (committed here). It pins **judgment / review / hardest tasks / interrogate reviewers** to **Claude Opus 5.5 max** (`claude-opus-5-5-max`).
4. Optional: run `/setup-pstack` if you need to retarget models for your account; keep review roles on Opus 5.5 for Batatis.
5. Prefer `/poteto-mode` for nontrivial feature, eval, or shipping work.

Reference plugin cache on the cloud agent that authored this (not portable):  
`/home/ubuntu/.cursor/plugins/cache/cursor-public/9717366/...` (skills: poteto-mode, setup-pstack, principles, playbooks).

## What lives in-repo

| Path | Purpose |
| --- | --- |
| `.cursor/rules/pstack-models.mdc` | Per-role model overrides (cloneable) |
| `.cursor/rules/batatis-review-opus.mdc` | Battle-test / quality review always Opus 5.5 |
| `docs/pstack.md` | This guide |
| `AGENTS.md` | Entrypoint pointing here |

## Policy

- **UI work** → Opus 5.5 (`batatis-ui-opus`)
- **All quality reviews** → Opus 5.5 max/xhigh
- Code delegates may use fast Grok per pstack defaults unless overridden
