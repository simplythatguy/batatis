import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import * as calendar from "./calendarDate.ts";
import { addMonths, formatDay, formatLong, formatMonth, monthGrid, moveFocus, parseIso, toIso, todayIn } from "./calendarDate.ts";

const day = (iso: string) => {
  const d = parseIso(iso);
  assert.ok(d, iso);
  return d;
};

test("the stored answer stays YYYY-MM-DD; anything else is not read as a date", () => {
  assert.deepEqual(parseIso("2026-10-25"), { year: 2026, month: 10, day: 25 });
  assert.deepEqual(parseIso(" 2028-02-29 "), { year: 2028, month: 2, day: 29 });
  for (const v of ["", "2026-02-29", "2026-13-01", "2026-00-10", "2026-1-5", "20261025", "October 25, 2026", "25/10/2026"]) {
    assert.equal(parseIso(v), null, v);
  }
  assert.equal(toIso({ year: 2026, month: 3, day: 7 }), "2026-03-07");
  assert.equal(toIso(day("0999-01-01")), "0999-01-01", "early years are not mapped to 19xx");
  assert.deepEqual(todayIn(new Date(2026, 9, 25, 23, 59)), { year: 2026, month: 10, day: 25 }, "today is the local day");
});

test("a month is six full weeks from the Sunday on or before the 1st", () => {
  const october = monthGrid(2026, 10);
  assert.equal(october.length, 6);
  assert.ok(october.every((w) => w.length === 7));
  assert.deepEqual(october[0].map(toIso), ["2026-09-27", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03"]);
  assert.equal(toIso(october[5][6]), "2026-11-07");
  assert.equal(toIso(monthGrid(2026, 2)[0][0]), "2026-02-01", "a month that starts on Sunday starts the grid");
});

test("calendar keys move by day, week, week edge, month and year", () => {
  const move = (iso: string, key: string, shift = false) => {
    const next = moveFocus(day(iso), key, shift);
    return next && toIso(next);
  };
  assert.equal(move("2026-10-31", "ArrowRight"), "2026-11-01");
  assert.equal(move("2026-10-01", "ArrowLeft"), "2026-09-30");
  assert.equal(move("2026-10-03", "ArrowUp"), "2026-09-26");
  assert.equal(move("2026-10-28", "ArrowDown"), "2026-11-04");
  assert.equal(move("2026-10-28", "Home"), "2026-10-25");
  assert.equal(move("2026-10-28", "End"), "2026-10-31");
  assert.equal(move("2026-03-31", "PageUp"), "2026-02-28", "a shorter month takes its last day");
  assert.equal(move("2028-03-31", "PageUp"), "2028-02-29");
  assert.equal(move("2026-12-15", "PageDown"), "2027-01-15");
  assert.equal(move("2028-02-29", "PageUp", true), "2027-02-28");
  assert.equal(move("2026-10-25", "PageDown", true), "2027-10-25");
  for (const key of ["Enter", " ", "Escape", "Tab", "a"]) assert.equal(move("2026-10-25", key), null, key);
  assert.equal(toIso(addMonths(day("2026-01-31"), 1)), "2026-02-28");
});

test("dates read in words", () => {
  assert.equal(formatLong(day("2026-10-25")), "October 25, 2026");
  assert.equal(formatMonth(day("2026-10-25")), "October 2026");
  assert.equal(formatDay(day("2026-10-25")), "Sunday, October 25, 2026");
});

/* —— The component, rendered without a browser —— */

const cls = (n): string => String(n?.props?.className ?? "");
const days = (tree) => nodes(tree, (n) => cls(n).split(" ").includes("cf-dp-day"));
const popover = (tree) => nodes(tree, (n) => cls(n).includes("cf-dp-pop"))[0];
const buttonNamed = (tree, name: string) => nodes(tree, (n) => n.type === "button" && text(n).trim() === name)[0];
const event = () => {
  const calls: string[] = [];
  return { calls, e: (key = "") => ({ key, shiftKey: false, metaKey: false, ctrlKey: false, altKey: false, preventDefault: () => calls.push("preventDefault"), stopPropagation: () => calls.push("stopPropagation") }) };
};

async function picker(value: string) {
  const changes: string[] = [];
  const listeners: string[] = [];
  const target = { addEventListener: (type: string) => listeners.push(`+${type}`), removeEventListener: (type: string) => listeners.push(`-${type}`) };
  const h = await componentHarness(new URL("./DatePicker.tsx", import.meta.url), "DatePicker", {
    "./calendarDate": calendar,
    "./icons": { Icon24: "Icon24" },
  }, { document: target, window: target });
  const props = { id: "field-date", label: "Date of request", value, onChange: (v: string) => changes.push(v) };
  return { h, changes, listeners, props, render: () => h.render(props) };
}

test("an empty date stays empty: opening, moving and closing the calendar answer nothing", async () => {
  const p = await picker("");
  let tree = await p.render();
  const trigger = nodes(tree, (n) => n.props?.id === "field-date")[0];
  assert.equal(trigger.type, "button");
  assert.equal(trigger.props.type, "button");
  assert.equal(trigger.props["aria-label"], "Date of request: Pick a date");
  assert.equal(trigger.props["aria-haspopup"], "dialog");
  assert.equal(trigger.props["aria-expanded"], false);
  assert.ok(cls(trigger).includes("cf-uline"), "the field reads like the other underline answers");
  assert.ok(nodes(tree, (n) => cls(n).includes("cf-dp-value is-empty")).length === 1, "the placeholder is drawn quiet");
  assert.equal(popover(tree), undefined, "closed until asked");

  trigger.props.onClick();
  tree = await p.render();
  const pop = popover(tree);
  assert.ok(pop, "the trigger opens the calendar");
  assert.equal(nodes(tree, (n) => n.props?.id === "field-date")[0].props["aria-expanded"], true);
  assert.deepEqual(days(tree).filter((n) => n.props.tabIndex === 0).map((n) => n.props["data-date"]), [toIso(todayIn(new Date()))], "with no answer, today holds focus");
  assert.equal(days(tree).filter((n) => cls(n).includes("is-picked")).length, 0, "nothing is chosen yet");
  assert.equal(buttonNamed(tree, "Clear"), undefined, "nothing to clear");

  nodes(tree, (n) => n.props?.["aria-label"] === "Next month")[0].props.onClick();
  tree = await p.render();
  const ev = event();
  nodes(tree, (n) => n.props?.role === "grid")[0].props.onKeyDown(ev.e("ArrowRight"));
  tree = await p.render();
  popover(tree).props.onKeyDown(ev.e("Escape"));
  tree = await p.render();
  assert.equal(popover(tree), undefined, "Escape closes");
  assert.deepEqual(ev.calls, ["preventDefault", "preventDefault", "stopPropagation"], "handled keys are claimed so the deck and page ignore them");
  assert.deepEqual(p.changes, [], "the answer is still empty");
  p.h.unmount();
});

test("the calendar is a dialog with a labelled grid, a .cf-pop the question deck leaves alone", async () => {
  const p = await picker("2026-10-25");
  let tree = await p.render();
  assert.equal(text(nodes(tree, (n) => cls(n).includes("cf-dp-value"))[0]), "October 25, 2026");
  assert.equal(nodes(tree, (n) => n.props?.id === "field-date")[0].props["aria-label"], "Date of request: October 25, 2026");
  nodes(tree, (n) => n.props?.id === "field-date")[0].props.onClick();
  tree = await p.render();
  const pop = popover(tree);
  assert.deepEqual(cls(pop).split(" "), ["cf-pop", "cf-dp-pop"], "QuestionDeck's key handler skips targets inside .cf-pop");
  assert.equal(pop.props.popover, "manual", "shown in the top layer, above the sticky footer");
  assert.equal(pop.props.role, "dialog");
  assert.equal(pop.props["aria-label"], "Date of request");
  const month = nodes(tree, (n) => cls(n) === "cf-dp-month")[0];
  assert.equal(text(month), "October 2026");
  assert.equal(month.props["aria-live"], "polite", "a new month is announced");
  const grid = nodes(tree, (n) => n.props?.role === "grid")[0];
  assert.equal(grid.props["aria-labelledby"], month.props.id);
  assert.deepEqual(nodes(grid, (n) => n.type === "th").map((n) => [text(n), n.props.abbr, n.props.scope]).slice(0, 2), [["Su", "Sunday", "col"], ["Mo", "Monday", "col"]]);
  assert.equal(days(tree).length, 42);
  const tabStops = days(tree).filter((n) => n.props.tabIndex === 0);
  assert.deepEqual(tabStops.map((n) => n.props["data-date"]), ["2026-10-25"], "one tab stop, on the chosen day");
  assert.match(tabStops[0].props["aria-label"], /^(Today, )?Sunday, October 25, 2026, selected$/);
  assert.ok(cls(tabStops[0]).includes("is-picked"));
  assert.deepEqual(days(tree).filter((n) => cls(n).includes("is-out")).map((n) => n.props["data-date"]).slice(0, 4), ["2026-09-27", "2026-09-28", "2026-09-29", "2026-09-30"], "the other months' days are marked");
  assert.ok(nodes(tree, (n) => n.type === "button").every((n) => n.props.type === "button"), "no control can submit a form");
  const down = event();
  pop.props.onMouseDown(down.e());
  assert.deepEqual(down.calls, ["preventDefault"], "pressing inside never drops focus on the page");
  p.h.unmount();
});

test("keys move the focused day and the month; only a picked day changes the answer", async () => {
  const p = await picker("2026-10-25");
  let tree = await p.render();
  nodes(tree, (n) => n.props?.id === "field-date")[0].props.onClick();
  tree = await p.render();
  const press = async (key: string, mods: Partial<{ shiftKey: boolean; ctrlKey: boolean; metaKey: boolean }> = {}) => {
    const ev = event();
    nodes(tree, (n) => n.props?.role === "grid")[0].props.onKeyDown({ ...ev.e(key), ...mods });
    tree = await p.render();
    return ev.calls;
  };
  const focused = () => days(tree).find((n) => n.props.tabIndex === 0)?.props["data-date"];

  assert.deepEqual(await press("ArrowDown"), ["preventDefault"]);
  assert.equal(focused(), "2026-11-01");
  assert.equal(text(nodes(tree, (n) => cls(n) === "cf-dp-month")[0]), "November 2026", "crossing the month edge shows the next month");
  await press("PageUp");
  assert.equal(focused(), "2026-10-01");
  await press("PageDown", { shiftKey: true });
  assert.equal(focused(), "2027-10-01");
  assert.deepEqual(await press("PageUp", { ctrlKey: true }), [], "Ctrl+PageUp stays the browser's tab switch");
  assert.equal(focused(), "2027-10-01");
  assert.deepEqual(await press("Enter"), [], "Enter is the day button's own click, not the deck's continue");
  nodes(tree, (n) => n.props?.["aria-label"] === "Previous month")[0].props.onClick();
  tree = await p.render();
  assert.equal(focused(), "2027-09-01", "the month buttons move the focused day with the month");
  assert.deepEqual(p.changes, [], "moving answers nothing");

  days(tree).find((n) => n.props["data-date"] === "2027-09-14").props.onClick();
  tree = await p.render();
  assert.deepEqual(p.changes, ["2027-09-14"], "the picked day is saved as YYYY-MM-DD");
  assert.equal(popover(tree), undefined, "picking closes the calendar");
  p.h.unmount();
});

test("picking the saved day again saves nothing; Today and Clear set and empty the answer", async () => {
  const p = await picker("2026-10-25");
  let tree = await p.render();
  const open = async () => {
    nodes(tree, (n) => n.props?.id === "field-date")[0].props.onClick();
    tree = await p.render();
  };
  await open();
  days(tree).find((n) => n.props["data-date"] === "2026-10-25").props.onClick();
  tree = await p.render();
  assert.deepEqual(p.changes, [], "the same day is not saved twice");

  await open();
  buttonNamed(tree, "Clear").props.onClick();
  tree = await p.render();
  assert.deepEqual(p.changes, [""], "Clear empties the answer (the store drops the fact)");
  assert.equal(popover(tree), undefined);

  await open();
  buttonNamed(tree, "Today").props.onClick();
  tree = await p.render();
  const today = toIso(todayIn(new Date()));
  assert.deepEqual(p.changes, today === "2026-10-25" ? [""] : ["", today]);
  p.h.unmount();
});

test("other stored text is shown as written until a day replaces it", async () => {
  const p = await picker("October 21, 2026");
  let tree = await p.render();
  assert.equal(text(nodes(tree, (n) => cls(n).includes("cf-dp-value"))[0]), "October 21, 2026");
  assert.equal(nodes(tree, (n) => cls(n).includes("is-empty")).length, 0);
  nodes(tree, (n) => n.props?.id === "field-date")[0].props.onClick();
  tree = await p.render();
  assert.equal(days(tree).filter((n) => cls(n).includes("is-picked")).length, 0, "text that is not a date marks no day");
  assert.ok(buttonNamed(tree, "Clear"), "it can still be cleared");
  assert.deepEqual(p.changes, []);
  p.h.unmount();
});

test("arrows on the field open the calendar instead of moving to another question", async () => {
  const p = await picker("");
  let tree = await p.render();
  for (const key of ["ArrowDown", "ArrowUp"]) {
    const ev = event();
    nodes(tree, (n) => n.props?.id === "field-date")[0].props.onKeyDown(ev.e(key));
    tree = await p.render();
    assert.deepEqual(ev.calls, ["preventDefault"], `${key} is claimed, so the deck's handler skips it`);
    assert.ok(popover(tree), `${key} opens the calendar`);
    popover(tree).props.onKeyDown(event().e("Escape"));
    tree = await p.render();
  }
  const enter = event();
  nodes(tree, (n) => n.props?.id === "field-date")[0].props.onKeyDown(enter.e("Enter"));
  assert.deepEqual(enter.calls, [], "Enter is left to the button (it opens the calendar on click)");
  assert.ok(p.listeners.includes("+pointerdown") && p.listeners.includes("-pointerdown"), "a press outside closes the calendar while it is open, and the listener goes with it");
  p.h.unmount();
});
