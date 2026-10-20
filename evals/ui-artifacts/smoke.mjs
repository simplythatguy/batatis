/**
 * Playwright smoke for ui-artifacts (Opus P0 interaction bar).
 *
 *   cd repo && npm i playwright-core@1.64.1 --no-save
 *   node evals/ui-artifacts/smoke.mjs
 */
import { chromium } from "playwright-core";
import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { extname, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "../..");
const preferPort = process.env.UI_PORT ? Number(process.env.UI_PORT) : 0; // 0 = ephemeral
const chrome = process.env.CHROME_PATH || "/usr/bin/google-chrome-stable";
const mime = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
};

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

function startServer() {
  return new Promise((resolve, reject) => {
    const server = createServer((req, res) => {
      const rel = decodeURIComponent((req.url || "/").split("?")[0]).slice(1);
      const file = join(root, rel || "evals/ui-artifacts/01-intake.html");
      if (!file.startsWith(root) || !existsSync(file)) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      res.writeHead(200, { "Content-Type": mime[extname(file)] || "application/octet-stream" });
      res.end(readFileSync(file));
    });
    server.once("error", reject);
    server.listen(preferPort, "127.0.0.1", () => resolve(server));
  });
}

const server = process.env.UI_BASE ? null : await startServer();
const listenPort = server ? server.address().port : preferPort;
const base = process.env.UI_BASE || `http://127.0.0.1:${listenPort}`;
const browser = await chromium.launch({
  executablePath: chrome,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();

try {
  // B01 — neutral primary, quiet nav, shared gaps, styled checkbox
  await page.goto(`${base}/evals/ui-artifacts/01-intake.html`, { waitUntil: "networkidle" });
  assert((await page.locator("button.btn-primary").count()) === 1, "B01: one primary");
  const primBg = await page.locator("button.btn-primary").evaluate((el) => getComputedStyle(el).backgroundColor);
  assert(/230,\s*230,\s*230|#e6e6e6/i.test(primBg), `B01: primary must be neutral grey (got ${primBg})`);
  const nav = await page.locator(".nav-item.active").evaluate((el) => {
    const s = getComputedStyle(el);
    return { border: s.borderColor, shadow: s.boxShadow, bg: s.backgroundColor };
  });
  assert(!/94,\s*106,\s*210/i.test(nav.border), `B01: active nav no accent border (${nav.border})`);
  assert(nav.shadow === "none", `B01: active nav no glow`);
  const gapText = await page.locator("#gap-strip").innerText();
  assert(/Representative/i.test(gapText) && /Mailing address/i.test(gapText) && /Municipal address/i.test(gapText), "B01: shared gaps on strip");
  assert(/Risk assessment/i.test(gapText) && /Assumptions/i.test(gapText), "B01: process gaps present");
  const checkAppearance = await page.locator('input[type="checkbox"]').evaluate((el) => getComputedStyle(el).appearance || getComputedStyle(el).webkitAppearance);
  assert(/none/i.test(checkAppearance), `B01: checkbox must be styled (appearance=${checkAppearance})`);

  // B02 — one primary, no demo row, nowrap
  await page.goto(`${base}/evals/ui-artifacts/02-article-ranking.html`, { waitUntil: "networkidle" });
  assert((await page.locator("button.btn-primary").count()) === 1, "B02: one primary");
  assert(!(await page.content()).toLowerCase().includes("demo"), "B02: no demo leakage");
  const wrap = await page.locator(".btn-row .btn").first().evaluate((el) => getComputedStyle(el).whiteSpace);
  assert(wrap === "nowrap", "B02: buttons nowrap");

  // B04 — admin-complete gated; tabs scoped; queue dots
  await page.goto(`${base}/evals/ui-artifacts/04-sco-review.html`, { waitUntil: "networkidle" });
  const admin = page.locator("[data-requires-no-blocking-gaps]");
  assert(await admin.isDisabled(), "B04: Mark admin-complete disabled while gaps");
  const scoGaps = await page.locator("#gap-list").innerText();
  assert(/Representative/i.test(scoGaps) && /Municipal address/i.test(scoGaps), "B04: shared gaps");
  assert((await page.locator(".item-title .status-dot").count()) >= 2, "B04: queue rows have status dots");

  // B05 — Download disabled; Override lists gaps; light sheet; shared gaps
  await page.goto(`${base}/evals/ui-artifacts/05-export.html`, { waitUntil: "networkidle" });
  assert(await page.locator("button.btn-primary").isDisabled(), "B05: Download disabled");
  const exportGaps = await page.locator("#gap-list").innerText();
  assert(/Risk assessment/i.test(exportGaps) && /Representative/i.test(exportGaps), "B05: shared gaps");
  const sheetBg = await page.locator(".sheet").evaluate((el) => getComputedStyle(el).backgroundColor);
  assert(/244,\s*244,\s*245|#f4f4f5/i.test(sheetBg), `B05: PDF preview should be light (got ${sheetBg})`);
  page.once("dialog", async (d) => {
    assert(/Representative/i.test(d.message()), "B05: Override dialog lists gaps");
    await d.dismiss();
  });
  await page.locator("#override-btn").click();

  // Cross-screen gap agreement (blocking labels)
  const normalize = (t) =>
    t
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean)
      .sort()
      .join("|");
  await page.goto(`${base}/evals/ui-artifacts/01-intake.html`, { waitUntil: "networkidle" });
  const g1 = normalize(await page.locator("#gap-strip").innerText());
  await page.goto(`${base}/evals/ui-artifacts/04-sco-review.html`, { waitUntil: "networkidle" });
  const g4 = normalize(await page.locator("#gap-list").innerText());
  await page.goto(`${base}/evals/ui-artifacts/05-export.html`, { waitUntil: "networkidle" });
  const g5 = normalize(await page.locator("#gap-list").innerText());
  assert(g1 === g4 && g4 === g5, `Gap lists must match across B01/B04/B05\nB01:${g1}\nB04:${g4}\nB05:${g5}`);

  console.log("ui-artifacts smoke: PASS (Opus P0 checks)");
} catch (e) {
  console.error("ui-artifacts smoke: FAIL");
  console.error(e);
  process.exitCode = 1;
} finally {
  await browser.close();
  if (server) await new Promise((r) => server.close(r));
}
