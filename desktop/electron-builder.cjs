const { existsSync } = require("node:fs");
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

/**
 * macOS Developer ID signing and notarization, when the Apple account is configured: CSC_LINK and
 * CSC_KEY_PASSWORD carry the Developer ID Application certificate, and APPLE_API_KEY (a .p8 file's
 * path), APPLE_API_KEY_ID and APPLE_API_ISSUER the App Store Connect key that notarizes. Ad hoc otherwise,
 * and macOS then blocks a downloaded copy until it is allowed in Privacy & Security.
 */
// An empty CSC_LINK, as CI sets for an unset secret, would make electron-builder read the working
// directory as the certificate; drop it so the build stays ad hoc.
if (process.env.CSC_LINK === "") delete process.env.CSC_LINK;
const macSigning = Boolean(process.env.CSC_LINK);
const MAC_NEEDS = ["CSC_KEY_PASSWORD", "APPLE_API_KEY", "APPLE_API_KEY_ID", "APPLE_API_ISSUER"];
if (macSigning && MAC_NEEDS.some((name) => !process.env[name])) {
  throw new Error(`macOS signing needs CSC_LINK, ${MAC_NEEDS.join(", ")}.`);
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
    // Built by `python -m codedb build`; the app copies it into its own data on launch (src/main/codedb.ts).
    ...(existsSync(join(__dirname, "../codedb/build/codedb.sqlite")) ? [{ from: "../codedb/build/codedb.sqlite", to: "codedb/codedb.sqlite" }] : []),
  ],
  electronFuses: {
    runAsNode: false,
    enableNodeOptionsEnvironmentVariable: false,
    enableNodeCliInspectArguments: false,
    enableEmbeddedAsarIntegrityValidation: true,
    onlyLoadAppFromAsar: true,
    grantFileProtocolExtraPrivileges: false,
  },
  mac: macSigning ? {
    icon: "assets/icon-mac.png",
    target: ["zip", "dmg"], category: "public.app-category.productivity",
    hardenedRuntime: true, notarize: true,
    entitlements: "assets/entitlements.mac.plist", entitlementsInherit: "assets/entitlements.mac.plist",
  } : {
    icon: "assets/icon-mac.png",
    target: ["zip", "dmg"], category: "public.app-category.productivity", identity: "-", hardenedRuntime: false, notarize: false,
  },
  win: windowsSigning ? {
    icon: "assets/icon-win.png",
    // The zip feeds the in-app updater; the installer is what people download and run.
    target: [{ target: "zip", arch: ["x64"] }, { target: "nsis", arch: ["x64"] }],
    azureSignOptions: windowsSigning,
    // The engine's libraries are signed too.
    signExts: [".dll", ".pyd"],
  } : { icon: "assets/icon-win.png", target: [{ target: "zip", arch: ["x64"] }, { target: "nsis", arch: ["x64"] }], signExecutable: false },
  nsis: { oneClick: true, perMachine: false, deleteAppDataOnUninstall: false, createDesktopShortcut: true },
};
