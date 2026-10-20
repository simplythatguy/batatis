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
const mime = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".mjs": "text/javascript" };
const PAGES = ["01-intake", "02-article-ranking", "03-section-c", "04-sco-review", "05-export", "06-evidence-plan"];

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
const base = process.env.UI_BASE || `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: chrome, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
const page = await context.newPage();
const jsErrors = [];
page.on("pageerror", (e) => jsErrors.push(`${page.url()}: ${e.message}`));
await page.addInitScript(() => (window.print = () => (window.__printed = true)));

const url = (name, { reset = false, hash = "" } = {}) => `${base}/evals/ui-artifacts/${name}.html${reset ? "?reset" : ""}${hash}`;
const go = (name, opts) => page.goto(url(name, opts), { waitUntil: "networkidle" });
const text = (sel) => page.locator(sel).innerText();
const normalize = (t) => t.split("\n").map((s) => s.trim()).filter(Boolean).sort().join("|");

async function assertChrome(label) {
  const clipped = await page.evaluate(() => {
    const clipAncestor = (el) => {
      for (let p = el.parentElement; p; p = p.parentElement) if (getComputedStyle(p).overflowX !== "visible") return p;
      return null;
    };
    const out = [];
    document.querySelectorAll(".btn").forEach((b) => {
      if (!b.offsetParent) return;
      const r = b.getBoundingClientRect();
      const anc = clipAncestor(b);
      const ar = anc ? anc.getBoundingClientRect() : { left: 0, right: innerWidth };
      if (b.scrollWidth > b.clientWidth + 1 || r.right > ar.right + 0.5 || r.left < ar.left - 0.5) out.push(b.textContent.trim());
    });
    document.querySelectorAll(".btn-row").forEach((row) => {
      if (row.offsetParent && row.scrollWidth > row.clientWidth + 1) out.push(`row:${row.textContent.trim().slice(0, 40)}`);
    });
    return out;
  });
  assert(clipped.length === 0, `${label}: clipped buttons/rows: ${clipped.join(", ")}`);
  const body = await text("body");
  const placeholder = body.match(/\[[a-z ]+\]/i);
  assert(!placeholder, `${label}: template placeholder leaked: ${placeholder && placeholder[0]}`);
  assert(!/\bpresent\b|from registry|registry row|\bdemo\b/i.test(body), `${label}: status word or internal id standing in for a value`);
  assert((await page.locator("div.nav-item, span.nav-item").count()) === 0, `${label}: nav items must be links`);
  const hrefs = await page.locator("a[href]").evaluateAll((as) => as.map((a) => a.getAttribute("href")).filter((h) => !/^https?:/.test(h)));
  for (const h of hrefs) {
    const file = h.split("#")[0];
    assert(file && existsSync(join(__dirname, file)), `${label}: dead link "${h}"`);
  }
  const docScroll = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight);
  assert(docScroll <= 0, `${label}: page scrolls ${docScroll}px; panes must scroll, not the shell`);
  const primaries = await page.locator(".footer-bar .btn-primary:visible").count();
  assert(primaries <= 1, `${label}: more than one primary in footer`);
}

try {
  // Chrome bar on every surface, two widths
  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const name of PAGES) {
      await go(name, { reset: true });
      await assertChrome(`${name}@${width}`);
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });

  // Cross-screen gap agreement from seeded state
  const lists = {};
  for (const [name, sel] of [
    ["01-intake", "#gap-strip"],
    ["02-article-ranking", "#gap-strip"],
    ["03-section-c", "#gap-strip"],
    ["04-sco-review", "#gap-list"],
    ["05-export", "#gap-list"],
    ["06-evidence-plan", "#gap-strip"],
  ]) {
    await go(name, { reset: true });
    lists[name] = normalize(await text(sel));
  }
  assert(new Set(Object.values(lists)).size === 1, `Gap lists differ:\n${Object.entries(lists).map(([k, v]) => `${k}: ${v}`).join("\n")}`);
  const seededBlocking = lists["01-intake"].split("|").length - 1;

  // B01 — chrome, styled controls, live gaps, save, deep links
  await go("01-intake", { reset: true });
  const primBg = await page.locator(".btn-primary").evaluate((el) => getComputedStyle(el).backgroundColor);
  assert(/230,\s*230,\s*230/.test(primBg), `B01: primary must be neutral grey (got ${primBg})`);
  const nav = await page.locator(".nav-item.active").evaluate((el) => ({ border: getComputedStyle(el).borderColor, shadow: getComputedStyle(el).boxShadow }));
  assert(!/94,\s*106,\s*210/.test(nav.border) && nav.shadow === "none", "B01: active nav fill only");
  assert(/none/.test(await page.locator('input[type="checkbox"]').evaluate((el) => getComputedStyle(el).appearance)), "B01: checkbox styled");
  const chevronOk = await page.locator("#juris").evaluate(async (el) => {
    const m = getComputedStyle(el).backgroundImage.match(/^url\("(.*)"\)$/);
    if (!m) return false;
    const img = new Image();
    img.src = m[1];
    try {
      await img.decode();
      return img.naturalWidth > 0;
    } catch {
      return false;
    }
  });
  assert(chevronOk, "B01: select chevron image must decode");
  assert((await page.locator("#juris").inputValue()) === "", "B01: jurisdiction select starts unanswered");
  assert(/Defaulted to today/.test(await text("body")), "B01: defaulted date is marked");
  assert(/Representative missing/.test(await text("#gap-strip")), "B01: rep gap seeded");
  await page.fill("#rep", "Kai Lindqvist");
  assert(!/Representative missing/.test(await text("#gap-strip")), "B01: typing clears the gap");
  assert(!(await page.locator('[data-required="rep"]').evaluate((el) => el.classList.contains("is-empty"))), "B01: field leaves empty state");
  assert((await text('[data-tab-count="A"]')) === "1", "B01: tab count updates");
  await page.click("#save-btn");
  assert(/Draft saved/.test(await text("#save-note")), "B01: Save draft shows saved state");
  await page.click("#owner-confirm");
  assert(/Confirmed by applicant/.test(await text("#owner-foot")), "B01: inferred owner can be confirmed");
  await go("01-intake", { hash: "#muni" });
  assert((await page.locator('[data-tab="B"]').getAttribute("aria-selected")) === "true", "B01: #muni opens Section B");
  assert(await page.locator("#muni").evaluate((el) => el === document.activeElement), "B01: #muni focuses the field");
  await page.locator('#gap-strip a', { hasText: "Risk assessment" }).click();
  await page.waitForFunction(() => document.activeElement?.id === "risk");
  assert((await page.locator('[data-tab="alt"]').getAttribute("aria-selected")) === "true", "B01: gap chip jumps to field");

  // B02 — counts, filters, gate, actions, navigation
  await go("02-article-ranking", { reset: true });
  assert((await page.locator(".btn-primary").count()) === 1, "B02: one primary");
  const clarifyCount = Number(await text('[data-count="needs-clarification"]'));
  assert(clarifyCount === (await page.locator('.row [data-status="needs-clarification"]').count()), "B02: clarification count = rows");
  assert(await page.locator("#continue-btn").isDisabled(), "B02: Continue disabled with 0 confirmed");
  await page.click('[data-filter="confirmed"]');
  assert(/No articles in this view/.test(await text("#list")), "B02: empty filter state");
  await page.click('[data-filter="all"]');
  await page.locator(".row").nth(1).click();
  assert(/Question for applicant/.test(await text("#detail")), "B02: clarification question shown for ambiguous row");
  await page.locator(".row").nth(0).click();
  await page.click('[data-act="confirmed"]');
  assert(await page.locator("#continue-btn").isEnabled(), "B02: Continue enabled after confirming");
  assert((await text('[data-count="confirmed"]')) === "1", "B02: confirmed count updates");
  await page.click('[data-filter="confirmed"]');
  assert((await page.locator(".row").count()) === 1, "B02: confirmed filter lists the article");
  await Promise.all([page.waitForURL(/03-section-c/), page.click("#continue-btn")]);

  // B03 — columns, row binding, intent, lookup
  await go("03-section-c", { reset: true });
  const headers = normalize(await text("thead"));
  for (const h of ["CODE", "ARTICLE", "OBJECTIVE", "FUNCTION", "INTENT"]) assert(headers.includes(h), `B03: missing ${h} column`);
  assert((await page.locator("#attr-body tr [data-status]").count()) === (await page.locator("#attr-body tr").count()), "B03: status per row");
  assert(await page.locator("#continue-btn").isDisabled(), "B03: Continue gated on confirmation");
  await page.locator("#attr-body tr").nth(1).click();
  assert((await text("#explain-article")) === "9.25.3.1." && (await text("#cite-article")) === "9.25.3.1.", "B03: cite + explainer follow row");
  assert(/air barrier/i.test(await text("#ai-explain")), "B03: explainer text matches row");
  const b03Values = await page.locator("#attr-body tr").evaluateAll((rows) =>
    rows.map((tr) => ({
      id: tr.dataset.id,
      objective: tr.querySelector('[data-value="objective"]').innerText.trim(),
      fn: tr.querySelector('[data-value="fn"]').innerText.trim(),
      intent: tr.querySelector(".intent-text")?.innerText.trim() || "—",
    }))
  );
  await page.click("#rerun-btn");
  await page.waitForFunction(() => /refreshed/.test(document.getElementById("provenance").textContent));
  await page.click('[data-add-intent="9.25.3.1."]');
  await page.fill("#intent-input", "Limit air leakage through insulated assemblies to control condensation.");
  await page.click("#intent-save");
  await page.waitForFunction(() => !/intent empty for 9\.25\.3\.1/.test(document.getElementById("gap-strip").innerText), null, { timeout: 3000 });
  assert(/Entered by applicant/.test(await text("#attr-body")), "B03: applicant-entered intent is labelled");

  // B04 — gating, counts, coverage, dialogs, queue
  await go("04-sco-review", { reset: true });
  assert(await page.locator("[data-requires-no-blocking-gaps]").isDisabled(), "B04: admin-complete disabled");
  assert(new RegExp(`Resolve ${seededBlocking} blocking gaps`).test(await text("#gate-reason")), "B04: disabled reason");
  assert((await text("#gap-summary")).startsWith(`${seededBlocking} blocking`), "B04: summary matches gap source");
  assert((await page.locator("#gap-list li").count()) === Number(await text("#gap-count")), "B04: Gaps tab count");
  await page.click('[data-pane="citations"]');
  assert((await page.locator("#cite-list .entry").count()) === 2, "B04: citations for every Section C article");
  assert(/Citations 2\/2 .* Section C incomplete/.test(await text("#cite-coverage")), "B04: citation coverage line");
  await page.click('[data-pane="explanations"]');
  assert((await page.locator("#explain-list .entry").count()) === 2, "B04: explanations for every article");
  await page.click("#request-btn");
  assert(await page.locator("#request-dialog[open]").count(), "B04: request dialog opens");
  await page.click("#request-send");
  await page.waitForFunction(() => /Fix request sent/.test(document.getElementById("gate-reason").textContent), null, { timeout: 3000 });
  assert(/Fix request sent/.test(await text("#gate-reason")), "B04: request sent state");
  await page.click('[data-project="VAR-1038"]');
  assert(await page.locator("#detail-1038").isVisible(), "B04: queue row selects detail");

  // B05 — values equal B03, gate honesty, override dialog + download
  await go("05-export", { reset: true });
  assert(await page.locator("#download-btn").isDisabled(), "B05: Download disabled");
  for (const v of b03Values) {
    for (const k of ["objective", "fn", "intent"]) {
      const got = (await page.locator(`[data-article="${v.id}"] [data-value="${k}"]`).innerText()).trim();
      assert(got === v[k], `B05: ${v.id} ${k} "${got}" ≠ B03 "${v[k]}"`);
    }
  }
  const sheet = await text("#sheet");
  assert(/Permit #/.test(sheet) && /Jurisdiction-wide/.test(sheet), "B05: Section B complete");
  assert((await text('[data-value="mitigation"]')).length > 20, "B05: mitigation value shown");
  const gateText = await text("#gate-text");
  assert(/Articles not confirmed: 9\.25\.2\.1\., 9\.25\.3\.1\./.test(gateText) && !/\.\./.test(gateText), `B05: gate names articles ("${gateText}")`);
  assert(/244,\s*244,\s*245/.test(await page.locator(".sheet").evaluate((el) => getComputedStyle(el).backgroundColor)), "B05: light sheet");
  await page.click("#override-btn");
  assert(/Representative missing/.test(await text("#override-list")), "B05: override dialog lists gaps");
  const [download] = await Promise.all([page.waitForEvent("download"), page.click("#override-confirm")]);
  assert(/VAR-1042-draft-with-gaps/.test(download.suggestedFilename()), "B05: override downloads draft");
  assert(/Draft downloaded/.test(await text("#export-note")), "B05: download confirmed in UI");

  // Happy path across screens: shared state unlocks every gate
  await go("01-intake", { reset: true });
  await page.fill("#rep", "Kai Lindqvist");
  await page.fill("#mail", "Box 12, Cochrane AB");
  await page.click('[data-tab="B"]');
  await page.fill("#muni", "41 Ridge Rd, Cochrane");
  await page.selectOption("#juris", "site");
  await page.uncheck("#atsAssumption");
  await page.click('[data-tab="alt"]');
  await page.fill("#risk", "Moisture ingress at sill plates is the governing risk.");
  await page.fill("#assumptions", "Single-storey; climate zone 7A.");
  await go("02-article-ranking");
  await page.click('[data-act="confirmed"]');
  await page.locator(".row").nth(1).click();
  await page.click('[data-act="confirmed"]');
  await go("03-section-c");
  await page.click('[data-add-intent="9.25.3.1."]');
  await page.fill("#intent-input", "Limit air leakage through insulated assemblies to control condensation.");
  await page.click("#intent-save");
  await page.waitForFunction(() => !/intent empty/.test(document.getElementById("gap-strip").innerText), null, { timeout: 3000 });
  await go("04-sco-review");
  assert(await page.locator("[data-requires-no-blocking-gaps]").isEnabled(), "Flow: admin-complete enabled when gaps resolved");
  await go("05-export");
  assert(await page.locator("#download-btn").isEnabled(), "Flow: Download enabled when gaps resolved");
  assert(/Ready to download/.test(await text("#gate-text")), "Flow: gate reports ready");
  assert(/Kai Lindqvist/.test(await text("#sheet")) && /No — site specific/.test(await text("#sheet")), "Flow: preview reflects intake edits");
  await page.click("#download-btn");
  assert(await page.evaluate(() => window.__printed === true), "Flow: Download opens print-to-PDF");

  assert(jsErrors.length === 0, `JS errors:\n${jsErrors.join("\n")}`);
  console.log("ui-artifacts smoke: PASS (Opus P0 checks)");
} catch (e) {
  console.error("ui-artifacts smoke: FAIL");
  console.error(e);
  process.exitCode = 1;
} finally {
  await browser.close();
  if (server) await new Promise((r) => server.close(r));
}
