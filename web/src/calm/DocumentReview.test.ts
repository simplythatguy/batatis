/** Real React DOM in Chromium, using API-typed unit fixtures and file:// (no server or inference).
 * PLAYWRIGHT_MODULE=/absolute/path/to/playwright-core/index.mjs node --experimental-strip-types --import ./scripts/register-ts.mjs --test src/calm/DocumentReview.test.ts
 */
import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import test from "node:test";
import { rolldown } from "rolldown";

let playwright;
try {
  playwright = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : "playwright-core");
} catch (error) {
  if (error.code !== "ERR_MODULE_NOT_FOUND") throw error;
}

test("document review in a real DOM (API-typed unit fixtures)", { skip: !playwright && "Set PLAYWRIGHT_MODULE to an installed playwright-core module" }, async (t) => {
  const directory = await mkdtemp(join(tmpdir(), "batatis-document-review-unit-"));
  const bundle = await rolldown({
    input: fileURLToPath(new URL("./DocumentReview.test.tsx", import.meta.url)),
    platform: "browser", moduleTypes: { ".css": "empty" },
    transform: { define: { "process.env.NODE_ENV": JSON.stringify("production") }, jsx: { runtime: "automatic" } },
  });
  let output;
  try { output = (await bundle.generate({ format: "iife" })).output; }
  finally { await bundle.close(); }
  const script = output.filter((file) => file.type === "chunk").map((file) => file.code).join("\n");
  const styles = (await Promise.all(["../shared.css", "./calm.css", "./DocumentReview.css"].map((file) => readFile(new URL(file, import.meta.url), "utf8")))).join("\n");
  const path = join(directory, "document-review-unit.html");
  await writeFile(path, `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Document review · unit fixture</title><style>body{margin:0}*{box-sizing:border-box}${styles}</style><div id="fixture"></div><script>${script.replaceAll("</script", "<\\/script")}</script></html>`);
  t.diagnostic(`Unit fixture (no application server): ${path}`);

  const browser = await playwright.chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
    const requests: string[] = [], errors: string[] = [];
    await context.route(/^https?:/, (route) => { requests.push(route.request().url()); return route.abort(); });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(pathToFileURL(path).href);
    const panel = page.locator(".cf-document-review");
    const heading = panel.locator(":scope > summary");
    const group = (name: string) => panel.locator(".cf-doc-group").filter({ has: page.locator(":scope > summary", { hasText: name }) });
    async function openFixture(name = "live") {
      await page.getByLabel("Unit fixture", { exact: true }).selectOption(name);
      await heading.focus();
      await page.keyboard.press("Enter");
      assert.equal(await panel.getAttribute("open"), "");
    }

    await t.test("disclosure is keyboard reachable; source facts retain status, exact excerpts, filename and page", async () => {
      assert.equal(await panel.getAttribute("open"), null);
      assert.equal(await panel.getByText("The source proposes a 450 mm projection.").isVisible(), false);
      await openFixture();
      assert.match(await panel.getByRole("status").innerText(), /not applicant-confirmed/);
      assert.match(await panel.innerText(), /not a design approval/);
      assert.equal(await panel.getByText("Outside Alberta", { exact: true }).isVisible(), true);
      assert.equal(await panel.getByText("Code edition", { exact: true }).isVisible(), true);
      const fact = panel.locator("li").filter({ hasText: "The source proposes a 450 mm projection." });
      assert.match(await fact.innerText(), /Proposed/);
      const quote = fact.locator("blockquote");
      assert.equal(await quote.isVisible(), false);
      await fact.locator("summary").focus();
      await page.keyboard.press("Enter");
      assert.equal(await quote.innerText(), "UNIT FIXTURE — Proposed projection: 450 mm.\nKeep this exact excerpt.");
      assert.equal(await fact.locator("figcaption").innerText(), "proposal.pdf · p. 3");
      await page.keyboard.press("Enter");
      assert.equal(await quote.isVisible(), false);
      const assumed = panel.locator("li").filter({ hasText: "The source assumes a dry location." });
      await assumed.locator("summary").click();
      assert.equal(await assumed.locator("figcaption").innerText(), "Your description");
      assert.match(await panel.innerText(), /Decision reported/);
      assert.match(await panel.innerText(), /reference projects.*remain source information/);
    });

    await t.test("conflicts expose both sources; citations separate the source edition from the Alberta lookup", async () => {
      await group("Conflicts").locator(":scope > summary").click();
      await group("Conflicts").getByText("Compare sources", { exact: false }).click();
      assert.deepEqual(await group("Conflicts").locator("figcaption").allTextContents(), ["proposal.pdf · p. 3", "reference.pdf · p. 2"]);
      assert.deepEqual(await group("Conflicts").locator("blockquote").allTextContents(), ["UNIT FIXTURE — Proposed projection: 450 mm.\nKeep this exact excerpt.", "UNIT FIXTURE — Previous proposal: 600 mm."]);
      const provisions = group("Cited provisions");
      await provisions.locator(":scope > summary").click();
      const rows = provisions.locator("li");
      assert.deepEqual(await rows.nth(0).locator("dd").allTextContents(), ["NBC 2015", "No match established in NBC(AE) 2023, 2nd printing"]);
      assert.deepEqual(await rows.nth(1).locator("dd").allTextContents(), ["NBC(AE) 2023, 2nd printing", "NBC(AE) 2023, 2nd printing · Div. B · 9.9.8.2."]);
      assert.match(await provisions.innerText(), /applicability still needs confirmation/);
    });

    await t.test("evidence and follow-up suggestions have reasons and never introduce blocking status or inert actions", async () => {
      for (const name of ["Evidence to request", "Next questions"]) await group(name).locator(":scope > summary").click();
      assert.match(await group("Evidence to request").innerText(), /Ask for supporting test documentation/);
      assert.match(await group("Evidence to request").innerText(), /responsible professional/);
      assert.match(await group("Next questions").innerText(), /Which projection/);
      assert.doesNotMatch(await panel.innerText(), /\bRequired\b|\bMissing\b|Applicant confirmed/);
      assert.equal(await panel.locator("button, input, textarea, a").count(), 0);
    });

    await t.test("unread content stays visible even if review failed or its gate was closed", async () => {
      for (const name of ["failed", "gate_closed"]) {
        await openFixture(name);
        assert.match(await heading.innerText(), /Unread content/);
        assert.equal(await panel.getByText("Outside Alberta", { exact: true }).count(), 0);
        assert.equal(await panel.getByText("Code edition", { exact: true }).count(), 0);
        assert.equal(await panel.getByText("The source proposes a 450 mm projection.").count(), 0);
        assert.match(await group("Flags").innerText(), /scan.pdf pages 1–2 were not read/);
        await group("Documents").locator(":scope > summary").click();
        const scan = group("Documents").locator("li").filter({ hasText: "scan.pdf" });
        assert.match(await scan.innerText(), /Text extraction: Not read/);
        assert.match(await scan.innerText(), /No text layer/);
        assert.match(await scan.innerText(), /Pages not read: 1, 2/);
      }
    });

    await t.test("unavailable and empty reviews stay hidden; test output retains its label", async () => {
      for (const name of ["off", "not_needed", "unknown", "no_review", "no_intake", "empty", "intake_error", "removed_all_files"]) {
        await page.getByLabel("Unit fixture", { exact: true }).selectOption(name);
        assert.equal(await panel.count(), 0, name);
      }
      await openFixture("fake");
      assert.match(await heading.innerText(), /Test output/);
      assert.doesNotMatch(await heading.innerText(), /Model checked/);
    });

    await t.test("a pending or failed intake hides old results; edited descriptions and changed file lists are labelled previous input", async () => {
      await openFixture("reading");
      assert.equal(await panel.getByText("The source proposes a 450 mm projection.").count(), 0);
      assert.doesNotMatch(await heading.innerText(), /Model checked|Unread content/);
      for (const name of ["changed_description", "added_file", "removed_file"]) {
        await openFixture(name);
        assert.match(await heading.innerText(), /Previous input/);
        assert.match(await panel.getByRole("status").innerText(), /earlier description or file list/);
      }
      await openFixture("unverified_input");
      assert.match(await heading.innerText(), /Input unverified/);
      assert.doesNotMatch(await heading.innerText(), /Model checked/);
      assert.match(await panel.getByRole("status").innerText(), /cannot be matched/);
    });

    await t.test("a source without file metadata is identified as unknown and keeps its page and excerpt", async () => {
      await openFixture("unknown_source");
      const fact = group("Source facts").locator("li").first();
      await fact.locator("summary").click();
      assert.equal(await fact.locator("figcaption").innerText(), "Unknown source (unavailable-file) · p. 3");
      assert.equal(await fact.locator("blockquote").innerText(), "UNIT FIXTURE — Proposed projection: 450 mm.\nKeep this exact excerpt.");
    });

    await t.test("reopened cases keep their saved review and source names when browser file metadata is absent", async () => {
      await openFixture("reopened");
      assert.match(await heading.innerText(), /Model checked/);
      assert.doesNotMatch(await heading.innerText(), /Previous input/);
      const fact = group("Source facts").locator("li").first();
      await fact.locator("summary").click();
      assert.equal(await fact.locator("figcaption").innerText(), "proposal.pdf · p. 3");
    });

    await t.test("long source names and excerpts wrap at narrow widths; the findings pane scrolls and preserves literal source text", async () => {
      await openFixture("long");
      const fact = group("Source facts").locator("li").first();
      await fact.locator("summary").click();
      assert.match(await fact.locator("blockquote").innerText(), /<script>window.injected=true<\/script>/);
      assert.equal(await page.evaluate(() => "injected" in window), false);
      for (const width of [390, 320]) {
        await page.setViewportSize({ width, height: 740 });
        const geometry = await panel.evaluate((root) => {
          const body = root.querySelector(".cf-doc-body");
          const region = body.getBoundingClientRect();
          return {
            pageOverflow: document.documentElement.scrollWidth > innerWidth,
            clipped: [...root.querySelectorAll("summary, figcaption, blockquote")].filter((element) => element.getClientRects().length).some((element) => element.scrollWidth > element.clientWidth + 1),
            paneScrolls: body.scrollHeight > body.clientHeight,
            right: region.right, viewport: innerWidth, overflowY: getComputedStyle(body).overflowY,
          };
        });
        assert.equal(geometry.pageOverflow, false, `${width}: page width`);
        assert.equal(geometry.clipped, false, `${width}: source text and controls`);
        assert.equal(geometry.paneScrolls, true);
        assert.equal(geometry.overflowY, "auto");
        assert.ok(geometry.right <= geometry.viewport);
      }
      const region = panel.getByRole("region", { name: "Document review findings" });
      await heading.focus();
      await page.keyboard.press("Tab");
      assert.equal(await region.evaluate((element) => element === document.activeElement), true);
      assert.equal(await region.evaluate((element) => getComputedStyle(element).outlineStyle), "solid");
    });

    assert.deepEqual(errors, [], "no React or browser errors");
    assert.deepEqual(requests, [], "no network or model calls");
    await context.close();
  } finally { await browser.close(); }
  assert.ok((await readFile(path, "utf8")).includes("Unit fixture"));
});
