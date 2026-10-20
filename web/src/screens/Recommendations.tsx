import { useEffect, useRef, useState } from "react";
import { SectionDRecoveryError } from "../api/sectionD";
import {
  failureText,
  type EngineProcessField,
  type ProfessionalResult,
  type SectionDIssue,
  type SectionDPlan,
} from "../api/client";
import { ServiceUnavailable, FieldSteps } from "../components";
import { practiceFlagLine, practicePrompt } from "../humanReview";
import { evidenceDocuments, shownProcessAnswer } from "../model";
import { AUTHORITY_DECISION_FIELDS, evidenceLinked, evidenceRecorded, isScopeField, practiceFromReview, SCOPE_HELP, sectionDIssueStatus } from "../professional";
import { useCase } from "../store";
import { evidenceTask } from "../evidence";
import type { Case } from "../types";

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
  const fact = [...c.facts].reverse().find((item) => item.field === `professional.${field}` && item.status === "unconfirmed");
  return fact?.value === "not_sure" || fact?.value === "not_engaged_yet" ? fact.value : "";
}

function confirmedValue(c: Case, field: string): unknown {
  const fact = [...c.facts].reverse().find((f) => f.field === field && f.status === "confirmed" && f.kind !== "proposed");
  return fact?.value;
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

function EvidenceAnswer({
  itemId,
  title,
  provisionId,
  types,
}: {
  itemId: string;
  title: string;
  provisionId: string;
  types: string[];
}) {
  const { c, dispatch } = useCase();
  const draft = c.evidenceDrafts?.[itemId] ?? { document: "", responsible: "", date: "", evidenceType: "", note: "" };
  const { document, responsible, date, evidenceType, note } = draft;
  const edit = (patch: Partial<typeof draft>) => dispatch({ type: "editEvidenceDraft", itemId, patch });
  const typeOptions = types.length ? types : [...EVIDENCE_TYPES];
  const docId = `evidence-doc-${itemId}`;
  const whoId = `evidence-who-${itemId}`;
  const dateId = `evidence-date-${itemId}`;

  function save() {
    const ref = document.trim();
    const who = responsible.trim();
    if (!ref || !who || !evidenceType) {
      edit({ note: "Add the document, person responsible and evidence type." });
      return;
    }
    dispatch({ type: "saveEvidence", itemId, document: ref, responsible: who, date, evidenceType, provisionId });
    edit({ note: `Added: ${ref}. Listed, not reviewed.` });
  }

  const earlier = evidenceDocuments(c, itemId);

  return (
    <div className="form-grid">
      <p className="sr-only">{title}</p>
      <div className="field">
        <label htmlFor={`evidence-type-${itemId}`}>Evidence type</label>
        <select id={`evidence-type-${itemId}`} value={evidenceType} onChange={(e) => edit({ evidenceType: e.target.value })}>
          <option value="">Not chosen</option>
          {typeOptions.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={docId}>Document name</label>
        <input id={docId} value={document} onChange={(e) => edit({ document: e.target.value })} />
      </div>
      <div className="field">
        <label htmlFor={whoId}>Person or organisation responsible</label>
        <input id={whoId} value={responsible} onChange={(e) => edit({ responsible: e.target.value })} />
      </div>
      <div className="field">
        <label htmlFor={dateId}>Date or revision</label>
        <input id={dateId} value={date} onChange={(e) => edit({ date: e.target.value })} placeholder="Left blank until you enter it" />
      </div>
      <div className="field">
        <button type="button" className="btn" onClick={save}>
          Save this evidence
        </button>
        {note && (
          <p className="field-note" role="status">
            {note}
          </p>
        )}
      </div>
      {earlier.length > 0 && (
        <div className="field full">
          <p className="meta">Documents already on this case</p>
          <ul className="plain-list">
            {earlier.map((item) => (
              <li key={item.id}>
                {item.title}{" "}
                <button type="button" className="btn" onClick={() => dispatch({ type: "removeEvidence", id: item.id })}>
                  Remove {item.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ProfessionalAnswers({ onEvidence }: { onEvidence: () => void }) {
  const { c, dispatch } = useCase();
  const inputs = PROFESSIONAL_FIELDS.map((q) => {
        const id = `prof-${q.field}`;
        const current = confirmedValue(c, `professional.${q.field}`);
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
              <details className="compact-help"><summary>Why we ask</summary><p>An engineer or architect must confirm their registration. Not sure keeps the official PDF on hold for officer review. A draft remains available.</p></details>
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
  const steps = PROFESSIONAL_FIELDS.map((q, i) => ({
    title: q.label,
    fields: [`prof-${q.field}`],
    content: <div className="form-grid">{inputs[i]}{q.field === "role" && deferred && <div className="full"><p className="meta">You can leave professional details for later. The officer will need them before the official PDF.</p><button className="btn" onClick={onEvidence}>Continue to evidence</button></div>}</div>,
  })).filter((_, i) => !deferred || ![1, 2].includes(i));
  return <FieldSteps previousHref="#/application?tab=alt&step=last" steps={steps} onComplete={onEvidence} />;
}

/** One coherent deterministic plan, after the current case has been saved. */
export function Recommendations() {
  const { c, dispatch, snapshotKey, loadSectionD } = useCase();
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
  const items = [...new Map<string, { id: string; issue?: SectionDIssue; plan?: SectionDPlan["items"][number] }>([
    ...(load.issues ?? []).map(issue => [issue.id, { id: issue.id, issue, plan: undefined as SectionDPlan["items"][number] | undefined }] as const),
    ...(load.plan?.items ?? []).filter(item => !load.issues?.some(issue => issue.id === item.id))
      .map(plan => [plan.id, { id: plan.id, issue: undefined as SectionDIssue | undefined, plan }] as const),
  ]).values()];
  const selectedId = items.some(item => item.id === selectedEvidence) ? selectedEvidence : items[0]?.id;
  const flag = load.professional?.required;

  return (
    <section className="stack" aria-labelledby="reco-title">
      <div className="step-heading"><h2 id="reco-title" className="section-title">Supporting documents</h2></div>
      <div className="toolbar section-switch" aria-label="Supporting document steps">
        <button className="pill" aria-pressed={view === "professional"} data-active={view === "professional"} onClick={() => setView("professional")}>Professional</button>
        <button className="pill" aria-pressed={view === "evidence"} data-active={view === "evidence"} onClick={() => setView("evidence")}>Evidence</button>
      </div>
      {view === "professional" && <>
      <ProfessionalAnswers onEvidence={() => setView("evidence")} />
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
        <a className="text-link" href="#/application?download=1">Keep a draft</a>
        <details><summary>Technical detail</summary><p>{load.recovery.detail}</p></details>
      </div> : (load.phase === "error" || load.phase === "unreachable") && <ServiceUnavailable reason={load.note} onRetry={() => setAttempt(n => n + 1)} />}
      {load.phase === "loading" && <p className="meta" role="status">Loading evidence…</p>}
      {items.length > 0 && <div className="field"><label htmlFor="evidence-choice">Document to add</label><select id="evidence-choice" value={selectedId ?? ""} onChange={e => setSelectedEvidence(e.target.value)}>
        {items.map(({ id, issue, plan }) => <option key={id} value={id}>{evidenceTask(c, issue ?? plan ?? {})}</option>)}
      </select></div>}

      {load.issues === null && load.issuesNote && <p className="empty">{load.issuesNote}</p>}
      {load.issues && (
        <div className="stack">

          {load.issues.length === 0 && <p className="empty">No Section D issues returned.</p>}
          {load.issues.filter(issue => issue.id === selectedId).map((issue) => {
            const practice = issue.practice_of_engineering;
            const practiceValue = practice.value === true ? true : practice.value === false ? false : "unknown";
            const prompt = practicePrompt(practiceValue, practice.question);
            const status = sectionDIssueStatus({
              practice: practice.value === true ? true : practice.value === false ? false : "unknown",
              facts: c.facts,
              evidenceLinked: evidenceLinked(c.facts, issue.id),
            });
            return (
              <article key={issue.id} className="card">
                <div className="card-head">
                  <h3 className="section-title">{evidenceTask(c, issue)}</h3>
                  <span className="label-pill">
                    <span className={`status-dot ${status === "needs_professional" ? "blocking" : "warning"}`} />
                    {status === "needs_professional" ? "Routed to the officer" : status === "evidence_listed" ? "evidence listed" : "open"}
                  </span>
                </div>
                <details className="compact-help"><summary>What this document should address</summary><p className="mono">{issue.provision?.provision_id ?? issue.entered_reference ?? "No confirmed reference"}</p><p>{issue.at_stake}</p>
                {issue.question && <p className="field-note">{issue.question}</p>}
                <p>
                  <span className={`status-dot ${practiceValue === true ? "blocking" : practiceValue === "unknown" ? "warning" : "pending"}`} />{" "}
                  {prompt.lead}
                </p>
                {prompt.question && <p className="field-note">{prompt.question}</p>}
                <p className="meta">
                  Evidence types to consider: {issue.recommended_types.join(", ") || "none listed"}. Not results, and not filled in for you.
                </p>
                {issue.provision?.citation && <p className="mono meta">{issue.provision.citation}</p>}
                </details>
                <EvidenceAnswer
                  itemId={issue.id}
                  provisionId={issue.provision?.provision_id ?? ""}
                  types={issue.recommended_types}
                  title="Document name"
                />
              </article>
            );
          })}
        </div>
      )}
      {load.plan && (
        <div className="stack">
          {!load.issues && <h3 className="sub-title">Evidence plan</h3>}
          {load.plan.items.length === 0 && (
            <p className="empty">No evidence items yet. Confirm a provision on Section C, then each item appears here for you to answer.</p>
          )}
          {load.plan.items.filter(item => item.id === selectedId && !load.issues?.some(issue => issue.id === item.id)).map((item) => (
            <article key={item.id} className="card">
              <div className="card-head">
                <h3 className="section-title">{evidenceTask(c, item)}</h3>
                <span className="label-pill">
                  <span className={`status-dot ${evidenceRecorded(item.status) ? "done" : "warning"}`} />
                  {item.status}
                </span>
              </div>
              <details className="compact-help"><summary>What this document should address</summary><p className="mono">{item.provision_id}</p><p>{item.performance_issue}</p>
              <p className="meta">
                Evidence types to consider: {item.recommended_types.join(", ") || "none listed"}. Not results, and not filled in for you.
              </p>
              {item.citation && <p className="mono meta">{item.citation}</p>}
              </details>
              <EvidenceAnswer
                itemId={item.id}
                provisionId={item.provision_id}
                types={item.recommended_types}
                title="Document name"
              />
            </article>
          ))}
          {load.plan.notices.map((n) => (
            <p key={n} className="meta">
              {n}
            </p>
          ))}
        </div>
      )}
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
