import { useEffect, useId, useLayoutEffect, useRef, useState, type FocusEvent, type KeyboardEvent } from "react";
import { addMonths, formatDay, formatLong, formatMonth, monthGrid, moveFocus, parseIso, sameDay, toIso, todayIn, WEEKDAYS, type CalendarDate } from "./calendarDate";
import { Icon24 } from "./icons";
import { placeMenu } from "./shell/placement";
import "./DatePicker.css";

/** Space between the field and its calendar. */
const GAP = 8;

/** The shared icon set has no calendar; this one is drawn the same way (24px grid, currentColor). */
function CalendarGlyph() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4.5" width="18" height="16.5" rx="2" />
      <path d="M8 2.5v4M16 2.5v4M3 10h18" />
    </svg>
  );
}

/**
 * A date field: the chosen day in words, and a small calendar under it. Nothing is answered until a
 * day (or Today) is picked, and Clear empties it again. The answer is stored as `YYYY-MM-DD`, as the
 * native date input stored it; any other stored text is shown as written until a day replaces it.
 * The calendar is a `.cf-pop`, so the question deck leaves the keys typed in it alone.
 */
export function DatePicker({ id, label, value, onChange }: { id?: string; label: string; value: string; onChange: (value: string) => void }) {
  const popId = useId();
  const monthId = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  // The focused day while the calendar is open (the month shown is its month); null while closed.
  const [focus, setFocus] = useState<CalendarDate | null>(null);
  const open = focus !== null;
  const picked = parseIso(value);
  const today = todayIn(new Date());
  const shown = picked ? formatLong(picked) : value.trim() || "Pick a date";

  const show = () => setFocus(picked ?? today);
  const close = (refocus: boolean) => {
    setFocus(null);
    if (refocus) trigger.current?.focus({ preventScroll: true });
  };
  const choose = (d: CalendarDate) => {
    const iso = toIso(d);
    if (iso !== value) onChange(iso);
    close(true);
  };

  // The top layer keeps the calendar above the sticky question footer and out of any clipping pane;
  // it sits under the field, or above it when the window has no room below.
  useLayoutEffect(() => {
    const el = pop.current;
    const anchor = trigger.current;
    if (!open || !el || !anchor) return;
    const layered = typeof el.showPopover === "function";
    if (layered) el.showPopover();
    const place = () => {
      const box = anchor.getBoundingClientRect();
      const viewport = { width: window.innerWidth, height: window.innerHeight };
      const at = placeMenu(
        { x: box.left, y: box.bottom + GAP, flipY: box.top - GAP, align: "start" },
        { width: el.offsetWidth, height: el.scrollHeight + el.offsetHeight - el.clientHeight },
        { left: 0, top: 0, right: viewport.width, bottom: viewport.height },
        viewport,
      );
      el.style.left = `${at.left}px`;
      el.style.top = `${at.top}px`;
      el.style.maxHeight = `${at.maxHeight}px`;
    };
    place();
    window.addEventListener("resize", place);
    // Capture: a scrolling pane moves the field.
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
      if (layered && el.matches(":popover-open")) el.hidePopover();
    };
  }, [open]);

  // Focus follows the focused day (opening, keys, a month button clicked), unless it is on another
  // calendar control such as a month button the keyboard is pressing again.
  useLayoutEffect(() => {
    const el = pop.current;
    if (!focus || !el) return;
    const active = document.activeElement;
    if (active && el.contains(active) && !active.classList.contains("cf-dp-day")) return;
    el.querySelector<HTMLElement>(`[data-date="${toIso(focus)}"]`)?.focus({ preventScroll: true });
  }, [focus]);

  // A press anywhere outside closes the calendar and leaves focus where the press put it.
  useEffect(() => {
    if (!open) return;
    const down = (e: PointerEvent) => { if (!(e.target instanceof Node && root.current?.contains(e.target))) close(false); };
    document.addEventListener("pointerdown", down, true);
    return () => document.removeEventListener("pointerdown", down, true);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Tabbing past the calendar closes it. */
  const leave = (e: FocusEvent<HTMLDivElement>) => {
    if (open && e.relatedTarget instanceof Node && !e.currentTarget.contains(e.relatedTarget)) close(false);
  };

  const onTriggerKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      // Arrows open the calendar here; the deck must not read them as the next or previous question.
      e.preventDefault();
      if (open) pop.current?.querySelector<HTMLElement>(".cf-dp-day[tabindex='0']")?.focus({ preventScroll: true });
      else show();
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      e.stopPropagation();
      close(false);
    }
  };

  const onGridKey = (e: KeyboardEvent<HTMLTableElement>) => {
    // Browser and system shortcuts (Ctrl+PageUp switches tabs) keep their keys.
    if (!focus || e.metaKey || e.ctrlKey || e.altKey) return;
    const next = moveFocus(focus, e.key, e.shiftKey);
    if (!next) return;
    e.preventDefault();
    setFocus(next);
  };

  return (
    <div className="cf-dp" ref={root} onBlur={leave}>
      <button
        ref={trigger}
        id={id}
        type="button"
        className="cf-uline cf-dp-trigger"
        aria-label={`${label}: ${shown}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? popId : undefined}
        onClick={() => (open ? close(true) : show())}
        onKeyDown={onTriggerKey}
      >
        <span className="cf-dp-lead" aria-hidden="true"><CalendarGlyph /></span>
        <span className={`cf-dp-value${value.trim() ? "" : " is-empty"}`}>{shown}</span>
      </button>
      {focus && (
        <div
          ref={pop}
          id={popId}
          className="cf-pop cf-dp-pop"
          popover="manual"
          role="dialog"
          aria-label={label}
          onKeyDown={(e) => {
            if (e.key !== "Escape") return;
            e.preventDefault();
            e.stopPropagation();
            close(true);
          }}
          // Pressing inside never moves focus (Safari would drop it on the page); each control moves it itself.
          onMouseDown={(e) => e.preventDefault()}
        >
          <div className="cf-dp-head">
            <p id={monthId} className="cf-dp-month" aria-live="polite">{formatMonth(focus)}</p>
            <button type="button" className="cf-dp-nav is-prev" aria-label="Previous month" onClick={() => setFocus(addMonths(focus, -1))}>
              <Icon24 name="chevRight" size={16} stroke={1.8} />
            </button>
            <button type="button" className="cf-dp-nav" aria-label="Next month" onClick={() => setFocus(addMonths(focus, 1))}>
              <Icon24 name="chevRight" size={16} stroke={1.8} />
            </button>
          </div>
          <table className="cf-dp-grid" role="grid" aria-labelledby={monthId} onKeyDown={onGridKey}>
            <thead>
              <tr>{WEEKDAYS.map(([short, full]) => <th key={full} scope="col" abbr={full}>{short}</th>)}</tr>
            </thead>
            <tbody>
              {monthGrid(focus.year, focus.month).map((week) => (
                <tr key={toIso(week[0])}>
                  {week.map((d) => {
                    const isToday = sameDay(d, today);
                    const isPicked = sameDay(d, picked);
                    return (
                      <td key={toIso(d)}>
                        <button
                          type="button"
                          className={`cf-dp-day${d.month === focus.month ? "" : " is-out"}${isToday ? " is-today" : ""}${isPicked ? " is-picked" : ""}`}
                          tabIndex={sameDay(d, focus) ? 0 : -1}
                          data-date={toIso(d)}
                          aria-label={`${isToday ? "Today, " : ""}${formatDay(d)}${isPicked ? ", selected" : ""}`}
                          onClick={() => choose(d)}
                        >
                          {d.day}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="cf-dp-foot">
            {value.trim() && <button type="button" className="cf-dp-act" onClick={() => { onChange(""); close(true); }}>Clear</button>}
            <button type="button" className="cf-dp-act is-end" onClick={() => choose(today)}>Today</button>
          </div>
        </div>
      )}
    </div>
  );
}
