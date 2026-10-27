/**
 * The one OpenCode release the managed OpenCode connection runs. Sizes and digests come from the GitHub
 * release metadata for v2.2.0; the download is a zip holding the executable.
 */
import type { RuntimePin } from "../runtime-install";

export const OPENCODE_VERSION = "2.2.0";

const RELEASES: Readonly<Record<string, { asset: string; bytes: number; sha256: string; executable: string }>> = {
  "darwin-arm64": { asset: "opencode-darwin-arm64.zip", bytes: 102507526, sha256: "c71b1cd96541539ad38e2a75377d2f43d2a27567289a14371a182e9a0800db3d", executable: "0614b30fd17c27258b16cd6ea9ab03e1160fa9897e4cefd2d9a5d86f71a0af11" },
  "darwin-x64": { asset: "opencode-darwin-x64.zip", bytes: 107678260, sha256: "cc191a1cec9b9cd0192d78dc066bbf48730639131422fa54c87c485a821ba1d5", executable: "bb918cf6ae44a0d7fb265e16b6b7ce329cb4cbf30c881054dda383308b417806" },
  "win32-x64": { asset: "opencode-windows-x64.zip", bytes: 118610002, sha256: "a56307bdccdafd3fc5255556f3bf867703ea56dbeffaf00add4e9663edb3b974", executable: "dcb54dc811ac30a9107f2e704b2cf1ac29d52971d288499f0a2c7420e1504a48" },
  "win32-arm64": { asset: "opencode-windows-arm64.zip", bytes: 112077419, sha256: "bceb8b16e4889b7766793e1e7b51e3ab97ad41e09367a5bf192c15c0334b848a", executable: "de0833e526a8a251e289f57a22f7cc27e9026897028e0214e33535cb35cf1bd3" },
};

export function opencodePin(platform: NodeJS.Platform, arch: string): RuntimePin | null {
  const key = `${platform}-${arch}`;
  const release = Object.hasOwn(RELEASES, key) ? RELEASES[key] : undefined;
  if (!release) return null;
  const executable = platform === "win32" ? "opencode.exe" : "opencode";
  return {
    version: OPENCODE_VERSION, key,
    url: `https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/${release.asset}`,
    download: { asset: release.asset, bytes: release.bytes, sha256: release.sha256, member: executable },
    executable, executables: [release.executable],
  };
}
