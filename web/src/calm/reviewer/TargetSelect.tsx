/** Where the applicant answers an item: a styled listbox (no browser select chrome), keyboard ready. */
import { useEffect, useId, useRef, useState } from "react";
import type { RequestTarget } from "../../api/types.gen";
import { AcIcon } from "../auth/bits";

const same = (a: RequestTarget | null, b: RequestTarget) => Boolean(a && a.section === b.section && (a.field ?? null) === (b.field ?? null));

export function TargetSelect({ options, value, onChange, disabled }: {
  options: RequestTarget[];
  value: RequestTarget | null;
  onChange: (target: RequestTarget) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open) return;
    const at = Math.max(0, options.findIndex((o) => same(value, o)));
    setActive(at);
    list.current?.focus();
    const away = (e: PointerEvent) => {
      if (!list.current?.contains(e.target as Node) && !button.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (open) list.current?.querySelector<HTMLElement>(`[data-i="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  function pick(i: number) {
    onChange(options[i]);
    setOpen(false);
    button.current?.focus();
  }

  return (
    <div className="rw-select">
      <button ref={button} type="button" className="rw-select-btn" aria-haspopup="listbox" aria-expanded={open}
        aria-controls={`${id}-l`} disabled={disabled} onClick={() => setOpen(!open)}
        onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); } }}>
        <span>{value?.label ?? "Where they answer"}</span>
        <AcIcon name="chev" size={14} />
      </button>
      {open && (
        <ul ref={list} id={`${id}-l`} className="rw-select-list" role="listbox" tabIndex={-1}
          aria-activedescendant={`${id}-${active}`} aria-label="Where they answer"
          onKeyDown={(e) => {
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(0, Math.min(options.length - 1, a + (e.key === "ArrowDown" ? 1 : -1))));
            } else if (e.key === "Home" || e.key === "End") {
              e.preventDefault();
              setActive(e.key === "Home" ? 0 : options.length - 1);
            } else if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              pick(active);
            } else if (e.key === "Escape" || e.key === "Tab") {
              // Back to the button before the list goes, so focus never falls to the page.
              e.preventDefault();
              setOpen(false);
              button.current?.focus();
            } else if (e.key.length === 1) {
              const at = options.findIndex((o, i) => i > active && o.label.toLowerCase().includes(e.key.toLowerCase()));
              if (at >= 0) setActive(at);
            }
          }}>
          {options.map((o, i) => (
            <li key={`${o.section}:${o.field ?? ""}`} id={`${id}-${i}`} data-i={i} role="option" aria-selected={same(value, o)}
              className={i === active ? "is-active" : undefined} onPointerMove={() => setActive(i)} onClick={() => pick(i)}>
              {o.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
