/**
 * The one Codex release this adapter runs, and the reviewed model catalog it runs with.
 * Digests come from the GitHub release metadata for rust-v0.164.0 and from the catalog proof.
 * No import here: codex/fetch.mjs loads this file directly.
 */

export const CODEX_VERSION = "0.164.0";
export const CODEX_TAG = "rust-v0.164.0";
export const CODEX_SOURCE_COMMIT = "6aaac694803004a63c6f393d153c96d22521a6b9";

export type PlatformKey = "darwin-arm64" | "darwin-x64" | "win32-arm64" | "win32-x64";

export interface ReleaseArchive {
  readonly asset: string;
  readonly bytes: number;
  readonly sha256: string;
  /** The single executable inside the archive. */
  readonly member: string;
  /** Its name once installed under codex/runtime/<platform>/. */
  readonly executable: "codex" | "codex.exe";
}

const download = (asset: string) => `https://github.com/openai/codex/releases/download/${CODEX_TAG}/${asset}`;

export const CODEX_ARCHIVES: Readonly<Record<PlatformKey, ReleaseArchive>> = {
  "darwin-arm64": {
    asset: "codex-aarch64-apple-darwin.tar.gz",
    bytes: 101767166,
    sha256: "aa8299c169d80111aac05543ad2621c9bdbedb9bc252c905fe3f5a5baf9a4142",
    member: "codex-aarch64-apple-darwin",
    executable: "codex",
  },
  "darwin-x64": {
    asset: "codex-x86_64-apple-darwin.tar.gz",
    bytes: 110491441,
    sha256: "de6bbc013c56337f6ddd3f26dfbfd62aad5924cb68cd5ef6430538922bfa0e75",
    member: "codex-x86_64-apple-darwin",
    executable: "codex",
  },
  "win32-arm64": {
    asset: "codex-aarch64-pc-windows-msvc.exe.zip",
    bytes: 160012951,
    sha256: "b70e039e76cba0faaed58028a88dc7a41e723b5506f6dacaf2f71336d24d1e19",
    member: "codex-aarch64-pc-windows-msvc.exe",
    executable: "codex.exe",
  },
  "win32-x64": {
    asset: "codex-x86_64-pc-windows-msvc.exe.zip",
    bytes: 172623445,
    sha256: "349827ef53a06a27c7ad9f93ad97a5ac019b0975ed7ab669f73bb0deccd7b4fa",
    member: "codex-x86_64-pc-windows-msvc.exe",
    executable: "codex.exe",
  },
};

export function archiveUrl(platform: PlatformKey): string {
  return download(CODEX_ARCHIVES[platform].asset);
}

/**
 * Executables a developer may point the adapter at directly. The macOS arm64 entry is the installed
 * standalone 0.164.0 build that the research inspected; it reports "codex-cli 0.164.0".
 */
export const KNOWN_EXECUTABLE_SHA256: Readonly<Partial<Record<PlatformKey, readonly string[]>>> = {
  "darwin-arm64": ["d8990e3ee7acfbc26f91265b12a1a83f0fee40d0e0f8f1f40a37d4ec21f499cf"],
  "win32-x64": ["6f267830b029ee25d9339864aa867cd45de9f8fd4c5ea007d2e63c13a0c66d36"],
};

/** The upstream bundled catalog at CODEX_SOURCE_COMMIT and the six reviewed edits to its gpt-6-luna entry. */
export const CATALOG = {
  file: "luna-models.json",
  sha256: "dca46de82fef92c2d3f7212467181b2d17cf8e5a3d468ade38d555280bf37fb8",
  bytes: 472002,
  source: {
    url: `https://raw.githubusercontent.com/openai/codex/${CODEX_SOURCE_COMMIT}/codex-rs/models-manager/models.json`,
    sha256: "943ca7fe1d19ed019054158303f0dbbd80b3bef43b3aa425a71aa7cb3fb52c2b",
    bytes: 472072,
  },
  /** Byte spans in the source file; each old value is checked before it is replaced. */
  edits: [
    { start: 197160, end: 197170, old: '"freeform"', value: "null" },
    { start: 197485, end: 197501, old: '"code_mode_only"', value: '"direct"' },
    { start: 197532, end: 197536, old: '"v2"', value: '"disabled"' },
    { start: 198991, end: 199006, old: '"shell_command"', value: '"disabled"' },
    { start: 258663, end: 258723, old: null, value: "[]" },
    { start: 259319, end: 259323, old: "true", value: "false" },
  ],
} as const;

export function platformKey(platform: NodeJS.Platform, arch: string): PlatformKey | null {
  const key = `${platform}-${arch}`;
  return key === "darwin-arm64" || key === "darwin-x64" || key === "win32-arm64" || key === "win32-x64" ? key : null;
}
