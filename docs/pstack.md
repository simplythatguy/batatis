# Open Pstack for Batatis

[Open Pstack](https://github.com/ericlitman/open-pstack) supplies pstack workflows for Codex and Claude Code. It replaces this machine’s old Cursor-specific copy. Version 1.16.0 was installed and pinned to `b4c5e3d63318308b7e11f26b2bc156e7793d834a` on 2026-10-23.

## Install

In a shell for Codex:

```sh
codex plugin marketplace add ericlitman/open-pstack --ref main
codex plugin add pstack@open-pstack
```

In Claude Code, install `pstack@open-pstack` from the `ericlitman/open-pstack` marketplace. Installing the plugin does not require using a Claude model. Use only one pstack plugin per harness to avoid duplicate names. Restart the task or reload plugins to discover new skills.

## Shared rules

All Batatis agent roles, including UI implementation and independent review, use **GPT-6.1-Sol at max** under the user's 2026-10-23 decision. The portable role map is [pstack-models.mdc](../.cursor/rules/pstack-models.mdc). T3 subagents also request Fast mode with `serviceTier=priority`. Verify the actual supported model/options before dispatching. Do not substitute another provider or lower effort silently.

In T3, `~/.codex/skills/t3-workflow/SKILL.md` routes the shared source at `~/.agents/skill-libraries/pstack/skills/`, Matt Pocock methods, and UI verification. Native Codex/Claude installations use the same Open Pstack version. T3 task, browser and PR tools take precedence over upstream subprocess-runner and polling examples. Keep the current main-thread model as the user's composer choice.

Children work in isolated checkouts, return results in their own task output/completion, and never message other threads or agents. The parent integrates and publishes. Upstream playbooks do not grant permission to send messages, change providers, deploy production or create extra remote branches.

The [two-branch Git workflow](agents/git-workflow.md), ports 3000/8000, privacy, version checks and domain/professional boundaries apply to every workflow. Follow the calm UI contract and inspect actual saved media for visible changes.

Old active source copies are archived outside skill discovery. The shared installation records its exact origin in `~/.agents/skill-libraries/sources.json`; `~/.agents/t3-workflow/UPDATE-SAFETY.md` covers local backups. This repository does not vendor the plugin or any credentials.
