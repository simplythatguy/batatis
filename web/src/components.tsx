import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useRoute } from "./router";
import { NRC_CREDIT, NRC_SOURCES } from "./config";
import { splitNoticeUrl } from "./rules";
import { PRIVACY_NOTICE } from "./privacy";
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
  info: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 7.25v3.5M8 5.25v.01" />
    </>
  ),
  external: <path d="M6.5 3.5h-3v9h9v-3M9 3.5h3.5V7M12.5 3.5 7.5 8.5" />,
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
  const { gapsSource, checkStatus, checkNote } = useCase();
  if (checkStatus === "not_requested") return null;
  if (checkStatus === "stale" || checkStatus === "running" || checkStatus === "unavailable") return <p className="check-summary" role="status">{checkNote}</p>;
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
          Reviewing your draft…
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
            Reviewing your draft…
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

/** Plain recovery; no synthetic case may replace real work. */
export function ServiceUnavailable({ reason, onRetry }: { reason: string; onRetry?: () => void }) {
  return <div className="recovery" role="status">
    <p>Couldn’t load this information.</p>
    {onRetry && <button type="button" className="btn" onClick={onRetry}>Try again</button>}
    <details><summary>Technical detail</summary><p>{reason}</p></details>
  </div>;
}

export function DraftNote() {
  const { savedNote, saveStatus, saveDetail, saveDraft } = useCase();
  return <div className="save-receipt">
    <span className="status-note" role="status">{savedNote || "Current visit only"}</span>
    {saveStatus === "failed" && <button type="button" className="btn btn-xs" onClick={() => void saveDraft()}>Try saving again</button>}
    {saveStatus === "gone" && <a className="text-link" href="#/application?download=1">Keep a draft</a>}
    <details className="save-help"><summary aria-label="About saving">About saving</summary>
      <p>Changes are sent to Batatis as you type. This page won’t reopen your draft after a reload. Download a draft to keep a copy.</p>
      <p className="meta">{PRIVACY_NOTICE}</p>
      <a className="text-link" href="#/application?download=1">Download options</a>
      {saveDetail && <details><summary>Technical detail</summary><p>{saveDetail}</p></details>}
    </details>
  </div>;
}

export function CheckAction() {
  const { checkStatus, checkNote, checkDetail, requestCheck } = useCase();
  const busy = checkStatus === "running";
  const finished = checkStatus === "ready" || checkStatus === "needs_answers";
  return <section className="check-action" aria-label="Draft check">
    <div>
      <h2 className="section-title">{finished ? "Your draft check" : "Check when you’re ready"}</h2>
      <p className="meta" role="status">{checkNote || "Fill in what you know. You can leave questions for later."}</p>
    </div>
    <button type="button" className={finished ? "btn" : "btn btn-primary"} disabled={busy} onClick={() => finished ? (location.hash = "#/application?review=1") : void requestCheck(checkStatus === "unavailable")}>
      {busy ? "Checking…" : checkStatus === "unavailable" ? "Try check again" : finished ? "View check" : "Check my draft"}
    </button>
    <details className="compact-help"><summary>What gets checked?</summary>
      <p>Saves your draft, looks for code articles, then checks for missing information. This may use AI. Nothing is submitted or downloaded.</p>
      <p>This checks completeness, not design safety or code compliance.</p>
      {checkDetail && <details><summary>Technical detail</summary><p>{checkDetail}</p></details>}
    </details>
  </section>;
}

/** Small field groups; deep links open the group containing the requested field. */
export function FieldSteps({ steps, nextHref, previousHref, onComplete }: { steps: { title: string; fields: string[]; content: ReactNode; continueAction?: { label: string; onClick: () => void; optionalLabel: string } }[]; nextHref?: string; previousHref?: string; onComplete?: () => void }) {
  const route = useRoute();
  const focus = route.params.get("focus");
  const focusIndex = steps.findIndex(step => focus && step.fields.includes(focus));
  const [index, setIndex] = useState(focusIndex >= 0 ? focusIndex : route.params.get("step") === "last" ? steps.length - 1 : 0);
  useEffect(() => { if (focusIndex >= 0) setIndex(focusIndex); }, [focusIndex, focus]);
  const current = Math.min(index, steps.length - 1);
  const step = steps[current];
  const heading = useRef<HTMLHeadingElement>(null);
  const moved = useRef(false);
  const move = (next: number) => {
    if (next === current) {
      heading.current?.focus({ preventScroll: true });
      heading.current?.scrollIntoView({ block: "start", behavior: "instant" });
    } else { moved.current = true; setIndex(next); }
  };
  useLayoutEffect(() => {
    if (!moved.current) return;
    moved.current = false;
    heading.current?.focus({ preventScroll: true });
    heading.current?.scrollIntoView({ block: "start", behavior: "instant" });
  }, [current]);
  if (!step) return null;
  return <section className="field-step">
    <div className="step-heading"><h2 ref={heading} tabIndex={-1}>{step.title}</h2><span className="meta">{current + 1} of {steps.length}</span></div>
    {step.content}
    {step.continueAction && current < steps.length - 1 && <button type="button" className="btn btn-ghost optional-next" onClick={() => move(current + 1)}>{step.continueAction.optionalLabel}</button>}
    <div className="step-controls">
      {current === 0 && previousHref ? <a className="btn btn-ghost" href={previousHref}>Previous</a> : <button type="button" className="btn btn-ghost" disabled={current === 0} onClick={() => move(current - 1)}>Previous</button>}
      <details className="jump-menu"><summary>All fields</summary><div>{steps.map((item, n) => <button key={item.title} type="button" className="btn btn-ghost" aria-current={current === n ? "step" : undefined} onClick={e => { move(n); e.currentTarget.closest("details")?.removeAttribute("open"); }}>{item.title}</button>)}</div></details>
      {step.continueAction ? <button type="button" className="btn btn-primary" onClick={step.continueAction.onClick}>{step.continueAction.label}</button> : current < steps.length - 1 ? <button type="button" className="btn btn-primary" onClick={() => move(current + 1)}>Continue</button> : nextHref ? <a className="btn btn-primary" href={nextHref}>Continue</a> : onComplete ? <button className="btn btn-primary" onClick={onComplete}>Continue to evidence</button> : <span className="meta">You can return to any answer.</span>}
    </div>
  </section>;
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

/**
 * Verbatim code text with its NRC credit and a link to the official publication.
 * Use only for text the code database returned; summaries and the applicant's words are not code text.
 */
export function CodeQuote({ text, source = "code", className = "" }: { text: ReactNode; source?: keyof typeof NRC_SOURCES; className?: string }) {
  return (
    <figure className="code-quote">
      {/* Long text scrolls inside the quote (styles.css), so it needs a keyboard stop. */}
      <blockquote className={`cite-block quote ${className}`.trim()} tabIndex={typeof text === "string" && text.length > 700 ? 0 : undefined}>
        {text}
      </blockquote>
      <NrcCredit source={source} as="figcaption" />
    </figure>
  );
}

/** "© National Research Council of Canada · <publication> · Official publication ↗". */
export function NrcCredit({ source = "code", as: Tag = "span" }: { source?: keyof typeof NRC_SOURCES; as?: "span" | "figcaption" }) {
  const pub = NRC_SOURCES[source];
  return (
    <Tag className="nrc-credit">
      {NRC_CREDIT} · {pub.title} ·{" "}
      <a href={pub.url} target="_blank" rel="noopener noreferrer">
        Official publication
        <Icon name="external" size={11} />
        <span className="sr-only"> (opens in a new tab)</span>
      </a>
    </Tag>
  );
}

/**
 * Information from the engine (severity `info`). Not a missing item, so it carries no count and no status dot.
 * A URL inside the message becomes the link; nothing points back into the app.
 */
export function NoticeRow({ text }: { text: string }) {
  const { text: shown, url } = splitNoticeUrl(text);
  return (
    <p className="notice-row" role="note">
      <span className="notice-icon" role="img" aria-label="Information">
        <Icon name="info" size={14} />
      </span>
      <span>
        {shown}
        {url && (
          <>
            {" "}
            <a href={url} target="_blank" rel="noopener noreferrer">
              Open the source
              <Icon name="external" size={11} />
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          </>
        )}
      </span>
    </p>
  );
}

export function Notices({ notices }: { notices: string[] }) {
  if (!notices.length) return null;
  return (
    <div className="notice-list">
      {[...new Set(notices)].map((n) => (
        <NoticeRow key={n} text={n} />
      ))}
    </div>
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
