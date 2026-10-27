import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { AUTHORITY_LIST_LIMIT, filterAuthorities, type AuthorityOption } from "./authorityFilter";
import { Icon24 } from "./icons";
import { resolveOffice } from "../config";
import "./AuthorityPicker.css";

/**
 * Pick the one office that reviews the application: a search field that opens a short list, so
 * two offices and four hundred read the same. Typing only filters; nothing is answered until an
 * option is chosen, and leaving the field puts the saved choice back.
 */
export function AuthorityPicker({ options, value, onPick, label, suggested, unsure = false, compact = false }: { options: readonly AuthorityOption[]; value: string; onPick: (id: string) => void; label: string; suggested?: AuthorityOption | null; unsure?: boolean; compact?: boolean }) {
  const listId = useId();
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const selected = options.find((o) => o.id === value);
  const { shown, total } = useMemo(() => {
    const filtered = filterAuthorities(options, query ?? "");
    const text = query?.trim();
    const custom = text && !options.some((option) => option.id.toLowerCase() === text.toLowerCase() || option.name.toLowerCase() === text.toLowerCase())
      ? [{ id: text, name: text }] : [];
    return { shown: [...filtered.shown, ...custom, { id: "unsure", name: "Not sure" }], total: filtered.total + custom.length + 1 };
  }, [options, query]);
  const optionId = (n: number) => `${listId}-${n}`;

  const close = () => { setOpen(false); setQuery(null); };
  const show = () => {
    if (open) return;
    setOpen(true);
    const at = shown.findIndex((o) => o.id === value);
    setActive(at >= 0 ? at : 0);
  };
  const choose = (o: AuthorityOption) => {
    onPick(resolveOffice(o.id)?.id ?? "unsure");
    close();
  };
  // A saved choice changed elsewhere (another application, a reload) closes any search in progress.
  useEffect(() => { setOpen(false); setQuery(null); }, [value]);
  useEffect(() => {
    if (open) root.current?.querySelector(`#${CSS.escape(optionId(active))}`)?.scrollIntoView({ block: "nearest" });
  }, [open, active]); // eslint-disable-line react-hooks/exhaustive-deps

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) return show();
      if (!shown.length) return;
      setActive((a) => (e.key === "ArrowDown" ? (a + 1) % shown.length : (a - 1 + shown.length) % shown.length));
    } else if (e.key === "Enter" && open) {
      // Enter picks the highlighted office; with the list closed it falls through and continues.
      e.preventDefault();
      if (shown[active]) choose(shown[active]);
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      e.stopPropagation();
      close();
    } else if (e.key === "Home" && open && shown.length) {
      e.preventDefault();
      setActive(0);
    } else if (e.key === "End" && open && shown.length) {
      e.preventDefault();
      setActive(shown.length - 1);
    }
  };

  return <>
    {!compact && suggested && !unsure && (!value || value === suggested.id) && <button type="button" className="cf-btn" onClick={() => choose(suggested)}>Yes, {suggested.name}</button>}
    <div className={`cf-ap${compact ? " is-compact" : ""}`} ref={root} onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) close(); }}>
      <span className="cf-ap-lead" aria-hidden="true"><Icon24 name="search" size={18} /></span>
      <input
        ref={input}
        className="cf-ap-input"
        type="text"
        role="combobox"
        aria-label={label}
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-haspopup="listbox"
        aria-activedescendant={open && shown[active] ? optionId(active) : undefined}
        autoComplete="off"
        spellCheck={false}
        placeholder="Find an Alberta place"
        value={query ?? selected?.name ?? (unsure ? "Not sure" : value)}
        onFocus={(e) => e.currentTarget.select()}
        onClick={show}
        onChange={(e) => { setQuery(e.target.value); setActive(0); setOpen(true); }}
        onKeyDown={onKeyDown}
      />
      <button
        type="button"
        className="cf-ap-toggle"
        tabIndex={-1}
        aria-label={open ? "Hide offices" : "Show offices"}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => { input.current?.focus(); if (open) close(); else show(); }}
      >
        <Icon24 name="down" size={16} />
      </button>
      {open && (
        <ul id={listId} className="cf-ap-list" role="listbox" aria-label={label}>
          {shown.map((o, n) => (
            <li
              key={o.id}
              id={optionId(n)}
              role="option"
              aria-selected={o.id === value}
              className={`cf-ap-opt${n === active ? " is-active" : ""}`}
              onMouseDown={(e) => e.preventDefault()}
              onMouseMove={() => { if (n !== active) setActive(n); }}
              onClick={() => choose(o)}
            >
              <span className="cf-ap-name">{o.name}</span>
              {o.id === value && <span className="cf-ap-check" aria-hidden="true"><Icon24 name="check" size={16} stroke={2} /></span>}
            </li>
          ))}
          {!shown.length && <li className="cf-ap-note" role="presentation">No match</li>}
          {total > AUTHORITY_LIST_LIMIT && <li className="cf-ap-note" role="presentation">{shown.length} of {total}. Keep typing.</li>}
        </ul>
      )}
      <span className="cf-sr" role="status" aria-live="polite">{open && query !== null ? (total === 0 ? "No match" : `${total} ${total === 1 ? "office" : "offices"}`) : ""}</span>
    </div>
    {/* Compact (the paperwork sheet): Not sure stays in the list; the row's own Later handles deferral. */}
    {!compact && <button type="button" className="cf-link-btn cf-ap-unsure" aria-pressed={unsure} onClick={() => choose({ id: "unsure", name: "Not sure" })}>Not sure</button>}
  </>;
}
