const { existsSync } = require("node:fs");
const { join } = require("node:path");

const runtime = join("codex", "runtime", `${process.platform}-${process.arch}`);
const hasRuntime = existsSync(join(__dirname, runtime, process.platform === "win32" ? "codex.exe" : "codex"));
if (process.env.BATATIS_DESKTOP_REQUIRE_CODEX === "1" && !hasRuntime) {
  throw new Error("The pinned Codex runtime must be prepared before packaging.");
}

async function auditBundle(context) {
  const { writeFileSync } = require("node:fs");
  const { audit } = require("./scripts/audit-package.cjs");
  const resources = context.electronPlatformName === "darwin"
    ? join(context.appOutDir, "Batatis.app", "Contents", "Resources") : join(context.appOutDir, "resources");
  writeFileSync(`${context.appOutDir}.audit.json`, JSON.stringify(audit(resources, context.electronPlatformName), null, 2));
}

module.exports = {
  appId: "ca.batatis.desktop",
  productName: "Batatis",
  directories: { output: "build/release" },
  artifactName: "Batatis-${version}-${os}-${arch}.${ext}",
  asar: true,
  files: ["dist/**/*", "package.json"],
  afterPack: auditBundle,
  afterSign: auditBundle,
  extraResources: [
    { from: "../web/dist", to: "web", filter: ["**/*", "!**/*.sqlite", "!**/*.map"] },
    { from: "build/engine-dist/batatis-engine", to: "engine", filter: ["**/*"] },
    ...(hasRuntime ? [
      { from: runtime, to: "codex", filter: ["codex", "codex.exe", "codex-runtime.json"] },
      { from: "codex", to: "codex", filter: ["luna-models.json", "LICENSE", "NOTICE"] },
    ] : []),
  ],
  electronFuses: {
    runAsNode: false,
    enableNodeOptionsEnvironmentVariable: false,
    enableNodeCliInspectArguments: false,
    enableEmbeddedAsarIntegrityValidation: true,
    onlyLoadAppFromAsar: true,
    grantFileProtocolExtraPrivileges: false,
  },
  mac: {
    target: ["zip"], category: "public.app-category.productivity", identity: "-", hardenedRuntime: false, notarize: false,
    signIgnore: ["/Contents/Resources/codex/codex$"],
  },
  win: { target: [{ target: "zip", arch: ["x64"] }], signAndEditExecutable: false },
};
