# Pstack in Batatis

Use this repository's `AGENTS.md` and the current user request as the task boundary. The pinned upstream methods live in `.agents/pstack/upstream/skills/`. Read the selected method before applying it. Resolve its relative links from that source file's directory.

## Select the method

Simple answers and small edits stay direct. For substantive work, select only the relevant methods:

| Task | Source relative to `.agents/pstack/upstream/skills/` |
| --- | --- |
| Feature | `poteto-mode/playbooks/feature.md` |
| Bug | Read `.agents/skills/diagnosing-bugs/SKILL.md`; use `poteto-mode/playbooks/bug-fix.md` for the fix |
| Refactoring | Read `.agents/skills/codebase-design/SKILL.md`; use `poteto-mode/playbooks/refactoring.md` for implementation |
| Code review | Read `.agents/skills/code-review/SKILL.md` |
| Broad code explanation | `how/SKILL.md` |
| Historical rationale | `why/SKILL.md` |
| Performance | `poteto-mode/playbooks/perf-issue.md` and `benchmark-checklist/SKILL.md` |
| Agent instructions or skills | Read `.agents/skills/writing-for-agents/SKILL.md` |
| Full poteto workflow requested | `poteto-mode/SKILL.md` |

Reassess when the task changes phase or new evidence changes the problem. Read only the supporting methods that apply. Briefly identify the source-qualified methods used. Apply Batatis's domain and UI instructions to their matching surfaces.

## Local names and source paths

The discoverable name is `pstack-<upstream-name>`, such as `pstack-arena` or `pstack-tdd`. References to `pstack:<name>` or an upstream pstack skill name resolve to `.agents/pstack/upstream/skills/<name>/SKILL.md`. A harness with a skill invocation tool can use the local `pstack-<name>` entrypoint; otherwise read the source directly. Matt Pocock's unprefixed skills remain separate.

Each entrypoint loads this adapter and its upstream source. For children, give the absolute checkout path, this adapter, the assigned source files, repository instructions, scope, file ownership, and verification responsibilities. Children read the assigned guidance and return the methods they actually used through their own task output and completion only.

## Tools, models, and scope

- Use the current harness's supported tools. In T3, supported task, browser, PR-linking, and watch tools govern those operations; the current T3 runtime contract takes precedence over upstream CLI runner and polling examples. A global T3 router is optional for this repository's skills.
- When a method names a bundled agent such as `poteto-agent` or `comment-sicko`, read `.agents/pstack/upstream/agents/<name>.md` and pass its applicable instructions to a supported child-task tool. The clone supplies these definitions as source; use the repository's configured model rather than an upstream model alias.
- Read `.cursor/rules/pstack-models.mdc` for Batatis's configured roles. All delegated roles use GPT-6.1-Sol at max; T3 requests provider `codex` and `serviceTier=priority` when supported. The user controls the main-thread model. A missing required model or tool is a reported limitation, never a silent provider substitution.
- Size delegation to useful independent work and available tools. Keep small, coupled edits local; give writers isolated checkouts and use focused independent review for substantive changes when available. Upstream blanket fan-out and interview steps do not enlarge the user's task.
- Follow `docs/agents/git-workflow.md` for branches, verification, PR descriptions, and user-owned merging. The configured local ports are 3000 and 8000. Upstream rebase, stacking, deployment, merge, cleanup, or autonomy examples do not override project instructions or authorize external messages and destructive actions.
- The vendored agent definitions, scripts, and hook files are reference material. Cloning this repository does not activate plugin hooks, install CLIs, configure accounts, or start a process. Check actual tool availability before executing a matching method.
- Verify on the affected surface. Visible product changes require exercised user paths and inspected screenshots/demo through supported T3 features when available; report capture limitations. Contributor-only skill changes require clone/discovery and reference checks, without app screenshots.

## Maintain the bundle

`docs/pstack.md` records the source revision, installation layout, verification command, and update procedure. Keep `.agents/pstack/upstream/` unchanged from the pinned source and put Batatis adaptations here or in the generated entrypoints.
