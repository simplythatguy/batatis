/**
 * Seal captures for ui-artifacts (1440×900, seeded state via ?reset).
 *
 *   cd repo && npm i playwright-core@1.64.1 --no-save
 *   UI_SHOT_DIR=/path/to/media node evals/ui-artifacts/screenshots.mjs
 */
import { chromium } from "playwright-core";
import { createServer } from "node:http";
import { readFileSync, existsSync, mkdirSync } from "node:fs";
import { extname, join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
const out = resolve(process.env.UI_SHOT_DIR || "ui-shots");
const chrome = process.env.CHROME_PATH || "/usr/bin/google-chrome-stable";
const mime = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript" };
mkdirSync(out, { recursive: true });

const server = createServer((req, res) => {
  const file = join(root, decodeURIComponent(req.url.split("?")[0]).slice(1));
  if (!file.startsWith(root) || !existsSync(file)) {
    res.writeHead(404);
    return res.end();
  }
  res.writeHead(200, { "Content-Type": mime[extname(file)] || "application/octet-stream" });
  res.end(readFileSync(file));
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}/evals/ui-artifacts`;
const browser = await chromium.launch({ executablePath: chrome, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();

const SHOTS = [
  ["ui-b01-intake.png", "01-intake"],
  ["ui-b01-intake-section-b.png", "01-intake", () => page.click('[data-tab="B"]')],
  ["ui-b01-intake-alternative-path.png", "01-intake", () => page.click('[data-tab="alt"]')],
  ["ui-b02-article-ranking.png", "02-article-ranking"],
  ["ui-b02-article-ranking-clarify.png", "02-article-ranking", () => page.locator(".row").nth(1).click()],
  ["ui-b03-section-c.png", "03-section-c"],
  ["ui-b03-section-c-row2.png", "03-section-c", () => page.locator("#attr-body tr").nth(1).click()],
  ["ui-b04-sco-review.png", "04-sco-review"],
  ["ui-b04-sco-review-citations.png", "04-sco-review", () => page.click('[data-pane="citations"]')],
  ["ui-b04-sco-review-request.png", "04-sco-review", () => page.click("#request-btn")],
  ["ui-b05-export.png", "05-export"],
  ["ui-b05-export-override.png", "05-export", () => page.click("#override-btn")],
  ["ui-b06-evidence-plan.png", "06-evidence-plan"],
];

for (const [file, name, act] of SHOTS) {
  await page.goto(`${base}/${name}.html?reset`, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  if (act) await act();
  await page.mouse.move(1439, 899);
  await page.waitForTimeout(250);
  await page.screenshot({ path: join(out, file) });
  console.log("shot", file);
}
await browser.close();
server.close();
