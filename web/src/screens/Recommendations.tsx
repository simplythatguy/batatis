import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { SectionDRecoveryError } from "../api/sectionD";
import {
  engine,
  failureText,
  type EngineProcessField,
  type ProfessionalResult,
  type SectionDIssue,
  type SectionDPlan,
  type StoredFile,
} from "../api/client";
import { ServiceUnavailable, FieldSteps } from "../components";
import { practiceFlagLine, practicePrompt } from "../humanReview";
import { evidenceDocuments, factFor, keptDocuments, orphanedEvidence, shownProcessAnswer } from "../model";
import { AUTHORITY_DECISION_FIELDS, evidenceLinked, evidenceRecorded, isScopeField, practiceFromReview, SCOPE_HELP, sectionDIssueStatus } from "../professional";
import { useCase } from "../store";
import { evidenceBinding, evidenceTask } from "../evidence";
import { EvidenceFileLink } from "../EvidenceFileLink";
import type { Case, EvidenceDraft } from "../types";

type Load = {
  recovery?: SectionDRecoveryError;
  phase: "idle" | "loading" | "live" | "error" | "unreachable";
  note: string;
  plan: SectionDPlan | null;
  issues: SectionDIssue[] | null;
  professional: ProfessionalResult | null;
  fields: EngineProcessField[];
  issuesNote: string | null;
};

const IDLE: Load = { phase: "idle", note: "", plan: null, issues: null, professional: null, fields: [], issuesNote: null };

const OCCUPANCY = [
  ["", "Not answered"],
  ["single_family", "Single-family house"],
  ["multi_family", "Multi-family"],
  ["hotel", "Hotel"],
  ["assembly", "Assembly"],
  ["care", "Care"],
  ["treatment", "Treatment"],
  ["detention", "Detention"],
  ["business", "Business"],
  ["mercantile", "Mercantile"],
  ["industrial", "Industrial"],
  ["farm", "Farm"],
  ["relocatable_industrial_camp", "Relocatable industrial camp"],
  ["mixed", "Mixed use"],
  ["other", "Other"],
] as const;

type ProfKind = "bool" | "authority" | "number" | "occupancy" | "role" | "text";

const PROFESSIONAL_FIELDS: { field: string; label: string; kind: ProfKind }[] = [
  { field: "role", label: "Who is the registered professional for this scope?", kind: "role" },
  { field: "registration_number", label: "APEGA or AAA registration number", kind: "text" },
  { field: "seal", label: "Seal that professional confirmed", kind: "text" },
  { field: "occupancy", label: "What is the occupancy or building type?", kind: "occupancy" },
  { field: "principal_dwelling_units", label: "How many principal dwelling units, excluding confirmed qualifying secondary suites?", kind: "number" },
  { field: "storeys", label: "How many storeys is the building?", kind: "number" },
  { field: "building_area_m2", label: "What is the building area in square metres (not the total of every floor)?", kind: "number" },
  { field: "part4_design", label: "Is any design carried out under Part 4, including beams, connections, or foundations?", kind: "bool" },
  { field: "ahj_requires_professional", label: "Has the authority required a registered professional for this project?", kind: "authority" },
  { field: "special_safety_concerns", label: "Has the authority found that size or complexity requires a professional?", kind: "authority" },
  { field: "roof_trusses", label: "Are wood roof trusses or truss assembly connections included?", kind: "bool" },
  { field: "preserved_wood_foundation_part4", label: "Does the project include a preserved wood foundation designed under Part 4?", kind: "bool" },
  { field: "prescriptive_route_confirmed", label: "Is the design following the prescriptive route, with no reserved professional judgement?", kind: "bool" },
  { field: "professional_judgement_required", label: "Does any proposed analysis require reserved professional judgement?", kind: "bool" },
  { field: "professional_scope_resolved", label: "Have the professional-law, discipline, and local submission requirements been resolved?", kind: "authority" },
  { field: "fire_suppression", label: "Is a fire suppression system being installed?", kind: "bool" },
  { field: "fire_alarm", label: "Is a fire alarm system being installed?", kind: "bool" },
  { field: "farm_public_use", label: "Is the farm building for public use?", kind: "bool" },
];

function deferredChoice(c: Case, field: string): "" | "not_sure" | "not_engaged_yet" {
  const fact = [...c.facts].reverse().find((item) => item.field === `professional.${field}`);
  return fact?.value === "not_sure" || fact?.value === "not_engaged_yet" ? fact.value : "";
}

function confirmedValue(c: Case, field: string): unknown {
  const fact = [...c.facts].reverse().find((f) => f.field === field && f.status === "confirmed" && f.kind !== "proposed");
  return fact?.value;
}

/** As the engine reads it (engine/professional.py): this checklist's own answer, else the project's value. */
function professionalValue(c: Case, field: string): unknown {
  return confirmedValue(c, `professional.${field}`) ?? confirmedValue(c, field);
}



const EVIDENCE_TYPES = [
  "manufacturer's literature",
  "existing STANDATA variance",
  "ISO 17025 test report",
  "evaluation",
  "evaluation + testing",
  "qualification",
  "ISO 17065 certification",
  "CCMC evaluation",
  "ICC-ES evaluation",
  "registered professional opinion",
  "engineering review",
] as const;

const EMPTY_DRAFT: EvidenceDraft = { document: "", responsible: "", date: "", evidenceType: "", fileRef: undefined, note: "", step: 0 };
const STEPS = 3;

/** Saved details of one document, or the staged edit waiting for the engine. */
function documentDetails(c: Case, id: string) {
  const staged = c.listedEvidence?.find((item) => item.id === id);
  const saved = (field: string) => {
    const value = factFor(c, `evidence.${id}.${field}`)?.value;
    return typeof value === "string" ? value : "";
  };
  return {
    document: staged?.description ?? saved("title"),
    evidenceType: staged?.evidenceType ?? saved("evidence_type"),
    responsible: staged && staged.responsible !== undefined ? staged.responsible ?? "" : saved("responsible_party"),
    date: staged && staged.date !== undefined ? staged.date ?? "" : saved("date"),
    fileRef: staged?.fileRef !== undefined ? staged.fileRef : evidenceBinding(c.facts, id)?.fileId ?? null,
  };
}

/**
 * Add or edit one document in three short steps: name, type, optional details. Saving stages
 * one versioned write, including the chosen uploaded PDF. Only an engine acknowledgement
 * counts as saved. Attaching bytes never reviews the document or confirms who prepared it.
 */
function EvidenceAnswer({ itemId, provisionId, types }: { itemId: string; provisionId: string; types: string[] }) {
  const { c, dispatch, saveStatus, saveDraft, engineId, uploadEvidenceFile } = useCase();
  const [files, setFiles] = useState<StoredFile[]>([]);
  const [filesNote, setFilesNote] = useState("");
  const [fileBusy, setFileBusy] = useState(false);
  const [inventoryRevision, setInventoryRevision] = useState(0);
  const uploadInput = useRef<HTMLInputElement>(null);
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => {
    if (!engineId) return;
    const ctl = new AbortController();
    setFiles([]);
    setFilesNote("");
    engine.files(engineId, ctl.signal).then(setFiles).catch((error) => {
      if (!ctl.signal.aborted) setFilesNote(failureText(error));
    });
    return () => ctl.abort();
  }, [engineId, inventoryRevision]);
  const draft = { ...EMPTY_DRAFT, ...c.evidenceDrafts?.[itemId] };
  const step = Math.min(Math.max(draft.step ?? 0, 0), STEPS - 1);
  const edit = (patch: Partial<EvidenceDraft>) => dispatch({ type: "editEvidenceDraft", itemId, patch });
  const input = useRef<HTMLInputElement & HTMLSelectElement>(null);
  const moved = useRef(false);
  useLayoutEffect(() => {
    if (!moved.current) return;
    moved.current = false;
    input.current?.focus({ preventScroll: true });
    input.current?.scrollIntoView({ block: "nearest" });
  });
  const go = (next: number, patch: Partial<EvidenceDraft> = {}) => {
    moved.current = true;
    edit({ ...patch, step: next, note: "" });
  };
  const typeOptions = [...new Set([...(types.length ? types : EVIDENCE_TYPES), ...(draft.evidenceType ? [draft.evidenceType] : [])])];
  const docId = `evidence-doc-${itemId}`;

  function next() {
    if (step === 0 && !draft.document.trim()) return edit({ note: "Enter the document name." });
    if (step === 1 && !draft.evidenceType) return edit({ note: "Choose a document type." });
    go(step + 1);
  }
  function save() {
    if (fileBusy) return;
    moved.current = true;
    dispatch({ type: "saveEvidence", itemId, document: draft.document, responsible: draft.responsible, date: draft.date, evidenceType: draft.evidenceType, provisionId, fileRef: draft.fileRef, ...(draft.editing ? { slot: draft.editing } : {}) });
  }
  async function upload(file: File) {
    setFileBusy(true);
    setFilesNote("");
    try {
      const saved = await uploadEvidenceFile(file);
      if (!active.current) return;
      edit({ fileRef: saved.id, note: "PDF uploaded. Save the document to attach it." });
      setInventoryRevision((n) => n + 1);
    } catch (error) { if (active.current) setFilesNote(failureText(error)); }
    finally { if (active.current) setFileBusy(false); }
  }
  const onEnter = (e: KeyboardEvent) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    if (step < STEPS - 1) next();
    else save();
  };

  const saved = evidenceDocuments(c, itemId);
  const savedIds = new Set(saved.map((doc) => doc.id));
  const staged = (c.listedEvidence ?? []).filter((item) => item.taskId === itemId && !savedIds.has(item.id) && !c.unscopedEvidence?.includes(item.id));
  const rows = [...saved.map((doc) => doc.id), ...staged.map((item) => item.id)];
  const removing = new Set(c.deletedEvidence ?? []);
  const busy = saveStatus === "saving";
  const unsaved = rows.some((id) => removing.has(id) || c.listedEvidence?.some((item) => item.id === id));

  return (
    <div className="stack doc-block">
      <div className="doc-entry" role="group" aria-label={draft.editing ? "Edit document" : "Add a document"}>
        <div className="doc-step-head">
          <span className="meta">{draft.editing ? `Editing ${documentDetails(c, draft.editing).document || "document"}` : ["Name", "Type", "Details"][step]}</span>
          <span className="meta">Step {step + 1} of {STEPS}</span>
        </div>
        {step === 0 && (
          <div className="field">
            <label htmlFor={docId}>Document name</label>
            <input ref={input} id={docId} value={draft.document} onKeyDown={onEnter} onChange={(e) => edit({ document: e.target.value })} />
            <p className="field-note">The title on the report, letter or listing.</p>
          </div>
        )}
        {step === 1 && (
          <div className="field">
            <label htmlFor={`evidence-type-${itemId}`}>Document type</label>
            <select ref={input} id={`evidence-type-${itemId}`} value={draft.evidenceType} onKeyDown={onEnter} onChange={(e) => edit({ evidenceType: e.target.value })}>
              <option value="">Choose a type</option>
              {typeOptions.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
            <details className="compact-help"><summary>About types</summary><p>These are suggestions, not test results. Your designer decides what the evidence must show.</p></details>
          </div>
        )}
        {step === 2 && (
          <>
            <div className="field">
              <label htmlFor={`evidence-who-${itemId}`}>Prepared by (optional)</label>
              <input ref={input} id={`evidence-who-${itemId}`} value={draft.responsible} onKeyDown={onEnter} onChange={(e) => edit({ responsible: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor={`evidence-date-${itemId}`}>Date or revision (optional)</label>
              <input id={`evidence-date-${itemId}`} value={draft.date} onKeyDown={onEnter} onChange={(e) => edit({ date: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor={`evidence-file-${itemId}`}>Supporting PDF</label>
              <select id={`evidence-file-${itemId}`} value={draft.fileRef ?? ""} disabled={fileBusy}
                onChange={(e) => edit({ fileRef: e.target.value || null, note: "" })}>
                <option value="">No file attached</option>
                {draft.fileRef && !files.some((f) => f.id === draft.fileRef) && <option value={draft.fileRef}>Selected PDF</option>}
                {files.map((file) => <option key={file.id} value={file.id}>{file.name}</option>)}
              </select>
              <input ref={uploadInput} type="file" accept="application/pdf,.pdf" hidden onChange={(e) => {
                const file = e.target.files?.[0]; e.target.value = ""; if (file) void upload(file);
              }} />
              <div className="btn-row">
                <button type="button" className="btn btn-xs" disabled={fileBusy} onClick={() => uploadInput.current?.click()}>{fileBusy ? "Uploading…" : draft.fileRef ? "Upload replacement PDF" : "Upload PDF"}</button>
                {draft.fileRef && <button type="button" className="btn btn-xs" disabled={fileBusy} onClick={() => edit({ fileRef: null, note: "Save to remove this binding. The source PDF stays in this application." })}>Remove file binding</button>}
              </div>
              <p className="field-note">Choose a saved PDF or upload one. A document name alone is a listing.</p>
              {filesNote && <p className="field-note" role="status">{filesNote} <button type="button" className="btn btn-xs" onClick={() => setInventoryRevision((n) => n + 1)}>Refresh files</button></p>}
            </div>
          </>
        )}
        {draft.note && <p className="field-note doc-note" role="status">{draft.note}</p>}
        <div className="step-controls">
          {step > 0
            ? <button type="button" className="btn btn-ghost" disabled={fileBusy} onClick={() => go(step - 1)}>Back</button>
            : draft.editing
              ? <button type="button" className="btn btn-ghost" onClick={() => edit({ ...EMPTY_DRAFT, editing: undefined })}>Cancel</button>
              : <span />}
          {step < STEPS - 1
            ? <button type="button" className="btn btn-primary" onClick={next}>Continue</button>
            : <button type="button" className="btn btn-primary" disabled={fileBusy} onClick={save}>Save document</button>}
        </div>
      </div>
      {rows.length > 0 && (
        <div className="doc-list" aria-live="polite">
          <p className="meta">Added documents</p>
          <ul className="plain-list">
            {rows.map((id) => {
              const details = documentDetails(c, id);
              const title = details.document || saved.find((doc) => doc.id === id)?.title || id;
              const pendingRemoval = removing.has(id);
              const pendingSave = c.listedEvidence?.some((item) => item.id === id);
              const binding = evidenceBinding(c.facts, id);
              const status = pendingRemoval ? (busy ? "Removing…" : "Not removed yet")
                : pendingSave ? (busy ? "Saving…" : "Not saved yet")
                : binding ? "Saved · PDF attached" : "Saved · listed, no file attached";
              return (
                <li key={id} className="doc-row">
                  <div className="doc-row-text">
                    <span className="doc-title">{title}</span>
                    <span className="meta doc-status">
                      <span className={`status-dot ${pendingRemoval || pendingSave ? (busy ? "pending" : "warning") : "done"}`} /><span>{status}</span>
                    </span>
                    {c.evidenceIssues?.[id] && <span className="field-note">{c.evidenceIssues[id]}</span>}
                    {binding && engineId && <span className="meta">Source: {binding.name} · <EvidenceFileLink caseId={engineId} fileId={binding.fileId} name={binding.name} /></span>}
                  </div>
                  {!pendingRemoval && (
                    <div className="doc-row-actions">
                      <button type="button" className="btn btn-xs" disabled={fileBusy} aria-label={`Edit ${title}`} onClick={() => go(0, { ...details, editing: id })}>Edit</button>
                      <button type="button" className="btn btn-xs" disabled={fileBusy} aria-label={`Remove ${title}`} onClick={() => dispatch({ type: "removeEvidence", id })}>Remove listing</button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
          {unsaved && saveStatus === "failed" && <button type="button" className="btn btn-xs" onClick={() => void saveDraft()}>Try saving again</button>}
        </div>
      )}
      {engineId && files.length > 0 && <details className="compact-help">
        <summary>Saved source PDFs ({files.length})</summary>
        <p className="field-note">Removing or replacing a binding keeps these PDFs until the application is deleted or expires.</p>
        <ul className="plain-list">{files.map((file) => <li key={file.id}>{file.name} · <EvidenceFileLink caseId={engineId} fileId={file.id} name={file.name} /></li>)}</ul>
      </details>}
    </div>
  );
}

function ProfessionalAnswers({ onEvidence, missing }: { onEvidence: () => void; missing?: string[] }) {
  const { c, dispatch } = useCase();
  const inputs = PROFESSIONAL_FIELDS.map((q) => {
        const id = `prof-${q.field}`;
        const current = professionalValue(c, q.field);
        if (q.kind === "occupancy") {
          const value = typeof current === "string" ? current : "";
          return (
            <div key={q.field} className={`field full ${value ? "" : "is-empty"}`}>
              <label className="sr-only" htmlFor={id}>{q.label}</label>
              <select
                id={id}
                value={value}
                onChange={(e) => {
                  if (e.target.value) dispatch({ type: "setProfessionalFact", field: q.field, value: e.target.value });
                  else dispatch({ type: "answerScope", field: q.field, answer: "clear" });
                }}
              >
                {OCCUPANCY.map(([value, label]) => (
                  <option key={value || "empty"} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          );
        }
        if (q.kind === "role") {
          const held = deferredChoice(c, q.field);
          const value = held || (current === "engineer" || current === "architect" ? current : "");
          return (
            <div key={q.field} className={`field full ${value ? "" : "is-empty"}`}>
              <label className="sr-only" htmlFor="prof-role">{q.label}</label>
              <details className="compact-help"><summary>Why we ask</summary><p>If a professional is required, provide their identity and authenticated work. Not sure or Not engaged yet leaves the requirement for the officer to determine. A draft remains available; mandatory duties still apply.</p></details>
              <select
                id="prof-role"
                value={value}
                onChange={(e) => {
                  const next = e.target.value;
                  if (next === "") {
                    dispatch({ type: "answerScope", field: q.field, answer: "clear" });
                  } else if (next === "not_sure" || next === "not_engaged_yet") {
                    dispatch({ type: "deferProfessional", field: q.field, choice: next, label: q.label });
                  } else if (next === "engineer" || next === "architect") {
                    dispatch({ type: "setProfessionalFact", field: q.field, value: next });
                  }
                }}
              >
                <option value="">Not answered</option>
                <option value="engineer">Engineer</option>
                <option value="architect">Architect</option>
                <option value="not_sure">Not sure</option>
                <option value="not_engaged_yet">Not engaged yet</option>
              </select>
            </div>
          );
        }
        if (q.kind === "text") {
          const held = deferredChoice(c, q.field);
          const value = held ? "" : typeof current === "string" ? current : "";
          return (
            <div key={q.field} className={`field full ${held || value ? "" : "is-empty"}`}>
              <label className="sr-only" htmlFor={id}>{q.label}</label>
              <select
                aria-label={`${q.label} choice`}
                value={held}
                onChange={(e) => {
                  const next = e.target.value;
                  if (next === "not_sure" || next === "not_engaged_yet") {
                    dispatch({ type: "deferProfessional", field: q.field, choice: next, label: q.label });
                  } else {
                    dispatch({ type: "answerScope", field: q.field, answer: "clear" });
                  }
                }}
              >
                <option value="">Enter it here</option>
                <option value="not_sure">Not sure</option>
                <option value="not_engaged_yet">Not engaged yet</option>
              </select>
              {held === "" && (
                <input id={id} value={value} onChange={(e) => dispatch({ type: "setProfessionalFact", field: q.field, value: e.target.value })} />
              )}
            </div>
          );
        }
        if (q.kind === "number") {
          const value = typeof current === "number" ? String(current) : "";
          return (
            <div key={q.field} className={`field full ${value ? "" : "is-empty"}`}>
              <label className="sr-only" htmlFor={id}>{q.label}</label>
              <input
                id={id}
                type="number"
                min={1}
                value={value}
                onChange={(e) => {
                  if (e.target.value === "") {
                    dispatch({ type: "answerScope", field: q.field, answer: "clear" });
                    return;
                  }
                  const n = Number(e.target.value);
                  if (Number.isFinite(n) && n > 0) {
                    dispatch({ type: "setProfessionalFact", field: q.field, value: q.field === "building_area_m2" ? n : Math.trunc(n) });
                  }
                }}
              />
            </div>
          );
        }
        if (q.kind !== "bool" && q.kind !== "authority") return null;
        const scopeField = isScopeField(q.field) ? q.field : null;
        const authorityField = (AUTHORITY_DECISION_FIELDS as readonly string[]).includes(q.field);
        const notSure = c.questions.some((question) => question.id === `q-scope-${q.field}` && !question.answer);
        const recorded = [...c.facts].reverse().find((fact) => fact.field === `professional.${q.field}` && fact.kind !== "proposed");
        const chosen = recorded?.value;
        const value = notSure ? "not-sure" : chosen === true ? "yes" : chosen === false ? "no" : "";
        return (
          <div key={q.field} className={`field full ${value ? "" : "is-empty"}`}>
            <label className="sr-only" htmlFor={id}>{q.label}</label>
            {scopeField && <details className="compact-help"><summary>Help</summary><p>{SCOPE_HELP[scopeField]}</p></details>}
            {authorityField && (
              <p className="field-note">
                Report the authority’s decision, or choose Not sure.
              </p>
            )}
            <select
              id={id}
              value={value}
              onChange={(e) => {
                const next = e.target.value;
                if (next === "" || next === "yes" || next === "no" || next === "not-sure") {
                  dispatch({
                    type: "answerScope",
                    field: q.field,
                    answer: next === "" ? "clear" : next,
                    text: q.label,
                  });
                }
              }}
            >
              <option value="">Not answered</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
              <option value="not-sure">Not sure</option>
            </select>
          </div>
        );
      });
  const deferred = deferredChoice(c, "role");
  const all = PROFESSIONAL_FIELDS.map((q, i) => ({
    title: q.label,
    fields: [`prof-${q.field}`],
    known: q.field !== "role" && professionalValue(c, q.field) !== undefined,
    content: <div className="form-grid">{inputs[i]}{q.field === "role" && deferred && <p className="meta full">Leave these details for later. The official PDF stays on hold.</p>}</div>,
    continueAction: q.field === "role" && deferred ? { label: "Add evidence", onClick: onEvidence, optionalLabel: "Add more details" } : undefined,
  })).filter((_, i) => !deferred || ![1, 2].includes(i));
  // Only what the professional screen still needs, never what the project already says (storeys, occupancy,
  // area…). Everything stays editable once nothing is open.
  const needed = missing && new Set(missing.flatMap((name) => name.split(" or ")).map((name) => name.replace(/^professional\./, "")));
  const open = all.filter((step, i) => !step.known && (!needed || i === 0 || needed.has(step.fields[0].replace(/^prof-/, ""))));
  const steps = open.length ? open : all;
  return <FieldSteps previousHref="#/application?tab=alt&step=last" steps={steps} onComplete={onEvidence} />;
}

/** One coherent deterministic plan, after the current case has been saved. */
export function Recommendations() {
  const { c, dispatch, snapshotKey, loadSectionD, saveStatus } = useCase();
  const [view, setView] = useState("professional");
  const [selectedEvidence, setSelectedEvidence] = useState("");
  const [attempt, setAttempt] = useState(0);
  const attempted = useRef(0);
  const [load, setLoad] = useState<Load>(IDLE);

  useEffect(() => {
    let active = true;
    setLoad({ ...IDLE, phase: "loading" });
    const retry = attempted.current !== attempt;
    attempted.current = attempt;
    void loadSectionD(retry).then(result => {
      if (!active || !result) return;
      const practice = practiceFromReview(c.practiceOfEngineering, result.professional.required,
        Boolean(result.issues?.some(issue => issue.practice_of_engineering.value === true)));
      if (c.practiceOfEngineering !== practice) dispatch({ type: "notePractice", value: practice });
      // Mirror the engine: a withdrawn reference leaves its documents on the case, unlinked,
      // and choosing that reference again does not relink them.
      const orphaned = orphanedEvidence(c, [...result.plan.items.map(item => item.id), ...(result.issues ?? []).map(issue => issue.id)]);
      if (orphaned.some(id => !c.unscopedEvidence?.includes(id))) dispatch({ type: "noteUnscopedEvidence", ids: orphaned });
      setLoad({ ...result, phase: "live", note: "" });
    }).catch(error => {
      if (active) setLoad({ ...IDLE, phase: "error", note: failureText(error), recovery: error instanceof SectionDRecoveryError ? error : undefined });
    });
    return () => { active = false; };
    // Snapshot captures generation, revision and deterministic reference expansion.
    // Status changes and unfinished editor text must not start another read.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshotKey, attempt, dispatch]);

  // Issues and plans describe the same items. Prefer the issue's richer context;
  // retain plan-only entries when an older engine has no issues route.
  // `benchmark-unconfirmed` (no provision, nothing entered) is the empty state, not a task.
  const taskIssues = load.issues?.filter(issue => issue.provision || issue.entered_reference) ?? null;
  const items = [...new Map<string, { id: string; issue?: SectionDIssue; plan?: SectionDPlan["items"][number] }>([
    ...(taskIssues ?? []).map(issue => [issue.id, { id: issue.id, issue, plan: undefined as SectionDPlan["items"][number] | undefined }] as const),
    ...(load.plan?.items ?? []).filter(item => !taskIssues?.some(issue => issue.id === item.id))
      .map(plan => [plan.id, { id: plan.id, issue: undefined as SectionDIssue | undefined, plan }] as const),
  ]).values()];
  const selectedId = items.some(item => item.id === selectedEvidence) ? selectedEvidence : items[0]?.id;
  const flag = load.professional?.required;
  const kept = keptDocuments(c);

  return (
    <section className="stack" aria-labelledby="reco-title">
      <div className="step-heading"><h2 id="reco-title" className="section-title">Supporting documents</h2></div>
      <div className="toolbar section-switch" aria-label="Supporting document steps">
        <button className="pill" aria-pressed={view === "professional"} data-active={view === "professional"} onClick={() => setView("professional")}>Professional</button>
        <button className="pill" aria-pressed={view === "evidence"} data-active={view === "evidence"} onClick={() => setView("evidence")}>Evidence</button>
      </div>
      {view === "professional" && <>
      <ProfessionalAnswers onEvidence={() => setView("evidence")} missing={load.professional?.missing_facts} />
      <details className="compact-help"><summary>Professional review notes</summary>
        {flag && <p>{practiceFlagLine(flag)}</p>}
        <p>Batatis recommends evidence. Your professional supplies the analysis. This is not a safety or compliance decision.</p>
        {load.professional?.reasons.map(r => <p key={r.code}>{r.message} {r.citation}</p>)}
        {load.professional?.questions.map(q => <p key={q}>{q}</p>)}
      </details>
      </>}
      {view === "evidence" && <>
      {load.recovery ? <div className="recovery" role="status"><p>{load.recovery.message}</p>
        {load.recovery.kind === "conflict" && <button className="btn" onClick={() => setAttempt(n => n + 1)}>Refresh case and retry</button>}
        {saveStatus !== "gone" && <a className="text-link" href="#/application?download=1">Keep a draft</a>}
        <details><summary>Technical detail</summary><p>{load.recovery.detail}</p></details>
      </div> : (load.phase === "error" || load.phase === "unreachable") && <ServiceUnavailable reason={load.note} onRetry={() => setAttempt(n => n + 1)} />}
      {load.phase === "loading" && <p className="meta" role="status">Loading evidence…</p>}
      {load.phase === "live" && items.length === 0 && <div className="empty-state" role="status">
        <p>No code references selected. Choose one in Section C to see its evidence tasks.</p>
        <a className="text-link" href="#/section-c">Review code references</a>
      </div>}
      {items.length > 0 && <div className="field"><label htmlFor="evidence-choice">Sentence & evidence task</label><select id="evidence-choice" value={selectedId ?? ""} onChange={e => setSelectedEvidence(e.target.value)}>
        {items.map(({ id, issue, plan }) => <option key={id} value={id}>{evidenceTask(c, issue ?? plan ?? {})}</option>)}
      </select></div>}

      {load.issues === null && load.issuesNote && <p className="empty">{load.issuesNote}</p>}
      {taskIssues && (
        <div className="stack">

          {taskIssues.filter(issue => issue.id === selectedId).map((issue) => {
            const practice = issue.practice_of_engineering;
            const practiceValue = practice.value === true ? true : practice.value === false ? false : "unknown";
            const prompt = practicePrompt(practiceValue, practice.question);
            const status = sectionDIssueStatus({
              practice: practice.value === true ? true : practice.value === false ? false : "unknown",
              facts: c.facts,
              evidenceLinked: evidenceLinked(c.facts, issue.id, c.unscopedEvidence),
            });
            return (
              <article key={issue.id} className="card">
                <div className="card-head">
                  <h3 className="section-title">Add a document</h3>
                  <span className="label-pill">
                    <span className={`status-dot ${status === "needs_professional" ? "blocking" : "warning"}`} />
                    {status === "needs_professional" ? "Routed to the officer" : status === "evidence_listed" ? "evidence listed" : "open"}
                  </span>
                </div>
                <p className="meta evidence-context">{issue.provision?.provision_id ?? issue.entered_reference ?? "No confirmed reference"} · {evidenceTask(c, issue).split(" · ").slice(1).join(" · ")}</p>
                <details className="compact-help"><summary>Document guidance</summary><p>Ask your designer to compare the proposed design with this code requirement.</p>
                <details className="compact-help"><summary>Comparison details</summary><p>{issue.at_stake}</p></details>
                {issue.question && <p className="field-note">{issue.question}</p>}
                <p>
                  <span className={`status-dot ${practiceValue === true ? "blocking" : practiceValue === "unknown" ? "warning" : "pending"}`} />{" "}
                  {prompt.lead}
                </p>
                {prompt.question && <p className="field-note">{prompt.question}</p>}
                <details className="compact-help"><summary>Evidence types</summary><p>{issue.recommended_types.join(", ") || "None listed"}. These are suggestions, not test results.</p></details>
                {issue.provision?.citation && <p className="mono meta">{issue.provision.citation}</p>}
                </details>
                <EvidenceAnswer key={issue.id} itemId={issue.id} provisionId={issue.provision?.provision_id ?? ""} types={issue.recommended_types} />
              </article>
            );
          })}
        </div>
      )}
      {load.plan && (
        <div className="stack">
          {!load.issues && items.length > 0 && <h3 className="sub-title">Evidence plan</h3>}
          {load.plan.items.filter(item => item.id === selectedId && !taskIssues?.some(issue => issue.id === item.id)).map((item) => (
            <article key={item.id} className="card">
              <div className="card-head">
                <h3 className="section-title">Add a document</h3>
                <span className="label-pill">
                  <span className={`status-dot ${evidenceRecorded(item.status) ? "done" : "warning"}`} />
                  {item.status}
                </span>
              </div>
              <p className="meta evidence-context">{item.provision_id}</p>
              <details className="compact-help"><summary>Document guidance</summary><p>{item.performance_issue}</p>
              <details className="compact-help"><summary>Evidence types</summary><p>{item.recommended_types.join(", ") || "None listed"}. These are suggestions, not test results.</p></details>
              {item.citation && <p className="mono meta">{item.citation}</p>}
              </details>
              <EvidenceAnswer key={item.id} itemId={item.id} provisionId={item.provision_id} types={item.recommended_types} />
            </article>
          ))}
          {load.plan.notices.length > 0 && <details className="compact-help"><summary>Evidence notes</summary>{load.plan.notices.map((n) => (
            <p key={n} className="meta">
              {n}
            </p>
          ))}</details>}
        </div>
      )}
      {kept.length > 0 && <details className="compact-help"><summary>Kept documents ({kept.length})</summary>
        <p className="meta">Their code reference was removed. They stay on this case, not linked to a task.</p>
        <ul className="plain-list">{kept.map(item => <li key={item.id}>{item.title}{" "}
          <button type="button" className="btn btn-xs" aria-label={`Remove ${item.title}`} onClick={() => dispatch({ type: "removeEvidence", id: item.id })}>Remove</button></li>)}</ul>
      </details>}
      </>}
      {load.fields.length > 0 && (
        <div>
          <details className="compact-help"><summary>Saved process answers</summary>
          <ul className="plain-list">
            {load.fields.map((f) => {
              const written = shownProcessAnswer(f.id, f.answer?.value, c.process);
              return (
                <li key={f.id}>
                  <span className={`status-dot ${written ? "done" : "blocking"}`} /> {f.label}: {written || "not written yet"}
                </li>
              );
            })}
          </ul></details>
        </div>
      )}
    </section>
  );
}
