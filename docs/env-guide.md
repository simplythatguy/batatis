# Batatis agent setup

Start from `main`, the only permanent branch:

```sh
git clone https://github.com/simplythatguy/batatis.git
cd batatis
scripts/install-git-hooks.sh
```

Follow [local development](local-development.md) to run the app on localhost:3000 with the engine on `8000`. GitHub has one permanent branch, `main`. Agents publish verified work as a pull request from a short-lived branch, and the user merges it into `main`. Vercel deploys only `main`, with preview deployments disabled.

## Engineering workflows

Read [AGENTS.md](../AGENTS.md) first. It routes the domain/variance skills, Matt Pocock engineering methods and UI quality checks. [Open Pstack](pstack.md) is bundled as `pstack-*` project skills for Codex, Claude Code, and Cursor. Cloning includes the pinned source and project adapter; no global pstack installation is required.

Every delegated agent role, including implementation, research and independent quality/UI review, uses **GPT-6.1-Sol at max**. T3 subagents request Fast mode through **serviceTier=priority**. The portable role map is `.cursor/rules/pstack-models.mdc`. Respect the user's selected main-thread model and actual supported task options.

Children work in isolated checkouts, return results through task output/completion only, and never message another thread or agent. The parent integrates and lands. T3's supported task, browser and PR tools govern transport; upstream CLI examples do not override them.

## Product rules

- Administrative completeness only; technical correctness, safety and professional decisions remain human-owned.
- Section C uses deterministic lookup after article identification. Section D recommends evidence topics and never invents professional evidence.
- The alternative path includes risk, mitigations, assumptions and limits.
- Keep the data model portable across **430+** Alberta jurisdictions; prefer NBC – 2023 Alberta Edition, 2nd printing citations.
- UI follows the light, minimal, mostly monotone [calm system](design-system-calm.md), plus the shared P0 interaction rules. Every control works; capabilities stay intact.

## Verification

Run `scripts/verify.sh` and the checks relevant to the change. Visible work needs actual browser/PDF evidence, saved media inspection and a fresh independent review on the final revision. Capture failures and limits explicitly.

The [understanding checklist](../evals/fixtures/understanding-checklist.md) and [battle prompts](../evals/battle-prompts/README.md) exercise domain understanding. Domain scoring retains the 80% hard-constraint and 4/5 review bar with zero material gaps; the current Sol-only role map governs reviewers. The [UI suite](../evals/battle-prompts/ui-blind/README.md) keeps its interaction/capability bar under the current design/model policy.
