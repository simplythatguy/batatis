const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
const { existsSync, readFileSync, readdirSync, writeFileSync } = require("node:fs");
const { join, relative } = require("node:path");
const { listPackage } = require("@electron/asar");

function files(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const file = join(root, entry.name);
    return entry.isDirectory() ? files(file) : entry.isFile() ? [file] : [];
  });
}

function audit(resources, platform) {
  const archive = join(resources, "app.asar");
  const packaged = [
    ...listPackage(archive, { isPack: false }).map((name) => `app.asar${name.replaceAll("\\", "/")}`),
    ...files(resources).filter((name) => name !== archive).map((name) => relative(resources, name).replaceAll("\\", "/")),
  ];
  const forbidden = packaged.filter((name) => /(?:^|\/)(?:\.env(?:\..*)?|Data Prompts|reference|evals|evals_dev|research|cases\.sqlite|codedb\.sqlite|auth\.json|config\.toml|providers)(?:\/|$)/i.test(name)
    || /\.(?:sqlite(?:3)?|sqlite-wal|sqlite-shm|key)$/i.test(name)
    || /NBC-AE-2023-2nd-printing-FULL|NBC-2020-Intent-Statements/i.test(name));
  assert.deepEqual(forbidden, [], "no workspaces, CodeDB, copyrighted source documents, corpus, credentials or environment files ship");
  const engine = join(resources, "engine", platform === "win32" ? "batatis-engine.exe" : "batatis-engine");
  assert.ok(existsSync(engine), "native frozen engine is bundled");
  assert.ok(existsSync(join(resources, "web", "index.html")), "the canonical web build is bundled");
  assert.ok(packaged.some((name) => /(?:lib)?pdfium\.(?:dll|dylib|so)$/.test(name)), "PDFium native library is bundled");
  assert.ok(packaged.some((name) => /reportlab\/fonts\/Vera\.ttf$/.test(name)), "PDF fonts are bundled");
  assert.ok(packaged.some((name) => /certifi\/cacert\.pem$/.test(name)), "TLS roots are bundled");
  assert.ok(packaged.some((name) => /cryptography\/.+\.(?:so|pyd)$/.test(name)), "native cryptography is bundled");
  const sha256 = (file) => createHash("sha256").update(readFileSync(file)).digest("hex");
  assert.ok(!existsSync(join(resources, "codex", platform === "win32" ? "codex.exe" : "codex")), "the Codex runtime is installed on first use, not bundled");
  for (const name of ["luna-models.json", "LICENSE", "NOTICE"]) assert.ok(existsSync(join(resources, "codex", name)), `Codex ${name} is bundled`);
  const codex = { catalogSha256: sha256(join(resources, "codex", "luna-models.json")) };
  return { ok: true, platform, files: packaged.length, engineSha256: sha256(engine), appAsarSha256: sha256(archive), codex, forbidden };
}

module.exports = { audit };

if (require.main === module) {
  const report = audit(process.argv[2], process.platform);
  if (process.argv[3]) writeFileSync(process.argv[3], JSON.stringify(report, null, 2));
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
}
