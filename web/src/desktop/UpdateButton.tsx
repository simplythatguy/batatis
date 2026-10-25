/**
 * The rail's update control, after T3 Code's sidebar update button: an icon that appears only when an
 * update exists, and a panel on hover or focus with the version, what changed and links to GitHub.
 * Clicking downloads; once verified, clicking saves this visit's work and restarts into the new version.
 */
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { Icon24 } from "../calm/icons";
import { useSaveBeforeSwitch } from "./People";
import { desktop, useUpdate, type UpdateRelease, type UpdateView } from "./host";

const CLOSE_DELAY_MS = 150;
const RING = 2 * Math.PI * 15;

type Shown = Extract<UpdateView, { status: "available" | "downloading" | "ready" }> | (Extract<UpdateView, { status: "failed" }> & { release: UpdateRelease });

function shown(view: UpdateView | null): Shown | null {
  if (!view) return null;
  if (view.status === "available" || view.status === "downloading" || view.status === "ready") return view;
  return view.status === "failed" && view.release ? { ...view, release: view.release } : null;
}

function heading(view: Shown): string {
  switch (view.status) {
    case "available": return view.release.downloadable ? "Update ready to download" : "Update available on GitHub";
    case "downloading": return "Downloading update";
    case "ready": return view.install === "restart" ? "Restart to update" : "Update downloaded";
    case "failed": return view.message;
  }
}

function action(view: Shown): { label: string; run: "download" | "install" | "open" } | null {
  if (view.status === "downloading") return null;
  if (view.status === "ready") return view.install === "restart" ? { label: "Restart", run: "install" } : { label: "Show download", run: "install" };
  if (!view.release.downloadable) return { label: "Open GitHub", run: "open" };
  return { label: view.status === "failed" ? "Try again" : "Download", run: "download" };
}

function StatusIcon({ view }: { view: Shown }) {
  if (view.status === "downloading") {
    const offset = RING * (1 - (view.percent ?? 0) / 100);
    return (
      <span className="dk-update-icon">
        <svg className="dk-update-ring" viewBox="0 0 36 36" aria-hidden="true">
          <circle cx="18" cy="18" r="15" className="dk-update-track" />
          <circle cx="18" cy="18" r="15" className="dk-update-arc" strokeDasharray={RING} strokeDashoffset={offset} />
        </svg>
        <Icon24 name="download" size={16} />
      </span>
    );
  }
  if (view.status === "ready") {
    return (
      <span className="dk-update-icon">
        <Icon24 name="restart" size={17} />
        <span className="dk-update-check" aria-hidden="true"><Icon24 name="check" size={8} stroke={3.5} /></span>
      </span>
    );
  }
  return (
    <span className="dk-update-icon">
      <Icon24 name="download" size={17} />
      <span className="dk-update-dot" aria-hidden="true" />
    </span>
  );
}

function GitHubLink({ href, children }: { href: string; children: string }) {
  return (
    <a className="dk-update-link" href={href} target="_blank" rel="noreferrer">
      {children}
      <Icon24 name="external" size={11} stroke={2.25} />
    </a>
  );
}

function Notes({ release }: { release: UpdateRelease }) {
  if (release.notes.length === 0) return <GitHubLink href={release.url}>View release on GitHub</GitHubLink>;
  return (
    <div className="dk-update-notes">
      {release.notes.map((note, index) => (
        <section key={note.version}>
          {index > 0 && <hr className="dk-update-rule" />}
          <h3>{index === 0 ? "What’s changed" : `Changes in ${note.version}`}</h3>
          {note.items.length > 0 && <ul>{note.items.map((item, i) => <li key={`${i}:${item}`}>{item}</li>)}</ul>}
          <GitHubLink href={note.url}>{note.more === 0 ? "View release on GitHub" : `${note.more} more ${note.more === 1 ? "change" : "changes"} on GitHub`}</GitHubLink>
        </section>
      ))}
      {release.older > 0 && (
        <>
          <hr className="dk-update-rule" />
          <GitHubLink href={release.history}>{`${release.older} older ${release.older === 1 ? "release" : "releases"} on GitHub`}</GitHubLink>
        </>
      )}
    </div>
  );
}

export function UpdateButton() {
  const view = shown(useUpdate());
  const prepare = useSaveBeforeSwitch();
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const closing = useRef<number | undefined>(undefined);
  /** The pointer is over the control or its panel; a blur there (a click on panel text) keeps it open. */
  const hovering = useRef(false);
  /** Escape returns focus to the button without reopening the panel. */
  const quiet = useRef(false);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const id = useId();

  useLayoutEffect(() => {
    if (!open || !button.current) return setPos(null);
    const r = button.current.getBoundingClientRect();
    const h = panel.current?.offsetHeight ?? 0;
    setPos({ left: r.right + 12, top: Math.max(8, Math.min(r.bottom - h, window.innerHeight - h - 8)) });
  }, [open, view?.status, view?.release.version]);

  useEffect(() => () => window.clearTimeout(closing.current), []);
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      quiet.current = true;
      setOpen(false);
      button.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!view) return null;
  const title = heading(view);
  const act = action(view);

  const show = () => {
    window.clearTimeout(closing.current);
    setOpen(true);
  };
  const hide = () => {
    window.clearTimeout(closing.current);
    closing.current = window.setTimeout(() => setOpen(false), CLOSE_DELAY_MS);
  };
  const focused = () => {
    if (quiet.current) quiet.current = false;
    else show();
  };
  const blurred = (event: React.FocusEvent<HTMLElement>) => {
    if (!hovering.current && !event.currentTarget.parentElement?.contains(event.relatedTarget)) hide();
  };

  async function run() {
    if (!act || busy || !view) return;
    setNote("");
    if (act.run === "open") {
      window.open(view.release.url, "_blank", "noreferrer");
      return;
    }
    setBusy(true);
    // The panel's button goes away once the work starts; keep focus on the control.
    button.current?.focus();
    if (act.run === "download") await desktop.updates.download();
    else {
      const reason = view.status === "ready" && view.install === "restart" ? await prepare() : null;
      const outcome = reason ? { ok: false as const, message: reason } : await desktop.updates.install();
      if (!outcome.ok && outcome.message) setNote(outcome.message);
    }
    setBusy(false);
  }

  return (
    <div className="dk-update" onPointerEnter={() => { hovering.current = true; show(); }} onPointerLeave={() => { hovering.current = false; hide(); }}>
      <button ref={button} type="button" className={`cf-rail-btn dk-update-btn is-${view.status}`}
        aria-label={`${title}, ${view.release.version}`} aria-expanded={open} aria-controls={open ? id : undefined}
        aria-disabled={!act || busy || undefined} onFocus={focused} onBlur={blurred}
        onClick={() => void run()}>
        <StatusIcon view={view} />
      </button>
      {open && (
        <div ref={panel} id={id} className="dk-update-panel" role="group" aria-label={`Update ${view.release.version}`}
          style={pos ?? { left: -9999, top: -9999 }} onFocus={show} onBlur={blurred}>
          <div className="dk-update-head">
            <p className="dk-update-title"><span aria-live="polite">{title}</span>
              {view.status === "downloading" && view.percent !== null && <span aria-hidden="true"> {Math.floor(view.percent)}%</span>}</p>
            <p className="dk-update-version">{view.release.version}</p>
          </div>
          <Notes release={view.release} />
          {((act && act.run !== "open") || note) && (
            <div className="dk-update-foot">
              {note && <p className="ac-error" role="alert">{note}</p>}
              {act && act.run !== "open" && <button type="button" className="cf-btn is-xs is-primary" disabled={busy} onClick={() => void run()}>{act.label}</button>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
