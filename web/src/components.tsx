import { useEffect, useId, useRef, type ReactNode } from "react";
import { useCase } from "./store";
import type { Fact, Gap, GapSeverity } from "./types";

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

/* —— Status language (spec § Status language) ——
   Four states, each with its own shape so it never relies on colour: blocked = solid octagon,
   attention = tinted rounded square, ok = bare glyph, info = tinted circle. */

export type Status = "blocked" | "attention" | "ok" | "info";
export type StatusKind =
  | "blocked"
  | "open-question"
  | "confirmed"
  | "needs-professional"
  | "pdf-locked"
  | "evidence-listed"
  | "unconfirmed"
  | "needs-evidence"
  | "info";

/** lucide glyphs (ISC), 24-unit viewBox. */
const GLYPHS: Record<string, ReactNode> = {
  x: <path d="M18 6 6 18M6 6l12 12" />,
  alert: (
    <>
      <path d="M12 7v6" />
      <path d="M12 17h.01" />
    </>
  ),
  help: (
    <>
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <path d="M12 17h.01" />
    </>
  ),
  dashed: <circle cx="12" cy="12" r="8" strokeDasharray="3.2 3.1" />,
  check: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  list: (
    <>
      <path d="m3 17 2 2 4-4" />
      <path d="m3 7 2 2 4-4" />
      <path d="M13 6h8M13 12h8M13 18h8" />
    </>
  ),
  hardhat: (
    <>
      <path d="M10 10V5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5" />
      <path d="M14 6a6 6 0 0 1 6 6v3" />
      <path d="M4 15v-3a6 6 0 0 1 6-6" />
      <rect x="2" y="15" width="20" height="4" rx="1" />
    </>
  ),
  lock: (
    <>
      <rect width="18" height="11" x="3" y="11" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </>
  ),
  search: (
    <>
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M4.268 21a2 2 0 0 0 1.727 1H18a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v3" />
      <path d="m9 18-1.5-1.5" />
      <circle cx="5" cy="14" r="3" />
    </>
  ),
  info: (
    <>
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </>
  ),
};

const KIND: Record<StatusKind, { status: Status; glyph: string }> = {
  blocked: { status: "blocked", glyph: "x" },
  "pdf-locked": { status: "blocked", glyph: "lock" },
  "open-question": { status: "attention", glyph: "help" },
  "needs-professional": { status: "attention", glyph: "hardhat" },
  unconfirmed: { status: "attention", glyph: "dashed" },
  "needs-evidence": { status: "attention", glyph: "search" },
  confirmed: { status: "ok", glyph: "check" },
  "evidence-listed": { status: "ok", glyph: "list" },
  info: { status: "info", glyph: "info" },
};

const DEFAULT_GLYPH: Record<Status, string> = { blocked: "x", attention: "alert", ok: "check", info: "info" };

interface MarkProps {
  status?: Status;
  kind?: StatusKind;
  /** Accessible name: required, so a mark never ships without one. */
  label: string;
  size?: "sm" | "md" | "lg";
  /** The surrounding control already carries the label (aria-hidden mark). */
  decorative?: boolean;
}

/** The mark alone: role="img" with `label` as its name and tooltip. */
export function StatusIcon({ status, kind, label, size = "md", decorative }: MarkProps) {
  const s = status ?? (kind ? KIND[kind].status : "attention");
  // A kind keeps its glyph when the status is overridden (ruling 6: hard hat in an octagon).
  const glyph = kind ? KIND[kind].glyph : DEFAULT_GLYPH[s];
  return (
    <span
      className={`si ${s} ${size}`}
      {...(decorative ? { "aria-hidden": true } : { role: "img", "aria-label": label, title: label })}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        {GLYPHS[glyph]}
      </svg>
    </span>
  );
}

/** Mark plus visible text in a neutral colour. The mark is hidden from assistive tech; `label`
 *  is read before the text when it adds to it. A bare count is read only through `label`. */
export function StatusBadge({ text, ...mark }: MarkProps & { text: ReactNode }) {
  return (
    <span className="status-badge" title={mark.label}>
      <StatusIcon {...mark} decorative />
      {typeof text === "number" ? (
        <>
          <span className="sr-only">{mark.label}</span>
          <span aria-hidden="true">{text}</span>
        </>
      ) : (
        <>
          {mark.label !== text && <span className="sr-only">{mark.label}: </span>}
          {text}
        </>
      )}
    </span>
  );
}

const SEVERITY_STATUS: Record<GapSeverity, Status> = { blocking: "blocked", warning: "attention", info: "info" };
const RANK: Record<Status, number> = { blocked: 3, attention: 2, info: 1, ok: 0 };

/** The worst state among gaps; nothing open reads as ok. Info only shows when nothing else is open. */
export function worstStatus(gaps: Gap[]): Status {
  return gaps.reduce<Status>((w, g) => (RANK[SEVERITY_STATUS[g.severity]] > RANK[w] ? SEVERITY_STATUS[g.severity] : w), "ok");
}

export const STATUS_WORDS: Record<Status, string> = {
  blocked: "Something here blocks the form",
  attention: "Needs you or the officer",
  info: "For your information",
  ok: "Nothing left for you here",
};

/* —— Fact kinds —— */

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

/* —— Code text —— */

/** NBC 2023 Alberta Edition on nrc.canada.ca (the URL the repo already cites in research/precedents). */
export const NRC_CODE_URL =
  "https://nrc.canada.ca/en/certifications-evaluations-standards/codes-canada/codes-canada-publications/national-building-code-2023-alberta-edition";

/** One muted credit line next to any code text. #16 uses the same component. */
export function CodeCredit() {
  return (
    <p className="code-credit">
      <a
        href={NRC_CODE_URL}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Code text: National Research Council of Canada (opens nrc.canada.ca in a new tab)"
      >
        Code text: National Research Council of Canada ↗
      </a>
    </p>
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

/** Verbatim code text, its citation and the NRC credit. Never an empty box: missing text says so. */
export function CodeText({ text, citation, loading }: { text?: string | null; citation?: string; loading?: boolean }) {
  const body = text?.trim();
  return (
    <div className="code-text">
      {body ? (
        <blockquote className="cite-block quote">{body}</blockquote>
      ) : (
        <p className="meta code-missing">{loading ? "Loading code text…" : "Code text not loaded"}</p>
      )}
      {citation && <Citation text={citation} />}
      {body && <CodeCredit />}
    </div>
  );
}

/* —— Gaps —— */

/** Gaps of one kind share an id prefix; three or more collapse into one row. Presentation only. */
const GROUP_LABEL: Record<string, (n: number) => string> = {
  detail: (n) => `${n} required fields are empty`,
  confirm: (n) => `${n} facts we read need your check`,
  answer: (n) => `${n} code rules need your answer`,
  process: (n) => `${n} alternative-path answers are not written`,
  question: (n) => `${n} open questions`,
};
const GROUP_MIN = 3;

function groupGaps(gaps: Gap[]): { key: string; gaps: Gap[] }[] {
  const groups = new Map<string, Gap[]>();
  for (const g of gaps) {
    const key = g.id.split("-")[0];
    groups.set(key, [...(groups.get(key) ?? []), g]);
  }
  return [...groups].map(([key, list]) => ({ key, gaps: list }));
}

function GapRow({ g, fix, onGo }: { g: Gap; fix?: boolean; onGo?: () => void }) {
  return (
    <li>
      <a className="drawer-row" href={g.href} onClick={onGo}>
        <StatusIcon status={SEVERITY_STATUS[g.severity]} label={STATUS_WORDS[SEVERITY_STATUS[g.severity]]} decorative />
        <span className="fix-label">{g.label}</span>
        {fix && <span className="meta">Fix</span>}
      </a>
    </li>
  );
}

/** One list of gaps, repeated kinds grouped behind an expander. Used by the drawer and the dialog. */
export function GapList({ gaps, fix, onGo }: { gaps: Gap[]; fix?: boolean; onGo?: () => void }) {
  return (
    <ul className="plain-list gap-list">
      {groupGaps(gaps).flatMap(({ key, gaps: list }) => {
        const label = GROUP_LABEL[key];
        if (!label || list.length < GROUP_MIN) return list.map((g) => <GapRow key={g.id} g={g} fix={fix} onGo={onGo} />);
        const s = worstStatus(list);
        return [
          <li key={key}>
            <details className="gap-group">
              <summary className="drawer-row">
                <StatusIcon status={s} label={STATUS_WORDS[s]} decorative />
                <span className="fix-label">{label(list.length)}</span>
                <Icon name="chevron" size={12} />
              </summary>
              <ul className="plain-list">
                {list.map((g) => (
                  <GapRow key={g.id} g={g} fix={fix} onGo={onGo} />
                ))}
              </ul>
            </details>
          </li>,
        ];
      })}
    </ul>
  );
}

export function splitGaps(gaps: Gap[]) {
  return {
    blocking: gaps.filter((g) => g.severity === "blocking"),
    attention: gaps.filter((g) => g.severity === "warning"),
    info: gaps.filter((g) => g.severity === "info"),
  };
}

/** Header control: marks and numbers open the one gap list. Info is shown apart and never counted. */
function GapControl({ gaps }: { gaps: Gap[] }) {
  const drawer = useRef<HTMLDialogElement>(null);
  const { blocking, attention, info } = splitGaps(gaps);
  const close = () => drawer.current?.close();
  const sentence = [
    blocking.length ? `${blocking.length} to fix` : "Nothing to fix",
    attention.length && `${attention.length} need attention`,
    info.length && `${info.length} for your information, not counted`,
  ]
    .filter(Boolean)
    .join(". ");
  const group = (title: string, list: Gap[]) =>
    list.length > 0 && (
      <section className="drawer-group" aria-label={title}>
        <h3 className="drawer-group-title">{title}</h3>
        <GapList gaps={list} onGo={close} />
      </section>
    );
  return (
    <>
      <button
        type="button"
        className="btn btn-ghost gap-control"
        aria-haspopup="dialog"
        aria-label={`${sentence}. Open the gap list.`}
        title={sentence}
        onClick={() => drawer.current?.showModal()}
      >
        {blocking.length ? (
          <>
            <StatusIcon status="blocked" label="" decorative />
            {blocking.length}
          </>
        ) : (
          <StatusIcon status="ok" label="" decorative />
        )}
        {attention.length > 0 && (
          <>
            <StatusIcon status="attention" label="" decorative />
            {attention.length}
          </>
        )}
        {info.length > 0 && (
          <>
            <StatusIcon status="info" label="" decorative />
            {info.length}
          </>
        )}
      </button>
      <dialog className="drawer" ref={drawer} aria-labelledby="drawer-title" onClick={(e) => e.target === e.currentTarget && close()}>
        <div className="drawer-head">
          <h2 className="dialog-title" id="drawer-title">
            {blocking.length ? `${blocking.length} to fix` : "Nothing to fix"}
          </h2>
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={close}>
            <Icon name="close" size={12} />
          </button>
        </div>
        <div className="drawer-body">
          <p className="meta">Checks that information is present. Not a finding that the design complies.</p>
          {group("To fix", blocking)}
          {group("Needs attention", attention)}
          {group("For your information · not counted", info)}
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

/* —— Confirm dialog (Reset, resume) —— */

export function ConfirmDialog({
  open,
  title,
  children,
  confirm,
  cancel,
  onConfirm,
  onCancel,
  onEscape = onCancel,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirm: string;
  cancel: string;
  onConfirm: () => void;
  onCancel: () => void;
  /** Escape takes the safe choice; defaults to `onCancel`. */
  onEscape?: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      className="dialog"
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        onEscape();
      }}
    >
      <div className="dialog-body">
        <h2 className="dialog-title" id={titleId}>
          {title}
        </h2>
        <div className="meta">{children}</div>
      </div>
      <div className="footer-bar">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          {cancel}
        </button>
        <button type="button" className="btn btn-primary" onClick={onConfirm}>
          {confirm}
        </button>
      </div>
    </dialog>
  );
}
