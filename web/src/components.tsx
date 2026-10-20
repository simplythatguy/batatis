import { useRef, type ReactNode } from "react";
import { useCase } from "./store";
import type { Fact, Gap } from "./types";

const ICONS: Record<string, ReactNode> = {
  file: (
    <>
      <path d="M4 2.5h5l3 3v8H4z" />
      <path d="M9 2.5v3h3" />
    </>
  ),
  upload: <path d="M8 11V3.5M5 6.5l3-3 3 3M3 12.5h10" />,
  close: <path d="m4.5 4.5 7 7m0-7-7 7" />,
  chevron: <path d="m6 4 4 4-4 4" />,
};

export function Icon({ name, size = 14 }: { name: keyof typeof ICONS | string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONS[name]}
    </svg>
  );
}

export type Dot = "blocking" | "warning" | "pending" | "done";

export function StatusPill({ dot, children }: { dot: Dot; children: ReactNode }) {
  return (
    <span className="label-pill">
      <span className={`status-dot ${dot}`} />
      {children}
    </span>
  );
}

/** Plain-word fact kinds. A pointed span says where it came from: a file or the applicant's words. */
function kindLabel(f: Fact): string {
  if (f.kind === "pointed") return f.source.type === "file" ? "From your file" : "From your words";
  return { exact: "Exact", computed: "Worked out", proposed: "Our guess · check it" }[f.kind];
}

const KIND_HELP: Record<Fact["kind"], string> = {
  exact: "Taken from the code database or the form",
  pointed: "Copied from your words or files, never generated",
  computed: "Worked out by a formula from other facts",
  proposed: "An AI guess. It counts only after you confirm it",
};

export function KindBadge({ fact }: { fact: Fact }) {
  return (
    <span className={`kind-badge kind-${fact.kind}`} title={KIND_HELP[fact.kind]}>
      {kindLabel(fact)}
    </span>
  );
}

/**
 * Citation line in the spec's order: edition · printing · division and provision · PDF page.
 * Built from the code database's citation string; anything that does not parse is shown verbatim.
 */
export function Citation({ text }: { text: string }) {
  const m = /^NBC\(AE\) 2023 p2, Div ([ABC]), (?:\w+ )?(\S+) \[PDF p\.(\d+)\]$/.exec(text.trim());
  if (!m) return <p className="cite-line">{text}</p>;
  return (
    <p className="cite-line" title={text}>
      NBC(AE) 2023 · 2nd printing · Div {m[1]} <span className="article-id">{m[2]}</span> · PDF p.{m[3]}
    </p>
  );
}

/** Header control: "● N to fix" opens the one gap list. Warnings live only in the drawer. */
function GapControl({ gaps }: { gaps: Gap[] }) {
  const drawer = useRef<HTMLDialogElement>(null);
  const blocking = gaps.filter((g) => g.severity === "blocking");
  const notes = gaps.filter((g) => g.severity === "warning");
  const label = blocking.length ? `${blocking.length} to fix` : "Nothing to fix";
  const group = (title: string, list: Gap[]) =>
    list.length > 0 && (
      <section className="drawer-group" aria-label={title}>
        <h3 className="drawer-group-title">
          {title} · {list.length}
        </h3>
        <ul className="plain-list">
          {list.map((g) => (
            <li key={g.id}>
              <a className="drawer-row" href={g.href} onClick={() => drawer.current?.close()}>
                <span className={`status-dot ${g.severity}`} />
                {g.label}
              </a>
            </li>
          ))}
        </ul>
      </section>
    );
  return (
    <>
      <button
        type="button"
        className="btn btn-ghost gap-control"
        aria-haspopup="dialog"
        onClick={() => drawer.current?.showModal()}
      >
        <span className={`status-dot ${blocking.length ? "blocking" : "done"}`} />
        {label}
        {notes.length > 0 && <span className="tab-count">· {notes.length} note{notes.length > 1 ? "s" : ""}</span>}
      </button>
      <dialog
        className="drawer"
        ref={drawer}
        aria-labelledby="drawer-title"
        onClick={(e) => e.target === e.currentTarget && drawer.current?.close()}
      >
        <div className="drawer-head">
          <h2 className="dialog-title" id="drawer-title">
            {label}
          </h2>
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={() => drawer.current?.close()}>
            <Icon name="close" size={12} />
          </button>
        </div>
        <div className="drawer-body">
          <p className="meta">Checks that information is present. Not a finding that the design complies.</p>
          {group("To fix", blocking)}
          {group("Notes", notes)}
          {!gaps.length && <p className="empty">Nothing is missing right now.</p>}
        </div>
      </dialog>
    </>
  );
}

export function PanelHeader({ title, meta }: { title: string; meta?: ReactNode }) {
  const { gaps } = useCase();
  return (
    <header className="panel-header">
      <h1 className="panel-title">{title}</h1>
      {meta && <span className="meta header-meta">{meta}</span>}
      <GapControl gaps={gaps} />
    </header>
  );
}
