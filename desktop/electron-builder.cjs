const { join } = require("node:path");

/**
 * Windows code signing through Microsoft Artifact Signing, when its account is configured. The
 * certificate details come from BATATIS_SIGN_*; the AZURE_TENANT_ID, AZURE_CLIENT_ID and
 * AZURE_CLIENT_SECRET credentials are read by the signing module itself. Unsigned otherwise.
 */
const windowsSigning = process.env.BATATIS_SIGN_ENDPOINT ? {
  publisherName: process.env.BATATIS_SIGN_PUBLISHER,
  endpoint: process.env.BATATIS_SIGN_ENDPOINT,
  codeSigningAccountName: process.env.BATATIS_SIGN_ACCOUNT,
  certificateProfileName: process.env.BATATIS_SIGN_PROFILE,
} : null;
if (windowsSigning && Object.values(windowsSigning).some((value) => !value)) {
  throw new Error("Windows signing needs BATATIS_SIGN_PUBLISHER, BATATIS_SIGN_ENDPOINT, BATATIS_SIGN_ACCOUNT and BATATIS_SIGN_PROFILE.");
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
    // The Codex runtime itself is downloaded on first use (src/main/codex/install.ts); only its reviewed catalog ships.
    { from: "codex", to: "codex", filter: ["luna-models.json", "LICENSE", "NOTICE"] },
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
  },
  win: windowsSigning ? {
    target: [{ target: "zip", arch: ["x64"] }],
    azureSignOptions: windowsSigning,
    // The engine's libraries are signed too.
    signExts: [".dll", ".pyd"],
  } : { target: [{ target: "zip", arch: ["x64"] }], signAndEditExecutable: false },
};
