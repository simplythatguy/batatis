import { useEffect, useState } from "react";
import {
  engine,
  failureText,
  type EngineProcessField,
  type ProfessionalResult,
  type SectionDPlan,
} from "../api/client";
import { DemoFallback } from "../components";
import { answeredYes } from "../model";
import { useCase } from "../store";

type Load = {
  phase: "idle" | "loading" | "live" | "stub";
  note: string;
  plan: SectionDPlan | null;
  professional: ProfessionalResult | null;
  fields: EngineProcessField[];
};

const IDLE: Load = { phase: "idle", note: "", plan: null, professional: null, fields: [] };

/**
 * Section D issues and the practice-of-engineering flag.
 * Both come from the engine. Identify is not called; there is no rank route.
 */
export function Recommendations() {
  const { c, engineId } = useCase();
  const provisions = answeredYes(c).map((a) => a.provision).filter((id) => /^\d/.test(id)).join("|");
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load>(IDLE);

  useEffect(() => {
    if (!engineId) {
      setLoad({
        phase: "stub",
        note: "No engine case yet. Save the draft, then this panel calls the Section D and professional routes.",
        plan: null,
        professional: null,
        fields: [],
      });
      return;
    }
    const ctl = new AbortController();
    setLoad({ phase: "loading", note: "Calling the engine…", plan: null, professional: null, fields: [] });
    const ids = provisions ? provisions.split("|") : undefined;
    Promise.all([
      engine.sectionD(engineId, ids, ctl.signal),
      engine.professional(engineId, ctl.signal),
      engine.processFields(engineId, ctl.signal),
    ])
      .then(([plan, professional, fields]) => {
        setLoad({
          phase: "live",
          note: "From POST /cases/{id}/section-d, GET /professional and GET /process-fields. Recommendations only. This tool does not write the evidence or the professional opinion.",
          plan,
          professional,
          fields,
        });
      })
      .catch((e: unknown) => {
        if (ctl.signal.aborted) return;
        const message = failureText(e);
        setLoad({
          phase: "stub",
          note: `Those routes did not return (${message}). Section D issues and the engineering flag stay blank until the code database answers. Identify is command-line only and is not called here.`,
          plan: null,
          professional: null,
          fields: [],
        });
      });
    return () => ctl.abort();
  }, [engineId, provisions, attempt]);

  const flag = load.professional?.required;

  return (
    <section className="stack" aria-labelledby="reco-title">
      <h2 id="reco-title" className="section-title">
        Section D and professional screening
      </h2>
      <p className="meta">{load.note}</p>
      {load.phase === "stub" && engineId && (
        <DemoFallback reason={load.note || "Section D did not return."} onRetry={() => setAttempt((n) => n + 1)} />
      )}
      {load.phase === "loading" && <p className="empty">Loading…</p>}
      {flag && (
        <p>
          <span className={`status-dot ${flag === "yes" ? "blocking" : flag === "depends" ? "warning" : "done"}`} />{" "}
          Practice of engineering: {flag === "yes" ? "a registered professional is indicated" : flag === "no" ? "the screen did not indicate one" : "the screen needs more facts"}.
          {flag !== "no" && " This is not a licence decision."}
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
      {load.plan && load.plan.items.length === 0 && <p className="empty">No Section D issues returned.</p>}
      {load.plan?.items.map((item) => (
        <article key={item.id} className="card">
          <div className="card-head">
            <span className="article-id">{item.provision_id}</span>
            <span className="label-pill">
              <span className={`status-dot ${item.status === "provided" ? "done" : "warning"}`} />
              {item.status}
            </span>
          </div>
          <p>{item.performance_issue}</p>
          <p className="meta">
            Evidence types to consider: {item.recommended_types.join(", ") || "none listed"}. Not results, and not a ladder rung the tool filled in.
          </p>
          {item.citation && <p className="mono meta">{item.citation}</p>}
        </article>
      ))}
      {load.plan?.notices.map((n) => (
        <p key={n} className="meta">
          {n}
        </p>
      ))}
      {load.fields.length > 0 && (
        <div>
          <h3 className="sub-title">Process answers the engine stored</h3>
          <ul className="plain-list">
            {load.fields.map((f) => (
              <li key={f.id}>
                <span className={`status-dot ${f.answer ? "done" : "blocking"}`} /> {f.label}: {f.answer ? f.answer.value : "not on the engine yet"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
