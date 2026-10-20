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

const PAGES = ["01-intake", "02-article-ranking", "03-section-c", "04-sco-review", "05-export"];

async function assertChrome(label) {
  const clipped = await page.evaluate(() => {
    const clips = (el) => {
      for (let p = el.parentElement; p; p = p.parentElement) {
        const o = getComputedStyle(p).overflowX;
        if (o !== "visible") return p;
      }
      return null;
    };
    const out = [];
    document.querySelectorAll(".btn").forEach((b) => {
      if (!b.offsetParent) return;
      const r = b.getBoundingClientRect();
      const anc = clips(b);
      const ar = anc ? anc.getBoundingClientRect() : { left: 0, right: innerWidth };
      if (b.scrollWidth > b.clientWidth + 1 || r.right > ar.right + 0.5 || r.left < ar.left - 0.5) out.push(b.textContent.trim());
    });
    document.querySelectorAll(".btn-row").forEach((row) => {
      if (row.offsetParent && row.scrollWidth > row.clientWidth + 1) out.push(`row:${row.textContent.trim().slice(0, 40)}`);
    });
    return out;
  });
  assert(clipped.length === 0, `${label}: clipped buttons/rows: ${clipped.join(", ")}`);
  const text = await page.locator("body").innerText();
  const placeholder = text.match(/\[[a-z ]+\]/i);
  assert(!placeholder, `${label}: template placeholder leaked: ${placeholder && placeholder[0]}`);
  assert(!/\bpresent\b|from registry/i.test(text), `${label}: status word standing in for a value`);
}

try {
  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const name of PAGES) {
      await page.goto(`${base}/evals/ui-artifacts/${name}.html`, { waitUntil: "networkidle" });
      await assertChrome(`${name}@${width}`);
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });

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
  const clipped = await page.locator(".detail .btn").evaluateAll((els) =>
    els.filter((el) => el.scrollWidth > el.clientWidth + 1).map((el) => el.textContent.trim())
  );
  assert(clipped.length === 0, `B02: clipped button labels: ${clipped.join(", ")}`);
  const overflowRight = await page.locator(".detail").evaluate((d) => {
    const dr = d.getBoundingClientRect();
    return [...d.querySelectorAll(".btn")].some((b) => b.getBoundingClientRect().right > dr.right - 12);
  });
  assert(!overflowRight, "B02: action buttons must keep right padding inside detail panel");
  assert((await page.locator("#gap-strip .gap-chip").count()) > 0, "B02: shared gap strip present");
  assert(/not confirmed/i.test(await page.locator("#gap-strip").innerText()), "B02: article-confirmation gap");
  const clarifyCount = Number(await page.locator('[data-count="needs-clarification"]').innerText());
  const clarifyRows = await page.locator('.row [data-status="needs-clarification"]').count();
  assert(clarifyCount === clarifyRows, `B02: clarification tab count ${clarifyCount} ≠ rows ${clarifyRows}`);
  const cont = page.locator("#continue-btn");
  assert(await cont.isDisabled(), "B02: Continue disabled with 0 confirmed");
  await page.locator('[data-act="confirm"]').click();
  assert(await page.locator("#continue-btn").isEnabled(), "B02: Continue enabled after confirming one");
  assert(Number(await page.locator('[data-count="confirmed"]').innerText()) === 1, "B02: confirmed count updates");

  // B03 — row status + empty intent affordance
  await page.goto(`${base}/evals/ui-artifacts/03-section-c.html`, { waitUntil: "networkidle" });
  assert((await page.locator("#attr-body tr [data-status]").count()) === (await page.locator("#attr-body tr").count()), "B03: every row has a status pill");
  assert((await page.locator("#attr-body .cell-gap .status-dot.blocking").count()) >= 1, "B03: empty intent has red dot");
  assert((await page.getByRole("button", { name: "Add intent" }).count()) >= 1, "B03: Add intent action");
  assert(/not confirmed/i.test(await page.locator("#gap-strip").innerText()), "B03: confirmation gap on strip");

  const b03Values = await page.locator("#attr-body tr").evaluateAll((rows) =>
    rows.map((tr) => ({
      id: tr.dataset.id,
      objective: tr.querySelector('[data-value="objective"]').innerText.trim(),
      fn: tr.querySelector('[data-value="fn"]').innerText.trim(),
      intent: tr.querySelector(".intent-text")?.innerText.trim() || "—",
    }))
  );
  assert(!/\[/.test(await page.locator("#cite-block").innerText()), "B03: cite block has no bracket placeholder");
  assert((await page.locator("#cite-link").count()) === 1, "B03: full-text link outside cite block");
  assert(await page.locator("#continue-btn").isDisabled(), "B03: Continue disabled while no article confirmed");

  // B04 — admin-complete gated; tabs scoped; queue dots
  await page.goto(`${base}/evals/ui-artifacts/04-sco-review.html`, { waitUntil: "networkidle" });
  const admin = page.locator("[data-requires-no-blocking-gaps]");
  assert(await admin.isDisabled(), "B04: Mark admin-complete disabled while gaps");
  const scoGaps = await page.locator("#gap-list").innerText();
  assert(/Representative/i.test(scoGaps) && /Municipal address/i.test(scoGaps), "B04: shared gaps");
  assert((await page.locator(".item-title .status-dot").count()) >= 2, "B04: queue rows have status dots");
  assert(/Resolve \d+ blocking gaps/.test(await page.locator("#gate-reason").innerText()), "B04: disabled reason shown");
  assert((await page.locator("#gap-list li").count()) === Number(await page.locator("#gap-count").innerText()), "B04: Gaps tab count matches list");

  // B05 — Download disabled; Override lists gaps; light sheet; shared gaps
  await page.goto(`${base}/evals/ui-artifacts/05-export.html`, { waitUntil: "networkidle" });
  assert(await page.locator("button.btn-primary").isDisabled(), "B05: Download disabled");
  const exportGaps = await page.locator("#gap-list").innerText();
  assert(/Risk assessment/i.test(exportGaps) && /Representative/i.test(exportGaps), "B05: shared gaps");
  assert(/not confirmed/i.test(exportGaps), "B05: confirmation gap in Remaining gaps");
  const sheetC = await page.locator("#sheet-section-c").innerText();
  assert(!/present/i.test(sheetC), "B05: preview must not claim attributions present for unconfirmed");
  assert(/Pending|Needs clarification/.test(sheetC), "B05: preview shows per-article confirmation status");
  for (const v of b03Values) {
    const art = page.locator(`[data-article="${v.id}"]`);
    for (const k of ["objective", "fn", "intent"]) {
      const got = (await art.locator(`[data-value="${k}"]`).innerText()).trim();
      assert(got === v[k], `B05: ${v.id} ${k} "${got}" ≠ B03 "${v[k]}"`);
    }
  }
  const mitigation = (await page.locator('[data-value="mitigation"]').innerText()).trim();
  assert(mitigation.length > 20, `B05: mitigating measures must show the value (got "${mitigation}")`);
  const gateText = await page.locator("#gate-text").innerText();
  assert(/Articles not confirmed: 9\.25\.2\.1\., 9\.25\.3\.1\./.test(gateText), `B05: gate must name unconfirmed articles ("${gateText}")`);
  assert(!/\.\./.test(gateText), "B05: no doubled punctuation in gate");
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
  await page.goto(`${base}/evals/ui-artifacts/02-article-ranking.html`, { waitUntil: "networkidle" });
  const g2 = normalize(await page.locator("#gap-strip").innerText());
  await page.goto(`${base}/evals/ui-artifacts/03-section-c.html`, { waitUntil: "networkidle" });
  const g3 = normalize(await page.locator("#gap-strip").innerText());
  const all = { B01: g1, B02: g2, B03: g3, B04: g4, B05: g5 };
  assert(
    new Set(Object.values(all)).size === 1,
    `Gap lists must match across all surfaces\n${Object.entries(all).map(([k, v]) => `${k}:${v}`).join("\n")}`
  );
  const summary = await (async () => {
    await page.goto(`${base}/evals/ui-artifacts/04-sco-review.html`, { waitUntil: "networkidle" });
    return page.locator("#gap-summary").innerText();
  })();
  const blockingCount = g1.split("|").length - 1;
  assert(summary.startsWith(`${blockingCount} blocking`), `B04 summary "${summary}" must match ${blockingCount} blocking`);

  console.log("ui-artifacts smoke: PASS (Opus P0 checks)");
} catch (e) {
  console.error("ui-artifacts smoke: FAIL");
  console.error(e);
  process.exitCode = 1;
} finally {
  await browser.close();
  if (server) await new Promise((r) => server.close(r));
}
