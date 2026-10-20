import type { ReactNode } from "react";
import type { FactKind, Gap } from "./types";

const ICONS: Record<string, ReactNode> = {
  describe: <path d="M3 4h10M3 8h10M3 12h6" />,
  application: (
    <>
      <rect x="3" y="2.5" width="10" height="11" rx="1.5" />
      <path d="M5.5 6h5M5.5 9h5M5.5 12h3" />
    </>
  ),
  check: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="m5.75 8 1.6 1.6 2.9-3.2" />
    </>
  ),
  table: (
    <>
      <rect x="2.5" y="3" width="11" height="10" rx="1.5" />
      <path d="M2.5 6.5h11M6.5 6.5V13" />
    </>
  ),
  officer: (
    <>
      <circle cx="8" cy="5.5" r="2.5" />
      <path d="M3.5 13.5c.6-2.4 2.4-3.5 4.5-3.5s3.9 1.1 4.5 3.5" />
    </>
  ),
  accuracy: <path d="M3 13V8M6.5 13V5M10 13V9.5M13.5 13V3" />,
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

const KIND_LABEL: Record<FactKind, string> = { exact: "Exact", pointed: "Pointed", computed: "Computed", proposed: "Proposed" };
const KIND_HELP: Record<FactKind, string> = {
  exact: "Exact: taken from the code database or the form",
  pointed: "Pointed: a span selected from your words or files, never generated",
  computed: "Computed: a formula over exact and pointed values",
  proposed: "Proposed: AI judgement; needs your confirmation",
};

export function KindBadge({ kind }: { kind: FactKind }) {
  return (
    <span className={`kind-badge kind-${kind}`} title={KIND_HELP[kind]}>
      {KIND_LABEL[kind]}
    </span>
  );
}

export function GapStrip({ gaps }: { gaps: Gap[] }) {
  if (!gaps.length) {
    return (
      <div className="gap-summary gap-panel" aria-label="Administrative gaps">
        <span className="gap-chip">
          <span className="status-dot done" />
          No open gaps
        </span>
      </div>
    );
  }
  const blocking = gaps.filter((g) => g.severity === "blocking").length;
  return (
    <details className="gap-panel">
      <summary className="gap-summary">
        <span className="gap-chip">
          <span className="status-dot blocking" />
          {blocking} blocking
        </span>
        <span className="gap-chip">
          <span className="status-dot warning" />
          {gaps.length - blocking} warning
        </span>
        <span className="meta gap-toggle">
          Review gaps <Icon name="chevron" size={12} />
        </span>
      </summary>
      <ul className="plain-list gap-grid" aria-label="Administrative gaps">
        {gaps.map((g) => (
          <li key={g.id}>
            <a className="gap-chip" href={g.href}>
              <span className={`status-dot ${g.severity}`} />
              {g.label}
            </a>
          </li>
        ))}
      </ul>
    </details>
  );
}

export function PanelHeader({ title, meta }: { title: string; meta?: ReactNode }) {
  return (
    <header className="panel-header">
      <h1 className="panel-title">{title}</h1>
      {meta && <span className="meta header-meta">{meta}</span>}
    </header>
  );
}
