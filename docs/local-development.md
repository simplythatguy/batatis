# Run Batatis locally

This guide starts the current Vite app and FastAPI engine without model API keys. The first block clones the prototype integration. Run later commands from that repository root unless a step says otherwise.

## Start the workspace

Use Python 3.12 and Node.js 22.12 or newer. CI uses Python 3.12 and Node.js 22.

```bash
git clone --branch work/mvp-improvement-20261022 \
  https://github.com/simplythatguy/batatis.git
cd batatis
python3.12 -m venv .venv
.venv/bin/pip install -r engine/requirements.txt -r codedb/requirements.txt
BATATIS_LIVE=0 BATATIS_STORE=file BATATIS_CASES=./.data/cases.sqlite \
  .venv/bin/uvicorn engine.api:app --port 8000
```

Keep that terminal open. The engine's interactive route documentation is at http://127.0.0.1:8000/docs.

In a second terminal, open the cloned repository's `web` directory:

```bash
cd batatis/web
npm ci
npm run dev
```

Open the URL Vite prints, usually http://localhost:5173. Create a local applicant account from the sign-in page to explore saved applications. Officer access requires a reviewer account; see the [account setup guide](api/accounts-review.md#configuration-and-security-receipt).

The launch command stores this clone's cases in `.data/cases.sqlite`. Without `BATATIS_CASES`, the engine uses `~/.batatis/cases.sqlite`, which other local clones can share. Cases and their files expire seven days after creation. Stop each server with Ctrl+C.

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

The build creates `codedb/build/codedb.sqlite`. The form is saved as `codedb/build/SCC-Variance-Form.pdf`. Refresh the app after a successful build. Do not commit these files or the downloaded source PDFs. See the [CodeDB guide](../codedb/README.md) for source details and lookup commands.

## Use another port

If port 8000 is occupied, start the engine on an unused port:

```bash
BATATIS_LIVE=0 BATATIS_STORE=file BATATIS_CASES=./.data/cases.sqlite \
  .venv/bin/uvicorn engine.api:app --port 8010
```

Start Vite from `web` with the same engine URL:

```bash
VITE_ENGINE_URL=http://127.0.0.1:8010 npm run dev
```

Use the URL each process prints. Vite may choose another port if 5173 is occupied.

## Optional configuration

The offline setup needs no `.env` file. [`.env.example`](../.env.example) lists optional variable names and defaults. The engine reads process environment variables; the commands above set the local storage and offline choices explicitly.

Keep real keys out of Git and the web bundle. Enabling a live provider requires separate configuration and spend controls. Adding a key alone is not proof that a provider works. See the [identification API](api/identify.md) and [deployment guide](deploy.md) before configuring a hosted environment.

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
