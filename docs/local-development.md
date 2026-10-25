# Run Batatis locally

This guide starts the current Vite app and FastAPI engine without model API keys. The first block clones `main`, the only permanent branch. Run later commands from that repository root unless a step says otherwise.

## Start the workspace

Use Python 3.12 and Node.js 22.12 or newer. CI uses Python 3.12 and Node.js 22.

```bash
git clone https://github.com/simplythatguy/batatis.git
cd batatis
scripts/install-git-hooks.sh # once per clone; covers all its worktrees
python3.12 -m venv .venv
.venv/bin/pip install -r engine/requirements.txt -r codedb/requirements.txt
npm ci --prefix web
BATATIS_LIVE=0 BATATIS_LIVE_ELEPHANT=0 scripts/local-app.sh start
```

Open http://localhost:3000. The engine's route documentation is at http://127.0.0.1:8000/docs. Create a local applicant account to explore saved applications. Officer access requires a reviewer account; see the [account setup guide](api/accounts-review.md#configuration-and-security-receipt).

The launcher keeps this checkout's cases in `.data/cases.sqlite`. Cases and their files expire seven days after creation. Stop both servers with `scripts/local-app.sh stop`.

The workspace can start before the code database exists. Code lookup and export then report that their source data is unavailable.

## Build code lookup and PDF export

In another terminal at the repository root, download the pinned source files and build CodeDB:

```bash
.venv/bin/pip install 'fonttools>=4.39'
.venv/bin/python scripts/fetch_sources.py
.venv/bin/python -m codedb build
```

The fetch script downloads and checks the expected hashes of these official publications:

- NBC – 2023 Alberta Edition, second printing.
- NBC 2020 Intent Statements, explanatory material used alongside the Alberta edition.
- The Safety Codes Council variance form used by PDF export.

It also extracts the page text needed by the builder. Downloads and extraction can take several minutes. A missing source or hash mismatch stops the process.

The build creates `codedb/build/codedb.sqlite`. The legacy five-page form is saved as `codedb/build/SCC-Variance-Form.pdf`; `BATATIS_SCC_FORM` overrides only that legacy version. The default seven-page challenge form is the tracked, hash-pinned `engine/export/templates/challenge_2026-09-15.pdf`. See [template provenance](../engine/export/templates/README.md). Refresh the app after a successful build. Do not commit the generated SQLite database, downloaded legacy form, or downloaded NRC source PDFs. See the [CodeDB guide](../codedb/README.md) for source details and lookup commands.

## Manage the local app

Use only port 3000 for the web app and 8000 for the engine. The launcher refuses to start if either port is occupied. Check its owner before stopping a server.

```bash
scripts/local-app.sh status
scripts/local-app.sh stop
scripts/local-app.sh start
```

`main` is the only permanent branch and the only Vercel deployment branch. Do each batch of work on a short-lived branch, verify it locally, and open its pull request into `main` with `scripts/land.sh`. Only the user merges pull requests. Never push directly to `main`. See the [Git workflow](agents/git-workflow.md) for shared ownership and local verification.

## Optional configuration

The offline setup needs no `.env` file. [`.env.example`](../.env.example) contains only OpenAI/OpenRouter keys, their live switches and the US$5 daily application cap. Copy it to `.env` for optional local AI, enter your own server keys and set the relevant switch to `1` when enabling that provider. OpenAI backs GPT; OpenRouter backs Elephant. Hosted app users do not need copies of the server's provider keys.

The launcher loads the checkout's `.env` into Uvicorn. Existing process variables take precedence, so the start command above keeps all live providers off. It does not load server credentials into Vite. Hosting and optional feature settings are documented in the [deployment guide](deploy.md).

Keep real keys out of Git and the web bundle. Enabling a live provider requires separate configuration and spend controls. Adding a key alone is not proof that a provider works. See the [Elephant provider guide](elephant-provider.md), [identification API](api/identify.md), and [deployment guide](deploy.md) before enabling providers or configuring a hosted environment.

## Run checks

From `web`, with its dependencies installed:

```bash
npm test
npm run typecheck
npm run build
```

From the repository root, install the remaining test dependencies and run the engine checks:

```bash
.venv/bin/pip install -r research/precedents/requirements.txt
BATATIS_LIVE=0 .venv/bin/python -m pytest -q engine/tests codedb/tests evals_dev -rs
```

Tests that need missing source files, a PostgreSQL test service, or live credentials may skip. Read the skip reasons. A local pass does not establish hosted behavior or professional approval. See [browser and sync checks](../web/tests/README.md) and the [user-testing guide](user-testing/README.md) for broader verification.
