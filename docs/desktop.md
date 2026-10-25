# Desktop setup

The desktop package runs Batatis on your computer. It includes the same screens as the website and a private copy of the Python engine. You do not start the web server or use ports 3000 and 8000.

Applications in the desktop package stay on that computer. The package does not connect to the website's application database.

## Open the package

Build the package on its target operating system, or download the matching portable archive from a verified desktop workflow run. The workflow saves the app and its acceptance reports as separate artifacts.

The package targets Apple Silicon Macs and Windows x64. Extract the archive before opening `Batatis.app` on macOS or `Batatis.exe` on Windows. The Python engine and Codex runtime come with the package.

The macOS package uses ad hoc signing. It is not notarized. The Windows package has no publisher signature. Download acceptance through Gatekeeper or SmartScreen needs a separate check.

## Use local development

Local development has one test applicant and separate reviewers for Calgary and Edmonton. These are distinct Batatis identities in the same local database. You do not create accounts or share a password.

Open local development from the desktop sign-in screen. In **Settings**, choose the person you want to use. The account menu also lets you switch people.

When you submit an application as the applicant, the reviewer for its authority sees it in the queue. The normal claim, return, message, submission history and seven-day retention rules still apply. Switching people does not claim an application for review.

The app saves pending work before switching. A failed save keeps you with the current person and shows the reason.

The **This computer** workspace keeps ordinary local accounts and applications separately. Switching workspaces does not copy applications between them. The website has no development identity switch.

## Set up the building code

The package does not include the building-code database or the official source PDFs. Code search, Section C and submission need a database built by Batatis.

Build CodeDB from the official sources using the [repository setup steps](../README.md#4-build-the-code-database). In the desktop app's **Settings**, choose that `codedb.sqlite` file under **Code database**. Batatis checks the database and imports a local copy.

Your applications are stored separately from CodeDB. Replacing CodeDB does not replace your applications.

## Choose the AI connection

The AI connection belongs to the computer. It is separate from your Batatis account and development identity.

Under **Generation** in **Settings**, choose ChatGPT or OpenAI API key after connecting that account or saving its key. ChatGPT uses the bundled local Codex runtime. An OpenAI API key uses your API account and API billing. Off is the default and makes no provider request.

A failed connection or subscription limit never selects API billing automatically. Adding a key does not sign you in to ChatGPT.

### ChatGPT through Codex

Connect from **Settings**, open the official sign-in page and enter the displayed device code. Complete sign-in yourself in the browser. The app never asks for your ChatGPT password.

The managed connection uses its own Codex home and operating-system credential store. It does not import your development CLI's login, projects or conversation history.

Each workflow task starts a fresh temporary Codex thread. It supplies the workflow's instructions, prepared input and output schema. The pinned configuration suppresses workspace instructions, skills, memory and model-visible tools. The app rejects a changed model or extra context reported by the runtime.

The runtime is pinned to Codex `0.164.0` and GPT-6 Luna at medium reasoning effort. Sign-in and model access depend on your account. Native request captures and offline tests do not establish account entitlement or successful live inference.

Disconnecting cancels pending work and ends the managed connection. Voice is unavailable in the desktop package.

### API keys

Enter keys in the desktop key dialog. The host encrypts them using operating-system storage. The application page receives connection status, not the saved key.

An OpenAI key is for text generation and document review through the OpenAI API. A Jev key is for the existing article screening and reranking workflow. After saving a Jev key, turn optional screening on. Saving a key does not change either choice. Missing Jev leaves the engine's labeled keyword fallback available.

The desktop host uses only the key entered for that connection. It does not import a repository `.env` file, the web server's keys or a separate Jev credential file. Provider errors never choose another account or model.

## How the package runs

Electron is the desktop host. It serves the built React screens through the private `batatis://app` address. Requests go to the Python engine through process pipes instead of a network listener.

The engine keeps the normal Batatis account and application checks. The host holds the current session outside the page. A person or workspace switch drains pending requests and opens a fresh application window.

AI calls travel back through the host. Keys and managed credentials stay outside the engine and application page. Section C still comes from deterministic code lookup. AI cannot author professional evidence or approve a design.

These folders hold the desktop parts.

| Folder | Purpose |
| --- | --- |
| [`desktop/src/main/`](../desktop/src/main/) | Windows, sessions, native dialogs, provider connections and the engine process |
| [`desktop/src/preload/`](../desktop/src/preload/) | The small, checked interface available to an application window |
| [`desktop/codex/`](../desktop/codex/) | The pinned runtime downloader, model catalog and request checks |
| [`engine/desktop/`](../engine/desktop/) | Private request transport and the local workspace |
| [`web/src/desktop/`](../web/src/desktop/) | Desktop entry, Settings and person switching |

## Build from source

Build on the operating system you want to run. A frozen macOS Python engine cannot run on Windows.

Use Node.js 24 or newer and Python 3.14 for the desktop build. The desktop workflow pins the remaining dependencies. The website's separate development setup stays in the [README](../README.md#get-started).

Install the web dependencies from the repository root.

```sh
npm ci --prefix web
```

Install the desktop dependencies.

```sh
npm ci --prefix desktop
```

Fetch the pinned Codex runtime for your machine. For Apple Silicon macOS, run this command.

```sh
node desktop/codex/fetch.mjs runtime darwin-arm64
```

For Windows x64, run this command instead.

```sh
node desktop/codex/fetch.mjs runtime win32-x64
```

The model catalog and license notices are checked in. The downloader verifies the runtime archive's size and hash before extracting it.

Build the Python engine. This creates a separate build environment under `desktop/build/`.

```sh
npm run build:engine --prefix desktop
```

If Python is not on your path under its normal name, set `BATATIS_BUILD_PYTHON` to its executable before this step. The default is `python3` on macOS and `python` on Windows.

To build CodeDB on Windows, use the engine's build environment from the repository root. Install the data tools first.

```powershell
.\desktop\build\engine-venv\Scripts\python.exe -m pip install `
  -r codedb/requirements.txt fonttools
```

Fetch the official sources.

```powershell
.\desktop\build\engine-venv\Scripts\python.exe scripts/fetch_sources.py
```

Build the database, then choose `codedb/build/codedb.sqlite` in the app's **Settings**.

```powershell
.\desktop\build\engine-venv\Scripts\python.exe -m codedb build
```

On macOS, use `desktop/build/engine-venv/bin/python` in place of the Windows executable in those three commands.

Check the desktop source.

```sh
npm run typecheck --prefix desktop
```

Run the desktop tests.

```sh
npm test --prefix desktop
```

Build the application and portable archive.

```sh
npm run package --prefix desktop
```

The archive appears under `desktop/build/release/`. Packaging audits check for the native engine, PDF tools, fonts, TLS roots and unchanged Codex bytes. The audits reject databases, source documents and credentials in the package.

## Verify a build

The [desktop workflow](../.github/workflows/desktop.yml) builds on native macOS and Windows runners. Its packaged acceptance launches the app twice and checks uploads, PDFs, authority boundaries, person switching, persistence and owned-process cleanup. It saves reports and screenshots with the workflow run.

Offline provider fixtures check request forwarding and failure handling. They are not live provider acceptance or an accuracy benchmark. Complete managed sign-in and a real workflow request separately before claiming account-specific acceptance.

Run the full repository gate before publishing a change.

```sh
bash scripts/verify.sh
```

Native packages, operating-system credential storage, live provider access and the hosted website are separate verification surfaces. Passing one does not establish the others.
