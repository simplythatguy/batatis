/** Parent-reviewed saved no-auth macOS request-boundary evidence, not authentication or inference. */
export const REVIEWED_MAC_CONTEXT = Object.freeze({
  evidence: "desktop/trusted-context macOS local-demo request-boundary; native manifest SHA-256 552f9b2ccbf9a9edd61122b75c7876e0ae18a388c14032eae265fbe21066fcdb; desktop-codex-build-20261025/adapter/parent-native-binding.json",
  runtimeSha256: "d8990e3ee7acfbc26f91265b12a1a83f0fee40d0e0f8f1f40a37d4ec21f499cf",
  contextFingerprint: "6f3aa205db02c55e79cb120090c99d17ae33db696fb306f3470e220ec61ef708",
});

/** A platform needs its own reviewed native record. Runtime hash validation remains in the adapter. */
export function reviewedContextForPlatform(platform: NodeJS.Platform) {
  return platform === "darwin" ? REVIEWED_MAC_CONTEXT : undefined;
}
