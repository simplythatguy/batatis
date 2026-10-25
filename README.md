# Batatis

Batatis helps builders in Alberta prepare a complete building-code variance application. It also shows Safety Codes Officers what an application is missing.

[Open the app](https://batatis-vert.vercel.app) · [License](LICENSE.md)

## The problem

Every new building in Alberta has to follow the building code. The code is a set of safety rules that tell builders how to build, so that buildings don't collapse, catch fire easily, or trap people inside.

Sometimes a builder wants to build something the rules don't describe, such as a new product or a different design. They can still ask to build it, but first they must apply for a variance. A variance is permission to meet a rule's purpose in a different way, and the builder has to prove that the different way is at least as safe.

Here is an example. The code requires at least two exits from every floor of a larger building, so people can still get out if fire or smoke blocks one staircase. Say you design a four-storey apartment building with only one staircase. To build it, you file a variance application. It has to show six things:

| The application shows | In the staircase example |
| --- | --- |
| Which rule you aren't following, and what the rule is for (code analysis) | Sentence 3.4.2.1.(1) of the National Building Code, 2023 Alberta Edition, requires two exits so that people can escape, and firefighters can get in, when one exit is blocked |
| Why you want a different design (rationale) | One staircase leaves room for more homes on a small lot |
| What could go wrong (risk assessment) | Smoke fills the only staircase |
| What you add to keep people as safe (mitigating measures) | Sprinklers throughout, and a staircase built to keep smoke out |
| What your plan depends on (assumptions and limits) | The sprinklers are maintained and always working |
| Proof (supporting evidence) | A fire engineer's report showing that everyone can get out in time |

A Safety Codes Officer then reviews the application and decides.

According to the challenge organizers, most first submissions fail because they are incomplete. The officer sends the application back, the builder fixes it, and each round adds weeks.

| Figure | What it counts | Source |
| --- | --- | --- |
| 3,088 | Building-code articles varied in Alberta, January to June 2026 | [Safety Codes Council Data Hub](https://www.safetycodes.ab.ca/data-hub/variance-data/) |
| 433 | Organizations that enforce safety codes in Alberta | [Council Annual Report 2025](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202025%20Final.pdf) |
| 2,317 | Certified Safety Codes Officers in Alberta | [Council Annual Report 2025](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202025%20Final.pdf) |
| 2 to 4 months | Time to allow for comments on an alternative solution | CWC and WoodWorks BC, *Alternative Solutions Guide* |
| Hundreds to tens of thousands of dollars | Cost of rework and delay on one application | Building Codes Challenge scope |

Nobody publishes how often applications come back incomplete, because the Council does not collect the documents. From December 1, 2026, officers must also register every variance in the Council's portal, with the documents they used ([IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf)).

## How variances work today

![A builder prepares the application alone, an officer checks it by hand, and missing items send it back for another round](docs/readme/current-process.png)

When a design doesn't follow the code as written, the builder prepares the variance application alone. They find the code articles, look up what each one is meant to achieve, explain the risks and safeguards, and choose the evidence. An officer then checks the package by hand. If anything is missing, the application goes back and the loop starts again. The delay comes from the red steps.

## Our solution

![The applicant describes the project, answers questions, confirms code articles, and submits. The officer reviews and accepts or returns it](docs/readme/solution.png)

Batatis turns the variance form into a guided flow for the applicant and a checklist for the officer. It checks that an application is complete. It never says that a design is safe or meets the code. Engineers and the officer make those decisions.

### For applicants

Manufacturers, homebuilders, and general contractors use Batatis to prepare the application.

1. Describe the project in your own words, or drop in PDFs.
2. Answer the questions that Batatis still needs, one at a time.
3. Confirm the code articles that Batatis found. Each one quotes the code.
4. Section C of the form fills in from the code's own tables.
5. Plan your evidence. Batatis flags when an engineer or another professional is required.
6. Fix anything the checklist marks as missing. Then download the official form, or submit it to Edmonton or Calgary.

### For Safety Codes Officers

Officers use Batatis to see what an application is missing.

1. Pick up a new or resubmitted application from the review queue.
2. Read it on the official form, with its missing items and code checks beside it.
3. Accept it as administratively complete, return it with a message, or refuse it.
4. Close out the application after the decision.

## Features

For applicants:

- Sign up with email. The server can also offer Google and Microsoft sign-in.
- Describe a project in text or PDFs. Batatis reads the facts and asks only for what is missing.
- Answer Sections A to D one question at a time, including the rationale, risk assessment, mitigating measures, and assumptions that an alternative solution needs.
- Confirm the code articles that apply, each with a quote from the code.
- Get Section C filled in from the code's tables.
- Get a Section D evidence plan that flags when a professional is required.
- For the articles varied most often, enter your numbers and see whether the design departs from the code's standard way.
- Learn when your city has a pre-reviewed path for your situation.
- Search and read the building code in the code library.
- See a checklist of missing items.
- Download the Council's variance form as a PDF. A draft works at any time, and the final form unlocks when nothing required is missing.
- Submit to the City of Edmonton or the City of Calgary, and resubmit after a return.
- Read messages from the officer.
- Ask the assistant about your application, by text or by voice.
- See which facts AI suggested and which still need your check.
- Rename, pin, archive, or delete applications.

For Safety Codes Officers:

- Sign up with your authority's access code.
- Find applications in a queue with tabs for new, resubmitted, mine, returned, accepted, and refused.
- Claim an application so that no one else reviews it at the same time.
- Review it on the official form, with missing items, code checks, and what changed since the last submission.
- Send an information request, return the application with a message, refuse it, or accept it as administratively complete.
- Record when an engineer or another professional is required.
- Review PDF packages that were made outside Batatis.
- Close out a decision and keep its record package.
- See every submission in the application's history.

For both:

- Get notified when an application changes status or a message arrives.
- Applications and their files are deleted 7 days after they are created.

## Practice cases

This repository includes 653 practice cases for testing how well Batatis reads real documents. Each case pairs a request, written the way an applicant might ask, with published documents to attach, such as feasibility studies, issued variances, and appeal decisions. No document in them was made up.

| Where the cases come from | Cases |
| --- | ---: |
| Calgary and Edmonton | 38 |
| The rest of Alberta | 121 |
| Product and research evidence from across Canada | 73 |
| Outside Alberta, used only to compare documents | 421 |

For example, one Calgary case hands Batatis the city's zero-lot-line variance. Page 4 limits a footing to 0.3 m into the easement, while page 5 says 0.6 m across the property line may be allowed. Batatis should flag the difference and ask, not pick one.

Many published decisions state their outcome, so the cases test reading and paperwork, not whether a design should be approved. To try one, open a case folder, paste its `prompt.txt` into Batatis, and attach the documents it lists. The [practice cases guide](Data%20Prompts/README.md) explains how to restore the original documents, which Git doesn't store, and how to check the results. The Calgary example is case [L04-001](Data%20Prompts/Canada/Alberta/Calgary/Prompts/L04-001-calgary-spv-001-zero-lot-line-revision-5-with-revision-4-history/prompt.txt).

## What's next

- Export Calgary's own Request for Specific Variance form next to the Council's form.
- Register decided variances in the Council's Orders and Variances Portal, which becomes mandatory on December 1, 2026.
- Add authorities beyond Edmonton and Calgary, then other provinces.
- Draft the officer's Part 2 decision page from the review findings.
- Search the CCMC product evaluation registry from inside the app.
- Measure the code check on applications that experts have reviewed, and calibrate its relevance scores.
- Test the full workflow with real applicants and officers.

---

## How Batatis works

![The same workflow as Our solution, with the technology under each step](docs/readme/how-it-works.png)

This diagram has the same steps as the one in [Our solution](#our-solution), with the technology that runs each step. The colors mark the same four stages in both diagrams. The website is React and TypeScript, built with Vite. It calls the engine, a Python API built with FastAPI. Vercel hosts both.

For applicants:

1. **Describe the project.** Rules read facts, such as the owner and the address, from the description and from the text and fields of any PDFs. If AI is on, GPT points at more facts, and each one must quote the applicant's own words.
2. **Answer a few questions.** A rule-based planner picks up to five questions. It starts with conflicts in what you wrote, then facts that narrow down the code articles. The website then shows one card for each item that is still open. No AI writes the questions.
3. **Confirm the code articles.** Elephant 1 scores all 2,080 articles in Division B of the code and reranks the top 60. Elephant 1 is a model hosted on Baseten, and Batatis reaches it through OpenRouter. GPT then reads the top 15 in full and quotes the sentences that apply. You confirm each article. With AI off, a keyword search over CodeDB suggests articles instead.
4. **Section C fills itself in.** The objectives, functions, and intent of each confirmed article come from the code's own tables in CodeDB. No AI is involved.
5. **Plan the evidence.** Rules match each article to the kinds of evidence it needs, and flag when an engineer or another professional is required. No AI is involved.
6. **Anything missing?** Completeness rules check every required part of Sections A to D. Anything missing sends you back to the questions.
7. **Submit the official form.** The engine fills in the Council's variance form, adds an appendix with the full code text, and saves the exact version you sent.

For Safety Codes Officers:

8. **Pick it up from the queue.** The queue lists submitted applications. Claiming one stops two officers from reviewing it at the same time.
9. **Review the application.** The officer sees the filled form, the same completeness checks, and the code citations checked against CodeDB.
10. **Decide.** Returning the application sends the applicant a message, and they fix it and resubmit. Accepting it marks it as administratively complete.
11. **Close-out.** The engine builds the decision's record package for the Council.

CodeDB is a SQLite database of the building code. You build it on your computer from the official PDFs of the National Building Code, 2023 Alberta Edition, second printing. Applications and accounts live in SQLite on your computer, or in PostgreSQL on Neon when the app is hosted. The assistant answers with GPT. Voice uses Grok from xAI.

Before any text goes to an AI service, Batatis removes the names, contact details, and addresses that it recognizes. A daily spend cap, US$5 by default, stops AI calls when it is reached.

<details>
<summary>Measured accuracy of the engineer-needed flag</summary>

At measured source `d479e82`, the shipped facts-only `rules_plus_unknown` agreed with model gold on 50/60 text-only dev cases (0 no outputs, 27 unknowns) and 8/11 model-constructed cases without ground truth. Unshipped `rules_only` had 55/60 dev agreement and 1 under-flag. These were in-sample, model-checked labels, not expert validation or a measurement of the current build. Zero under-flags on the dev set was partly by design, because the flag never answered no. See the [API contract](docs/api-contract.md) for the receipt and its limits.

</details>

## Folder structure

The repository and the backend:

![The main folders and backend files: engine, codedb, scripts, docs, evals, the practice cases in Data Prompts, agent skills, and the root files](docs/readme/folder-structure-backend.png)

The frontend, meaning the files that build the screens and their look:

![The frontend files: the web app's entry, the screens in web/src/calm, and the design rules and tokens in docs](docs/readme/folder-structure-frontend.png)

Both pictures show the main folders and files, not every one.

## Get started

### Set it up with an AI agent

Open an AI coding agent, such as Claude Code, Codex, or Cursor, in an empty folder, and paste this prompt:

```text
Set up the Batatis app on this computer so I can run it locally.

1. Unless this folder is already a clone, clone this repository:
   https://github.com/simplythatguy/batatis.git
   Then run scripts/install-git-hooks.sh.
2. Check for Git, Python 3.12, and Node.js 22.12 or newer. Install only what is missing. On
   macOS, use Homebrew.
3. Create .venv with Python 3.12. Install engine/requirements.txt, codedb/requirements.txt,
   and research/precedents/requirements.txt into it. Then run npm ci --prefix web.
4. Build the code database. Run .venv/bin/pip install 'fonttools>=4.39', then
   .venv/bin/python scripts/fetch_sources.py, then .venv/bin/python -m codedb build.
5. If .env does not exist, copy .env.example to .env. Leave the API keys empty. I will add
   my own.
6. Start the app with scripts/local-app.sh start, and check that http://localhost:3000
   loads. Use only ports 3000 and 8000. If a port is busy, stop and tell me.
7. Do not commit, push, or create branches. When you finish, tell me what you installed and
   anything that failed.
```

### Open a pull request with an AI agent

When you know what you want to change, paste this prompt into the same agent and add your request at the end:

```text
Make my change to github.com/simplythatguy/batatis and open a pull request for it.

1. Read AGENTS.md and the skills it names before you change any code.
2. Start a short-lived branch from the latest main, named for the change. For example:
   git switch main
   git pull
   git switch -c fix-intake-wording
3. Make the change. Run scripts/verify.sh and fix anything that fails. Then commit.
4. If I can't push to simplythatguy/batatis, make my fork the origin remote:
   gh repo fork simplythatguy/batatis --remote
5. Push the branch:
   git push -u origin HEAD
6. Write the description in a file, starting from .github/pull_request_template.md. Keep
   its three sections: New features added, Improvements, and Bug Fixes. Use short bullets
   in everyday words, with no technical jargon, and write "None." under an empty section.
7. Open the pull request into main:
   gh pr create --repo simplythatguy/batatis --base main --body-file <description file>
8. Stop there. Never push to, merge into, or delete main, and do not merge the pull request.

My change:
```

Every pull request uses the same three sections. Here is part of the description of [#72](https://github.com/simplythatguy/batatis/pull/72), which added the practice cases:

> **New features added:**
>
> - Added 653 practice cases based on published building code documents, with instructions for using them to test how Batatis handles attachments.
>
> **Improvements:**
>
> - Organized research cases by country, province or state, and city or town, making Calgary and Edmonton cases easier to find.
>
> **Bug Fixes:**
>
> - Fixed problems restoring some publicly available source documents.

### Set it up by hand

If you'd rather not use an agent, follow steps 1 to 6.

### 1. Clone the repository

If you plan to contribute but can't push to this repository, fork it on GitHub first and clone your fork instead.

```bash
git clone https://github.com/simplythatguy/batatis.git
```

```bash
cd batatis
```

Install the Git hook. It blocks pushes to `main`, rewriting a branch, and tags.

```bash
scripts/install-git-hooks.sh
```

### 2. Install the tools

You need Git, Python 3.12, and Node.js 22.12 or newer. Node.js comes with npm. React, TypeScript, and Vite install with the project in step 3.

Skip any tool you already have. These commands use [Homebrew](https://brew.sh) on macOS. On Windows or Linux, use the installers from [git-scm.com](https://git-scm.com/downloads), [python.org](https://www.python.org/downloads/), and [nodejs.org](https://nodejs.org/en/download).

Install Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install Git:

```bash
brew install git
```

Install Python 3.12:

```bash
brew install python@3.12
```

Install Node.js and npm:

```bash
brew install node
```

### 3. Install the project

Create a Python environment:

```bash
python3.12 -m venv .venv
```

Install the engine's packages:

```bash
.venv/bin/pip install -r engine/requirements.txt
```

Install the code database's packages:

```bash
.venv/bin/pip install -r codedb/requirements.txt
```

Install the packages that the tests need:

```bash
.venv/bin/pip install -r research/precedents/requirements.txt
```

Install the web app's packages, including React, TypeScript, and Vite:

```bash
npm ci --prefix web
```

### 4. Build the code database

Code search, Section C, and the PDF export need CodeDB. The app starts without it, but those parts show as unavailable. The download step fetches the official code PDFs, checks their hashes, and takes several minutes.

```bash
.venv/bin/pip install 'fonttools>=4.39'
```

```bash
.venv/bin/python scripts/fetch_sources.py
```

```bash
.venv/bin/python -m codedb build
```

### 5. Add your settings

The app runs without any API key. Keys turn on the AI steps. Copy the example settings file:

```bash
cp .env.example .env
```

`.env.example` holds two API keys and three switches:

```dotenv
OPENAI_API_KEY=
OPENROUTER_API_KEY=
BATATIS_LIVE=0
BATATIS_LIVE_ELEPHANT=0
BATATIS_DAILY_SPEND_CAP_USD=5
```

#### `OPENAI_API_KEY`

The OpenAI API runs GPT models. Batatis uses GPT to read more facts from descriptions and PDFs, and to check and quote the top code articles. The assistant also answers with GPT. Set `BATATIS_LIVE=1` to turn it on.

Files that use it:

- [`engine/llm_gate.py`](engine/llm_gate.py)
- [`engine/intake/model.py`](engine/intake/model.py)
- [`engine/identify/providers.py`](engine/identify/providers.py)
- [`engine/routes_assist.py`](engine/routes_assist.py)

Get a key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

#### `OPENROUTER_API_KEY`

OpenRouter is one API that reaches many AI models. Batatis uses it to call Elephant 1, a model hosted on Baseten that scores how relevant each code article is to the project. Set `BATATIS_LIVE_ELEPHANT=1` to turn on only this model.

The route that Batatis uses is free, but OpenRouter limits free requests per day, and one full scoring run takes about 135 requests. See the [Elephant guide](docs/elephant-provider.md).

Files that use it:

- [`engine/llm_gate.py`](engine/llm_gate.py)
- [`engine/identify/elephant_runtime.py`](engine/identify/elephant_runtime.py)
- [`engine/identify/providers.py`](engine/identify/providers.py)
- [`engine/identify/jevkit/keystore.py`](engine/identify/jevkit/keystore.py)

Get a key at [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys).

#### Switches

[`engine/llm_gate.py`](engine/llm_gate.py) reads all three switches.

| Switch | What it does |
| --- | --- |
| `BATATIS_LIVE` | `1` turns on every AI step that has a key. `0` keeps the app offline. |
| `BATATIS_LIVE_ELEPHANT` | `1` turns on only Elephant 1. `0` turns it off, even when `BATATIS_LIVE` is `1`. |
| `BATATIS_DAILY_SPEND_CAP_USD` | Stops AI calls for the day after this many US dollars. |

Voice needs an xAI key, `XAI_API_KEY`, which is not in the example file. See the [voice notes](docs/api/voice.md).

#### Officer access

To sign in as a Safety Codes Officer, add an access code for an authority to `.env`. Pick any code:

```dotenv
BATATIS_REVIEWER_CODES='{"edmonton":"pick-any-code"}'
```

### 6. Run the app

```bash
scripts/local-app.sh start
```

Open http://localhost:3000. The engine runs on port 8000, and its API docs are at http://127.0.0.1:8000/docs.

To try the officer side, sign up, choose **I review applications for an authority**, pick **Edmonton**, and enter your code.

To stop the app:

```bash
scripts/local-app.sh stop
```

#### Why `npm run dev` isn't enough

Batatis has two parts: the website, and the engine, a Python server that saves applications and runs the checks. `npm run dev` starts only the website, which can't load anything without the engine. `scripts/local-app.sh start` runs `npm run dev` for the website on port 3000 and starts the engine on port 8000.

To run the two parts yourself instead, start the engine in one terminal:

```bash
.venv/bin/python -m uvicorn engine.api:app --env-file .env --port 8000
```

Then start the website in a second terminal:

```bash
npm run dev --prefix web
```

### Make a pull request

`main` is the only permanent branch. Every change reaches it through a pull request from a short-lived branch, and GitHub deletes that branch after the pull request merges.

Start a branch from the latest `main`, named for your change:

```bash
git switch main
```

```bash
git pull
```

```bash
git switch -c fix-intake-wording
```

When your change is ready, run every check:

```bash
scripts/verify.sh
```

If you can't push to this repository, make your fork the `origin` remote:

```bash
gh repo fork simplythatguy/batatis --remote
```

Push your branch:

```bash
git push -u origin HEAD
```

Open the pull request into `main`, then fill in its three sections in everyday words:

```bash
gh pr create --repo simplythatguy/batatis --base main
```

On GitHub, you can instead click **Compare & pull request** and check that the base branch is `main`.

### Test a pull request

To test a pull request on your computer, check it out into its own branch. Replace `123` with the pull request number.

```bash
gh pr checkout 123 --repo simplythatguy/batatis --branch pr-123
```

Without the GitHub CLI, fetch it with Git and switch to it:

```bash
git fetch https://github.com/simplythatguy/batatis.git pull/123/head:pr-123
```

```bash
git switch pr-123
```

If the pull request changes `engine/requirements.txt` or `web/package.json`, repeat step 3. Then run the app:

```bash
scripts/local-app.sh start
```

To go back to `main`:

```bash
git switch main
```

## For AI agents

Read [`AGENTS.md`](AGENTS.md) and the skills it names before you write any code. Read them again when the task moves to a new area, such as from the engine to the screens.

| Before you | Read |
| --- | --- |
| Start any task | [`AGENTS.md`](AGENTS.md) and [`batatis-hackathon`](.cursor/skills/batatis-hackathon/SKILL.md) |
| Change the application flow or the engine | [`batatis-variance-workflow`](.cursor/skills/batatis-variance-workflow/SKILL.md) |
| Change anything on screen | [`batatis-ui-linear`](.cursor/skills/batatis-ui-linear/SKILL.md), [`batatis-ui-opus`](.cursor/skills/batatis-ui-opus/SKILL.md), [`batatis-ui-minimalist`](.cursor/skills/batatis-ui-minimalist/SKILL.md), and [`docs/design-system-calm.md`](docs/design-system-calm.md) |
| Change a skill or a rule | [`evals/fixtures/understanding-checklist.md`](evals/fixtures/understanding-checklist.md) |
| Plan, build, debug, or review code | The engineering skills in [`.agents/skills/`](.agents/skills/) and [pstack](docs/pstack.md) |
| Change this README or its diagrams | [`prettyme`](.agents/skills/prettyme/SKILL.md) |

These rules always apply:

- Never say that a design complies with the code or is safe. Batatis checks administrative completeness only.
- Never invent a code article number. Ask a question instead.
- Section C comes from lookup, never from a model.
- Never write Section D professional evidence. Say what the evidence must cover and when an engineer is required.
- On the alternative-solution path, keep the risk assessment, mitigating measures, and assumptions.
- Cite the National Building Code, 2023 Alberta Edition, second printing, first.
- Keep AI provider names out of everything the app shows. Tests enforce this.
- `main` is the only permanent branch. Do each batch of work on a short-lived branch, and let GitHub delete it after its pull request merges. Never recreate `dev`.
- Contribute through a pull request into `main`, after `scripts/verify.sh` passes, with the three-section description in everyday words. Never push to, merge into, or delete `main`.
- Run the app with `scripts/local-app.sh`, on ports 3000 and 8000 only.
- Subagents report only in their own task output. They never message other threads or agents.

## License

Copyright (c) 2026 the Batatis team. You may read and run this code for personal, educational, and evaluation use. Commercial use is not allowed without written permission. See [`LICENSE.md`](LICENSE.md).
