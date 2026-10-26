/**
 * The application as the officer reads it (Part 1, A to D and the alternative path), with each
 * finding placed under the row it is about. Rows the review has no field for keep their findings at
 * the end of their section, so nothing is ever dropped. Code checks and document attributes sit on
 * their own rows as small status pills; the code text itself opens in the code drawer, verbatim.
 */
import { useState, type ReactNode } from "react";
import type { Case, DispositionEdit, Finding, FindingState, RequestLimits, ReviewSession, RulebookGap } from "../../api/types.gen";
import { CODE_EDITION } from "../../config";
import { localField } from "../../intakeFields";
import { RetainedSourceFiles } from "../../RetainedSourceFiles";
import { AcIcon } from "../auth/bits";
import { CodeRef } from "./CodeRef";
import { FindingCard, RulebookRow } from "./FindingCard";
import { OpenFileLink } from "./OpenFileLink";
import { citationView, documentView, fileItemsView, isPeer, sectionCView, type Tone } from "./packageView";
import { sentPhrase } from "./queue";
import type { DraftRequestItem } from "./requestDraft";
import type { SheetView } from "./sheet";
import { anchoredItems, changedFields, SECTIONS, visibleFinding, visibleRulebook, type FindingFilter, type Section, type SheetAnchor, type WorkspaceRow } from "./workspaceView";

const TITLE: Record<Section, string> = {
  A: "Applicant",
  B: "Project",
  C: "Code references",
  process: "Alternative path · written by the applicant",
  D: "Supporting documents",
};

const Pill = ({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string }) => (
  <span className="rw-pill" title={title}><span className={`cf-dot is-${tone}`} aria-hidden="true" />{children}</span>
);

/** "Changed" beside a value; the earlier value opens in place. */
function Changed({ before }: { before: string | null | undefined }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="rw-chg" aria-expanded={open} onClick={() => setOpen(!open)}>Changed</button>
      {open && <span className="rw-was">Before: {before || "—"}</span>}
    </>
  );
}

export function ApplicationSheet({ c, sheet, rows, anchors, session, rulebook, states, items, limits, filter, editable, historical, focus, professional, questions, onDisposition, onText }: {
  c: Case;
  sheet: SheetView;
  rows: WorkspaceRow[];
  anchors: SheetAnchor[];
  session: ReviewSession | null;
  rulebook: RulebookGap[];
  states: Map<string, FindingState>;
  items: DraftRequestItem[];
  limits: RequestLimits;
  filter: FindingFilter;
  editable: boolean;
  /** An earlier review version: its own readings, no edits. */
  historical: boolean;
  focus: string | null;
  professional: ReactNode;
  /** The applicant's answers to saved questions, at the end. */
  questions?: ReactNode;
  onDisposition: (edit: DispositionEdit) => void;
  onText: (key: string, text: string) => void;
}) {
  const changes = historical ? new Map() : changedFields(c);
  const findings = anchoredItems((session?.findings ?? []).filter((f) => !isPeer(f)), anchors);
  const gaps = anchoredItems(rulebook, anchors);
  const files = session?.files ?? [];

  const inline = (anchor: string) => (
    <>
      {(findings.get(anchor) ?? []).map((f: Finding) => {
        const state = states.get(f.key);
        if (!state || !visibleFinding(f, state, filter)) return null;
        return (
          <FindingCard key={f.key} finding={f} state={state} item={items.find((i) => i.finding_key === f.key)} caseId={c.id}
            files={files} limits={limits} editable={editable} focused={focus === f.key} onDisposition={onDisposition} onText={onText} />
        );
      })}
      {(gaps.get(anchor) ?? []).filter((g) => visibleRulebook(g, filter)).map((g) => <RulebookRow key={g.id} message={g.message} />)}
    </>
  );

  const row = (anchor: string, label: ReactNode, value: ReactNode, field: string) => {
    const change = changes.get(localField(field));
    return (
      <div key={anchor} className="rw-row">
        <div className="rw-k">{label}</div>
        <div className="rw-v">{value}{change && <Changed before={change.before} />}</div>
        {inline(anchor)}
      </div>
    );
  };

  const refs = anchors.filter((a) => a.section === "C" && a.field.startsWith("section_c."));
  const docs = anchors.filter((a) => a.section === "D" && a.field.startsWith("evidence."));
  const fileList = session ? fileItemsView(session) : null;
  const peer = session?.findings.find(isPeer);

  return (
    <article className="cf-sheet rw-sheet" aria-label="Application">
      <h2>Safety Codes Variance · Part 1</h2>
      <p className="rw-sub">
        {CODE_EDITION}
        {session ? ` · review v${session.version}` : ""}
        {!historical && c.submitted_at ? ` · sent ${sentPhrase(c.submitted_at)}` : ""}
      </p>

      {SECTIONS.map((section) => (
        <section key={section} className="rw-sec" aria-label={TITLE[section]}>
          <h3>
            <span className="rw-badge" aria-hidden="true">{section === "process" ? <AcIcon name="list" size={13} /> : section}</span>
            {TITLE[section]}
          </h3>

          {rows.filter((r) => r.section === section).map((r) =>
            row(r.id, r.label, r.reading.value
              ? <><span className="rw-text">{r.reading.value}</span>{r.reading.unconfirmed && <span className="rw-note"> · not confirmed by the applicant</span>}</>
              : <span className={r.reading.required ? "rw-missing" : "rw-none"}>{r.reading.required ? "— missing" : "—"}</span>, r.field))}

          {section === "C" && (refs.length ? refs.map((a) => {
            const cite = session?.citations.find((x) => (x.provision_id || x.text) === a.label);
            const rowsC = session?.section_c.filter((x) => x.provision_id === a.label) ?? [];
            const canonical = cite?.canonical_citation || (!historical ? c.section_c.find((x) => x.provision_id === a.label)?.citation : null);
            return row(a.id, <span className="pr-mono">{a.label}</span>, (
              <>
                <span className="rw-pills">
                  {cite && (() => { const v = citationView(cite); return <Pill tone={v.tone} title={v.issues.join(" · ") || undefined}>{v.status}</Pill>; })()}
                  {rowsC.map((x) => { const v = sectionCView(x); return <Pill key={x.row} tone={v.tone} title={`On the form ${v.form} · in the table ${v.table}`}>{v.status}</Pill>; })}
                </span>
                {canonical && <span className="rw-code"><CodeRef citation={canonical} /></span>}
              </>
            ), a.field);
          }) : <p className="rw-empty">No code reference on file</p>)}

          {section === "process" && (fileList?.read || findings.has("process:file-checklist")) && row("process:file-checklist", "Division C file", fileList?.read ? (
            <span className="rw-pills">
              {[...fileList.items, ...fileList.demonstrate].map((r) => <Pill key={r.key} tone={r.tone} title={`Div C ${r.provision} · ${r.status}`}>{r.label}</Pill>)}
            </span>
          ) : <span className="rw-none">Not read</span>, "div_c")}

          {section === "D" && (
            <>
              {docs.map((a) => {
                const id = a.field.slice("evidence.".length);
                const read = session?.documents.find((d) => d.id === id);
                const listed = sheet.documents.find((d) => d.id === id);
                const view = read ? documentView(read) : null;
                const fileId = read ? files.find((f) => f.name === read.file)?.file_id : historical ? null : listed?.fileId;
                const known = view?.cells.filter((cell) => cell.known) ?? [];
                const unknown = view?.cells.filter((cell) => !cell.known) ?? [];
                return row(a.id, a.label, (
                  <>
                    {view ? (
                      <span className="rw-attrs">
                        {known.map((cell) => <span key={cell.label} title={cell.where || undefined}><i>{cell.label}</i> {cell.value}</span>)}
                        {unknown.length > 0 && <span className="rw-note">Not stated: {unknown.map((cell) => cell.label.toLowerCase()).join(", ")}</span>}
                      </span>
                    ) : (
                      [listed?.type, listed?.author, listed?.date].filter(Boolean).join(" · ") || null
                    )}
                    {fileId
                      ? <OpenFileLink caseId={c.id} fileId={fileId} name={read?.file || listed?.fileName || a.label} />
                      : <span className="rw-missing"> · no file</span>}
                  </>
                ), a.field);
              })}
              {professional}
              <RetainedSourceFiles caseId={c.id} />
              <p className="rw-fine">Professional evidence comes from the applicant’s registered professional. Batatis doesn’t write it.</p>
            </>
          )}

          {inline(`${section}:end`)}
        </section>
      ))}

      {questions}

      {peer && (
        <details className="rw-peer">
          <summary><span className="cf-dot is-warning" aria-hidden="true" />Peer review may help · your call</summary>
          <p>{peer.message}</p>
        </details>
      )}
    </article>
  );
}
