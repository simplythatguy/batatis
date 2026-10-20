import type { ReactNode } from "react";
import { EXAMPLES } from "./examples";
import { roleNote } from "./humanReview";
import { useCase } from "./store";
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
  const { gapsSource, c } = useCase();
  if (gapsSource === "idle") {
    return (
      <div className="gap-summary gap-panel" aria-label="Administrative gaps">
        <span className="gap-chip">
          <span className="status-dot pending" />
          Your application has not been reviewed online yet.
        </span>
      </div>
    );
  }
  if (gapsSource === "loading" && !gaps.length) {
    return (
      <div className="gap-summary gap-panel" aria-label="Administrative gaps">
        <span className="gap-chip">
          <span className="status-dot pending" />
          Reviewing {c.exampleId ? "this example" : "your application"}…
        </span>
        <span className="meta">The missing-item list may change when the review finishes.</span>
      </div>
    );
  }
  if (!gaps.length && gapsSource === "browser") {
    return (
      <div className="gap-summary gap-panel" aria-label="Administrative gaps">
        <span className="gap-chip">
          <span className="status-dot warning" />
          No missing fields found by this browser check. The online review has not completed.
        </span>
      </div>
    );
  }
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
        {gapsSource === "loading" && (
          <span className="gap-chip">
            <span className="status-dot pending" />
            Reviewing {c.exampleId ? "this example" : "your application"}…
          </span>
        )}
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

/** Shown only when the engine cannot be reached. Example buttons ask before they replace a case. */
export function DemoFallback({ reason, onRetry }: { reason: string; onRetry?: () => void }) {
  const { askExample } = useCase();
  return (
    <div className="demo-offer" role="alert">
      <p>{reason}</p>
      <p className="meta">The engine could not be reached. Retry, or open a cached example. An example does not replace your case until you confirm.</p>
      <div className="btn-row">
        {onRetry && (
          <button type="button" className="btn" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
      <div className="btn-row">
        <button type="button" className="btn" onClick={() => askExample("manufacturer-northcore")}>
          Manufacturer example
        </button>
        <button type="button" className="btn" onClick={() => askExample("contractor-dampers")}>
          Contractor example
        </button>
        <button type="button" className="btn" onClick={() => askExample("homebuilder-soffit")}>
          Homebuilder example
        </button>
      </div>
    </div>
  );
}

export function DraftNote() {
  const { savedNote, gapsNote } = useCase();
  if (!gapsNote && !savedNote) return null;
  return (
    <span className="status-note" role="status">
      {gapsNote}
      {gapsNote && savedNote ? " " : ""}
      {savedNote}
    </span>
  );
}

/** Persistent example provenance. Not dismissible. Shown only while an example is loaded. */
export function ExampleBanner({ officer = false }: { officer?: boolean }) {
  const { c, resetToWho } = useCase();
  const label = EXAMPLES.find((ex) => ex.id === c.exampleId)?.label ?? "Loaded example";
  return (
    <aside className="example-banner" role="note" aria-label="Example data">
      <div className="example-banner-copy">
        <p className="example-banner-title">EXAMPLE · {label}</p>
        <p className="example-banner-body">
          {officer
            ? "This officer review is of the loaded example."
            : "You are viewing a sample application. Starting your own application clears this example."}
        </p>
      </div>
      {officer ? (
        <a className="btn" href="#/describe">
          Return to application
        </a>
      ) : (
        <button type="button" className="btn" onClick={resetToWho}>
          Start my own application
        </button>
      )}
    </aside>
  );
}

/** When this role needs an engineer, and what the officer decides. */
export function RoleNote() {
  const { c } = useCase();
  const note = roleNote(c.applicantType);
  return (
    <p className="field-note">
      {note.engineer} {note.officer}
    </p>
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
