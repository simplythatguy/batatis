import { useEffect, useState } from "react";
import {
  engine,
  EngineError,
  failureText,
  type EngineProcessField,
  type ProfessionalResult,
  type SectionDIssue,
  type SectionDPlan,
} from "../api/client";
import { DemoFallback, RoleNote } from "../components";
import { practiceFlagLine, practicePrompt } from "../humanReview";
import { answeredYes } from "../model";
import { evidenceLinked, evidenceRecorded, isScopeField, practiceFromReview, professionalConfirmed, SCOPE_HELP, sectionDIssueStatus } from "../professional";
import { failureKind } from "../rules";
import { useCase } from "../store";
import type { Case } from "../types";

type Load = {
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

type ProfKind = "bool" | "number" | "occupancy" | "role" | "text";

const PROFESSIONAL_FIELDS: { field: string; label: string; kind: ProfKind }[] = [
  { field: "role", label: "Who is the registered professional for this scope?", kind: "role" },
  { field: "registration_number", label: "APEGA or AAA registration number", kind: "text" },
  { field: "seal", label: "Seal that professional confirmed", kind: "text" },
  { field: "occupancy", label: "What is the occupancy or building type?", kind: "occupancy" },
  { field: "principal_dwelling_units", label: "How many principal dwelling units, excluding confirmed qualifying secondary suites?", kind: "number" },
  { field: "storeys", label: "How many storeys is the building?", kind: "number" },
  { field: "building_area_m2", label: "What is the building area in square metres (not the total of every floor)?", kind: "number" },
  { field: "part4_design", label: "Is any design carried out under Part 4, including beams, connections, or foundations?", kind: "bool" },
  { field: "ahj_requires_professional", label: "Has the authority required a registered professional for this project?", kind: "bool" },
  { field: "special_safety_concerns", label: "Has the authority found that size or complexity requires a professional?", kind: "bool" },
  { field: "roof_trusses", label: "Are wood roof trusses or truss assembly connections included?", kind: "bool" },
  { field: "preserved_wood_foundation_part4", label: "Does the project include a preserved wood foundation designed under Part 4?", kind: "bool" },
  { field: "prescriptive_route_confirmed", label: "Is the design following the prescriptive route, with no reserved professional judgement?", kind: "bool" },
  { field: "professional_judgement_required", label: "Does any proposed analysis require reserved professional judgement?", kind: "bool" },
  { field: "professional_scope_resolved", label: "Have the professional-law, discipline, and local submission requirements been resolved?", kind: "bool" },
  { field: "fire_suppression", label: "Is a fire suppression system being installed?", kind: "bool" },
  { field: "fire_alarm", label: "Is a fire alarm system being installed?", kind: "bool" },
  { field: "farm_public_use", label: "Is the farm building for public use?", kind: "bool" },
];

function confirmedValue(c: Case, field: string): unknown {
  const fact = [...c.facts].reverse().find((f) => f.field === field && f.status === "confirmed" && f.kind !== "proposed");
  return fact?.value;
}

function flagDot(flag: "yes" | "no" | "depends"): string {
  if (flag === "yes") return "blocking";
  if (flag === "depends") return "warning";
  return "pending";
}

function EvidenceAnswer({ itemId, title }: { itemId: string; title: string }) {
  const { c, dispatch } = useCase();
  const savedDoc = confirmedValue(c, `evidence.${itemId}.file_ref`);
  const savedWho = confirmedValue(c, `evidence.${itemId}.responsible_party`);
  const savedDate = confirmedValue(c, `evidence.${itemId}.date`);
  const [document, setDocument] = useState(typeof savedDoc === "string" ? savedDoc : "");
  const [responsible, setResponsible] = useState(typeof savedWho === "string" ? savedWho : "");
  const [date, setDate] = useState(typeof savedDate === "string" ? savedDate : "");
  const [note, setNote] = useState("");
  const docId = `evidence-doc-${itemId}`;
  const whoId = `evidence-who-${itemId}`;
  const dateId = `evidence-date-${itemId}`;

  function save() {
    if (!document.trim() || !responsible.trim()) {
      setNote("Name the document and the person responsible. Both stay blank until you write them.");
      return;
    }
    dispatch({ type: "saveEvidence", itemId, document, responsible, date });
    setNote("Saved. Earlier documents stay on the case. This does not assess the document.");
  }

  const earlier = c.facts
    .filter((f) => (f.field.startsWith(`evidence.${itemId}.`) || f.field.startsWith(`evidence.${itemId}~`)) && f.field.endsWith(".title"))
    .map((f) => (typeof f.value === "string" ? f.value : ""))
    .filter(Boolean);

  return (
    <div className="form-grid">
      <p className="meta full">{title}</p>
      <div className="field">
        <label htmlFor={docId}>Document name</label>
        <input id={docId} value={document} onChange={(e) => setDocument(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor={whoId}>Person or organisation responsible</label>
        <input id={whoId} value={responsible} onChange={(e) => setResponsible(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor={dateId}>Date or revision</label>
        <input id={dateId} value={date} onChange={(e) => setDate(e.target.value)} placeholder="Left blank until you enter it" />
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
            {earlier.map((title, index) => (
              <li key={`${title}-${index}`}>{title}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ProfessionalAnswers() {
  const { c, dispatch } = useCase();
  return (
    <div className="form-grid">
      <p className="meta full section-hint">
        These start empty. A registered professional is an engineer or architect you confirm, with a seal or a registration number. Yes, No, and Not sure on the questions below do not clear that. Not sure is sent to the officer. You can return a question to Not answered.
      </p>
      {PROFESSIONAL_FIELDS.map((q) => {
        const id = `prof-${q.field}`;
        const current = confirmedValue(c, `professional.${q.field}`);
        if (q.kind === "occupancy") {
          const value = typeof current === "string" ? current : "";
          return (
            <div key={q.field} className={`field full ${value ? "" : "is-empty"}`}>
              <label htmlFor={id}>{q.label}</label>
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
          const value = typeof current === "string" ? current : "";
          return (
            <div key={q.field} className={`field full ${value ? "" : "is-empty"}`}>
              <label htmlFor="prof-role">{q.label}</label>
              <p className="field-note">Engineer or architect. A name copied from a document does not count. A seal can stand in for the registration number.</p>
              <select
                id="prof-role"
                value={value === "engineer" || value === "architect" ? value : ""}
                onChange={(e) => {
                  if (e.target.value === "engineer" || e.target.value === "architect") {
                    dispatch({ type: "setProfessionalFact", field: q.field, value: e.target.value });
                  }
                }}
              >
                <option value="">Not answered</option>
                <option value="engineer">Engineer</option>
                <option value="architect">Architect</option>
              </select>
            </div>
          );
        }
        if (q.kind === "text") {
          const value = typeof current === "string" ? current : "";
          return (
            <div key={q.field} className={`field full ${value ? "" : "is-empty"}`}>
              <label htmlFor={id}>{q.label}</label>
              <input id={id} value={value} onChange={(e) => dispatch({ type: "setProfessionalFact", field: q.field, value: e.target.value })} />
            </div>
          );
        }
        if (q.kind === "number") {
          const value = typeof current === "number" ? String(current) : "";
          return (
            <div key={q.field} className={`field full ${value ? "" : "is-empty"}`}>
              <label htmlFor={id}>{q.label}</label>
              <input
                id={id}
                type="number"
                min={1}
                value={value}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  if (e.target.value !== "" && Number.isFinite(n) && n > 0) {
                    dispatch({ type: "setProfessionalFact", field: q.field, value: q.field === "building_area_m2" ? n : Math.trunc(n) });
                  }
                }}
              />
            </div>
          );
        }
        const scopeField = isScopeField(q.field) ? q.field : null;
        const notSure = c.questions.some((question) => question.id === `q-scope-${q.field}` && !question.answer);
        const recorded = [...c.facts].reverse().find((fact) => fact.field === `professional.${q.field}` && fact.kind !== "proposed");
        const chosen = recorded?.value;
        const value = notSure ? "not-sure" : chosen === true ? "yes" : chosen === false ? "no" : "";
        return (
          <div key={q.field} className={`field full ${value ? "" : "is-empty"}`}>
            <label htmlFor={id}>{q.label}</label>
            {scopeField && <p className="field-note">{SCOPE_HELP[scopeField]}</p>}
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
      })}
    </div>
  );
}

/**
 * Section D. Today's engine returns the evidence plan from POST /cases/{id}/section-d.
 * GET /cases/{id}/section-d/issues is requested first and shown when that route exists.
 */
export function Recommendations() {
  const { c, engineId, dispatch, factsEpoch } = useCase();
  const provisions = answeredYes(c).map((a) => a.provision).filter((id) => /^\d/.test(id)).join("|");
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load>(IDLE);

  useEffect(() => {
    if (!engineId) {
      setLoad({
        phase: "error",
        note: "Save the draft first. Then this page lists the evidence still missing.",
        plan: null,
        issues: null,
        professional: null,
        fields: [],
        issuesNote: null,
      });
      return;
    }
    const ctl = new AbortController();
    setLoad({ phase: "loading", note: "Loading Section D…", plan: null, issues: null, professional: null, fields: [], issuesNote: null });
    const ids = provisions ? provisions.split("|") : undefined;
    void (async () => {
      let issues: SectionDIssue[] | null = null;
      let issuesNote: string | null = null;
      try {
        issues = await engine.sectionDIssues(engineId, ctl.signal);
      } catch (e) {
        if (ctl.signal.aborted) return;
        if (e instanceof EngineError && failureKind(e.status, e.detail) === "unreachable") {
          setLoad({ phase: "unreachable", note: e.detail, plan: null, issues: null, professional: null, fields: [], issuesNote: null });
          return;
        }
        if (e instanceof EngineError && failureKind(e.status, e.detail) === "missing-route") {
          issuesNote = "Section D issues aren't available on this engine yet.";
        } else if (e instanceof EngineError && failureKind(e.status, e.detail) === "codedb") {
          issuesNote = "code database not found";
        } else {
          issuesNote = failureText(e);
        }
      }
      try {
        const [plan, professional, fields] = await Promise.all([
          engine.sectionD(engineId, ids, ctl.signal),
          engine.professional(engineId, ctl.signal),
          engine.processFields(engineId, ctl.signal),
        ]);
        if (ctl.signal.aborted) return;
        const practice = practiceFromReview(
          c.practiceOfEngineering,
          professional.required,
          Boolean(issues?.some((issue) => issue.practice_of_engineering.value === true)),
        );
        if (c.practiceOfEngineering !== practice) dispatch({ type: "notePractice", value: practice });
        setLoad({
          phase: "live",
          note: "Recommendations only. You write the evidence and the answers. This does not decide that the design complies or is safe.",
          plan,
          issues,
          professional,
          fields,
          issuesNote,
        });
      } catch (e) {
        if (ctl.signal.aborted) return;
        const message = failureText(e);
        const unreachable = e instanceof EngineError && failureKind(e.status, e.detail) === "unreachable";
        setLoad({
          phase: unreachable ? "unreachable" : "error",
          note: message,
          plan: null,
          issues,
          professional: null,
          fields: [],
          issuesNote,
        });
      }
    })();
    return () => ctl.abort();
  }, [engineId, provisions, attempt, factsEpoch, c.practiceOfEngineering, dispatch]);

  const flag = load.professional?.required;

  return (
    <section className="stack" aria-labelledby="reco-title">
      <h2 id="reco-title" className="section-title">
        Section D and professional screening
      </h2>
      <RoleNote />
      <p className="meta">{load.note}</p>
      {load.phase === "unreachable" && (
        <DemoFallback reason={load.note || "The engine could not be reached."} onRetry={() => setAttempt((n) => n + 1)} />
      )}
      {load.phase === "error" && engineId && (
        <p className="field-note" role="status">
          <span className="status-dot warning" /> {load.note}{" "}
          <button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>
            Try again
          </button>
        </p>
      )}
      {load.phase === "loading" && <p className="empty">Loading…</p>}
      {flag && (
        <p>
          <span className={`status-dot ${flagDot(flag)}`} /> {practiceFlagLine(flag)}
        </p>
      )}
      {c.practiceOfEngineering === true && !professionalConfirmed(c.facts) && (
        <p className="field-note" role="status">
          This is routed to the officer. Name an engineer or architect and their seal or registration number. You can keep preparing the application. Official export stays blocked until that person is confirmed. This screen does not write their judgment.
        </p>
      )}
      {load.professional?.reasons.map((r) => (
        <p key={r.code} className="meta">
          {r.message} {r.citation ? <span className="mono">{r.citation}</span> : null}
        </p>
      ))}
      {load.professional?.questions.map((q) => (
        <p key={q} className="field-note">
          <span className="status-dot warning" />
          {q}
        </p>
      ))}
      <ProfessionalAnswers />
      {load.issues === null && load.issuesNote && <p className="empty">{load.issuesNote}</p>}
      {load.issues && (
        <div className="stack">
          <h3 className="sub-title">Section D issues</h3>
          {load.issues.length === 0 && <p className="empty">No Section D issues returned.</p>}
          {load.issues.map((issue) => {
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
                  <span className="article-id">{issue.provision?.provision_id ?? issue.entered_reference ?? "No provision yet"}</span>
                  <span className="label-pill">
                    <span className={`status-dot ${status === "needs_professional" ? "blocking" : "warning"}`} />
                    {status === "needs_professional" ? "needs_professional" : status === "evidence_listed" ? "evidence listed" : "open"}
                  </span>
                </div>
                <p>{issue.at_stake}</p>
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
                <EvidenceAnswer itemId={issue.id} title="Name the document you are supplying for this issue. The words are yours." />
              </article>
            );
          })}
        </div>
      )}
      {load.plan && (
        <div className="stack">
          <h3 className="sub-title">Evidence plan</h3>
          {load.plan.items.length === 0 && (
            <p className="empty">No evidence items yet. Confirm a provision on Section C, then each item appears here for you to answer.</p>
          )}
          {load.plan.items.map((item) => (
            <article key={item.id} className="card">
              <div className="card-head">
                <span className="article-id">{item.provision_id}</span>
                <span className="label-pill">
                  <span className={`status-dot ${evidenceRecorded(item.status) ? "done" : "warning"}`} />
                  {item.status}
                </span>
              </div>
              <p>{item.performance_issue}</p>
              <p className="meta">
                Evidence types to consider: {item.recommended_types.join(", ") || "none listed"}. Not results, and not filled in for you.
              </p>
              {item.citation && <p className="mono meta">{item.citation}</p>}
              <EvidenceAnswer itemId={item.id} title="Name the document you are supplying. The words are yours." />
            </article>
          ))}
          {load.plan.notices.map((n) => (
            <p key={n} className="meta">
              {n}
            </p>
          ))}
        </div>
      )}
      {load.fields.length > 0 && (
        <div>
          <h3 className="sub-title">Process answers stored for this case</h3>
          <ul className="plain-list">
            {load.fields.map((f) => (
              <li key={f.id}>
                <span className={`status-dot ${f.answer ? "done" : "blocking"}`} /> {f.label}: {f.answer ? f.answer.value : "not written yet"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
