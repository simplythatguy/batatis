/**
 * Calendar days for the date field: no time and no zone, stored as `YYYY-MM-DD` (the format the
 * native date input wrote). Pure, so the calendar's arithmetic is tested without a browser.
 */

export interface CalendarDate {
  year: number;
  /** 1 to 12. */
  month: number;
  day: number;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/** Column headers, Sunday first: the short label and the full name. */
export const WEEKDAYS = [["Su", "Sunday"], ["Mo", "Monday"], ["Tu", "Tuesday"], ["We", "Wednesday"], ["Th", "Thursday"], ["Fr", "Friday"], ["Sa", "Saturday"]] as const;

/** Midnight UTC of the day; `setUTCFullYear` keeps years below 100 as written (`Date.UTC` maps them to 19xx). */
function stamp({ year, month, day }: CalendarDate): Date {
  const t = new Date(0);
  t.setUTCFullYear(year, month - 1, day);
  return t;
}

function fromStamp(t: Date): CalendarDate {
  return { year: t.getUTCFullYear(), month: t.getUTCMonth() + 1, day: t.getUTCDate() };
}

/** The stored answer as a day, or null when it is empty or not a real `YYYY-MM-DD` date. */
export function parseIso(value: string): CalendarDate | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (!m) return null;
  const d = { year: Number(m[1]), month: Number(m[2]), day: Number(m[3]) };
  return sameDay(fromStamp(stamp(d)), d) ? d : null;
}

export function toIso({ year, month, day }: CalendarDate): string {
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function sameDay(a: CalendarDate | null, b: CalendarDate | null): boolean {
  return Boolean(a && b && a.year === b.year && a.month === b.month && a.day === b.day);
}

/** Today on the person's own clock. */
export function todayIn(now: Date): CalendarDate {
  return { year: now.getFullYear(), month: now.getMonth() + 1, day: now.getDate() };
}

export function addDays(d: CalendarDate, n: number): CalendarDate {
  const t = stamp(d);
  t.setUTCDate(t.getUTCDate() + n);
  return fromStamp(t);
}

/** The same day n months away, or that month's last day when it is shorter (Jan 31 → Feb 28). */
export function addMonths(d: CalendarDate, n: number): CalendarDate {
  const first = fromStamp(stamp({ year: d.year, month: d.month + n, day: 1 }));
  const last = fromStamp(stamp({ year: first.year, month: first.month + 1, day: 0 })).day;
  return { ...first, day: Math.min(d.day, last) };
}

/** 0 is Sunday. */
export function weekday(d: CalendarDate): number {
  return stamp(d).getUTCDay();
}

/** Six weeks from the Sunday on or before the 1st, so the calendar keeps one height in every month. */
export function monthGrid(year: number, month: number): CalendarDate[][] {
  const first = { year, month, day: 1 };
  const start = addDays(first, -weekday(first));
  return Array.from({ length: 6 }, (_, w) => Array.from({ length: 7 }, (_, n) => addDays(start, w * 7 + n)));
}

/** Where a calendar key moves the focused day, or null for a key the calendar does not use. */
export function moveFocus(d: CalendarDate, key: string, shift: boolean): CalendarDate | null {
  switch (key) {
    case "ArrowLeft": return addDays(d, -1);
    case "ArrowRight": return addDays(d, 1);
    case "ArrowUp": return addDays(d, -7);
    case "ArrowDown": return addDays(d, 7);
    case "Home": return addDays(d, -weekday(d));
    case "End": return addDays(d, 6 - weekday(d));
    case "PageUp": return addMonths(d, shift ? -12 : -1);
    case "PageDown": return addMonths(d, shift ? 12 : 1);
    default: return null;
  }
}

/** "October 25, 2026" */
export function formatLong(d: CalendarDate): string {
  return `${MONTHS[d.month - 1]} ${d.day}, ${d.year}`;
}

/** "October 2026" */
export function formatMonth(d: CalendarDate): string {
  return `${MONTHS[d.month - 1]} ${d.year}`;
}

/** "Sunday, October 25, 2026": a day's accessible name. */
export function formatDay(d: CalendarDate): string {
  return `${WEEKDAYS[weekday(d)][1]}, ${formatLong(d)}`;
}
