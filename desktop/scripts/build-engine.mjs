/**
 * Build the frozen engine (PyInstaller, one directory) into build/engine-dist/batatis-engine.
 * It must run on the target OS: a macOS build cannot produce the Windows engine.
 * BATATIS_BUILD_PYTHON picks the interpreter for the build venv (default python3, or python on Windows).
 */
import { spawnSync } from "node:child_process";
import { existsSync, renameSync } from "node:fs";
import { join } from "node:path";

const windows = process.platform === "win32";
const venv = join("build", "engine-venv");
const python = windows ? join(venv, "Scripts", "python.exe") : join(venv, "bin", "python");
const base = process.env.BATATIS_BUILD_PYTHON ?? (windows ? "python" : "python3");

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (!existsSync(python)) run(base, ["-m", "venv", venv]);
const pip = [python, "-m", "pip", "install", "--disable-pip-version-check", "-q", "--only-binary", ":all:"];
run(pip[0], [...pip.slice(1), "--no-deps", "-r", "engine-requirements.txt"]);
run(pip[0], [...pip.slice(1), "pyinstaller==6.22.3"]);
const stamp = `${Date.now()}-${process.pid}`;
const candidate = join("build", `engine-dist-${stamp}`);
run(python, ["-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
  "--distpath", candidate, "--workpath", join("build", `engine-work-${stamp}`), "engine.spec"]);
const active = join("build", "engine-dist");
if (existsSync(active)) renameSync(active, join("build", `engine-dist-before-${stamp}`));
renameSync(candidate, active);
