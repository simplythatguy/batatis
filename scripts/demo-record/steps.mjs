/**
 * Walkthrough for the Batatis demo recording.
 *
 * Ids, titles, and primary routes match #20's docs/demo/script.md (7 shots).
 * The burned-in caption names only text that is on screen. It is not the
 * shot title. The EXAMPLE DATA label and the caption sit in a band at the top
 * of the frame. The app is inset below that band so the header subtitle and
 * the footer stay visible.
 *
 * Recording order follows the script: Case C stays open through shots 2, 4, 5,
 * and 7's Case C frame. Reset runs before shot 3 and wipes Case C. Shot 6 is
 * last, with Case A still open. Case B is named on shot 1 and is not walked.
 *
 * A screen that is not in the build is skipped and logged. The runner does not
 * invent article numbers, listings, test results, professional opinions, or
 * stills. It does not upload a PDF, click Try an example, or open Accuracy.
 */
import { existsSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const LOWER = {
  A: "EXAMPLE DATA · Case A · Manufacturer",
  B: "EXAMPLE DATA · Case B · General contractor",
  C: "EXAMPLE DATA · Case C · Homebuilder",
};

const ALL_LOWER = `${LOWER.A}\n${LOWER.B}\n${LOWER.C}`;

const CASES = {
  A: {
    role: "Manufacturer",
    authority: "Edmonton",
    lower: LOWER.A,
    text: "We make EPW NailBase CI-50, a 50 mm insulating sheathing panel, and we want it approved across Alberta so builders can nail vinyl siding straight into the facer. One pilot house: 0000 Example Way NW, Edmonton. Owner not decided. No legal description. No permit yet.",
  },
  C: {
    role: "Homebuilder",
    authority: "Edmonton",
    lower: LOWER.C,
    text: "Two-storey infill at 0000 Example Crescent NW, Edmonton, about 210 m², no sprinklers. Heated slab with R-7.5 under it. Unvented low-slope roof, spray foam thickness still TBD. Bedroom 3 window clear opening 400 mm by 780 mm. What needs a variance?",
  },
};

const OPEN_QUESTION_HOLD_MS = 3500;
const OFFICER_INTRO =
  "This review is of the application in front of you. It checks whether information is present. It does not decide whether the design complies or is safe.";
const OFFICER_HEADINGS = ["Documents", "Open Not sure", "Professional", "Grouped completeness report", "Information request"];
const LIMIT_LINE =
  "Recommendations only. You write the evidence and the answers. This does not decide that the design complies or is safe.";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function skipped(reason) {
  return { status: "skipped", reason };
}

function pending(reason) {
  return { status: "pending", reason };
}

function recorded() {
  return { status: "recorded" };
}

function failed(reason) {
  return { status: "failed", reason };
}

function escapeReg(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function slug(title) {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48);
}

function exampleLabel(lower) {
  if (!lower) return "EXAMPLE DATA";
  if (lower.includes("EXAMPLE DATA")) return lower;
  return `EXAMPLE DATA\n${lower}`;
}

async function visible(locator, timeout = 1000) {
  try {
    await locator.first().waitFor({ state: "visible", timeout });
    return true;
  } catch {
    return false;
  }
}

function h1(page, name) {
  return page.getByRole("heading", { level: 1, name }).first();
}

function describeHeading(page) {
  return h1(page, /What are you building\?|Describe your idea/);
}

function navLink(page, name) {
  return page.getByRole("navigation", { name: "Main" }).getByRole("link", { name });
}

function roleButton(page, label) {
  return page.getByRole("button", { name: new RegExp(`^${escapeReg(label)}(?!\\s*·)`) }).first();
}

async function overlay(page, { caption, lower }) {
  await page.evaluate(
    ({ caption, lower }) => {
      let band = document.getElementById("demo-recorder-band");
      if (!band) {
        band = document.createElement("div");
        band.id = "demo-recorder-band";
        band.setAttribute("data-demo-recorder", "true");
        const low = document.createElement("div");
        low.id = "demo-recorder-lower";
        const cap = document.createElement("div");
        cap.id = "demo-recorder-caption";
        band.append(low, cap);
        document.body.appendChild(band);
      }
      const root = document.getElementById("root");
      const shell = document.querySelector(".app-shell");
      const panel = document.querySelector(".main-panel");
      const restore = () => {
        for (const el of [root, shell, panel]) {
          if (!el) continue;
          el.style.marginTop = "";
          el.style.height = "";
          el.style.maxHeight = "";
          el.style.minHeight = "";
          el.style.overflow = "";
        }
      };
      if (!caption && !lower) {
        band.style.display = "none";
        restore();
        return;
      }
      Object.assign(band.style, {
        position: "fixed",
        top: "0",
        left: "0",
        right: "0",
        zIndex: "10000",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        padding: "8px 16px",
        background: "#18181b",
        borderBottom: "1px solid #3f3f46",
        boxSizing: "border-box",
        pointerEvents: "none",
      });
      const low = document.getElementById("demo-recorder-lower");
      const cap = document.getElementById("demo-recorder-caption");
      Object.assign(low.style, {
        position: "static",
        background: "#fff7ed",
        color: "#7c2d12",
        border: "2px solid #c2410c",
        font: "700 14px/1.3 ui-sans-serif, system-ui, sans-serif",
        padding: "4px 8px",
        borderRadius: "6px",
        whiteSpace: "pre",
        maxWidth: "70%",
        width: "auto",
      });
      Object.assign(cap.style, {
        position: "static",
        marginLeft: "auto",
        background: "rgba(39,39,42,0.96)",
        color: "#f4f4f5",
        border: "1px solid #52525b",
        font: "600 13px/1.3 ui-sans-serif, system-ui, sans-serif",
        padding: "4px 8px",
        borderRadius: "6px",
        whiteSpace: "nowrap",
        width: "auto",
      });
      low.textContent = lower || "";
      low.style.display = lower ? "block" : "none";
      low.setAttribute("data-example-data", lower && lower.includes("EXAMPLE DATA") ? "true" : "false");
      cap.textContent = caption || "";
      cap.style.display = caption ? "block" : "none";
      const height = Math.ceil(band.getBoundingClientRect().height);
      const inset = `${height}px`;
      if (root) {
        root.style.marginTop = inset;
        root.style.height = `calc(100dvh - ${inset})`;
        root.style.maxHeight = `calc(100dvh - ${inset})`;
        root.style.overflow = "hidden";
      }
      if (shell) {
        shell.style.height = "100%";
        shell.style.maxHeight = "100%";
        shell.style.minHeight = "0";
        shell.style.marginTop = "0";
      }
      if (panel) {
        panel.style.display = "flex";
        panel.style.flexDirection = "column";
        panel.style.minHeight = "0";
        panel.style.overflow = "hidden";
      }
      const pane = document.querySelector(".main-panel .scroll-body, .main-panel .pane");
      if (pane) {
        pane.style.flex = "1 1 auto";
        pane.style.minHeight = "0";
        pane.style.overflow = "auto";
      }
      const footer = [...document.querySelectorAll(".footer-bar")].find((el) => {
        if (el.closest("dialog")) return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 1 && rect.height > 1;
      });
      if (footer && panel) {
        const overflow = footer.getBoundingClientRect().bottom - (window.innerHeight - 2);
        if (overflow > 0) {
          const next = Math.max(240, panel.getBoundingClientRect().height - overflow);
          panel.style.height = `${next}px`;
          panel.style.maxHeight = `${next}px`;
        }
      }
    },
    { caption, lower: lower || "" },
  );
}

async function overlayClearsChrome(page) {
  return page.evaluate(() => {
    const overlaps = (a, b) => {
      if (!a || !b) return false;
      if (a.width < 1 || a.height < 1 || b.width < 1 || b.height < 1) return false;
      return !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom);
    };
    const inView = (rect) =>
      rect.top >= -1 && rect.left >= -1 && rect.bottom <= window.innerHeight + 1 && rect.right <= window.innerWidth + 1;
    const band = document.getElementById("demo-recorder-band");
    const bandRect = band && band.style.display !== "none" ? band.getBoundingClientRect() : null;
    const subtitle = document.querySelector(".header-meta");
    const footer = [...document.querySelectorAll(".footer-bar")].find((el) => {
      if (el.closest("dialog")) return false;
      const rect = el.getBoundingClientRect();
      return rect.width > 1 && rect.height > 1;
    });
    const disclaimerRe =
      /not a finding that the design complies|does not decide whether the design complies|does not confirm that the design complies/i;
    let disclaimer = null;
    let disclaimerArea = Infinity;
    for (const el of document.querySelectorAll("body *")) {
      if (el.closest("#demo-recorder-band")) continue;
      const text = (el.innerText || "").replace(/\s+/g, " ").trim();
      if (!disclaimerRe.test(text)) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) continue;
      const area = rect.width * rect.height;
      if (area < disclaimerArea) {
        disclaimer = el;
        disclaimerArea = area;
      }
    }
    const subtitleRect = subtitle?.getBoundingClientRect();
    const footerRect = footer?.getBoundingClientRect();
    const disclaimerRect = disclaimer?.getBoundingClientRect();
    const problems = [];
    if (subtitle && subtitleRect && subtitleRect.width > 1 && overlaps(bandRect, subtitleRect)) problems.push("the header subtitle");
    if (footer && footerRect && overlaps(bandRect, footerRect)) problems.push("the footer");
    if (disclaimer && disclaimerRect && overlaps(bandRect, disclaimerRect)) problems.push("the compliance disclaimer");
    if (subtitle && subtitleRect && subtitleRect.width > 1 && !inView(subtitleRect)) problems.push("the header subtitle is outside the frame");
    if (footer && footerRect && !inView(footerRect)) {
      problems.push(
        `the footer is outside the frame (${Math.round(footerRect.top)} to ${Math.round(footerRect.bottom)} px, viewport ${window.innerHeight} px)`,
      );
    }
    if (disclaimer && disclaimerRect && !inView(disclaimerRect)) problems.push("the compliance disclaimer is outside the frame");
    return {
      ok: problems.length === 0,
      reason: problems.length ? `The recorder band leaves app text hidden: ${problems.join("; ")}.` : "",
      subtitle: subtitle ? subtitle.textContent.replace(/\s+/g, " ").trim() : "",
      footer: footer ? footer.innerText.replace(/\s+/g, " ").trim() : "",
      disclaimer: disclaimer ? disclaimer.innerText.replace(/\s+/g, " ").trim() : "",
    };
  });
}

async function clearOverlay(page) {
  await overlay(page, { caption: "", lower: "" });
}

async function settle(page, api, lower, { holdMs, suffix, caption } = {}) {
  const label = exampleLabel(lower);
  await overlay(page, { caption: caption || "", lower: label });
  const chrome = await overlayClearsChrome(page);
  if (!chrome.ok) return { ok: false, reason: chrome.reason };
  if (chrome.subtitle) api.notes.push(`Header subtitle visible: ${chrome.subtitle}`);
  if (chrome.footer) api.notes.push(`Footer visible: ${chrome.footer}`);
  if (chrome.disclaimer) api.notes.push(`Compliance disclaimer visible: ${chrome.disclaimer}`);
  await sleep(holdMs ?? api.holdMs);
  const file = join(
    api.framesDir,
    `shot-${api.step.id.padStart(2, "0")}-${slug(api.step.title)}${suffix ? `-${suffix}` : ""}.png`,
  );
  await page.screenshot({ path: file });
  api.frames.push(file);
  return { ok: true };
}

async function goHash(page, hash) {
  await clearOverlay(page);
  const target = hash.startsWith("#") ? hash : `#${hash}`;
  await page.evaluate((next) => {
    if (location.hash !== next) location.hash = next;
  }, target);
  await sleep(350);
}

async function openReviewGaps(page, api) {
  const summary = page.locator("summary").filter({ hasText: "Review gaps" }).first();
  if (await visible(summary, 2500)) {
    const details = summary.locator("xpath=ancestor::details[1]");
    const isOpen = await details.evaluate((el) => el.open).catch(() => false);
    if (!isOpen) {
      await summary.scrollIntoViewIfNeeded().catch(() => {});
      await summary.click();
      await sleep(250);
    }
    return;
  }
  api.notes.push("Review gaps is not on this screen.");
}

async function showLedger(page, api) {
  const ledger = page.getByRole("heading", { name: "Fact ledger" }).first();
  if (!(await visible(ledger, 800))) {
    api.notes.push("Fact ledger is not on this screen.");
    return;
  }
  await ledger.scrollIntoViewIfNeeded().catch(() => {});
}

async function ensureRole(page, api, label) {
  const who = h1(page, "Who are you?");
  if (!(await visible(who, 700))) {
    const link = navLink(page, "Describe");
    if (await visible(link, 700)) {
      await link.click();
      await sleep(400);
    }
  }
  if (await visible(who, 700)) {
    api.state.sawWho = true;
    const button = roleButton(page, label);
    if (!(await visible(button, 1500))) {
      return { ok: false, reason: `The ${label} role button is not on Who are you?.` };
    }
    await button.click();
    if (!(await visible(describeHeading(page), 8000))) {
      return { ok: false, reason: `Choosing ${label} did not open the describe screen.` };
    }
    return { ok: true, mode: "role" };
  }
  if (await visible(describeHeading(page), 1500)) {
    return {
      ok: false,
      reason: "Who are you? is not on this build, so this case was not started over the fixture.",
    };
  }
  return { ok: false, reason: "Neither Who are you? nor the describe screen is on this build." };
}

async function fillIntake(page, api, spec) {
  const started = await ensureRole(page, api, spec.role);
  if (!started.ok) return started;
  const box = page.getByRole("textbox", { name: /What are you building\?|Describe your idea/ }).first();
  if (await visible(box, 2000)) await box.fill(spec.text);
  else api.notes.push("The description field was not found, so the script paragraph was not pasted.");
  const authority = page.getByLabel(/Which authority will review this/).first();
  if (await visible(authority, 800)) {
    try {
      await authority.selectOption({ label: spec.authority });
    } catch (error) {
      api.notes.push(`The authority select did not accept ${spec.authority}: ${error.message}`);
    }
  } else {
    api.notes.push("Which authority will review this? is not on this build.");
  }
  api.notes.push("Did not upload a PDF.");
  await sleep(500);
  await openReviewGaps(page, api);
  await showLedger(page, api);
  if (await visible(box, 500)) await box.scrollIntoViewIfNeeded().catch(() => {});
  api.state.caseOpen = true;
  return { ok: true, mode: "role", lower: spec.lower };
}

async function goDescribe(page) {
  if (await visible(describeHeading(page), 400)) return true;
  const nav = navLink(page, "Describe");
  if (await visible(nav, 800)) await nav.click();
  else await goHash(page, "/describe");
  return visible(describeHeading(page), 8000);
}

async function goCodeCheck(page) {
  const button = page.getByRole("button", { name: "Continue to code check" }).first();
  if (await visible(button, 800)) await button.click();
  else {
    const link = page.getByRole("link", { name: "Continue to code check" }).first();
    if (await visible(link, 800)) await link.click();
    else {
      const nav = navLink(page, "Code check");
      if (!(await visible(nav, 800))) return false;
      await nav.click();
    }
  }
  return visible(h1(page, "Code check"), 8000);
}

async function goSectionC(page, api) {
  const button = page.getByRole("button", { name: "Continue to Section C" }).first();
  if (await visible(button, 800)) await button.click();
  else {
    const link = page.getByRole("link", { name: "Continue to Section C" }).first();
    if (await visible(link, 800)) await link.click();
  }
  if (await visible(h1(page, /Section C/), 2500)) return true;
  const nav = navLink(page, "Section C");
  if (!(await visible(nav, 800))) return false;
  await nav.click();
  if (!(await visible(h1(page, /Section C/), 8000))) return false;
  if (api) api.notes.push("Continue to Section C did not leave Code check. Section C was opened from the sidebar.");
  return true;
}

async function goApplication(page, tabLabel) {
  const onApp = await visible(h1(page, "Application"), 400);
  if (!onApp) {
    const nav = navLink(page, "Application");
    if (!(await visible(nav, 800))) return false;
    await nav.click();
    if (!(await visible(h1(page, "Application"), 8000))) return false;
  }
  if (!tabLabel) return true;
  const tab = page
    .getByRole("navigation", { name: "Application sections" })
    .getByRole("link", { name: new RegExp(`^${escapeReg(tabLabel)}\\b`) })
    .first();
  if (!(await visible(tab, 1200))) return false;
  await tab.click();
  await sleep(350);
  return true;
}

async function answerNotSure(page, api) {
  const cards = page.locator("article").filter({ hasText: "Your words" });
  const count = await cards.count();
  const topics = [];
  let clicked = 0;
  for (let i = 0; i < count; i += 1) {
    const card = cards.nth(i);
    const topic = (await card.locator("h2").first().innerText().catch(() => "")).trim();
    if (topic) topics.push(topic);
    const button = card.getByRole("button", { name: "Not sure", exact: true });
    if (await visible(button, 500)) {
      await card.scrollIntoViewIfNeeded().catch(() => {});
      await button.click();
      clicked += 1;
    }
  }
  api.notes.push(
    count
      ? `Answered Not sure on ${clicked} Your words card(s)${topics.length ? `: ${topics.join("; ")}` : ""}. Did not answer Yes or No.`
      : "No Your words card is on this screen, so Not sure was not clicked.",
  );
  const openQ = page.getByText("Open question", { exact: true }).last();
  if (clicked && (await visible(openQ, 1000))) {
    await openQ.scrollIntoViewIfNeeded().catch(() => {});
    return true;
  }
  if (clicked) {
    api.notes.push("Not sure was clicked, but the Open question label was not on screen. That sentence was not invented.");
  }
  return false;
}

async function searchDivisionB(page, query, acceptId) {
  const box = page.getByLabel("Search Division B").first();
  if (!(await visible(box, 1000))) {
    return { note: "Search Division B is not on this build. No article id was typed in." };
  }
  await box.fill(query);
  const form = box.locator("xpath=ancestor::form[1]");
  const search = form.getByRole("button", { name: "Search", exact: true });
  if (!(await visible(search, 800))) {
    return { note: `The Search button for "${query}" is not on this screen. No article id was typed in.` };
  }
  await search.click();
  const finished = page
    .getByText(/\d+ provisions returned|No provisions returned|did not return|could not be reached|unreachable|Failed to fetch|Bad Gateway|ERR_/)
    .first();
  if (!(await visible(finished, 8000))) {
    return { note: `Search for "${query}" did not report a result. No article id was typed in.` };
  }
  const text = await page.locator("main").innerText();
  if (
    /did not return|unreachable|could not be reached|bad gateway|failed to fetch|err_/i.test(text) &&
    !/\d+ provisions returned/.test(text)
  ) {
    return {
      note: `Search for "${query}" did not return (no engine or code database). ${acceptId} was not typed in.`,
    };
  }
  const rows = page.locator("li").filter({ has: page.getByRole("button", { name: "Add to this check" }) });
  const count = await rows.count();
  let matched = null;
  const seen = [];
  for (let i = 0; i < count; i += 1) {
    const row = rows.nth(i);
    const idText = (await row.locator(".article-id").first().innerText().catch(() => "")).trim();
    if (idText) seen.push(idText);
    if (idText === acceptId) matched = row;
  }
  if (!matched) {
    return {
      note: `Search for "${query}" did not show a row whose id is ${acceptId}${seen.length ? ` (rows: ${seen.join(", ")})` : ""}. Nothing was added.`,
    };
  }
  await matched.getByRole("button", { name: "Add to this check" }).click();
  await sleep(400);
  const card = page
    .locator("article")
    .filter({ has: page.locator(".article-id", { hasText: new RegExp(`^${escapeReg(acceptId)}$`) }) })
    .last();
  const yes = card.getByRole("button", { name: "Yes", exact: true });
  if (await visible(yes, 1500)) await yes.click();
  else return { added: acceptId, note: `Added ${acceptId} from the returned rows. The Yes button was not on that card.` };
  return { added: acceptId, note: `Added ${acceptId} from the returned search rows and answered Yes on that card.` };
}

async function resetCase(page, api) {
  const button = page.getByRole("button", { name: "Reset case" }).first();
  if (!(await visible(button, 1500))) return false;
  await button.click();
  const confirm = page.getByRole("heading", { name: "Clear this case?" }).first();
  if (await visible(confirm, 800)) {
    await page.getByRole("button", { name: "Reset case", exact: true }).last().click();
  }
  await sleep(400);
  const who = await visible(h1(page, "Who are you?"), 4000);
  if (!who) return false;
  api.state.sawWho = true;
  api.state.caseOpen = false;
  api.state.caseC = false;
  api.state.caseA = false;
  const note = page.getByText("Cleared. Nothing from the previous case is kept.").first();
  if (await visible(note, 800)) {
    api.notes.push("Reset case showed: Cleared. Nothing from the previous case is kept.");
  } else {
    api.notes.push("Reset case returned to Who are you?. The cleared-note sentence was not on screen.");
  }
  return true;
}

async function noteCheckCompleteness(page, api) {
  const check = page.getByRole("button", { name: /Check completeness|Run pre-flight/ }).first();
  if (!(await visible(check, 800))) {
    api.notes.push("Neither Check completeness nor Run pre-flight is on this build. No PDF was downloaded.");
    return;
  }
  const disabled = await check.isDisabled();
  api.notes.push(
    disabled
      ? "Check completeness stays disabled."
      : "Check completeness is enabled.",
  );
  await check.scrollIntoViewIfNeeded().catch(() => {});
}

async function shot1(page, api) {
  await goHash(page, "/");
  const who = h1(page, "Who are you?");
  if (!(await visible(who, 2000))) {
    return skipped("Who are you? is not on this build. This checkout opens the describe screen on the fixture case.");
  }
  api.state.sawWho = true;
  api.notes.push("Try an example was left unclicked.");
  const frame = await settle(page, api, ALL_LOWER, { caption: "Who are you?" });
  if (!frame.ok) return skipped(frame.reason);
  return recorded();
}

async function shot2(page, api) {
  const filled = await fillIntake(page, api, CASES.C);
  if (!filled.ok) return skipped(filled.reason);
  if (!(await visible(describeHeading(page), 2000))) return skipped("The describe screen is not showing.");
  api.state.caseC = true;
  const pasted = page.getByText("0000 Example Crescent NW").first();
  if (await visible(pasted, 800)) await pasted.scrollIntoViewIfNeeded().catch(() => {});
  const frame = await settle(page, api, filled.lower, { caption: "Homebuilder paste" });
  if (!frame.ok) return skipped(frame.reason);
  return recorded();
}

async function shot3(page, api) {
  if (!api.state.sawWho) {
    return skipped("Who are you? is not on this build, so the manufacturer case cannot be started.");
  }
  if (!(await resetCase(page, api))) return skipped("Reset case is not available, so Case A was not started.");
  const filled = await fillIntake(page, api, CASES.A);
  if (!filled.ok || filled.mode !== "role") {
    return skipped(filled.reason || "Manufacturer did not open an empty describe screen.");
  }
  api.state.caseA = true;
  const pastedA = page.getByText("0000 Example Way NW").first();
  if (await visible(pastedA, 800)) await pastedA.scrollIntoViewIfNeeded().catch(() => {});
  const paste = await settle(page, api, CASES.A.lower, { suffix: "paste", caption: "Manufacturer paste" });
  if (!paste.ok) return skipped(paste.reason);
  if (!(await goCodeCheck(page))) return skipped("Code check did not open for the manufacturer case.");
  const sawOpen = await answerNotSure(page, api);
  if (!sawOpen) return failed("Not sure was not saved as an open question, so that beat was not recorded.");
  const frame = await settle(page, api, CASES.A.lower, {
    holdMs: Math.max(api.holdMs, OPEN_QUESTION_HOLD_MS),
    suffix: "open-question",
    caption: "Open question",
  });
  if (!frame.ok) return skipped(frame.reason);
  return recorded();
}

async function shot4(page, api) {
  if (!api.state.caseC) return skipped("Case C is not the open case, so the code-identification shot was not recorded.");
  if (!(await visible(h1(page, "Code check"), 400)) && !(await goCodeCheck(page))) {
    return skipped("Code check is not on this build.");
  }
  await answerNotSure(page, api);
  const search = await searchDivisionB(page, "bedroom window unobstructed", "9.9.10.1.(2)");
  api.notes.push(search.note);
  if (!search.added) {
    return skipped(
      "Search did not show a returned row for 9.9.10.1.(2). No article id was typed in, and Section C was not recorded over the offline sample.",
    );
  }
  const reference = page
    .locator("article")
    .filter({ hasText: search.added })
    .locator("summary")
    .filter({ hasText: "Code reference" })
    .first();
  if (await visible(reference, 800)) {
    await reference.click();
    api.notes.push("Opened Code reference on the row that was added.");
  } else api.notes.push("Code reference disclosure was not on the added row.");
  const searchBox = page.getByLabel("Search Division B").first();
  if (await visible(searchBox, 500)) await searchBox.scrollIntoViewIfNeeded().catch(() => {});
  const searchFrame = await settle(page, api, CASES.C.lower, { suffix: "search", caption: search.added });
  if (!searchFrame.ok) return skipped(searchFrame.reason);
  if (!(await goSectionC(page, api))) return skipped("Section C is not on this build.");
  const row = page.getByRole("row").filter({ hasText: search.added }).first();
  if (!(await visible(row, 1500))) {
    return skipped(`Section C has no row for ${search.added}. The offline sample was not recorded as the lookup.`);
  }
  await row.scrollIntoViewIfNeeded().catch(() => {});
  api.notes.push("Ranked list still is not in this build. Omitted. No ranked caption was added.");
  api.notes.push("Benchmark card is not in this build. Omitted.");
  api.notes.push("Eval still is not in this build. Omitted. #/accuracy was not opened.");
  const frame = await settle(page, api, CASES.C.lower, { caption: search.added });
  if (!frame.ok) return skipped(frame.reason);
  return recorded();
}

async function shot5(page, api) {
  if (!api.state.caseC) return skipped("Case C is not the open case, so Section D was not recorded.");
  if (!(await goApplication(page, "Alternative path"))) {
    return skipped("Alternative path is not an application tab on this build.");
  }
  const risk = page.getByLabel("Risk assessment").first();
  if (await visible(risk, 800)) await risk.scrollIntoViewIfNeeded().catch(() => {});
  else api.notes.push("Risk assessment is not on the alternative path.");
  api.notes.push("Process fields were left empty. Nothing was typed into them.");
  await openReviewGaps(page, api);
  const riskEmpty = (await visible(risk, 400)) && (await risk.inputValue().catch(() => "x")) === "";
  const altFrame = await settle(page, api, CASES.C.lower, {
    suffix: "alternative-path",
    caption: riskEmpty ? "Risk assessment empty" : "Alternative path",
  });
  if (!altFrame.ok) return skipped(altFrame.reason);
  if (!(await goApplication(page, "Section D"))) return skipped("Section D is not an application tab on this build.");
  const heading = page.getByRole("heading", { name: "Section D and professional screening" }).first();
  if (!(await visible(heading, 5000))) {
    return skipped("The Section D tab opened without the professional screening heading.");
  }
  const limit = page.getByText(LIMIT_LINE).first();
  if (!(await visible(limit, 1000))) {
    return skipped(
      `The limit line "${LIMIT_LINE}" is not on screen. The shot was not recorded, and the line was not invented.`,
    );
  }
  api.notes.push("The on-screen limit line is visible. It was not typed by the recorder.");
  await limit.scrollIntoViewIfNeeded().catch(() => {});
  const frame = await settle(page, api, CASES.C.lower, { suffix: "section-d", caption: "Does not write the evidence" });
  if (!frame.ok) return skipped(frame.reason);
  return recorded();
}

async function openOfficerReview(page, api) {
  const nav = navLink(page, "Officer review");
  if (!(await visible(nav, 1500))) return { ok: false, reason: "Officer review is not in the navigation." };
  const href = (await nav.getAttribute("href")) || "#/officer";
  await clearOverlay(page);
  await page.evaluate((next) => {
    location.hash = next.startsWith("#") ? next : `#${next}`;
  }, href);
  await sleep(200);
  const title = h1(page, "Officer review");
  if (!(await visible(title, 8000))) return { ok: false, reason: "Officer review did not open." };
  if (await visible(page.getByRole("heading", { name: "Not built yet", exact: true }), 500)) {
    return { ok: false, reason: "Officer review is the Not built yet placeholder." };
  }
  if (await visible(h1(page, "Who are you?"), 400)) {
    return { ok: false, reason: "Officer review sent the browser back to Who are you?." };
  }
  if (await visible(page.getByText("does not open the sample package").first(), 800)) {
    return {
      ok: false,
      reason: "Officer review says this application does not open the sample package. The open-application review was not on screen.",
    };
  }
  const loading = page.getByText("Reviewing your application…").first();
  if (await visible(loading, 800)) {
    await page
      .getByRole("heading", { name: "Documents", exact: true })
      .first()
      .waitFor({ state: "visible", timeout: 10000 })
      .catch(() => {});
  }
  const seen = [];
  for (const name of OFFICER_HEADINGS) {
    const heading = page.getByRole("heading", { name, exact: true }).first();
    if (await visible(heading, 400)) seen.push(name);
  }
  api.notes.push(
    seen.length
      ? `Officer sections on screen: ${seen.join(", ")}.`
      : "Officer section headings were not on screen.",
  );
  const intro = page.getByText(OFFICER_INTRO, { exact: true }).first();
  if (!(await visible(intro, 1500))) {
    return {
      ok: false,
      reason: `Officer review opened without the open-application line: "${OFFICER_INTRO}"`,
    };
  }
  const copy = page.getByRole("button", { name: "Copy request", exact: true }).first();
  if ((await copy.count()) < 1) {
    return { ok: false, reason: "Officer review is open, and the Copy request button is not on screen." };
  }
  api.notes.push("Copy request is on screen. No package version control was clicked.");
  return { ok: true };
}

async function shot6(page, api) {
  if (!api.state.caseOpen) {
    return pending("No case is open, so Officer review does not show the open application.");
  }
  const opened = await openOfficerReview(page, api);
  if (!opened.ok) return pending(opened.reason);
  const intro = page.getByText(OFFICER_INTRO, { exact: true }).first();
  await intro.scrollIntoViewIfNeeded().catch(() => {});
  const frame = await settle(page, api, CASES.A.lower, { caption: "Does not decide whether the design complies" });
  if (!frame.ok) return pending(frame.reason);
  const copy = page.getByRole("button", { name: "Copy request", exact: true }).first();
  await copy.scrollIntoViewIfNeeded().catch(() => {});
  if (!(await visible(copy, 1000))) {
    return pending("Copy request is on the officer page and was not in the frame.");
  }
  const requestFrame = await settle(page, api, CASES.A.lower, { suffix: "request", caption: "Copy request" });
  if (!requestFrame.ok) return pending(requestFrame.reason);
  return recorded();
}

async function closeDialog(page) {
  for (let i = 0; i < 3; i += 1) {
    const open = page.locator("dialog[open]");
    if ((await open.count()) < 1) return;
    const close = open.getByRole("button", { name: "Close", exact: true }).first();
    if (await visible(close, 300)) await close.click().catch(() => {});
    if ((await page.locator("dialog[open]").count()) > 0) await page.keyboard.press("Escape").catch(() => {});
    await sleep(150);
  }
}

async function downloadDraftPdf(page, api, suffix, lower) {
  const check = page.getByRole("button", { name: "Check completeness", exact: true }).first();
  if (!(await visible(check, 1500))) {
    return { ok: false, reason: "Check completeness is not on screen, so the draft PDF step was not recorded." };
  }
  await check.click();
  try {
    const dialog = page.locator("dialog[open]").last();
    await dialog.waitFor({ state: "visible", timeout: 5000 }).catch(() => {});
    await page
      .waitForFunction(() => {
        const open = document.querySelector("dialog[open]");
        if (!open) return false;
        return !/Saving and reviewing/.test(open.innerText || "");
      }, { timeout: 15000 })
      .catch(() => {});
    const draft = page.getByRole("button", { name: "Download draft PDF", exact: true }).first();
    const enabled = await draft.isEnabled({ timeout: 1000 }).catch(() => false);
    if (!enabled) {
      const text = (await dialog.innerText().catch(() => "")).replace(/\s+/g, " ").trim();
      return {
        ok: false,
        reason: text
          ? `Download draft PDF was not available. On screen: ${text.slice(0, 280)}`
          : "Check completeness did not open a dialog with Download draft PDF.",
      };
    }
    const downloadPromise = page.waitForEvent("download", { timeout: 25000 }).catch(() => null);
    await draft.click();
    const started = page.getByText(/Download started:/).first();
    const draftNote = page.getByText("This draft may have missing or unconfirmed information.").first();
    const dialogLine = page
      .getByText("This is an administrative completeness check. It does not decide whether the design complies or is safe.")
      .first();
    const failedLine = page
      .getByText(/could not be prepared|Online review unavailable|application PDF form is unavailable|The PDF was blocked/)
      .first();
    await Promise.race([
      started.waitFor({ state: "visible", timeout: 20000 }).catch(() => {}),
      draftNote.waitFor({ state: "visible", timeout: 20000 }).catch(() => {}),
      failedLine.waitFor({ state: "visible", timeout: 20000 }).catch(() => {}),
    ]);
    const download = await downloadPromise;
    if (download) {
      api.notes.push(`Draft PDF download started: ${download.suggestedFilename()}.`);
      await download.path().catch(() => {});
    }
    const sawDraft = (await visible(started, 500)) || (await visible(draftNote, 500));
    if (!sawDraft) {
      const status = await failedLine.innerText().catch(() => "");
      return {
        ok: false,
        reason: status
          ? `Download draft PDF did not start. On screen: ${status.replace(/\s+/g, " ").trim()}`
          : "Download draft PDF did not show Download started.",
      };
    }
    if (await visible(dialogLine, 800)) await dialogLine.scrollIntoViewIfNeeded().catch(() => {});
    api.notes.push("The draft PDF dialog is on screen. Download application PDF was not clicked.");
    const frame = await settle(page, api, lower, { suffix: `${suffix}-draft`, caption: "Download draft PDF" });
    if (!frame.ok) return { ok: false, reason: frame.reason };
    return { ok: true };
  } finally {
    await closeDialog(page);
  }
}

async function authorityFrame(page, api, spec, suffix) {
  if (!(await goDescribe(page))) return skipped("The describe screen is not available for the authority select.");
  const authority = page.getByLabel(/Which authority will review this/).first();
  if (!(await visible(authority, 800))) {
    return failed("Which authority will review this? is not visible.");
  }
  await authority.scrollIntoViewIfNeeded().catch(() => {});
  const label = await authority.evaluate((el) => el.selectedOptions?.[0]?.label?.trim() || "").catch(() => "");
  if (!label || label === "Select…") return failed("The authority select is visible and nothing is selected.");
  api.notes.push(`Authority select shows "${label}".`);
  const describeFrame = await settle(page, api, spec.lower, { suffix: `${suffix}-authority`, caption: `Authority · ${label}` });
  if (!describeFrame.ok) return skipped(describeFrame.reason);
  if (!(await goApplication(page, "Alternative path"))) {
    return skipped("The application screen is not on this build for the gaps frame.");
  }
  await openReviewGaps(page, api);
  await noteCheckCompleteness(page, api);
  const owner = page.getByText("Owner missing", { exact: true }).first();
  const gapsCaption = (await visible(owner, 500)) ? "Owner missing" : "Gaps open";
  if (await visible(owner, 400)) await owner.scrollIntoViewIfNeeded().catch(() => {});
  const appFrame = await settle(page, api, spec.lower, { suffix: `${suffix}-application`, caption: gapsCaption });
  if (!appFrame.ok) return skipped(appFrame.reason);
  const draft = await downloadDraftPdf(page, api, suffix, spec.lower);
  if (!draft.ok) return skipped(draft.reason);
  return recorded();
}

async function shot7(page, api) {
  if (api.frame === "A") {
    if (!api.state.caseA) return skipped("Case A is not the open case, so its authority frame was not recorded.");
    api.notes.push("Case A authority frame.");
    return authorityFrame(page, api, CASES.A, "case-a");
  }
  if (!api.state.caseC) return skipped("Case C is not the open case, so its authority frame was not recorded.");
  api.notes.push("Case C authority frame.");
  return authorityFrame(page, api, CASES.C, "case-c");
}

export const STEPS = [
  { id: "1", title: "Three applicants (0:18)", route: "#/", run: shot1 },
  { id: "2", title: "Homebuilder paste (0:10)", route: "#/describe", run: shot2 },
  { id: "3", title: "Not sure (0:23)", route: "#/", run: shot3 },
  { id: "4", title: "Code identification (0:45)", route: "#/section-c", run: shot4 },
  { id: "5", title: "Section D, then the limit (0:24 + 0:08)", route: "#/application?tab=alt", run: shot5 },
  { id: "6", title: "Officer review of the open application (0:36)", route: "#/officer", run: shot6 },
  { id: "7", title: "Authority, gaps open, then the draft variance-form PDF (0:16)", route: "#/describe", run: shot7 },
];

function mergeParts(step, parts) {
  const failed = parts.filter((part) => part.status !== "recorded");
  const notes = parts.flatMap((part) => part.notes || []);
  const frames = parts.flatMap((part) => part.frames || []);
  if (failed.length) {
    const hard = failed.some((part) => part.status === "failed");
    return {
      id: step.id,
      title: step.title,
      route: step.route,
      status: hard ? "failed" : "skipped",
      reason: failed.map((part) => part.reason).filter(Boolean).join(" "),
      notes,
      frames,
    };
  }
  return { id: step.id, title: step.title, route: step.route, status: "recorded", notes, frames };
}

export async function runWalkthrough(page, opts) {
  const apiBase = {
    holdMs: opts.holdMs ?? 1600,
    framesDir: opts.framesDir,
    state: { sawWho: false, caseOpen: false, caseC: false, caseA: false },
  };
  const stepById = new Map(STEPS.map((step) => [step.id, step]));

  async function exec(id, extra) {
    await clearOverlay(page);
    const step = stepById.get(id);
    const notes = [];
    const frames = [];
    const api = { ...apiBase, step, notes, frames, ...extra };
    try {
      const outcome = await step.run(page, api);
      return { id: step.id, title: step.title, route: step.route, notes, frames, ...outcome };
    } catch (error) {
      return {
        id: step.id,
        title: step.title,
        route: step.route,
        status: "skipped",
        reason: `Step threw and was skipped: ${error instanceof Error ? error.message : String(error)}`,
        notes,
        frames,
      };
    }
  }

  // Script order: 1, 2, 4, 5, 7 (Case C), reset inside 3, 7 (Case A), 6.
  const shot1Result = await exec("1");
  const shot2Result = await exec("2");
  const shot4Result = await exec("4");
  const shot5Result = await exec("5");
  const shot7c = await exec("7", { frame: "C" });
  const shot3Result = await exec("3");
  const shot7a = await exec("7", { frame: "A" });
  const shot6Result = await exec("6");
  const shot7Result = mergeParts(stepById.get("7"), [shot7c, shot7a]);

  return [shot1Result, shot2Result, shot3Result, shot4Result, shot5Result, shot6Result, shot7Result].sort(
    (a, b) => Number(a.id) - Number(b.id),
  );
}

/** Deck slots from the screenshot list. Filenames are the PNG basenames. */
export const DECK_STILLS = [
  { id: "shot-s08-roles", file: "shot-s08-roles.png" },
  { id: "shot-s02-describe", file: "shot-s02-describe.png" },
  { id: "shot-s03-not-sure", file: "shot-s03-not-sure.png" },
  { id: "shot-s04-search", file: "shot-s04-search.png" },
  { id: "shot-s04-benchmark", file: "shot-s04-benchmark.png" },
  { id: "shot-s05-eval", file: "shot-s05-eval.png" },
  { id: "shot-s06-section-d", file: "shot-s06-section-d.png" },
  { id: "shot-s07-officer", file: "shot-s07-officer.png" },
  { id: "shot-s09-locked", file: "shot-s09-locked.png" },
  { id: "shot-s09-scc-form", file: "shot-s09-scc-form.png" },
];

function pngSize(buffer) {
  if (buffer.length < 24 || buffer.readUInt32BE(12) !== 0x49484452) return { width: 0, height: 0 };
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}

async function saveStill(page, api, lower, filePath) {
  const label = exampleLabel(lower);
  await overlay(page, { caption: "", lower: label });
  const chrome = await overlayClearsChrome(page);
  if (!chrome.ok) return { ok: false, reason: chrome.reason };
  if (chrome.subtitle) api.notes.push(`Header subtitle visible: ${chrome.subtitle}`);
  if (chrome.footer) api.notes.push(`Footer visible: ${chrome.footer}`);
  if (chrome.disclaimer) api.notes.push(`Compliance disclaimer visible: ${chrome.disclaimer}`);
  const screenText = await page.locator("body").innerText().catch(() => "");
  if ((chrome.footer || "").includes("Online review unavailable") || screenText.includes("Online review unavailable")) {
    return {
      ok: false,
      reason: 'The footer reads "Online review unavailable". The still was not captured.',
    };
  }
  await sleep(300);
  const buffer = await page.screenshot({ type: "png" });
  const size = pngSize(buffer);
  if (size.width !== 1440 || size.height !== 900) {
    return { ok: false, reason: `Screenshot was ${size.width}×${size.height}, not 1440×900.` };
  }
  writeFileSync(filePath, buffer);
  return { ok: true, width: size.width, height: size.height };
}

export async function runDeckStills(page, opts) {
  const outDir = opts.outDir;
  const sourceBranch = opts.sourceBranch || "unknown";
  const shortSha = opts.sourceSha ? String(opts.sourceSha).slice(0, 7) : "unknown";
  const date = String(opts.recordedAt || new Date().toISOString()).slice(0, 10);
  const source = `${sourceBranch} @ ${shortSha}`;
  const api = {
    holdMs: 400,
    framesDir: outDir,
    step: { id: "0", title: "still" },
    notes: [],
    frames: [],
    state: { sawWho: false, caseOpen: false, caseC: false, caseA: false },
  };
  const byId = new Map();
  const apiStatuses = new Set();
  page.on("response", (response) => {
    try {
      const url = new URL(response.url());
      const apiCall = url.port === "8000" || url.pathname === "/api" || url.pathname.startsWith("/api/");
      if (apiCall) apiStatuses.add(response.status());
    } catch {
      // A malformed response URL is not an engine status.
    }
  });

  function drop(id) {
    const slot = DECK_STILLS.find((item) => item.id === id);
    const filePath = join(outDir, slot.file);
    if (existsSync(filePath)) rmSync(filePath);
  }

  function finish(id, outcome) {
    const slot = DECK_STILLS.find((item) => item.id === id);
    if (outcome.status !== "captured") drop(id);
    byId.set(id, {
      id,
      file: slot.file,
      notes: outcome.notes || [],
      ...outcome,
    });
  }

  async function capture(id, lower, caseName, onScreen) {
    if (opts.engineSearchStatus === 503 || apiStatuses.has(503)) {
      return skip(id, "An /api call returned 503. The still was not captured.");
    }
    const slot = DECK_STILLS.find((item) => item.id === id);
    const saved = await saveStill(page, api, lower, join(outDir, slot.file));
    const notes = [...api.notes];
    api.notes.length = 0;
    if (!saved.ok) return finish(id, { status: "pending", reason: saved.reason, notes });
    const caseLabel = caseName || "unspecified";
    const caption = `scripted demo capture, ${source}`;
    return finish(id, {
      status: "captured",
      width: saved.width,
      height: saved.height,
      notes,
      caption,
      provenance: caption,
      source,
      case: caseLabel,
      date,
      onScreen: onScreen || "",
    });
  }

  function skip(id, reason) {
    const notes = [...api.notes];
    api.notes.length = 0;
    return finish(id, { status: "pending", reason, notes });
  }

  try {
    await goHash(page, "/");
    const who = h1(page, "Who are you?");
    const roles = ["Manufacturer", "General contractor", "Homebuilder"];
    const missingRole = [];
    if (await visible(who, 2000)) {
      api.state.sawWho = true;
      for (const label of roles) {
        if (!(await visible(roleButton(page, label), 1000))) missingRole.push(label);
      }
    }
    if (!api.state.sawWho) {
      skip("shot-s08-roles", "Who are you? is not on this build.");
    } else if (missingRole.length) {
      skip("shot-s08-roles", `Role buttons not on screen: ${missingRole.join(", ")}.`);
    } else {
      api.notes.push("Try an example was left unclicked.");
      await capture("shot-s08-roles", ALL_LOWER, "All three");
    }

    const filledC = api.state.sawWho ? await fillIntake(page, api, CASES.C) : { ok: false, reason: "Who are you? is not on this build, so Case C was not pasted." };
    if (!filledC.ok) {
      skip("shot-s02-describe", filledC.reason);
    } else {
      api.state.caseC = true;
      const body = await page.locator("main").innerText();
      if (!body.includes("0000 Example Crescent")) {
        skip("shot-s02-describe", "The Case C paragraph is not in the description. The still was not saved.");
      } else {
        const gaps = ["Owner", "Mailing address", "Legal description"].filter((label) => body.includes(label));
        api.notes.push(gaps.length ? `Missing-item text on screen: ${gaps.join(", ")}.` : "Owner, mailing address, and legal description were not named on this screen.");
        if (!body.includes("Review gaps")) {
          skip("shot-s02-describe", "Review gaps is not on this screen. The describe still was not saved.");
        } else {
          const summary = page.locator("summary").filter({ hasText: "Review gaps" }).first();
          if (await visible(summary, 500)) await summary.scrollIntoViewIfNeeded().catch(() => {});
          await page
            .getByText(/Online administrative review finished|Online review unavailable/)
            .first()
            .waitFor({ timeout: 10000 })
            .catch(() => {});
          await capture("shot-s02-describe", CASES.C.lower, "Case C");
        }
      }
    }

    if (!api.state.caseC) {
      skip("shot-s04-search", "Case C is not open, so the bedroom-window search was not run.");
    } else {
      if (opts.engineSearchStatus === 503) {
        skip("shot-s04-search", "Code search returned 503. No article id was typed in, and the Section C lookup was not drawn.");
      } else if (!(await visible(h1(page, "Code check"), 400)) && !(await goCodeCheck(page))) {
        skip("shot-s04-search", "Code check is not on this build.");
      } else {
        await answerNotSure(page, api);
        const search = await searchDivisionB(page, "bedroom window unobstructed", "9.9.10.1.(2)");
        api.notes.push(search.note);
        if (!search.added) {
          skip(
            "shot-s04-search",
            "Search did not show a returned row for 9.9.10.1.(2). No article id was typed in, and the Section C lookup was not drawn.",
          );
        } else if (!(await goSectionC(page, api))) {
          skip("shot-s04-search", "Section C is not on this build, so the lookup still was not saved.");
        } else {
          const row = page.getByRole("row").filter({ hasText: search.added }).first();
          if (!(await visible(row, 1500))) {
            skip("shot-s04-search", `Section C has no row for ${search.added}. The lookup still was not drawn.`);
          } else {
            await row.scrollIntoViewIfNeeded().catch(() => {});
            await capture("shot-s04-search", CASES.C.lower, "Case C");
          }
        }
      }
    }

    skip(
      "shot-s04-benchmark",
      "The ranked list and benchmark card are not in this app build. The still was not drawn.",
    );
    skip(
      "shot-s05-eval",
      "The eval still is not a screen in this build. #/accuracy was not opened, and the figures were not drawn.",
    );

    if (!api.state.caseC) {
      skip("shot-s09-locked", "Case C is not open, so the application still was not captured.");
    } else if (!(await goApplication(page))) {
      skip("shot-s09-locked", "The application screen is not on this build.");
    } else {
      await openReviewGaps(page, api);
      const check = page.getByRole("button", { name: /Check completeness|Run pre-flight/ }).first();
      if (!(await visible(check, 800))) {
        skip("shot-s09-locked", "Check completeness is not on this build. The locked still was not drawn.");
      } else if (!(await check.isDisabled())) {
        skip(
          "shot-s09-locked",
          "Check completeness is enabled while gaps are open. The disabled control is not on this build, and the still was not faked.",
        );
      } else {
        api.notes.push("Check completeness is disabled. It was not clicked. No PDF was downloaded.");
        await check.scrollIntoViewIfNeeded().catch(() => {});
        await capture("shot-s09-locked", CASES.C.lower, "Case C");
      }
    }

    await captureSectionD();

    if (!api.state.sawWho) {
      skip("shot-s03-not-sure", "Who are you? is not on this build, so the manufacturer case cannot be started.");
    } else if (!(await resetCase(page, api))) {
      skip("shot-s03-not-sure", "Reset case is not available, so the Not sure still was not captured.");
    } else {
      const filledA = await fillIntake(page, api, CASES.A);
      if (!filledA.ok) {
        skip("shot-s03-not-sure", filledA.reason);
      } else {
        api.state.caseA = true;
        if (!(await goCodeCheck(page))) {
          skip("shot-s03-not-sure", "Code check did not open for the manufacturer case.");
        } else {
          await answerNotSure(page, api);
          const cards = page.locator("article").filter({ hasText: "Your words" });
          const count = await cards.count();
          let pressed = 0;
          for (let i = 0; i < count; i += 1) {
            const button = cards.nth(i).getByRole("button", { name: "Not sure", exact: true });
            if ((await button.getAttribute("aria-pressed").catch(() => "")) === "true") pressed += 1;
          }
          if (pressed < 2) {
            skip(
              "shot-s03-not-sure",
              `Not sure is pressed on ${pressed} Your words card(s), not two. The still was not saved.`,
            );
          } else {
            await cards.first().scrollIntoViewIfNeeded().catch(() => {});
            await capture("shot-s03-not-sure", CASES.A.lower, "Case A");
          }
        }
      }
    }

    async function captureOfficer(id) {
      if (!api.state.caseA) {
        skip(id, "Case A is not open, so Officer review of the open application was not captured.");
        return;
      }
      const opened = await openOfficerReview(page, api);
      if (!opened.ok) {
        skip(id, opened.reason);
        return;
      }
      const intro = page.getByText(OFFICER_INTRO, { exact: true }).first();
      if (!(await visible(intro, 1500))) {
        skip(id, "The open-application review line is not on screen. The officer still was not captured.");
        return;
      }
      await intro.scrollIntoViewIfNeeded().catch(() => {});
      api.notes.push("Officer review of the open Case A application.");
      await capture(id, CASES.A.lower, "Case A");
    }

    async function captureSectionD() {
      const id = "shot-s06-section-d";
      if (!api.state.caseC) {
        skip(id, "Case C is not the open case, so Section D was not captured.");
        return;
      }
      if (!(await goApplication(page, "Section D"))) {
        skip(id, "Section D is not an application tab on this build.");
        return;
      }
      const heading = page.getByRole("heading", { name: "Section D and professional screening" }).first();
      if (!(await visible(heading, 2500))) {
        skip(id, "The Section D tab opened without the professional screening heading. The still was not captured.");
        return;
      }
      const tab = page
        .getByRole("navigation", { name: "Application sections" })
        .getByRole("link", { name: /^Section D\b/ })
        .first();
      if ((await tab.getAttribute("aria-current").catch(() => "")) !== "page") {
        skip(id, "The current application tab is not Section D. The still was not captured.");
        return;
      }
      const limit = page.getByText(LIMIT_LINE).first();
      if (!(await visible(limit, 8000))) {
        skip(
          id,
          `The limit line "${LIMIT_LINE}" is not on screen. The shot was not recorded, and the line was not invented.`,
        );
        return;
      }
      await Promise.all([heading, limit].map((locator) => locator.evaluate((el) => {
        const pane = el.closest(".scroll-body");
        if (!pane) return;
        const paneRect = pane.getBoundingClientRect();
        const rect = el.getBoundingClientRect();
        if (rect.top < paneRect.top) pane.scrollTop -= paneRect.top - rect.top + 8;
        else if (rect.bottom > paneRect.bottom) pane.scrollTop += rect.bottom - paneRect.bottom + 8;
      }).catch(() => {})));
      if (!(await visible(heading, 500)) || !(await visible(limit, 500))) {
        skip(id, "The Section D heading or the limit line is outside the frame. The still was not captured.");
        return;
      }
      api.notes.push("Section D tab is current. The recommendations limit line is on screen.");
      await capture(id, CASES.C.lower, "Case C");
    }

    await captureOfficer("shot-s07-officer");

    skip(
      "shot-s09-scc-form",
      "The filled SCC form is an engine PDF. Check completeness was not clicked, so the form was not captured.",
    );
  } catch (error) {
    const reason = `Stills stopped: ${error instanceof Error ? error.message : String(error)}`;
    for (const slot of DECK_STILLS) {
      if (!byId.has(slot.id)) finish(slot.id, { status: "pending", reason, notes: [] });
    }
  }

  return DECK_STILLS.map((slot) => byId.get(slot.id) || { id: slot.id, file: slot.file, status: "pending", reason: "Not reached.", notes: [] });
}
