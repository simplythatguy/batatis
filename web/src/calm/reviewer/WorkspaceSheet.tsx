import { Fragment, useMemo, type ReactNode } from "react";
import type { Case, DispositionEdit, FindingState, RequestLimits, ReviewSession, RulebookGap, Workspace } from "../../api/types.gen";
import type { InformationRequest } from "../../api/client";
import { localField } from "../../intakeFields";
import { CODE_EDITION } from "../../config";
import { RetainedSourceFiles } from "../../RetainedSourceFiles";
import { CodeRef } from "./CodeRef";
import { FindingCard } from "./FindingCard";
import { OpenFileLink } from "./OpenFileLink";
import { OpenQuestions } from "./OpenQuestions";
import { citationView, documentView, isPeer, sectionCView } from "./packageView";
import { sentPhrase } from "./queue";
import type { DraftRequestItem } from "./requestDraft";
import type { SheetView } from "./sheet";
import { anchoredItems, changedFields, SECTIONS, visibleFinding, visibleRulebook, type FindingFilter, type Section, type SheetAnchor, type WorkspaceRow } from "./workspaceView";

const LABELS: Record<Section, string> = { A: "Applicant", B: "Project", C: "Code references", process: "Alternative path · written by the applicant", D: "Supporting documents" };

function RulebookRow({ gap }: { gap: RulebookGap }) {
  return <div className="rw-rulebook"><span className="cf-dot is-blocking" aria-hidden="true" /><div><p>{gap.message}</p><small>Required by the completeness rules · cannot be dismissed</small></div></div>;
}

export function WorkspaceSheet({ c, sheet, rows, anchors, information, questionError, session, workspace, states, items, limits, filter, editable, historical, professional, onDisposition, onText }: {
  c: Case; sheet: SheetView; rows: WorkspaceRow[]; anchors: SheetAnchor[]; information: InformationRequest | null; questionError: string;
  session: ReviewSession | null; workspace: Workspace | null; states: Map<string, FindingState>; items: DraftRequestItem[]; limits: RequestLimits;
  filter: FindingFilter; editable: boolean; historical: boolean; professional: ReactNode;
  onDisposition: (edit: DispositionEdit) => void; onText: (key: string, text: string) => void;
}) {
  const changes = useMemo(() => historical ? new Map() : changedFields(c), [c, historical]);
  const findings = anchoredItems((session?.findings ?? []).filter(f => !isPeer(f)), anchors);
  const gaps = anchoredItems(workspace?.rulebook ?? [], anchors);
  const inline = (id: string) => <>
    {(findings.get(id) ?? []).map(f => {
      const state = states.get(f.key);
      if (!state || !visibleFinding(f, state, filter)) return null;
      return <FindingCard key={f.key} finding={f} state={state} item={items.find(i => i.finding_key === f.key)} caseId={c.id} files={session?.files ?? []}
        limits={limits} editable={editable} onDisposition={onDisposition} onText={onText} />;
    })}
    {(gaps.get(id) ?? []).filter(g => visibleRulebook(g, filter)).map(g => <RulebookRow key={g.id} gap={g} />)}
  </>;
  const change = (field: string) => {
    const value = changes.get(localField(field));
    return value ? <details className="rw-change"><summary>Changed</summary><span>Previously: {value.before || "—"}</span></details> : null;
  };
  const row = (id: string, label: ReactNode, content: ReactNode, field: string) => <div key={id} className="rw-row">
    <div className="rw-key" title={typeof label === "string" ? label : undefined}>{label}</div><div className="rw-value">{content}{change(field)}</div>{inline(id)}
  </div>;

  return <article className="cf-sheet ac-sheet rw-sheet" aria-label={historical ? `Application read for review version ${session?.version}` : "Submitted application"}>
    <h2>Safety Codes Variance · Part 1</h2>
    <div className="cf-sheet-sub">{CODE_EDITION}{session ? ` · review version ${session.version}` : ""}{!historical && c.submitted_at ? ` · sent ${sentPhrase(c.submitted_at)}` : ""}</div>
    {historical && <p className="rw-meta">Earlier review · only values recorded in this review are shown</p>}
    {SECTIONS.map(section => <section className="rw-section" key={section} aria-label={LABELS[section]}>
      <h3><span className="rw-section-letter">{section === "process" ? <span aria-hidden="true">↳</span> : section}</span>{LABELS[section]}</h3>
      {rows.filter(r => r.section === section).map(r => row(r.id, r.label, r.reading.value
        ? <span>{r.reading.value}{r.reading.unconfirmed && <small className="rw-meta"> · not confirmed by the applicant</small>}</span>
        : <span className="cf-sheet-none">—</span>, r.field))}
      {section === "C" && <>
        {anchors.filter(a => a.section === "C" && a.field.startsWith("section_c.")).map(anchor => {
          const citation = session?.citations.find(c => (c.provision_id || c.text) === anchor.label);
          const checked = session?.section_c.filter(r => r.provision_id === anchor.label) ?? [];
          const ref = sheet.references.find(r => r.provision === anchor.label);
          const canonical = citation?.canonical_citation || (!historical ? c.section_c.find(r => r.provision_id === anchor.label)?.citation : null);
          return row(anchor.id, <span className="pr-mono">{anchor.label}</span>, <>
            {canonical && <CodeRef citation={canonical} />}
            <div className="rw-pills">
              {citation && (() => { const v = citationView(citation); return <span className="rw-pill" title={v.issues.join(" · ")}><span className={`cf-dot is-${v.tone}`} aria-hidden="true" />{v.status}</span>; })()}
              {checked.map(r => { const v = sectionCView(r); return <span className="rw-pill" key={r.row} title={`${v.message} · On the form: ${v.form} · In the table: ${v.table}`}><span className={`cf-dot is-${v.tone}`} aria-hidden="true" />{v.status}</span>; })}
            </div>
            {ref && !historical && <p className="rw-meta">{ref.codes}</p>}
          </>, anchor.field);
        })}
        {!anchors.some(a => a.section === "C" && a.field.startsWith("section_c.")) && <p className="rw-meta">No confirmed code reference on file</p>}
      </>}
      {section === "process" && row("process:file-checklist", "Division C file checklist", <div className="rw-pills">
        {(session?.findings ?? []).filter(f => /^(div_c\.|demonstrate\.)/.test(f.field)).map(f => <span className="rw-pill" key={f.key}>
          <span className={`cf-dot is-${states.get(f.key)?.state === "dismissed" ? "pending" : f.severity}`} aria-hidden="true" />{f.label}
        </span>)}
        {!session?.findings.some(f => /^(div_c\.|demonstrate\.)/.test(f.field)) && <span className="rw-meta">No file-checklist findings recorded</span>}
      </div>, "div_c")}
      {section === "D" && <>
        {anchors.filter(a => a.section === "D" && a.field.startsWith("evidence.")).map(anchor => {
          const id = anchor.field.slice("evidence.".length);
          const doc = session?.documents.find(d => d.id === id);
          const listed = sheet.documents.find(d => d.id === id);
          const view = doc ? documentView(doc) : null;
          const fileId = doc ? session?.files.find(f => f.name === doc.file)?.file_id : historical ? null : listed?.fileId;
          return row(anchor.id, anchor.label, <>
            {view ? <><p className="rw-meta">{view.note}</p><dl className="rw-document-props">{view.cells.map(cell => <Fragment key={cell.label}><dt>{cell.label}</dt><dd title={cell.where || undefined}>{cell.known ? cell.value : "— unknown"}</dd></Fragment>)}</dl></>
              : <p>{[listed?.type, listed?.author, listed?.date].filter(Boolean).join(" · ") || "Attributes not recorded"}</p>}
            {fileId ? <OpenFileLink caseId={c.id} fileId={fileId} name={doc?.file || listed?.fileName || anchor.label} /> : <p className="rw-meta">No retained file linked</p>}
          </>, anchor.field);
        })}
        {professional}
        <RetainedSourceFiles caseId={c.id} />
        <p className="cf-sheet-note">Professional evidence is provided by the applicant’s registered professional. Batatis does not write it.</p>
      </>}
      {inline(`${section}:end`)}
    </section>)}
    {!historical && <OpenQuestions questions={sheet.questions} loading={information === null && !questionError} error={questionError} />}
    {session?.findings.filter(isPeer).map(f => <details className="rw-peer" key={f.key}><summary>Peer review · officer’s call</summary><p>{f.message}</p></details>)}
  </article>;
}
