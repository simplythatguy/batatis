# README structure, section by section

Keep this order. Each section says what it is for, what goes in it, and what to avoid. A blank template is in [`../assets/README.template.md`](../assets/README.template.md).

## Contents

- [Top of the page](#top-of-the-page)
- [The problem](#the-problem)
- [How it works today](#how-it-works-today)
- [Our solution](#our-solution)
- [Features](#features)
- [Showcase (optional)](#showcase-optional)
- [What's next](#whats-next)
- [The divider](#the-divider)
- [How the project works](#how-the-project-works)
- [Folder structure](#folder-structure)
- [Get started](#get-started)
- [For AI agents](#for-ai-agents)
- [License](#license)

## Top of the page

- `# Name` as the only h1.
- One or two sentences: what the project does and for whom. No adjectives like "powerful" or "seamless".
- One line of links, separated by ` · `, such as `[Open the app](url) · [License](LICENSE.md)`.
- Callouts are allowed here when the user asks for them, using GitHub's `> [!TIP]` or `> [!NOTE]` syntax. Keep each one to two or three sentences.

## The problem

Write for someone who has never heard of the field.

1. **What the thing is.** Two or three short paragraphs that explain the domain in everyday words. Say what the rules or tools are for and why people struggle with them.
2. **A concrete example.** Pick one familiar situation and walk through it. When the example has several required parts, use a two-column table: the left column says what is required, in plain words, with the official term in parentheses for experts. The right column shows it in the example.

   | The application shows | In the staircase example |
   | --- | --- |
   | What could go wrong (risk assessment) | Smoke fills the only staircase |
   | What you add to keep people as safe (mitigating measures) | Sprinklers throughout |

3. **The cost.** One or two sentences on what goes wrong today and what it costs people.
4. **Evidence.** A table with `Figure | What it counts | Source`, with each source linked. Use only figures you verified at the source. When nobody measures something, say so: "Nobody publishes how often applications come back incomplete." Honest gaps build more trust than padded numbers.

Avoid opening with a statistic. Readers need the plain explanation before the numbers mean anything.

## How it works today

- The **today's process** diagram comes first. See [`diagram-style.md`](diagram-style.md).
- Then three to five sentences that walk through the diagram in order and end by pointing at the red steps, for example "The delay comes from the red steps."
- Describe what people do today, not what is wrong with them. The red marks carry the judgment.

## Our solution

- The **solution** diagram comes first. It shows the flow for each audience in plain words, with no technology.
- Then two or three sentences: what the project does, and what it never does. If the project must not claim something, such as "it never says a design is safe", say it here.
- Then one `###` subsection per audience, such as `### For applicants`:
  - One sentence on who they are.
  - A numbered list of four to seven steps. Each step is one action, starting with a verb.
- If demo videos exist, place each one right after its audience's steps. If a video is broken or missing, leave it out. Never link a placeholder.

## Features

- Group by audience with plain lead-in lines: `For applicants:`, `For officers:`, `For both:`.
- One short bullet per feature, starting with a verb: "Search and read the building code in the code library."
- List only what exists today. Check each bullet in the code. Mark conditional features plainly: "The server can also offer Google and Microsoft sign-in."

## Showcase (optional)

Use this when the project has a notable asset, such as a dataset, templates, or practice cases.

- What it is and what it is for, in two sentences.
- A small table of counts, such as where the cases come from.
- One concrete example from the asset, specific enough to be interesting: "Page 4 limits a footing to 0.3 m into the easement, while page 5 says 0.6 m may be allowed."
- How to try it, in one or two sentences, and a link to its own guide.
- Its honest limits, such as what it cannot prove.

## What's next

- Bullets of planned work that is not built yet, each starting with a verb.
- No dates unless the user gave them. No "coming soon" claims.
- If the user wants contributions, end with an invitation.

## The divider

A line with `---`. Do not add a heading such as "Technical". The rule is the only signal that the second half begins.

## How the project works

- The **how it works** diagram comes first. It mirrors the solution diagram and adds the technology under each step.
- One sentence that ties the two together: "This diagram has the same steps as the one in [Our solution](#our-solution), with the technology that runs each step. The colors mark the same stages in both diagrams."
- One sentence that names the stack and where it runs.
- A numbered list with one item per diagram step. Start each item with the step's label in bold, ending with a period, exactly as it appears in the diagram. Then say what runs it and what it does, in one to three sentences. Say "No AI is involved" where that is true, because readers care.
- Then a short paragraph on where data lives, and another on privacy and cost limits, when they exist.
- Put measurements or other detail that most readers don't need in a collapsed `<details>` block.

## Folder structure

- When the project has both a backend and a frontend, draw **two trees**, in this order:
  1. **The repository and the backend:** top-level folders, root files, and the server, data, and script files a newcomer needs.
  2. **The frontend:** the files that build the screens and their look, such as the entry file, the screen components, the styles, and the design tokens and rules.
- Never cram both sides into one picture. A crowded tree is unreadable, and readers usually want only one side.
- A project with only one side, such as a library, a command-line tool, or a skill, gets one tree. Don't invent a frontend or a backend to fill the slot.
- A short line before each tree: "The repository and the backend:" and "The frontend, meaning the files that build the screens and their look:".
- End with: "Both pictures show the main folders and files, not every one."

## Get started

Order matters: the agent prompts come first, then the same steps by hand.

### Set it up with an AI agent

- One sentence: open a coding agent in an empty folder and paste this prompt.
- A `text` code block with a numbered prompt that clones the repository, checks and installs only the missing tools, installs the project, builds any data, copies the settings file without filling in keys, starts the app, and checks that it loads. It ends by telling the agent not to commit or push, and to report what it installed and what failed.
- Hard-wrap lines at 92 characters. Put each command or URL on its own line.

### Open a pull request with an AI agent

- A prompt that follows the repository's real branch rules. For a single `main` branch: start a short-lived branch from the latest `main`, make the change, run the checks, push, and open a pull request into `main`.
- Tell the agent to write the description in the repository's pull request format, in everyday words, and to stop without merging.
- When the repository has a description format, show a short real example as a quote.

### Set it up by hand

- "If you'd rather not use an agent, follow steps 1 to N."
- `### 1. Clone the repository`: the clone command, the `cd` command, and any one-time hook setup, each in its own code block.
- `### 2. Install the tools`: name every tool and version. Say "Skip any tool you already have." Give one command per code block for macOS, such as Homebrew, and link the official installers for Windows and Linux. Say which tools come with the project, such as React and Vite through `npm`, so nobody installs them twice.
- `### 3. Install the project`: one code block per command, each with a one-line purpose above it.
- `### 4. Build the data` (when needed): what the data is, in plain words, why the app needs it, and how long the step takes.
- `### 5. Add your settings`: show the example settings file as is. Then, for each key, a `####` heading with the key's name and:
  - What the service is and what the project uses it for, plus how to turn it on.
  - "Files that use it:" and a linked list of the files.
  - "Get a key at" and a link to the official key page.
  Then a table for switches that are not keys, and any other setup, such as an access code for a second role.
- `### 6. Run the app`: the command, the address to open, and how to stop it. When the obvious command is not enough, such as `npm run dev` without the backend, add a short `####` section that explains why and shows the manual alternative.
- `### Make a pull request`: the same flow as the agent prompt, one command per block.
- `### Test a pull request`: `gh pr checkout <number> --branch pr-<number>` and the plain Git alternative, a reminder to reinstall when dependencies change, and how to switch back.

## For AI agents

- One paragraph: read `AGENTS.md` (or its equivalent) and the skills it names before writing code, and read them again when the work moves to a new area.
- A table, `Before you | Read`, that maps each kind of work to the skill or document to read first.
- "These rules always apply:" and a bullet list of the project's non-negotiables, branch rules, port rules, and anything agents must never do.

## License

- One short paragraph that says who holds the copyright and what people may and may not do, and a link to `LICENSE.md`.
- If the user wants no commercial use, say so in plain words. Don't invent license terms the user did not ask for.
