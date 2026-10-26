import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { chmod, copyFile, mkdir, mkdtemp, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { CATALOG, CODEX_ARCHIVES, CODEX_SOURCE_COMMIT, CODEX_VERSION, archiveUrl } from "../src/main/codex/release.ts";

const ROOT = dirname(fileURLToPath(import.meta.url));

export async function fileHash(path) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest("hex");
}

export function deriveCatalog(bytes) {
  if (bytes.length !== CATALOG.source.bytes || createHash("sha256").update(bytes).digest("hex") !== CATALOG.source.sha256)
    throw new Error("Catalog source digest mismatch");
  let candidate = bytes;
  for (const edit of [...CATALOG.edits].reverse()) {
    const old = bytes.subarray(edit.start, edit.end).toString("utf8");
    if (edit.old === null ? JSON.stringify(JSON.parse(old)) !== '["send_user_message_async","clock"]' : old !== edit.old)
      throw new Error("Catalog source span mismatch");
    candidate = Buffer.concat([candidate.subarray(0, edit.start), Buffer.from(edit.value), candidate.subarray(edit.end)]);
  }
  if (candidate.length !== CATALOG.bytes || createHash("sha256").update(candidate).digest("hex") !== CATALOG.sha256)
    throw new Error("Candidate catalog digest mismatch");
  const parsed = JSON.parse(candidate);
  if (parsed.models.length !== 11 || parsed.models[3].slug !== "gpt-6-luna") throw new Error("Catalog identity mismatch");
  return candidate;
}

async function download(url, path, limit) {
  const response = await fetch(url, { signal: AbortSignal.timeout(180_000) });
  if (!response.ok || !response.body) throw new Error("Official source download failed");
  const chunks = [];
  let size = 0;
  for await (const chunk of response.body) {
    size += chunk.length;
    if (size > limit) throw new Error("Official source exceeds size limit");
    chunks.push(chunk);
  }
  await writeFile(path, Buffer.concat(chunks), { flag: "wx", mode: 0o600 });
}

function tarExecutable() {
  if (process.platform !== "win32") return "/usr/bin/tar";
  const root = process.env.SystemRoot;
  if (!root || !isAbsolute(root)) throw new Error("Windows SystemRoot is unavailable");
  return join(root, "System32", "tar.exe");
}

export async function installRuntime(platform, archivePath, destination) {
  if (!Object.hasOwn(CODEX_ARCHIVES, platform)) throw new Error("Unsupported runtime target");
  const pin = CODEX_ARCHIVES[platform];
  const archive = resolve(archivePath);
  const info = await stat(archive);
  if (!info.isFile() || info.size !== pin.bytes || await fileHash(archive) !== pin.sha256)
    throw new Error("Runtime archive digest mismatch");
  const temp = await mkdtemp(join(tmpdir(), "batatis-codex-extract-"));
  try {
    const options = { shell: false, windowsHide: true, encoding: "utf8", timeout: 120_000, maxBuffer: 1024 * 1024 };
    const listing = spawnSync(tarExecutable(), ["-tf", archive], options);
    if (listing.error || listing.status !== 0) throw new Error("Cannot list verified archive with system tar");
    const members = listing.stdout.trim().split(/\r?\n/);
    if (!members.includes(pin.member) || members.some((name) => name.startsWith("/") || name.split(/[\\/]/).includes("..")))
      throw new Error("Runtime archive member mismatch");
    const extract = spawnSync(tarExecutable(), ["-xf", archive, "-C", temp, pin.member], options);
    if (extract.error || extract.status !== 0) throw new Error("Cannot extract verified archive with system tar");
    const extracted = join(temp, pin.member);
    if (!(await stat(extracted)).isFile()) throw new Error("Runtime member is not a file");
    const executableSha256 = await fileHash(extracted);
    await mkdir(destination, { recursive: true });
    const staged = join(destination, `${pin.executable}.partial`);
    await copyFile(extracted, staged);
    await chmod(staged, 0o755);
    await rename(staged, join(destination, pin.executable));
    const manifest = { version: CODEX_VERSION, platform, archiveSha256: pin.sha256, executableSha256 };
    await writeFile(join(destination, "codex-runtime.json"), JSON.stringify(manifest, null, 2) + "\n");
    return manifest;
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
}

async function main(args) {
  const [command, target, localArchive] = args;
  if (command === "catalog") {
    const temp = await mkdtemp(join(tmpdir(), "batatis-codex-catalog-"));
    try {
      const source = join(temp, "models.json");
      if (target) await copyFile(resolve(target), source);
      else await download(CATALOG.source.url, source, CATALOG.source.bytes);
      await writeFile(join(ROOT, CATALOG.file), deriveCatalog(await readFile(source)));
    } finally { await rm(temp, { recursive: true, force: true }); }
    process.stdout.write(`Verified ${CATALOG.file} ${CATALOG.sha256}\n`);
  } else if (command === "runtime" && Object.hasOwn(CODEX_ARCHIVES, target)) {
    const temp = await mkdtemp(join(tmpdir(), "batatis-codex-download-"));
    try {
      const archive = localArchive ? resolve(localArchive) : join(temp, CODEX_ARCHIVES[target].asset);
      if (!localArchive) await download(archiveUrl(target), archive, CODEX_ARCHIVES[target].bytes);
      const manifest = await installRuntime(target, archive, join(ROOT, "runtime", target));
      process.stdout.write(JSON.stringify(manifest) + "\n");
    } finally { await rm(temp, { recursive: true, force: true }); }
  } else if (command === "notices") {
    for (const name of ["LICENSE", "NOTICE"]) {
      const path = join(ROOT, `${name}.partial`);
      await rm(path, { force: true });
      await download(`https://raw.githubusercontent.com/openai/codex/${CODEX_SOURCE_COMMIT}/${name}`, path, 100_000);
      await rename(path, join(ROOT, name));
    }
    process.stdout.write("Downloaded pinned upstream license and notice\n");
  } else throw new Error("Usage: node codex/fetch.mjs catalog [pinned-source] | runtime <darwin-arm64|win32-x64> [archive] | notices");
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.message : "Fetch failed"}\n`);
    process.exitCode = 1;
  });
}
