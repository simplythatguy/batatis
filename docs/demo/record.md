# Record a demo video

One command boots the Vite app in `web/`, walks the shots in the demo script, and writes an mp4 plus a key frame for each shot that was actually on screen.

```bash
./scripts/record-demo.sh
```

Output, gitignored, from the repo root:

- `artifacts/demo/batatis-demo.mp4`
- `artifacts/demo/record-log.json`
- `artifacts/demo/frames/shot-NN-*.png`

The log lists every shot as `recorded` or `skipped`, with the reason. A missing screen does not fail the run. The command exits non-zero only when the app does not boot, the mp4 is not a playable H.264 file, or every shot was skipped.

No API key is required. The recorder does not start the engine and does not call a model. It uses whatever the running app already does offline: the fixture case, the example role flow, and bundled fallbacks. Search rows and Section D issues appear only when an engine is already listening on `127.0.0.1:8000`. The recorder will not type an article id that the search did not return.

Chrome (or `CHROME_PATH`) and `ffmpeg` must be on the machine. The first run installs `playwright-core` under `scripts/demo-record/`, downloads Playwright's small ffmpeg build (it muxes the capture; the system `ffmpeg` writes the mp4), and, if needed, installs `web/` dependencies.

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

`--out` sets the directory. `--hold 2000` is the pause, in milliseconds, on each recorded shot. `--base http://127.0.0.1:5173` records an app you already started.

## Keeping steps in sync with the script

Walkthrough steps live in `scripts/demo-record/steps.mjs`. Each step's id, title, and primary route are the shot-list row in `docs/demo/script.md`.

```bash
./scripts/record-demo.sh --check-script
```

When `docs/demo/script.md` is on the branch, this diffs the shot table and the `### Shot N —` headings against the step catalog and exits non-zero on drift. When the file is not on the branch yet, the check reports that and exits zero. A normal recording prints the same report and still records.

`node --test scripts/demo-record/sync.test.mjs` checks the parser and that the catalog still lists those eleven shots.
