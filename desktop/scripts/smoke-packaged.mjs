import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const [input, destination] = process.argv.slice(2);
if (!input || !destination) throw new Error("Usage: npm run smoke:packaged -- <Batatis.app|win-unpacked> <prepared-output-dir>");
const output = resolve(destination);
assert.ok(existsSync(join(output, "scenario.json")), "prepare-smoke.py must prepare disposable data first");
const source = resolve(input);
const staged = join(output, "Application composée 100% #", process.platform === "darwin" ? "Batatis.app" : "Batatis");
assert.ok(!existsSync(staged), "use a new output directory for each packaged acceptance run");
mkdirSync(dirname(staged), { recursive: true });
cpSync(source, staged, { recursive: true, verbatimSymlinks: true });
const executable = process.platform === "darwin" ? join(staged, "Contents", "MacOS", "Batatis") : join(staged, "Batatis.exe");
assert.ok(existsSync(executable), "the native packaged executable exists");
// The app installs its pinned Codex runtime into app data on first use; seed the same verified bytes.
const runtimeKey = `${process.platform}-${process.arch}`;
const fetchedRuntime = join(dirname(fileURLToPath(import.meta.url)), "..", "codex", "runtime", runtimeKey);
assert.ok(existsSync(fetchedRuntime), "node codex/fetch.mjs runtime prepared the pinned Codex executable");
cpSync(fetchedRuntime, join(output, "workspace données 100% #", "codex", "runtime", runtimeKey), { recursive: true });

const env = {};
const allowed = ["SystemRoot", "SYSTEMROOT", "WINDIR", "windir", "SystemDrive", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL", "DISPLAY", "XAUTHORITY"];
for (const name of allowed) if (process.env[name]) env[name] = process.env[name];
env.PATH = process.platform === "win32" ? join(env.SystemRoot ?? env.SYSTEMROOT ?? "C:\\Windows", "System32") : "/usr/bin:/bin";
env.BATATIS_DESKTOP_SMOKE_DIR = output;

async function launch(stage) {
  const child = spawn(executable, ["--batatis-smoke-test"], {
    cwd: dirname(executable), env: { ...env, BATATIS_DESKTOP_SMOKE_STAGE: String(stage) },
    stdio: ["ignore", "pipe", "pipe"], windowsHide: false, shell: false,
  });
  const logs = [];
  child.stdout.on("data", (data) => logs.push(data));
  child.stderr.on("data", (data) => logs.push(data));
  const timer = setTimeout(() => child.kill("SIGKILL"), 240_000);
  const code = await new Promise((done, fail) => { child.once("error", fail); child.once("exit", done); });
  clearTimeout(timer);
  writeFileSync(join(output, `launch-${stage}.log`), Buffer.concat(logs));
  const reportFile = join(output, `report-${stage}.json`);
  assert.ok(existsSync(reportFile), `packaged app wrote stage ${stage} report, exit ${code}`);
  const report = JSON.parse(readFileSync(reportFile, "utf8"));
  assert.equal(report.packaged, true, "the test exercised a packaged app");
  assert.equal(code, 0, JSON.stringify(report, null, 2));
  assert.equal(report.ok, true, JSON.stringify(report, null, 2));
  assert.equal(report.csp.length, 0, "no content security policy violations");
  assert.equal(report.errors.length, 0, "no renderer errors");
  for (const pid of report.enginePids) {
    let alive = false;
    try { process.kill(pid, 0); alive = true; } catch (error) { if (error.code !== "ESRCH") throw error; }
    assert.equal(alive, false, `owned engine ${pid} stopped after quit`);
  }
  return report;
}

const reports = [await launch(1), await launch(2)];
assert.equal(reports[0].applicantId, reports[1].applicantId, "the seeded principal persists across app launches");
const screenshots = readdirSync(output).filter((name) => name.endsWith(".png"));
assert.ok(screenshots.length >= 5, "native windows were captured");
writeFileSync(join(output, "acceptance.json"), JSON.stringify({ ok: true, executable, screenshots, stages: reports.map((r) => ({ steps: r.steps, enginePids: r.enginePids })) }, null, 2));
process.stdout.write(`Packaged acceptance passed on ${process.platform}-${process.arch}. Reports and ${screenshots.length} screenshots are in ${output}.\n`);
