import assert from "node:assert/strict";
import test from "node:test";
import { betaTarget, desktopReleases, planRelease } from "../scripts/release-plan.mjs";

const NOW = Date.parse("2026-10-26T12:00:00Z");
const published = (tag: string, hoursAgo: number, prerelease = tag.includes("-beta.")) =>
  ({ tag_name: tag, prerelease, draft: false, published_at: new Date(NOW - hoursAgo * 3_600_000).toISOString() });

function plan(overrides: Partial<Parameters<typeof planRelease>[0]> = {}) {
  const compared: string[][] = [];
  const run = planRelease({
    event: "push", channel: "", ref: "refs/heads/main", sha: "a".repeat(40), now: NOW, date: "20261026", run: 57,
    packageVersion: "0.1.0", releases: [],
    compare: async (base: string, head: string) => { compared.push([base, head]); return "ahead"; },
    commitOf: async (tag: string) => `sha-of-${tag}`,
    ...overrides,
  });
  return { run, compared };
}

test("the first beta previews the package version; later ones preview the patch after the latest stable", async () => {
  assert.deepEqual(await plan().run, { build: true, release: true, channel: "beta", version: "0.1.0-beta.20261026.57",
    tag: "v0.1.0-beta.20261026.57", sha: "a".repeat(40), prerelease: true, notesStart: "" });
  const releases = [published("v0.1.0", 48), published("v0.1.0-beta.20261020.40", 100)];
  const afterStable = await plan({ releases }).run;
  assert.equal(afterStable.version, "0.1.1-beta.20261026.57");
  assert.equal(afterStable.notesStart, "v0.1.0-beta.20261020.40");
  assert.equal(betaTarget("0.3.0", desktopReleases(releases)[0]), "0.3.0", "a higher package version starts a new minor");
  assert.throws(() => betaTarget("0.3.0-beta.1", null));
});

test("every merge into main is a beta right away, unless the last beta already ships that commit", async () => {
  const minutesLater = plan({ releases: [published("v0.1.0-beta.20261026.50", 0.1)] });
  assert.equal((await minutesLater.run).build, true, "no waiting period between betas");
  assert.deepEqual(minutesLater.compared, [["v0.1.0-beta.20261026.50", "a".repeat(40)]]);

  const same = plan({ releases: [published("v0.1.0-beta.20261026.50", 1)], compare: async () => "identical" });
  assert.equal((await same.run).build, false);

  const manual = await plan({ event: "workflow_dispatch", channel: "beta", releases: [published("v0.1.0-beta.20261026.50", 1)], compare: async () => "identical" }).run;
  assert.equal(manual.build, true, "a manual beta builds now");
});

test("stable publishes the latest beta's commit under its X.Y.Z, once", async () => {
  const releases = [published("v0.1.0", 200), published("v0.1.1-beta.20261024.60", 50), published("v0.1.1-beta.20261025.61", 20), published("v0.0.9", 400)];
  assert.deepEqual(await plan({ event: "workflow_dispatch", channel: "stable", releases }).run, {
    build: true, release: true, channel: "stable", version: "0.1.1", tag: "v0.1.1", sha: "sha-of-v0.1.1-beta.20261025.61", prerelease: false, notesStart: "v0.1.0",
  });
  await assert.rejects(plan({ event: "workflow_dispatch", channel: "stable", releases: [...releases, published("v0.1.1", 1)] }).run, /already released/);
  await assert.rejects(plan({ event: "workflow_dispatch", channel: "stable" }).run, /No beta/);
});

test("only main releases, and unrelated or mislabeled releases are ignored", async () => {
  await assert.rejects(plan({ ref: "refs/heads/feature" }).run, /built from main/);
  const parsed = desktopReleases([published("desktop-v9.0.0", 1), published("v9.0.0-beta.20261026.1", 1, false), published("v8.0.0", 1, true),
    { ...published("v7.0.0", 1), draft: true }, published("v0.2.0", 1)]);
  assert.deepEqual(parsed.map((item) => item.tag), ["v0.2.0"]);
});
