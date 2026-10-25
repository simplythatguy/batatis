# <Name>

<One or two sentences: what the project does and for whom.>

[Open the app](<url>) · [License](LICENSE.md)

## The problem

<Two or three short paragraphs that explain the field in everyday words.>

<One concrete example. When it has several required parts, use a table:>

| <What is required> | In the <example> |
| --- | --- |
| <Plain words> (<official term>) | <How it shows up in the example> |

<One or two sentences on what goes wrong today and what it costs.>

| Figure | What it counts | Source |
| --- | --- | --- |
| <number> | <what it counts> | [<source name>](<url>) |

<What nobody measures, said plainly, if anything.>

## How <it> works today

![<What the diagram shows, in one sentence>](docs/readme/current-process.png)

<Three to five sentences that walk through the diagram and point at the red steps.>

## Our solution

![<What the diagram shows, in one sentence>](docs/readme/solution.png)

<Two or three sentences: what the project does, and what it never does.>

### For <audience one>

<One sentence on who they are.>

1. <Verb-first step.>
2. <Verb-first step.>

### For <audience two>

<One sentence on who they are.>

1. <Verb-first step.>
2. <Verb-first step.>

## Features

For <audience one>:

- <Verb-first feature that exists today.>

For <audience two>:

- <Verb-first feature that exists today.>

## What's next

- <Planned work, verb first.>

---

## How <name> works

![<What the diagram shows, in one sentence>](docs/readme/how-it-works.png)

This diagram has the same steps as the one in [Our solution](#our-solution), with the technology that runs each step. The colors mark the same stages in both diagrams. <One sentence on the stack and where it runs.>

1. **<Step label from the diagram>.** <What runs it and what it does.>
2. **<Step label from the diagram>.** <What runs it and what it does.>

<Where data lives. Privacy and cost limits.>

## Folder structure

The repository and the backend:

![<The main folders and backend files>](docs/readme/folder-structure-backend.png)

The frontend, meaning the files that build the screens and their look:

![<The entry file, the screens, and the styles>](docs/readme/folder-structure-frontend.png)

Both pictures show the main folders and files, not every one.

<A project with only one side keeps one tree and drops the other.>

## Get started

### Set it up with an AI agent

Open an AI coding agent in an empty folder, and paste this prompt:

```text
Set up <name> on this computer so I can run it locally.

1. Unless this folder is already a clone, clone this repository:
   <clone url>
2. Check for <tools and versions>. Install only what is missing.
3. <Install the project's packages.>
4. If .env does not exist, copy .env.example to .env. Leave the API keys empty.
5. Start the app with <command>, and check that <address> loads.
6. Do not commit or push. When you finish, tell me what you installed and anything that
   failed.
```

### Open a pull request with an AI agent

When you know what you want to change, paste this prompt and add your request at the end:

```text
Make my change to <repository> and open a pull request for it.

1. Read AGENTS.md before you change any code.
2. <Branch rules for this repository.>
3. Make the change, run <checks>, and fix anything that fails. Then commit.
4. Push the branch and open the pull request:
   gh pr create --repo <owner/repo> --base <branch>
5. Stop there. Do not merge the pull request.

My change:
```

### Set it up by hand

If you'd rather not use an agent, follow steps 1 to <N>.

### 1. Clone the repository

```bash
git clone <clone url>
```

### 2. Install the tools

You need <tools and versions>. Skip any tool you already have.

### 3. Install the project

### 4. Add your settings

### 5. Run the app

### Make a pull request

### Test a pull request

## For AI agents

Read [`AGENTS.md`](AGENTS.md) and the skills it names before you write any code.

| Before you | Read |
| --- | --- |
| <Kind of work> | <Skill or document> |

These rules always apply:

- <Rule.>

## License

<Who holds the copyright, and what people may and may not do.> See [`LICENSE.md`](LICENSE.md).
