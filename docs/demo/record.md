# Record a demo video

One command boots the Vite app in `web/`, walks the seven shots in `docs/demo/script.md`, and writes an mp4 plus a key frame for each shot that was actually on screen.

```bash
./scripts/record-demo.sh
```

Output, gitignored, from the repo root:

- `artifacts/demo/batatis-demo.mp4`
- `artifacts/demo/record-log.json`
- `artifacts/demo/frames/shot-NN-*.png`

The log lists every shot as `recorded`, `skipped`, or `failed`, with the reason. A missing screen is `skipped`. A screen that opened without the target on it is `failed`, and that shot is not marked recorded. `--strict` exits non-zero unless all seven shots are recorded. Without `--strict`, a missing screen does not fail the run. The command still exits non-zero when the app does not boot, the mp4 is not a playable H.264 file of at least three seconds, or a file is downloaded.

On this branch the web app does not have Who, an empty case, Search Division B, the Section D tab, the planted officer package, or the authority select. Those shots are skipped or failed. The mp4 is the opening screen. It is not labelled as Case A or Case C. `--strict` is the submission take, for a branch that has the seven screens.

No API key is required. The recorder does not start the engine and does not call a model. The browser aborts `/api` and port 8000, so search rows and Section D issues stay on the app's offline path. The recorder will not type an article id that the search did not return, and it does not upload or download a PDF. Every recorded frame that shows fixture or sample data carries a visible `EXAMPLE DATA` label. If the officer screen shows `11821 73 Avenue NW`, that string is replaced with `100 Example Street NW` before the frame is kept.

Chrome (or `CHROME_PATH`), `ffmpeg`, and `ffprobe` must be on the machine. `ffprobe` checks that the mp4 is H.264 and at least three seconds. The first run installs `playwright-core` under `scripts/demo-record/` and downloads Playwright's ffmpeg into `~/.cache/ms-playwright/ffmpeg-*` (on Linux the binary is `ffmpeg-linux`). That copy only muxes the browser capture. The system `ffmpeg` writes the mp4 and the system `ffprobe` checks it. Chrome is also looked up at the usual Linux Chromium paths and under `/Applications` on macOS. If `web/node_modules` is missing, the same run installs those dependencies.

Burned-in captions name the text on screen. They are not the shot titles. The EXAMPLE DATA label sits in the sidebar, under the navigation, so it does not cover the header subtitle or the footer line about compliance.

If an engine is already listening on `127.0.0.1:8000`, the recorder prints a warning and continues. The browser aborts `/api` and port 8000, so the recording does not create cases. Pass `--engine` to record that the engine was present on purpose. The recorder still does not start one.

## Another branch

Record a branch without checking it out and without committing on it:

```bash
./scripts/record-demo.sh --branch cursor/e2e-product-flow-4362
```

That fetches the ref, adds a detached worktree, installs that worktree's `web/` dependencies, and deletes the worktree when the recording finishes. Your current branch is unchanged. The target branch is not updated.

To record a checkout you already have:

```bash
./scripts/record-demo.sh --web /path/to/that/checkout/web --out artifacts/demo-pr16
```

`--web`, `--out`, and `--script` are resolved from the directory you ran the command in. `--hold 2000` is the pause, in milliseconds, on each recorded beat. The open-question beat holds for 3.5 seconds. `--base http://127.0.0.1:5173` records an app you already started. `--branch` uses a new temporary worktree each run.

## Keeping steps in sync with the script

Walkthrough steps live in `scripts/demo-record/steps.mjs`. There are seven shots. Each step's id, title, and primary route match `docs/demo/script.md`: the `### Shot N —` heading, and the first hash route on that shot's `**Route:**` line. The burned-in caption describes the screen. The catalog title stays the `### Shot N —` heading.

The camera follows the script's order, not shot numbers. Case C stays open for shots 2, 4, 5, and shot 7's Case C frame. Reset runs at the start of shot 3 and wipes Case C. Shot 7's Case A frame is next, then shot 6. Case B is named on shot 1 and is not walked. Shot 3 holds on the saved open question. Ranked-list, benchmark, and eval stills are not in the app, so they are logged and omitted.

```bash
./scripts/record-demo.sh --check-script
./scripts/record-demo.sh --strict
```

`--check-script` diffs the script against the step catalog and exits non-zero on drift. It does not record, including when `--out` is also set. When `docs/demo/script.md` is absent, the check reports that and exits zero. A normal recording prints the same report and still records.

`node --test scripts/demo-record/sync.test.mjs` checks the parser and that the catalog still lists those seven shots.
