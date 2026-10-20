/**
 * Cold-user walk against a running production preview and the dev engine.
 *   VITE_ENGINE_URL=http://127.0.0.1:8000 npm run build && npm run preview
 *   node scripts/smoke-flow.mjs [previewUrl]
 *
 * Search and the official PDF need the code database. When it is missing, the
 * walk still finishes at the draft record once the local gaps are closed.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const puppeteer = (() => {
  try {
    return require("puppeteer-core");
  } catch {
    return require("/tmp/node_modules/puppeteer-core");
  }
})();

const preview = process.argv[2] ?? "http://127.0.0.1:4173";
const shots = process.env.SMOKE_SHOTS ?? "/opt/cursor/artifacts/screenshots";
mkdirSync(shots, { recursive: true });

const DESCRIPTION =
  "A single family house with hempcrete walls instead of the wall an acceptable solution would specify.";

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

async function shot(page, name) {
  await page.screenshot({ path: join(shots, `${name}.png`), fullPage: true });
}

async function jargon(page, where) {
  const text = await page.evaluate(() => document.body.innerText);
  assert(!/command-?line/i.test(text), `${where} mentions the command line`);
  assert(!/no route/i.test(text), `${where} says no route`);
  return text;
}

async function clickButton(page, label) {
  const handle = await page.evaluateHandle((wanted) => {
    const nodes = [...document.querySelectorAll("button")];
    return (
      nodes.find((b) => b.textContent?.replace(/\s+/g, " ").trim() === wanted) ??
      nodes.find((b) => b.querySelector(".choice-label")?.textContent?.trim() === wanted) ??
      null
    );
  }, label);
  const el = handle.asElement();
  assert(el, `button not found: ${label}`);
  await el.click();
}

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || "/usr/local/bin/google-chrome",
  headless: process.env.SMOKE_HEADLESS !== "0",
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1280,900"],
  defaultViewport: { width: 1280, height: 900 },
});

try {
  const page = await browser.newPage();
  const client = await page.createCDPSession();
  await client.send("Browser.setDownloadBehavior", {
    behavior: "allow",
    downloadPath: shots,
    eventsEnabled: true,
  });
  await page.goto(`${preview}/?reset#/`, { waitUntil: "networkidle0" });
  await page.waitForSelector("button.choice");
  await jargon(page, "who");
  await clickButton(page, "Homebuilder");
  await page.waitForSelector("#description");

  await page.type("#description", DESCRIPTION);
  await page.select("#authority", "calgary");
  let text = await jargon(page, "describe");
  assert(/Upload isn't available yet\. Paste the text instead\./.test(text), "describe does not say to paste instead of uploading");
  await shot(page, "01-describe");

  await clickButton(page, "Continue to code check");
  await page.waitForSelector("article.card");
  text = await jargon(page, "code check");
  assert(!/9\.9\.4\.4/.test(text), "code check cites 9.9.4.4");
  const cards = await page.$$("article.card");
  for (const card of cards) {
    const clicked = await card.evaluate((node) => {
      const button = [...node.querySelectorAll("button")].find((b) => b.textContent?.trim() === "No");
      button?.click();
      return Boolean(button);
    });
    assert(clicked, "a code-check card has no No answer");
  }
  await shot(page, "02-code-check");

  await page.goto(`${preview}/#/section-c`, { waitUntil: "networkidle0" });
  await page.waitForSelector("#section-c-search");
  const query = await page.$eval("#section-c-search", (el) => el.value);
  assert(query.includes("hempcrete"), `search box was not prefilled from the description: ${query}`);
  await page.waitForFunction(
    () => {
      const note = document.querySelector("#section-c-search")?.parentElement?.innerText ?? "";
      return /provisions|code database|Internal Server Error|not available|did not answer|No provisions/i.test(note);
    },
    { timeout: 20000 },
  );
  text = await jargon(page, "section C");
  assert(/Search the code for a provision/.test(text), "section C has no search");
  assert(/Continue to application/.test(text), "section C continue control missing");
  const continueIsButton = await page.$eval("button.btn-primary", (el) => el.textContent?.includes("Continue to application") ?? false);
  assert(continueIsButton, "Continue to application is not a button");
  await shot(page, "03-section-c");

  const useProvision = await page.evaluate(() => [...document.querySelectorAll("button")].some((b) => b.textContent?.includes("Use this provision")));
  if (useProvision) {
    await clickButton(page, "Use this provision");
    await page.waitForFunction(() => [...document.querySelectorAll("button")].some((b) => b.textContent?.includes("Confirm this provision")));
    await clickButton(page, "Confirm this provision");
    await shot(page, "03b-section-c-confirmed");
  }

  await clickButton(page, "Continue to application");
  await page.waitForSelector("#reco-title");
  await page.waitForFunction(
    () => /Evidence plan|Section D issues|Internal Server Error|not available yet|could not be reached|Save the draft/.test(document.body.innerText),
    { timeout: 20000 },
  );
  text = await jargon(page, "section D");
  assert(/What is the occupancy or building type/.test(text), "section D has no occupancy question");
  assert(/Document name|Evidence plan|No evidence items yet|Internal Server Error/.test(text), "section D has no evidence area");
  await page.select("#prof-occupancy", "single_family");
  for (const [id, value] of [
    ["#prof-part4_design", "no"],
    ["#prof-ahj_requires_professional", "no"],
    ["#prof-special_safety_concerns", "no"],
    ["#prof-roof_trusses", "no"],
    ["#prof-preserved_wood_foundation_part4", "no"],
    ["#prof-prescriptive_route_confirmed", "yes"],
    ["#prof-professional_judgement_required", "no"],
    ["#prof-professional_scope_resolved", "yes"],
    ["#prof-fire_suppression", "no"],
    ["#prof-fire_alarm", "no"],
  ]) {
    await page.select(id, value);
  }
  const evidenceButtons = await page.$$("button");
  for (const button of evidenceButtons) {
    const label = await button.evaluate((b) => b.textContent?.trim());
    if (label !== "Save this evidence") continue;
    const card = await button.evaluateHandle((b) => b.closest("article"));
    const article = card.asElement();
    if (!article) continue;
    const inputs = await article.$$("input");
    if (inputs.length >= 2) {
      await inputs[0].type("Example test report");
      await inputs[1].type("Example Applicant");
      if (inputs[2]) await inputs[2].type("2026-10-20");
      await button.click();
    }
  }
  for (const [id, value] of [
    ["#field-rationale", "The hempcrete wall is the departure from the acceptable wall."],
    ["#field-risk", "If the wall stays wet it can lose strength."],
    ["#field-mitigation", "Keep the wall above grade with a rainscreen."],
    ["#field-assumptions", "One suite, above grade, no second dwelling unit."],
    ["#field-maintenance", "The owner inspects the rainscreen once a year."],
    ["#field-qualifications", "Example Applicant is writing this. No professional opinion is invented here."],
  ]) {
    const el = await page.$(id);
    if (el) await el.type(value);
  }
  await shot(page, "04-section-d");

  await page.goto(`${preview}/#/application?tab=A`, { waitUntil: "networkidle0" });
  await page.type("#field-owner", "Example Applicant");
  await page.type("#field-representative", "Example Applicant");
  await page.type("#field-mailingAddress", "100 Example Street NW, Edmonton");
  await page.type("#field-date", "2026-10-20");
  await page.goto(`${preview}/#/application?tab=B`, { waitUntil: "networkidle0" });
  await page.select("#field-scope", "site");
  await page.type("#field-municipalAddress", "100 Example Street NW, Edmonton");
  await page.type("#field-legalDescription", "Lot 1, Block 1, Plan EXAMPLE");
  const alt = await page.$eval("#field-alternative", (el) => el.value);
  if (!alt.trim()) await page.type("#field-alternative", DESCRIPTION);
  await shot(page, "05-section-b");

  await page.waitForFunction(
    () => {
      const button = [...document.querySelectorAll("button")].find((b) => b.textContent?.includes("Check completeness"));
      return button && !button.disabled;
    },
    { timeout: 15000 },
  ).catch(async () => {
    const gaps = await page.evaluate(() =>
      [...document.querySelectorAll(".gap-chip, .status-note")].map((n) => n.textContent?.replace(/\s+/g, " ").trim()),
    );
    throw new Error(`Check completeness stayed disabled. Visible gaps: ${gaps.join(" | ")}`);
  });
  await jargon(page, "application");
  await clickButton(page, "Check completeness");
  await page.waitForSelector("#completeness-title");
  await page.waitForFunction(() => /PDF|draft|did not|blocked|missing/i.test(document.body.innerText), { timeout: 20000 });
  await jargon(page, "completeness dialog");
  await shot(page, "06-completeness");
  await clickButton(page, "Download draft record");
  await page.waitForFunction(() => /draft-record\.txt/.test(document.body.innerText), { timeout: 5000 });

  await page.goto(`${preview}/#/officer`, { waitUntil: "networkidle0" });
  text = await jargon(page, "officer");
  assert(/Planted example\. Not a real application\./.test(text), "officer does not label the planted example");
  assert(!/case_[0-9a-f]{6,}/.test(text), "officer shows a raw case id");
  await shot(page, "07-officer");

  await page.goto(`${preview}/#/accuracy`, { waitUntil: "networkidle0" });
  text = await jargon(page, "accuracy");
  assert(/55 of 60/.test(text), "model-checked screen is missing the 55/60 evaluation");
  await shot(page, "08-accuracy");

  console.log("ok: cold path finished at the draft record");
} finally {
  await browser.close();
}
