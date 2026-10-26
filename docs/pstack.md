# Pstack for the Batatis team

[Open Pstack](https://github.com/ericlitman/open-pstack) is included in this repository. A normal clone has the skills ready for discovery by Codex, Claude Code, and Cursor. Open the checkout in your agent; reload the session if it was already open when the skills were added. No global pstack plugin installation or setup command is required.

Ask for `pstack-poteto-mode` to use the full workflow, or a focused skill such as `pstack-how`, `pstack-arena`, or `pstack-interrogate`. Claude Code exposes project skill commands such as `/pstack-poteto-mode`. The `pstack-` prefix keeps these separate from Matt Pocock's skills, including `tdd` and `teach`.

## Included files

| Location | Purpose |
| --- | --- |
| `.agents/skills/pstack-*/SKILL.md` | Codex project skill entrypoints |
| `.claude/skills/pstack-*/SKILL.md` | Claude Code project skill entrypoints |
| `.cursor/skills/pstack-*/SKILL.md` | Cursor project skill entrypoints |
| `.agents/pstack/upstream/` | Unmodified pinned pstack skills, references, support files, and licenses |
| `.agents/pstack/ADAPTER.md` | Batatis routing, tool mapping, and scope rules |
| `.agents/pstack/manifest.json` | Source revision and file hashes |
| `scripts/pstack_skills.py` | Generate and verify the portable entrypoints |

Entrypoints are regular tracked files, including on Windows checkouts with symlinks disabled. Their instructions load the shared adapter and exact upstream skill source. Root `AGENTS.md` points agents at the project workflow, and `CLAUDE.md` imports those instructions for Claude Code.

## Version and attribution

The snapshot is Open Pstack **1.16.0**, commit [`b4c5e3d63318308b7e11f26b2bc156e7793d834a`](https://github.com/ericlitman/open-pstack/tree/b4c5e3d63318308b7e11f26b2bc156e7793d834a/plugins/pstack). It contains the upstream `plugins/pstack/` tree and the root `LICENSE`, `LICENSE-cursor-team-kit`, `LICENSE-superpowers`, `NOTICE.md`, and `UPSTREAM.md`. Those notices retain the original attribution and license terms.

Keep Batatis adaptations outside the upstream snapshot so updates and provenance stay reviewable. This includes the prefix used for project skill names and the project-specific workflow adapter.

The manifest records two known `NOTICE.md` links to the upstream repository's unbundled `CHANGES.md`. The verifier reports those attribution references separately while checking the bundled skill links.

## Shared behavior

Read [the adapter](../.agents/pstack/ADAPTER.md) before using an upstream method. Batatis's domain boundaries, [Git workflow](agents/git-workflow.md), ports, and PR format apply. All delegated roles use **GPT-6.1-Sol at max** under the user's 2026-10-23 decision; [the portable role map](../.cursor/rules/pstack-models.mdc) is included in every clone. In T3, use supported task, browser, PR, and watch tools. Global source paths are optional.

The clone provides instructions and supporting source files. It does not install model providers or CLI dependencies, supply credentials, or activate upstream hooks. Methods that need an external integration still require that integration to be available. If you already have the global pstack plugin, use this repository's `pstack-*` skills for its pinned version and Batatis adapter.

## Verify or update

Run from the checkout root:

```sh
python3 scripts/pstack_skills.py --check
```

This offline check also runs in `scripts/verify.sh` and CI. It checks the pinned source hashes and the generated entrypoints across all three agent folders.

`--write` repairs generated entrypoints while preserving the existing source pin; it refuses source hash drift. To update the bundle, choose an upstream commit, replace `.agents/pstack/upstream/` with that commit's `plugins/pstack/` tree and the five root license/provenance files listed above, and update the generator's provenance and inventory constants. After verifying the replacement against that upstream commit, remove the old manifest and regenerate it with `python3 scripts/pstack_skills.py --write`. Review any reported upstream reference issues, run `--check`, review the source and adapter changes, and follow the normal verified pull request workflow. Clones never fetch a moving upstream version automatically.
