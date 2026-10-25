---
name: prettyme
description: Write or rewrite a project's README so that anyone can understand it, and draw its diagrams in one clean, consistent style. The README has a plain-language first half (the problem with sourced numbers and a concrete example, today's process with the trouble spots in red, the solution, features, what's next) and a technical second half (a how-it-works diagram that mirrors the solution diagram with real logos, folder-tree pictures, a copy-paste prompt that lets a coding agent set everything up, every API key explained, contribution steps, rules for AI agents). Claude writes, and an image model such as GPT draws from prompts this skill provides. Use this skill whenever someone asks for a README, a project overview or landing page, setup instructions, or architecture, flow, or folder diagrams for a repository, or says a README is unreadable, too technical, cluttered, inconsistent, or "AI slop", even if they never say "prettyme".
---

# prettyme

Make READMEs that anyone can read, with diagrams that look like one matching set.

A prettyme README has two halves with no labels. The first half explains the project to anyone, technical or not. After a horizontal rule, the second half gives developers, and the agents they work with, everything needed to understand, run, and change the project. Every diagram uses the same flat, minimal flowchart style with real logos.

AI-written READMEs usually fail in two ways. They explain every low-level detail in jargon, so nobody can find the point. And their setup steps skip things, so people run the code, hit an error, install one more thing, and repeat. This skill fixes both: plain words first, and a setup prompt that an agent can follow from start to finish.

## Who does what

- **You, the writing model (Claude works best).** Read the project, write the README, write every image prompt word for word, and check every image.
- **The image model (GPT's image model works best).** Draw each diagram from your prompt and the attached reference images. In Codex, that is the built-in `image_gen` tool. Elsewhere, use an OpenAI image model through the API.

Claude writes plain, careful prose and catches mistakes. GPT draws text inside images more accurately. If you are not the image model, hand it the prompt and the reference images unchanged, and keep the checking for yourself. [`references/image-workflow.md`](references/image-workflow.md) covers each way to hand off.

## Workflow

1. **Learn the project.** Read the code, not only the old README. Note the real names of folders, scripts, environment variables, and services, what each part does, and how to install and run it. Collect any numbers you might quote, with their sources. Never invent a figure, a feature, or a step. If you can't verify something, leave it out or say it is unknown.
2. **Plan the README** with [`references/readme-structure.md`](references/readme-structure.md). Keep the section order. Drop a section only when the project has nothing for it, and tell the user which one and why.
3. **Write it** with [`references/writing-rules.md`](references/writing-rules.md). Plain words come first. Explain every internal name the first time it appears.
4. **Plan the diagrams** with [`references/diagram-style.md`](references/diagram-style.md). Decide which diagrams the README needs, the exact text of every box, and which diagrams must mirror each other.
5. **Prepare the references.** Use [`assets/style-reference.png`](assets/style-reference.png) for the look. Download official logo artwork with [`scripts/fetch_logos.py`](scripts/fetch_logos.py). **Confirm that every logo is the current version** before it goes on a sheet: compare it with the brand's own site or brand page, and replace anything outdated. The steps are in [Make sure every logo is current](references/diagram-style.md#make-sure-every-logo-is-current). Then build the labeled sheet with [`scripts/logo_sheet.py`](scripts/logo_sheet.py), and look at it. Pick the matching approved example from [`assets/examples/`](assets/examples/).
6. **Generate each diagram** from the templates in [`references/diagram-prompts.md`](references/diagram-prompts.md), following [`references/image-workflow.md`](references/image-workflow.md). Attach the references, allow at most three tries per diagram, and use edit mode for small fixes.
7. **Inspect every image yourself.** Read every label letter by letter, follow every line to its parent, and compare every logo with the sheet. When you must choose, take the version whose structure is right over the prettier one.
8. **Finish the images** with [`scripts/finish_image.py`](scripts/finish_image.py) and save them in `docs/readme/`.
9. **Check the README** with [`scripts/check_readme.py`](scripts/check_readme.py). When `gh` and Chrome are available, look at it the way GitHub shows it with [`scripts/preview_readme.sh`](scripts/preview_readme.sh).
10. **Show the user** every image the model made, as one sheet from [`scripts/contact_sheet.py`](scripts/contact_sheet.py), plus the prompts you used and anything you could not verify.

## The README at a glance

```text
# Name
One or two sentences: what it does and for whom.
Links: open the app · license

## The problem                 plain explanation, a concrete example, sourced numbers
## How it works today          diagram with the trouble spots in red
## Our solution                diagram, then a section per audience with numbered steps
## Features                    grouped by audience, short bullets
## <Showcase> (optional)       a notable dataset or asset, with one concrete example
## What's next                 planned, not built
---
## How <name> works            mirrors the solution diagram, with real logos
## Folder structure            a backend tree, then a frontend tree
## Get started                 agent setup prompt, agent pull-request prompt, then steps by hand
## For AI agents               skills to read first, rules that always apply
## License
```

The first half never needs code knowledge. The second half is technical, but it still explains every name it uses. Neither half carries a "technical" or "non-technical" heading. The horizontal rule is the only divider.

## The diagram style at a glance

- A white background, flat shapes, thin dark-gray outlines, small rounded boxes, diamonds for decisions, and smooth curved lines that fan out from a parent to its children. Lots of white space, and no title, legend, or step numbers inside the image.
- Color only identifies things. Red marks the steps that cause the problem in today's process. Four faint, almost-white tints mark the same stages in the solution diagram and the technical diagram. Brand colors appear only inside logos.
- Logos come from official artwork on a logo sheet, never from the model's memory.
- The technical diagram copies the solution diagram's layout exactly and hangs what runs each step under it.
- Folder trees show the main folders and files only. A project with a backend and a frontend gets two trees, backend first. A file is its language logo, its name, and a two-to-five-word tag.

[`references/diagram-style.md`](references/diagram-style.md) has the full rules, sizes, and colors.

## Lessons from real runs

- **Logos go stale, so every logo must be current.** Chrome changed its logo in 2022, and devicon still ships the old glossy one. An outdated logo makes the whole README look neglected. Never use a logo you haven't compared with the brand's current one. Simple Icons are single-color, so recolor them to the official brand color.
- **Long trees break.** The image model may chain siblings together or drop a folder. Check every parent link. Split a tree that has more than about 25 nodes.
- **One change ripples.** When a label changes in the project, such as a script's job or a folder's name, search every diagram for the old wording, not only the one you were fixing.
- **GitHub doesn't wrap code blocks.** Hard-wrap prompt blocks at 92 characters, and keep each command whole on its own line. Show long example text as a quote instead of a code block.
- **Facts before polish.** Check the README against the code before you style anything. Look for tests that read the README. Some projects require certain text to stay.
- **Keep everything.** Save the prompts, the reference images, and every attempt, so that anyone can regenerate or adjust a diagram later.
