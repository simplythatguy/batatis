import { useEffect, useState } from "react";
import { EngineError, engine, type CompletenessReport, type InformationRequest } from "../api/client";
import { MissingItems, RecordHeading } from "../completenessView";
import { PanelHeader, RoleNote } from "../components";
import { EXAMPLES } from "../examples";
import {
  notSureQuestions,
  officerProfessionalLines,
  officerRequest,
  rankingQuestions,
  roleNote,
  SCO_JUDGEMENT,
  unseenRequestItems,
  type InformationItem,
} from "../humanReview";
import { practiceFromReview } from "../professional";
import { failureKind } from "../rules";
import { useCase } from "../store";

type ReportState =
  | { phase: "loading" }
  | { phase: "missing"; note: string }
  | { phase: "unavailable"; note: string }
  | { phase: "ready"; note: string; skipped: { label: string; reason: string }[] };

function reportFrom(body: CompletenessReport): ReportState {
  const reasons = (body.reviews ?? []).flatMap((review) =>
    Array.isArray(review.export_reasons) ? review.export_reasons.filter((item): item is string => typeof item === "string") : [],
  );
  const skipped = (body.reviews ?? []).flatMap((review) =>
    (review.sections ?? []).flatMap((section) =>
      (section.elements ?? [])
        .filter((element) => element.lookup_skipped === true && typeof element.label === "string")
        .map((element) => ({
          label: element.label as string,
          reason: typeof element.reason === "string" ? element.reason : "",
        })),
    ),
  );
  const notice = typeof body.notice === "string" ? body.notice : "Administrative completeness only.";
  const reasonLine = reasons.length ? `Export reasons: ${reasons.join(" ")}` : "";
  return { phase: "ready", note: [notice, reasonLine].filter(Boolean).join(" "), skipped };
}

export function Officer() {
  const { c, gaps, gapsSource, gapsNote, reviewDetail, saveDraft, engineGaps, completenessRecord, dispatch } = useCase();
  const blank = !c.exampleId && !c.description.trim() && c.facts.length === 0 && !c.authority;
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState(blank);
  const [report, setReport] = useState<ReportState>({ phase: "loading" });
  const [copyNote, setCopyNote] = useState("");
  const [requestItems, setRequestItems] = useState<InformationItem[]>([]);
  const [professionalChecked, setProfessionalChecked] = useState<"pending" | "ready">("pending");
  const [technical, setTechnical] = useState<string[]>([]);

  useEffect(() => {
    if (blank) return;
    const ctl = new AbortController();
    let cancelled = false;
    setSettled(false);
    setCopyNote("");
    setRequestItems([]);
    setProfessionalChecked("pending");
    setTechnical([]);
    setReport({ phase: "loading" });
    void (async () => {
      const id = await saveDraft();
      if (cancelled) return;
      if (!id) {
        setReport({ phase: "unavailable", note: "Online review unavailable." });
        setSettled(true);
        return;
      }
      try {
        const professional = await engine.professional(id, ctl.signal);
        if (!cancelled) {
          const practice = practiceFromReview(
            c.practiceOfEngineering,
            professional.required,
            false,
          );
          if (c.practiceOfEngineering !== practice) dispatch({ type: "notePractice", value: practice });
          setProfessionalChecked("ready");
        }
      } catch (e) {
        if (!cancelled && !ctl.signal.aborted && e instanceof EngineError && failureKind(e.status, e.detail) !== "missing-route") {
          setTechnical((current) => [...current, e.technical]);
        }
      }
      try {
        const body = await engine.completeness(id, ctl.signal);
        if (cancelled) return;
        setReport(reportFrom(body));
      } catch (e) {
        if (cancelled || ctl.signal.aborted) return;
        if (e instanceof EngineError && failureKind(e.status, e.detail) === "missing-route") {
          setReport({ phase: "missing", note: "" });
        } else if (e instanceof EngineError) {
          setTechnical((current) => [...current, e.technical]);
          setReport({ phase: "unavailable", note: e.detail });
        } else {
          setReport({ phase: "unavailable", note: "The grouped completeness report did not load." });
        }
      }
      if (!cancelled && id) {
        try {
          const info: InformationRequest = await engine.informationRequest(id, ctl.signal);
          if (!cancelled) setRequestItems(info.items ?? []);
        } catch (e) {
          if (!cancelled && !ctl.signal.aborted) {
            setRequestItems([]);
            if (e instanceof EngineError && failureKind(e.status, e.detail) !== "missing-route") {
              setTechnical((current) => [...current, e.technical]);
            }
          }
        }
      }
      if (!cancelled) setSettled(true);
    })();
    return () => {
      cancelled = true;
      ctl.abort();
    };
    // Retry is explicit. saveDraft changes identity every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blank, attempt]);

  const openNotSure = notSureQuestions(c.questions);
  const ranked = rankingQuestions(c.questions);
  const flags = officerProfessionalLines(professionalChecked, c.practiceOfEngineering, c.facts);
  const exampleLabel = c.exampleId ? (EXAMPLES.find((ex) => ex.id === c.exampleId)?.label ?? "Loaded example") : undefined;
  const reportNote = report.phase === "ready" ? report.note : null;
  const pending = !blank && !settled;
  const pendingLine = c.exampleId ? "Reviewing this example…" : "Reviewing your application…";
  const statusLine = pending ? pendingLine : gapsSource === "engine" ? gapsNote : "Online review unavailable.";
  const techLines = [...technical, ...(gapsSource === "browser" && reviewDetail ? [reviewDetail] : [])].filter(Boolean);
  const engineItems = unseenRequestItems(openNotSure, requestItems);
  const request = officerRequest({
    title: c.title,
    exampleLabel,
    files: c.files.map((file) => ({ name: file.name, pages: file.pages, read: file.read, error: file.error })),
    gaps,
    notSure: openNotSure,
    ranking: ranked,
    professional: flags,
    record: completenessRecord,
    role: roleNote(c.applicantType),
    reportNote,
    engineItems,
    sectionById: new Map(engineGaps.map((gap) => [gap.id, gap.section])),
  });
  const sectionById = new Map(engineGaps.map((gap) => [gap.id, gap.section]));

  async function copy() {
    if (pending) return;
    try {
      await navigator.clipboard.writeText(request);
      setCopyNote("Information request copied.");
    } catch {
      setCopyNote("Copy was unavailable. Select the request text below and copy it.");
    }
  }

  if (blank) {
    return (
      <>
        <PanelHeader title="Officer review" meta="Administrative completeness" />
        <div className="pane scroll-body">
          <div className="content-col stack">
            <RoleNote />
            <p>Your application is blank. This screen does not open the sample package.</p>
            <Judgement skipped={[]} />
            <a className="btn" href="#/describe">
              Return to application
            </a>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <PanelHeader title="Officer review" meta="Administrative completeness" />
      <div className="pane scroll-body">
        <div className="content-col stack">
          <RoleNote />
          <p className="meta intro">This review is of the application in front of you. It checks whether information is present. It does not decide whether the design complies or is safe.</p>
          <p className="meta" role="status">
            {statusLine}
          </p>
          {pending && (
            <div aria-busy="true">
              <p>
                <span className="status-dot pending" /> Missing items will appear here when the review finishes.
              </p>
              <progress aria-label={pendingLine} />
            </div>
          )}
          {!pending && gapsSource === "browser" && (
            <button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>
              Retry review
            </button>
          )}
          {!pending && techLines.length > 0 && (
            <details>
              <summary>Technical detail</summary>
              {techLines.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </details>
          )}
          {!pending && (
            <>
              <section aria-labelledby="docs-title">
                <h2 id="docs-title" className="section-title">
                  Documents
                </h2>
                {c.files.length === 0 ? (
                  <p className="empty">No documents uploaded on this application.</p>
                ) : (
                  <ul className="plain-list">
                    {c.files.map((file) => (
                      <li key={file.id}>
                        {file.name}
                        {file.pages ? ` · ${file.pages} pages` : ""}
                        <div className="meta">{file.error ? file.error : file.read ? "Stored" : "Not read yet"}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <section aria-labelledby="not-sure-title">
                <h2 id="not-sure-title" className="section-title">
                  Questions the applicant marked Not sure
                </h2>
                {openNotSure.length === 0 && engineItems.length === 0 ? (
                  <p className="empty">No questions marked Not sure.</p>
                ) : (
                  <ul className="plain-list">
                    {openNotSure.map((q) => (
                      <li key={q.id}>
                        {q.text}
                        <div className="meta">{q.why}</div>
                      </li>
                    ))}
                    {engineItems.map((item) => (
                      <li key={item.id}>
                        {item.text}
                        <div className="meta">{item.provision_id}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              {ranked.length > 0 && (
                <section aria-labelledby="ranked-questions">
                  <h2 id="ranked-questions" className="section-title">
                    Questions from code matching
                  </h2>
                  <ul className="plain-list">
                    {ranked.map((q) => (
                      <li key={q.id}>{q.text}</li>
                    ))}
                  </ul>
                </section>
              )}
              <section aria-labelledby="professional-flags">
                <h2 id="professional-flags" className="section-title">
                  Professional
                </h2>
                <ul className="plain-list">
                  {flags.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </section>
              <RecordHeading record={completenessRecord} />
              <MissingItems gaps={gaps} sectionById={sectionById} />
              {report.phase === "ready" && (
                <section aria-labelledby="report-title">
                  <h2 id="report-title" className="section-title">
                    Grouped completeness report
                  </h2>
                  <p>{report.note}</p>
                </section>
              )}
              <Judgement skipped={report.phase === "ready" ? report.skipped : []} />
            </>
          )}
          <section aria-labelledby="request-title">
            <h2 id="request-title" className="section-title">
              Information request
            </h2>
            {!pending && (
              <div className="field request-field">
                <label htmlFor="request-text">Request</label>
                <textarea id="request-text" className="mono" readOnly rows={12} value={request} />
              </div>
            )}
            <div className="btn-row">
              <button type="button" className="btn btn-primary" disabled={pending} onClick={() => void copy()}>
                Copy request
              </button>
              <a className="btn btn-ghost" href="#/describe">
                Return to application
              </a>
            </div>
            {copyNote && (
              <p className="field-note" role="status">
                {copyNote}
              </p>
            )}
          </section>
        </div>
      </div>
    </>
  );
}

function Judgement({ skipped }: { skipped: { label: string; reason: string }[] }) {
  return (
    <section aria-labelledby="sco-judgement">
      <h2 id="sco-judgement" className="section-title">
        <span className="label-pill">SCO judgement</span>
      </h2>
      <p>Administrative completeness does not decide these.</p>
      <ul className="plain-list">
        {SCO_JUDGEMENT.map((item) => (
          <li key={item.id}>{item.label}</li>
        ))}
      </ul>
      {skipped.length > 0 && (
        <>
          <h3 className="sub-title">Skipped by the completeness report</h3>
          <ul className="plain-list">
            {skipped.map((item) => (
              <li key={item.label}>
                {item.label}
                {item.reason && <div className="meta">{item.reason}</div>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
