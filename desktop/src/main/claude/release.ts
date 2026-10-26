/**
 * The one Claude Code release the managed Claude connection runs. Sizes and digests come from
 * https://downloads.claude.ai/claude-code-releases/2.1.309/manifest.json; the download is the executable.
 */
import type { RuntimePin } from "../runtime-install";

export const CLAUDE_VERSION = "2.1.309";

const RELEASES: Readonly<Record<string, { bytes: number; sha256: string }>> = {
  "darwin-arm64": { bytes: 275923296, sha256: "5eadc0009cdcdbc0d06e58110d7b2baf88ced6088b1c33a60a21217fe410619c" },
  "darwin-x64": { bytes: 287157296, sha256: "200e0d775ae55c040db3bb8db8de3e22efcddbd7e0abff5ab50dd10f6853425d" },
  "win32-x64": { bytes: 298624160, sha256: "5441781f2b6bbd07354b4a74560ee88c68c9bf05d6db3c7e24c452c91673dc53" },
  "win32-arm64": { bytes: 282697888, sha256: "063f45f61dca573b76e378f06728dc4e8f1b8600905dbd19be6d210f8c882501" },
};

export function claudePin(platform: NodeJS.Platform, arch: string): RuntimePin | null {
  const key = `${platform}-${arch}`;
  const release = Object.hasOwn(RELEASES, key) ? RELEASES[key] : undefined;
  if (!release) return null;
  const executable = platform === "win32" ? "claude.exe" : "claude";
  return {
    version: CLAUDE_VERSION, key,
    url: `https://downloads.claude.ai/claude-code-releases/${CLAUDE_VERSION}/${key}/${executable}`,
    download: { asset: executable, bytes: release.bytes, sha256: release.sha256, member: null },
    executable, executables: [release.sha256],
  };
}
