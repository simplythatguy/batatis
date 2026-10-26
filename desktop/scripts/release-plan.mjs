// Decides what the desktop workflow publishes, after T3 Code's nightly and stable releases.
//
// Beta: every merge into main builds it as a prerelease, unless the last beta already ships that
// commit; a manual beta run builds main now. A beta is
// vX.Y.Z-beta.YYYYMMDD.RUN, previewing the stable X.Y.Z: one patch after the latest stable release,
// or desktop/package.json's version when that is higher.
// Stable: a manual stable run publishes the latest beta's exact commit as vX.Y.Z, so stable only
// ships what beta users already ran.
//
// Run in GitHub Actions: node desktop/scripts/release-plan.mjs (writes build, release, channel,
// version, tag, sha, prerelease and notes_start to GITHUB_OUTPUT).
import { appendFileSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { compareVersions, parseVersion } from "../src/main/updates.ts";

const tagVersion = (tag) => (/^v(.+)$/.exec(tag)?.[1] ?? null);

/** Published desktop releases, parsed; anything else on the releases page is ignored. */
export function desktopReleases(list) {
  return list.flatMap((item) => {
    const version = item && !item.draft && item.published_at ? tagVersion(item.tag_name) : null;
    const parsed = version ? parseVersion(version) : null;
    return parsed && Boolean(parsed.beta) === Boolean(item.prerelease) ? [{ tag: item.tag_name, version, parsed, published: Date.parse(item.published_at) }] : [];
  });
}

export function betaTarget(packageVersion, latestStable) {
  const fromPackage = parseVersion(packageVersion);
  if (!fromPackage || fromPackage.beta) throw new Error(`desktop/package.json version ${packageVersion} must be X.Y.Z.`);
  if (!latestStable) return packageVersion;
  const [major, minor, patch] = latestStable.parsed.core;
  const next = `${major}.${minor}.${patch + 1}`;
  return compareVersions(parseVersion(next), fromPackage) > 0 ? next : packageVersion;
}

/**
 * @param input.event push | workflow_dispatch
 * @param input.channel beta | stable (workflow_dispatch only)
 * @param input.compare (base, head) => Promise<"ahead" | "identical" | "behind" | "diverged">
 * @param input.commitOf (tag) => Promise<sha>
 */
export async function planRelease({ event, channel, ref, sha, now, date, run, packageVersion, releases, compare, commitOf }) {
  const chosen = event === "push" ? "beta" : channel;
  if (chosen !== "beta" && chosen !== "stable") throw new Error(`Unknown release channel: ${channel}`);
  if (ref !== "refs/heads/main") throw new Error(`Releases are built from main; this run is on ${ref}.`);
  const parsed = desktopReleases(releases);
  const latest = (items) => items.sort((a, b) => compareVersions(b.parsed, a.parsed))[0] ?? null;
  const latestStable = latest(parsed.filter((item) => !item.parsed.beta));
  const latestBeta = latest(parsed.filter((item) => item.parsed.beta));

  if (chosen === "beta") {
    if (event === "push" && latestBeta) {
      const status = await compare(latestBeta.tag, sha);
      if (status !== "ahead") return { build: false, reason: `main is ${status} relative to ${latestBeta.tag}.` };
    }
    const version = `${betaTarget(packageVersion, latestStable)}-beta.${date}.${run}`;
    return { build: true, release: true, channel: "beta", version, tag: `v${version}`, sha, prerelease: true, notesStart: latestBeta?.tag ?? "" };
  }

  if (!latestBeta) throw new Error("No beta has been published. A stable release ships the latest beta's commit.");
  const version = latestBeta.parsed.core.join(".");
  if (parsed.some((item) => item.version === version)) throw new Error(`v${version} is already released.`);
  return { build: true, release: true, channel: "stable", version, tag: `v${version}`, sha: await commitOf(latestBeta.tag),
    prerelease: false, notesStart: latestStable?.tag ?? "" };
}

async function main() {
  const { GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_EVENT_NAME, GITHUB_REF, GITHUB_SHA, GITHUB_RUN_NUMBER, GITHUB_OUTPUT, RELEASE_CHANNEL } = process.env;
  const api = async (path) => {
    const reply = await fetch(`https://api.github.com/repos/${GITHUB_REPOSITORY}${path}`, {
      headers: { Authorization: `Bearer ${GITHUB_TOKEN}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" },
    });
    if (!reply.ok) throw new Error(`GitHub answered ${reply.status} for ${path}`);
    return reply.json();
  };
  const releases = [];
  for (let page = 1; page <= 10; page++) {
    const batch = await api(`/releases?per_page=100&page=${page}`);
    releases.push(...batch);
    if (batch.length < 100) break;
  }
  const packageVersion = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")).version;
  const plan = await planRelease({
    event: GITHUB_EVENT_NAME, channel: RELEASE_CHANNEL, ref: GITHUB_REF, sha: GITHUB_SHA, now: Date.now(),
    date: new Date().toISOString().slice(0, 10).replaceAll("-", ""), run: Number(GITHUB_RUN_NUMBER), packageVersion, releases,
    compare: async (base, head) => (await api(`/compare/${encodeURIComponent(base)}...${head}`)).status,
    commitOf: async (tag) => (await api(`/commits/${encodeURIComponent(tag)}`)).sha,
  });
  process.stdout.write(`${JSON.stringify(plan)}\n`);
  const outputs = { build: plan.build, release: plan.release ?? false, channel: plan.channel ?? "", version: plan.version ?? "", tag: plan.tag ?? "",
    sha: plan.sha ?? "", prerelease: plan.prerelease ?? false, notes_start: plan.notesStart ?? "" };
  appendFileSync(GITHUB_OUTPUT, Object.entries(outputs).map(([key, value]) => `${key}=${value}\n`).join(""));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main().catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
