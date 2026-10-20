/**
 * Boot the Vite app in web/ and record a walkthrough.
 *
 *   ./scripts/record-demo.sh
 *   ./scripts/record-demo.sh --branch cursor/e2e-product-flow-4362
 *
 * By default this starts the checkout's engine on 127.0.0.1:8000, or reuses
 * one that is already listening, and lets the browser call /api. Pass
 * --offline to skip the engine and abort /api. The recorder does not call a
 * model API itself.
 */
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { copyFileSync, mkdirSync, writeFileSync, existsSync, readFileSync, readdirSync, rmSync, mkdtempSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { basename, dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import { STEPS, runDeckStills, runWalkthrough } from "./steps.mjs";
import { diffScript } from "./sync.mjs";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

function parseArgs(argv) {
  const out = {
    checkScript: false,
    strict: false,
    engine: false,
    offline: false,
    stills: false,
    allowDrift: false,
    holdMs: 1600,
    web: null,
    branch: null,
    out: null,
    base: null,
    script: null,
    help: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => {
      const value = argv[(i += 1)];
      if (!value || value.startsWith("--")) throw new Error(`Missing value for ${arg}`);
      return value;
    };
    if (arg === "--check-script") out.checkScript = true;
    else if (arg === "--strict") out.strict = true;
    else if (arg === "--engine") out.engine = true;
    else if (arg === "--offline") out.offline = true;
    else if (arg === "--stills") out.stills = true;
    else if (arg === "--allow-drift") out.allowDrift = true;
    else if (arg === "--web") out.web = next();
    else if (arg === "--branch") out.branch = next();
    else if (arg === "--out") out.out = next();
    else if (arg === "--base") out.base = next();
    else if (arg === "--hold") out.holdMs = Number(next());
    else if (arg === "--script") out.script = next();
    else if (arg === "--help" || arg === "-h") out.help = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (Number.isNaN(out.holdMs) || out.holdMs < 0) throw new Error("--hold must be a number of milliseconds");
  if (out.web && out.branch) throw new Error("Pass either --web or --branch, not both.");
  if (out.offline && out.engine) throw new Error("Pass either --offline or --engine, not both.");
  return out;
}

const HELP = `Record a Batatis walkthrough mp4.

  ./scripts/record-demo.sh
  ./scripts/record-demo.sh --branch <git-ref>
  ./scripts/record-demo.sh --web <path-to-web>
  ./scripts/record-demo.sh --check-script
  ./scripts/record-demo.sh --strict
  ./scripts/record-demo.sh --stills --branch <git-ref>

Options
  --out <dir>       Output directory (default artifacts/demo, or artifacts/deck-stills with --stills)
  --hold <ms>       Pause on each recorded shot (default 1600)
  --base <url>      Record an app that is already running
  --script <file>   Shot list to diff (default: docs/demo/script.md on #20, cursor/demo-video-script-1e38)
  --stills          Write the deck PNGs at 1440×900 and skip the mp4
  --strict          Exit non-zero unless every shot or still is captured
  --allow-drift     Record even when the script and the step catalog disagree
  --offline         Do not start the engine, and abort /api and port 8000
  --engine          Use the engine (this is already the default)
`;

function run(cmd, args, opts = {}) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"], ...opts });
    let stdout = "";
    let stderr = "";
    child.stdout?.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr?.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolveRun({ stdout, stderr });
      else reject(new Error(`${cmd} ${args.join(" ")} exited ${code}\n${stderr.slice(-4000)}`));
    });
  });
}

async function ensurePlaywrightFfmpeg() {
  const home = process.env.HOME || "";
  const cache = join(home, ".cache/ms-playwright");
  if (existsSync(cache)) {
    const found = readdirSync(cache).some((name) => {
      if (!name.startsWith("ffmpeg-")) return false;
      const dir = join(cache, name);
      return existsSync(dir) && readdirSync(dir).some((file) => file.startsWith("ffmpeg"));
    });
    if (found) return;
  }
  const require = createRequire(import.meta.url);
  const pkg = dirname(require.resolve("playwright-core/package.json"));
  console.log("Downloading Playwright's ffmpeg (video mux only; no browser download).");
  await run(process.execPath, [join(pkg, "cli.js"), "install", "ffmpeg"]);
}

function chromePath() {
  if (process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  for (const path of [
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/local/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
  ]) {
    if (existsSync(path)) return path;
  }
  throw new Error("Chrome was not found. Set CHROME_PATH to a Chrome or Chromium binary.");
}

function freePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolvePort(port));
    });
  });
}

async function git(args, cwd) {
  const { stdout } = await run("git", args, { cwd });
  return stdout.trim();
}

async function materializeBranch(ref) {
  const safe = ref.replace(/[^a-zA-Z0-9._-]+/g, "-").slice(0, 80);
  const parent = mkdtempSync(join(tmpdir(), `batatis-record-${safe}-`));
  const dir = join(parent, "checkout");
  const suffix = basename(parent).split("-").pop();
  const localRef = `refs/batatis-record/${safe}-${suffix}`;
  try {
    await run("git", ["fetch", "origin", `${ref}:${localRef}`], { cwd: repoRoot });
  } catch (error) {
    const local = await git(["rev-parse", "--verify", `${ref}^{commit}`], repoRoot).catch(() => "");
    if (!local) {
      rmSync(parent, { recursive: true, force: true });
      throw new Error(`Could not fetch ${ref}. ${error.message}`);
    }
    await run("git", ["update-ref", localRef, local], { cwd: repoRoot });
  }
  try {
    await run("git", ["worktree", "add", "--detach", dir, localRef], { cwd: repoRoot });
  } catch (error) {
    await run("git", ["update-ref", "-d", localRef], { cwd: repoRoot }).catch(() => {});
    rmSync(parent, { recursive: true, force: true });
    throw error;
  }
  return {
    dir,
    async cleanup() {
      await run("git", ["worktree", "remove", "--force", dir], { cwd: repoRoot }).catch(() => {});
      await run("git", ["update-ref", "-d", localRef], { cwd: repoRoot }).catch(() => {});
      rmSync(parent, { recursive: true, force: true });
    },
  };
}

async function ensureWebDeps(webDir) {
  if (existsSync(join(webDir, "node_modules", "vite"))) return;
  console.log(`Installing web dependencies in ${webDir}`);
  await run("npm", ["ci"], { cwd: webDir });
}

function startVite(webDir, port) {
  const child = spawn(
    "npm",
    ["run", "dev", "--", "--host", "127.0.0.1", "--port", String(port), "--strictPort"],
    {
      cwd: webDir,
      detached: true,
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, BROWSER: "none", NO_COLOR: "1" },
    },
  );
  let log = "";
  const take = (chunk) => {
    log += chunk.toString();
    if (log.length > 30000) log = log.slice(-30000);
  };
  child.stdout.on("data", take);
  child.stderr.on("data", take);
  const url = `http://127.0.0.1:${port}/`;
  const ready = (async () => {
    const started = Date.now();
    while (Date.now() - started < 60000) {
      if (child.exitCode !== null) throw new Error(`Vite exited early.\n${log}`);
      try {
        const res = await fetch(url);
        if (res.status < 500) return url;
      } catch {
        /* still booting */
      }
      await new Promise((resolveWait) => setTimeout(resolveWait, 300));
    }
    throw new Error(`Vite did not start.\n${log}`);
  })();
  return { child, ready, log: () => log };
}

function stopChild(child) {
  if (!child?.pid || child.exitCode !== null) return;
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {
    try {
      child.kill("SIGTERM");
    } catch {
      /* already gone */
    }
  }
}

async function engineUp() {
  try {
    const res = await fetch("http://127.0.0.1:8000/openapi.json", { signal: AbortSignal.timeout(800) });
    return res.ok;
  } catch {
    return false;
  }
}

function loggedWebDir(absPath) {
  const rel = relative(repoRoot, absPath || "");
  if (rel && !rel.startsWith("..") && !isAbsolute(rel)) return rel.split("\\").join("/");
  return "web";
}

async function ensureCodeDb(engineRoot) {
  const db = join(engineRoot, "codedb/build/codedb.sqlite");
  if (existsSync(db)) return "The code database is already built.";
  const local = join(repoRoot, "codedb/build/codedb.sqlite");
  if (existsSync(local) && resolve(local) !== resolve(db)) {
    mkdirSync(dirname(db), { recursive: true });
    copyFileSync(local, db);
    return "Copied the code database into the recorded checkout.";
  }
  const pdf = join(engineRoot, "reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf");
  const text = join(engineRoot, "reference/text/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl");
  if (!existsSync(pdf) || !existsSync(text)) {
    return "The NBC source PDF and page text are not in this checkout, so the code database was not built.";
  }
  console.log("Building the code database from the checkout's NBC sources.");
  try {
    await run("python3", ["-m", "codedb", "build"], { cwd: engineRoot });
  } catch (error) {
    const line = (error instanceof Error ? error.message : String(error)).split("\n")[0];
    return `The code database build failed: ${line}`;
  }
  return existsSync(db)
    ? "Built the code database from the checkout's NBC sources."
    : "The code database build did not write codedb/build/codedb.sqlite.";
}

async function ensureEnginePython(engineRoot) {
  try {
    await run("python3", ["-c", "import uvicorn, fastapi"], { cwd: engineRoot });
    return;
  } catch {
    const requirements = join(engineRoot, "engine/requirements.txt");
    if (!existsSync(requirements)) {
      throw new Error(`The engine at ${engineRoot} has no engine/requirements.txt, and uvicorn is not installed.`);
    }
    console.log(`Installing engine dependencies from ${requirements}`);
    await run("python3", ["-m", "pip", "install", "-r", requirements], { cwd: engineRoot });
  }
}

async function startEngine(engineRoot) {
  const api = join(engineRoot, "engine/api.py");
  if (!existsSync(api)) throw new Error(`${engineRoot} has no engine/api.py, so the recorder cannot start the engine.`);
  await ensureEnginePython(engineRoot);
  const child = spawn("python3", ["-m", "uvicorn", "engine.api:app", "--host", "127.0.0.1", "--port", "8000"], {
    cwd: engineRoot,
    detached: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env },
  });
  let log = "";
  const take = (chunk) => {
    log += chunk.toString();
    if (log.length > 20000) log = log.slice(-20000);
  };
  child.stdout.on("data", take);
  child.stderr.on("data", take);
  const started = Date.now();
  while (Date.now() - started < 45000) {
    if (child.exitCode !== null) {
      throw new Error(`The engine exited before it was ready.\n${log.slice(-2000)}`);
    }
    if (await engineUp()) return child;
    await new Promise((resolveWait) => setTimeout(resolveWait, 300));
  }
  stopChild(child);
  throw new Error(`The engine did not answer on 127.0.0.1:8000.\n${log.slice(-2000)}`);
}

async function probeCodeSearch() {
  try {
    const res = await fetch("http://127.0.0.1:8000/code/search?q=window&limit=1", { signal: AbortSignal.timeout(2000) });
    return res.status;
  } catch {
    return 0;
  }
}

function engineNote(state, codedbNote, searchStatus) {
  const search =
    searchStatus === 200
      ? "Code search answered."
      : searchStatus
        ? `Code search returned ${searchStatus}.`
        : "Code search did not answer.";
  const how =
    state === "reused"
      ? "Reused the engine already listening on 127.0.0.1:8000."
      : "Started uvicorn engine.api:app on 127.0.0.1:8000 from the recorded checkout.";
  return `${how} Browser requests to /api are proxied to it. ${codedbNote} ${search} The recorder did not call a model API. No PDF is uploaded.`;
}

async function prepareEngine(args, engineRoot) {
  if (args.offline) {
    return {
      networkMode: "offline",
      engineState: "offline",
      child: null,
      searchStatus: 0,
      note: "Offline mode (--offline). The recorder did not start an engine. Browser requests to /api and port 8000 are aborted. No PDF is uploaded.",
    };
  }
  const codedbNote = await ensureCodeDb(engineRoot);
  if (await engineUp()) {
    const searchStatus = await probeCodeSearch();
    return {
      networkMode: "engine",
      engineState: "reused",
      child: null,
      searchStatus,
      note: engineNote("reused", codedbNote, searchStatus),
    };
  }
  console.log(`Starting the engine from ${engineRoot}`);
  const child = await startEngine(engineRoot);
  const searchStatus = await probeCodeSearch();
  return {
    networkMode: "engine",
    engineState: "started",
    child,
    searchStatus,
    note: engineNote("started", codedbNote, searchStatus),
  };
}

async function gitIdentity(cwd) {
  try {
    const sha = await git(["rev-parse", "HEAD"], cwd);
    const branch = await git(["rev-parse", "--abbrev-ref", "HEAD"], cwd);
    return { sha: sha || null, branch: branch || null };
  } catch {
    return { sha: null, branch: null, error: "not a git checkout" };
  }
}

async function blockTraffic(page, { offline }) {
  await page.route("**/*", (route) => {
    let blocked = false;
    try {
      const url = new URL(route.request().url());
      const model =
        url.hostname === "api.openai.com" ||
        url.hostname.endsWith(".openai.com") ||
        url.hostname === "api.anthropic.com";
      const engine = url.port === "8000" || url.pathname === "/api" || url.pathname.startsWith("/api/");
      blocked = model || (offline && engine);
    } catch {
      blocked = false;
    }
    if (blocked) return route.abort();
    return route.continue();
  });
}

const SCRIPT_SOURCES = [
  "docs/demo/script.md",
  "origin/dev:docs/demo/script.md",
  "origin/cursor/demo-video-script-1e38:docs/demo/script.md",
];

function reportScript(markdown, source) {
  const diff = diffScript(STEPS, markdown);
  const drifted = diff.problems.length > 0;
  return {
    status: drifted ? "drift" : "ok",
    source,
    problems: diff.problems,
    note: drifted
      ? "The demo script and the recorder steps do not match. This is a hard failure."
      : `Recorder steps match ${source}.`,
  };
}

async function showGitScript(spec) {
  const ref = spec.slice(0, spec.indexOf(":"));
  const remoteRef = ref.startsWith("origin/") ? ref.slice("origin/".length) : ref;
  try {
    await run("git", ["fetch", "--quiet", "origin", remoteRef], { cwd: repoRoot });
  } catch (error) {
    const line = (error instanceof Error ? error.message : String(error)).split("\n")[0];
    console.log(`Could not refresh ${remoteRef} (${line}). Reading ${spec}.`);
  }
  const { stdout } = await run("git", ["show", spec], { cwd: repoRoot });
  return stdout;
}

async function loadScript(args) {
  if (args.script) {
    const path = resolve(args.script);
    if (!existsSync(path)) {
      return {
        status: "missing",
        source: args.script,
        problems: [`Script file not found: ${path}`],
        note: `Script file not found: ${args.script}. Leave --script unset to read the working tree, origin/dev, then #20.`,
      };
    }
    return reportScript(readFileSync(path, "utf8"), args.script);
  }
  const local = join(repoRoot, SCRIPT_SOURCES[0]);
  if (existsSync(local)) return reportScript(readFileSync(local, "utf8"), SCRIPT_SOURCES[0]);
  const problems = [];
  for (const spec of SCRIPT_SOURCES.slice(1)) {
    try {
      return reportScript(await showGitScript(spec), spec);
    } catch (error) {
      const line = (error instanceof Error ? error.message : String(error)).split("\n")[0];
      problems.push(`Could not read ${spec}. ${line}`);
    }
  }
  return {
    status: "missing",
    source: SCRIPT_SOURCES.join(", "),
    problems,
    note: "Could not read docs/demo/script.md from the working tree, origin/dev, or #20.",
  };
}

function printStills(results) {
  const captured = results.filter((slot) => slot.status === "captured");
  const pending = results.filter((slot) => slot.status !== "captured");
  console.log(`\nCaptured ${captured.length} of ${results.length} deck stills.`);
  for (const slot of captured) {
    console.log(`  captured  ${slot.file}`);
    if (slot.provenance) console.log(`            ${slot.provenance}`);
  }
  for (const slot of pending) {
    const label = String(slot.status || "pending").padEnd(8);
    console.log(`  ${label} ${slot.file}`);
    console.log(`            ${slot.reason}`);
  }
}

function printReport(results) {
  const recorded = results.filter((step) => step.status === "recorded");
  const skipped = results.filter((step) => step.status !== "recorded");
  console.log(`\nRecorded ${recorded.length} of ${results.length} shots.`);
  for (const step of recorded) {
    const extra = step.notes?.length ? ` (${step.notes.length} note${step.notes.length === 1 ? "" : "s"})` : "";
    console.log(`  recorded  ${step.id}  ${step.title}${extra}`);
  }
  for (const step of skipped) {
    const label = step.status === "failed" ? "failed   " : step.status === "pending" ? "pending  " : "skipped  ";
    console.log(`  ${label} ${step.id}  ${step.title}`);
    console.log(`            ${step.reason}`);
  }
}

async function convertMp4(webm, mp4, trimSeconds) {
  const args = ["-y"];
  if (trimSeconds > 0.05) args.push("-ss", trimSeconds.toFixed(3));
  args.push(
    "-i",
    webm,
    "-an",
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    "-crf",
    "20",
    mp4,
  );
  await run("ffmpeg", args);
  const { stdout: durationOut } = await run("ffprobe", [
    "-v",
    "error",
    "-show_entries",
    "format=duration",
    "-of",
    "csv=p=0",
    mp4,
  ]);
  const { stdout: codecOut } = await run("ffprobe", [
    "-v",
    "error",
    "-select_streams",
    "v:0",
    "-show_entries",
    "stream=codec_name,width,height",
    "-of",
    "csv=p=0",
    mp4,
  ]);
  const duration = Number(durationOut.trim());
  const [codec, width, height] = codecOut.trim().split(",");
  if (!Number.isFinite(duration) || duration < 3) throw new Error(`mp4 duration is ${durationOut.trim()}`);
  if (codec !== "h264") throw new Error(`expected h264, got ${codecOut.trim()}`);
  return { duration, codec, width: Number(width), height: Number(height) };
}

async function stillSourceBranch(args, gitInfo) {
  const requested = args.branch;
  const sha = gitInfo.sha || "";
  if (requested && sha && !sha.startsWith(requested) && requested !== "HEAD") return requested;
  if (sha) {
    try {
      const { stdout } = await run("git", ["branch", "-r", "--contains", sha], { cwd: repoRoot });
      const names = stdout
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.startsWith("origin/") && !line.includes("->"))
        .map((line) => line.replace(/^origin\//, ""));
      if (names.length === 1) return names[0];
    } catch {
      // A detached sha with no containing branch keeps the short sha below.
    }
  }
  if (requested && sha.startsWith(requested)) return sha.slice(0, 7);
  if (requested) return requested;
  if (gitInfo.branch && gitInfo.branch !== "HEAD") return gitInfo.branch;
  return "detached";
}

async function captureDeckStills({ args, outDir, base, webDir, gitInfo, engineSession, sync }) {
  const browser = await chromium.launch({
    executablePath: chromePath(),
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
      colorScheme: "dark",
    });
    try {
      await context.grantPermissions(["clipboard-read", "clipboard-write"]);
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      const pageErrors = [];
      const downloads = [];
      page.on("pageerror", (error) => pageErrors.push(error.message));
      page.on("download", (download) => downloads.push(download.suggestedFilename()));
      await blockTraffic(page, { offline: args.offline });
      await page.goto(`${base.replace(/\/$/, "")}/?reset`, { waitUntil: "domcontentloaded", timeout: 30000 });
      await h1Ready(page);
      await page.evaluate(() => document.fonts?.ready);
      const recordedAt = new Date().toISOString();
      const sourceBranch = await stillSourceBranch(args, gitInfo);
      const results = await runDeckStills(page, {
        outDir,
        sourceBranch,
        sourceSha: gitInfo.sha,
        recordedAt,
        engineSearchStatus: engineSession.searchStatus,
      });
      const log = {
        recordedAt,
        mode: "stills",
        networkMode: engineSession.networkMode,
        engineState: engineSession.engineState,
        viewport: { width: 1440, height: 900 },
        webDir: loggedWebDir(webDir),
        git: { ...gitInfo, requestedBranch: args.branch },
        baseUrl: base,
        engine: engineSession.note,
        scriptSync: sync,
        pageErrors,
        downloads,
        slots: results,
      };
      const logPath = join(outDir, "stills-log.json");
      writeFileSync(logPath, `${JSON.stringify(log, null, 2)}\n`);
      printStills(results);
      console.log(`\nstills ${outDir}`);
      console.log(`log ${logPath}`);
      if (downloads.length) {
        throw new Error(`A file was downloaded (${downloads.join(", ")}). The recorder does not save a PDF.`);
      }
      const captured = results.filter((slot) => slot.status === "captured");
      if (!captured.length) throw new Error("No deck still was captured.");
      const missing = results.filter((slot) => slot.status !== "captured");
      if (args.strict && missing.length) {
        const detail = missing.map((slot) => slot.file).join(", ");
        throw new Error(`--strict: ${missing.length} still(s) missing: ${detail}`);
      }
    } finally {
      await context.close().catch(() => {});
    }
  } finally {
    await browser.close().catch(() => {});
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(HELP);
    return;
  }
  const sync = await loadScript(args);
  console.log(sync.note);
  for (const problem of sync.problems) console.log(`  ${problem}`);
  if (sync.status === "drift" && args.allowDrift && !args.checkScript) {
    console.log("Recording with --allow-drift. The script and the recorder steps do not match.");
  } else if (sync.status !== "ok") {
    process.exitCode = 1;
    if (!args.checkScript) console.log("Stopped before recording. Pass --allow-drift to record when the script and the steps disagree.");
    return;
  }
  if (args.checkScript) return;

  let cleanup = async () => {};
  let webDir = resolve(args.web || join(repoRoot, "web"));
  if (args.branch) {
    console.log(`Fetching ${args.branch} into a detached worktree. That branch will not be checked out or modified.`);
    const tree = await materializeBranch(args.branch);
    cleanup = tree.cleanup;
    webDir = join(tree.dir, "web");
    if (!existsSync(webDir)) {
      await cleanup();
      throw new Error(`${args.branch} has no web/ directory.`);
    }
  }

  const outDir = resolve(args.out || join(repoRoot, args.stills ? "artifacts/deck-stills" : "artifacts/demo"));
  mkdirSync(outDir, { recursive: true });
  const framesDir = join(outDir, "frames");
  const videoDir = join(outDir, ".video");
  if (!args.stills) {
    mkdirSync(framesDir, { recursive: true });
    mkdirSync(videoDir, { recursive: true });
  }
  const mp4 = join(outDir, "batatis-demo.mp4");
  let vite;
  let engineSession;

  try {
    let base = args.base;
    if (!base) {
      await ensureWebDeps(webDir);
      const port = await freePort();
      vite = startVite(webDir, port);
      base = await vite.ready;
      console.log(`App at ${base}`);
    }
    const gitInfo = await gitIdentity(dirname(webDir));
    engineSession = await prepareEngine(args, dirname(webDir));
    console.log(engineSession.note);
    if (args.stills) {
      await captureDeckStills({ args, outDir, base, webDir, gitInfo, engineSession, sync });
      return;
    }
    await ensurePlaywrightFfmpeg();

    const browser = await chromium.launch({
      executablePath: chromePath(),
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    });
    try {
      const context = await browser.newContext({
        viewport: { width: 1440, height: 900 },
        recordVideo: { dir: videoDir, size: { width: 1440, height: 900 } },
        colorScheme: "dark",
      });
      try {
        await context.grantPermissions(["clipboard-read", "clipboard-write"]);
        const videoT0 = Date.now();
        const page = await context.newPage();
        page.setDefaultTimeout(8000);
        const pageErrors = [];
        const downloads = [];
        page.on("pageerror", (error) => pageErrors.push(error.message));
        page.on("download", (download) => downloads.push(download.suggestedFilename()));
        await blockTraffic(page, { offline: args.offline });
        await page.goto(`${base.replace(/\/$/, "")}/?reset`, { waitUntil: "domcontentloaded", timeout: 30000 });
        await h1Ready(page);
        await page.evaluate(() => document.fonts?.ready);
        const paintMs = Date.now() - videoT0;
        await page.waitForTimeout(1200);
        const results = await runWalkthrough(page, {
          holdMs: args.holdMs,
          framesDir,
          repoRoot: args.branch ? dirname(webDir) : repoRoot,
          webRoot: webDir,
        });
        const video = page.video();
        await context.close();
        const webm = await video.path();
        const media = await convertMp4(webm, mp4, Math.max(0, (paintMs - 120) / 1000));
        rmSync(videoDir, { recursive: true, force: true });
        const log = {
          recordedAt: new Date().toISOString(),
          webDir: loggedWebDir(webDir),
          git: { ...gitInfo, requestedBranch: args.branch },
          baseUrl: base,
          networkMode: engineSession.networkMode,
          engineState: engineSession.engineState,
          engine: engineSession.note,
          scriptSync: sync,
          media,
          mp4,
          pageErrors,
          downloads,
          steps: results,
        };
        const logPath = join(outDir, "record-log.json");
        writeFileSync(logPath, `${JSON.stringify(log, null, 2)}\n`);
        printReport(results);
        console.log(`\nmp4 ${mp4} (${media.duration.toFixed(1)}s, ${media.width}x${media.height} ${media.codec})`);
        console.log(`log ${logPath}`);
        const draftNoted = results.some((step) => (step.notes || []).some((note) => note.startsWith("Draft PDF download started")));
        if (downloads.length && !draftNoted) {
          throw new Error(`A file was downloaded (${downloads.join(", ")}). The recorder does not save a PDF except the shot 7 draft.`);
        }
        const missing = results.filter((step) => step.status !== "recorded");
        if (!results.some((step) => step.status === "recorded")) {
          console.log("No script shot was recorded. The mp4 is the opening screen.");
        }
        if (args.strict && missing.length) {
          const detail = missing.map((step) => `${step.id} ${step.title}`).join("; ");
          throw new Error(`--strict: ${missing.length} shot(s) missing: ${detail}`);
        }
      } finally {
        await context.close().catch(() => {});
      }
    } finally {
      await browser.close().catch(() => {});
    }
  } finally {
    stopChild(vite?.child);
    stopChild(engineSession?.child);
    await cleanup();
  }
}

async function h1Ready(page) {
  await page.getByRole("heading", { level: 1 }).first().waitFor({ timeout: 15000 });
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
