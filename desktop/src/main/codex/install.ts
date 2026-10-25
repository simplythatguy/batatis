/** The Codex release the installer downloads: the archive and executable digests pinned in release.ts. */
import type { RuntimePin } from "../runtime-install";
import { archiveUrl, CODEX_ARCHIVES, CODEX_VERSION, KNOWN_EXECUTABLE_SHA256, platformKey } from "./release";

export function codexPin(platform: NodeJS.Platform, arch: string): RuntimePin | null {
  const key = platformKey(platform, arch);
  const executables = key ? KNOWN_EXECUTABLE_SHA256[key] : undefined;
  if (!key || !executables?.length) return null;
  const { asset, bytes, sha256, member, executable } = CODEX_ARCHIVES[key];
  return { version: CODEX_VERSION, key, url: archiveUrl(key), download: { asset, bytes, sha256, member }, executable, executables };
}
