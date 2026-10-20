/**
 * Boot the Vite app in web/ and record a walkthrough.
 *
 *   ./scripts/record-demo.sh
 *   ./scripts/record-demo.sh --branch cursor/e2e-product-flow-4362
 *
 * No model API key is read or sent. The app's fixture, example, and offline
 * paths are what the camera sees. If an engine is already on 127.0.0.1:8000,
 * Vite proxies /api to it; this script does not start one.
 */
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { mkdirSync, writeFileSync, existsSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import { STEPS, runWalkthrough } from "./steps.mjs";
import { diffScript } from "./sync.mjs";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

function parseArgs(argv) {
  const out = {
    checkScript: false,
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
  return out;
}

const HELP = `Record a Batatis walkthrough mp4.

  ./scripts/record-demo.sh
  ./scripts/record-demo.sh --branch <git-ref>
  ./scripts/record-demo.sh --web <path-to-web>
  ./scripts/record-demo.sh --check-script

Options
  --out <dir>       Output directory (default artifacts/demo)
  --hold <ms>       Pause on each recorded shot (default 1600)
  --base <url>      Record an app that is already running
  --script <file>   Shot list to diff (default docs/demo/script.md)
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
    const found = readdirSync(cache).some((name) => name.startsWith("ffmpeg-") && existsSync(join(cache, name, "ffmpeg-linux")));
    if (found) return;
  }
  const require = createRequire(import.meta.url);
  const pkg = dirname(require.resolve("playwright-core/package.json"));
  console.log("Downloading Playwright's ffmpeg (video mux only; no browser download).");
  await run(process.execPath, [join(pkg, "cli.js"), "install", "ffmpeg"]);
}

function chromePath() {
  if (process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  for (const path of ["/usr/bin/google-chrome-stable", "/usr/bin/google-chrome", "/usr/local/bin/google-chrome"]) {
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
  const localRef = `refs/batatis-record/${safe}`;
  const dir = join("/tmp", `batatis-record-${safe}`);
  await run("git", ["update-ref", "-d", localRef], { cwd: repoRoot }).catch(() => {});
  await run("git", ["fetch", "origin", `${ref}:${localRef}`], { cwd: repoRoot }).catch(async (error) => {
    throw new Error(`Could not fetch ${ref}. ${error.message}`);
  });
  await run("git", ["worktree", "remove", "--force", dir], { cwd: repoRoot }).catch(() => {});
  await run("git", ["worktree", "add", "--detach", dir, localRef], { cwd: repoRoot });
  return {
    dir,
    async cleanup() {
      await run("git", ["worktree", "remove", "--force", dir], { cwd: repoRoot }).catch(() => {});
      await run("git", ["update-ref", "-d", localRef], { cwd: repoRoot }).catch(() => {});
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

async function engineNote() {
  try {
    const res = await fetch("http://127.0.0.1:8000/openapi.json", { signal: AbortSignal.timeout(600) });
    return res.ok
      ? "An engine is already listening on 127.0.0.1:8000. The recorder did not start it and did not send an API key."
      : `Port 8000 responded ${res.status}. The recorder did not start an engine.`;
  } catch {
    return "No engine is listening on 127.0.0.1:8000. The recording uses the app's fixture, example, and offline paths.";
  }
}

function scriptReport(scriptPath) {
  if (!existsSync(scriptPath)) {
    return {
      status: "absent",
      path: scriptPath,
      problems: [],
      note: "docs/demo/script.md is not on this branch. Step ids still follow that shot list, and --check-script will diff them once the file is present.",
    };
  }
  const diff = diffScript(STEPS, readFileSync(scriptPath, "utf8"));
  return {
    status: diff.problems.length ? "drift" : "ok",
    path: scriptPath,
    problems: diff.problems,
    note: diff.problems.length ? "The recorder steps and the shot list disagree." : "Recorder steps match the shot list.",
  };
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
    console.log(`  skipped   ${step.id}  ${step.title}`);
    console.log(`            ${step.reason}`);
  }
}

async function convertMp4(webm, mp4) {
  await run("ffmpeg", [
    "-y",
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
  ]);
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(HELP);
    return;
  }
  const scriptPath = resolve(args.script || join(repoRoot, "docs/demo/script.md"));
  const sync = scriptReport(scriptPath);
  console.log(sync.note);
  for (const problem of sync.problems) console.log(`  ${problem}`);
  if (args.checkScript && !args.branch && !args.web && !args.base && !args.out) {
    if (sync.status === "drift") process.exitCode = 1;
    return;
  }
  if (sync.status === "drift") console.log("Recording anyway. Fix the shot list or the step catalog, then re-run --check-script.");

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

  const outDir = resolve(args.out || join(repoRoot, "artifacts/demo"));
  const framesDir = join(outDir, "frames");
  const videoDir = join(outDir, ".video");
  mkdirSync(framesDir, { recursive: true });
  mkdirSync(videoDir, { recursive: true });
  const mp4 = join(outDir, "batatis-demo.mp4");
  let vite;

  try {
    let base = args.base;
    if (!base) {
      await ensureWebDeps(webDir);
      const port = await freePort();
      vite = startVite(webDir, port);
      base = await vite.ready;
      console.log(`App at ${base}`);
    }
    const sha = await git(["rev-parse", "HEAD"], webDir).catch(() => "");
    const branchName = await git(["rev-parse", "--abbrev-ref", "HEAD"], webDir).catch(() => "");
    const engine = await engineNote();
    console.log(engine);
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
        const page = await context.newPage();
        page.setDefaultTimeout(8000);
        const pageErrors = [];
        page.on("pageerror", (error) => pageErrors.push(error.message));
        await page.goto(`${base.replace(/\/$/, "")}/?reset`, { waitUntil: "domcontentloaded", timeout: 30000 });
        await h1Ready(page);
        await page.evaluate(() => document.fonts?.ready);
        const results = await runWalkthrough(page, {
          holdMs: args.holdMs,
          framesDir,
          repoRoot: args.branch ? dirname(webDir) : repoRoot,
          webRoot: webDir,
        });
        const video = page.video();
        await context.close();
        const webm = await video.path();
        const media = await convertMp4(webm, mp4);
        rmSync(videoDir, { recursive: true, force: true });
        const log = {
          recordedAt: new Date().toISOString(),
          webDir,
          git: { sha, branch: branchName, requestedBranch: args.branch },
          baseUrl: base,
          engine,
          scriptSync: sync,
          media,
          mp4,
          pageErrors,
          steps: results,
        };
        const logPath = join(outDir, "record-log.json");
        writeFileSync(logPath, `${JSON.stringify(log, null, 2)}\n`);
        printReport(results);
        console.log(`\nmp4 ${mp4} (${media.duration.toFixed(1)}s, ${media.width}x${media.height} ${media.codec})`);
        console.log(`log ${logPath}`);
        if (!results.some((step) => step.status === "recorded")) {
          throw new Error("No shot was recorded.");
        }
      } finally {
        await context.close().catch(() => {});
      }
    } finally {
      await browser.close().catch(() => {});
    }
  } finally {
    stopChild(vite?.child);
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
