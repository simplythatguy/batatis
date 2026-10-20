# Record a demo video

One command boots the Vite app in `web/`, walks the seven shots in `docs/demo/script.md`, and writes an mp4 plus a key frame for each shot that was actually on screen.

```bash
./scripts/record-demo.sh
```

Output, gitignored, from the repo root:

- `artifacts/demo/batatis-demo.mp4`
- `artifacts/demo/record-log.json`
- `artifacts/demo/frames/shot-NN-*.png`

The log lists every shot as `recorded` or `skipped`, with the reason. A missing screen does not fail the run unless you pass `--strict`, which exits non-zero when any shot is skipped. The command also exits non-zero when the app does not boot, the mp4 is not a playable H.264 file, a file is downloaded, or every shot was skipped.

No API key is required. The recorder does not start the engine and does not call a model. The browser aborts `/api` and port 8000, so search rows and Section D issues stay on the app's offline path. The recorder will not type an article id that the search did not return, and it does not upload or download a PDF. Every recorded frame that shows fixture or sample data carries a visible `EXAMPLE DATA` label. If the officer screen shows `11821 73 Avenue NW`, that string is replaced with `100 Example Street NW` before the frame is kept.

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

Walkthrough steps live in `scripts/demo-record/steps.mjs`. There are seven shots. Each step's id, title, and primary route match `docs/demo/script.md`: the `### Shot N —` heading, and the first hash route on that shot's `**Route:**` line. The burned-in caption is `Shot N · <title>`.

The camera follows the script's order, not shot numbers. Case C stays open for shots 2, 4, 5, and shot 7's Case C frame. Reset runs at the start of shot 3 and wipes Case C. Shot 7's Case A frame is next, then shot 6. Case B is named on shot 1 and is not walked. Shot 3 holds on the saved open question. Ranked-list, benchmark, and eval stills are not in the app, so they are logged and omitted.

```bash
./scripts/record-demo.sh --check-script
./scripts/record-demo.sh --strict
./scripts/record-demo.sh --stills --branch cursor/e2e-product-flow-4362
```

`--stills` writes the deck PNGs named in the screenshot slot list, 1440×900, under `artifacts/deck-stills/`. It does not record the mp4. A slot whose screen is not in the build is skipped and listed in `stills-log.json`. Nothing is drawn in its place. Seeded frames carry the `EXAMPLE DATA` label. The run does not upload a PDF and does not click Check completeness.

`--check-script` diffs the script against the step catalog and exits non-zero on drift. It does not record, including when `--out` is also set. When `docs/demo/script.md` is absent, the check reports that and exits zero. A normal recording prints the same report and still records.

`node --test scripts/demo-record/sync.test.mjs` checks the parser and that the catalog still lists those seven shots.
