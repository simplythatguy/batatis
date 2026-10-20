import { useEffect, useState } from "react";
import { EngineError, engine, type EngineGap } from "../api/client";
import { PanelHeader } from "../components";
import { browserPlantedGaps, PLANTED_AFTER, PLANTED_BEFORE, SECTION_LABEL, SECTION_ORDER } from "../planted";
import { useCase } from "../store";

type Side = "before" | "after";

interface Review {
  side: Side;
  source: "engine" | "browser";
  note: string;
  gaps: EngineGap[];
}

const SAMPLE = "EXAMPLE — Officer review · Hempcrete garden suite";

function requestText(gaps: EngineGap[], side: Side, source: Review["source"]): string {
  const version = side === "before" ? "Original example" : "Updated example";
  const lines = [
    SAMPLE,
    version,
    source === "engine" ? "Online administrative review" : "EXAMPLE — Limited browser check; online review unavailable.",
    "This asks for missing administrative items. It does not decide whether the design complies or is safe.",
    "",
  ];
  for (const section of SECTION_ORDER) {
    const group = gaps.filter((g) => g.section === section);
    if (!group.length) continue;
    lines.push(SECTION_LABEL[section]);
    for (const g of group) lines.push(`- ${g.message}`);
    lines.push("");
  }
  if (gaps.length === 0) {
    lines.push(
      source === "engine"
        ? "No missing administrative items found in this review."
        : "No missing fields found by this browser check. The online review has not completed.",
    );
  }
  return lines.join("\n");
}

export function Officer() {
  const { c } = useCase();
  const blank = !c.exampleId && !c.description.trim() && c.facts.length === 0 && !c.authority;
  const [side, setSide] = useState<Side>("before");
  const [attempt, setAttempt] = useState(0);
  const [review, setReview] = useState<Review | null>(null);
  const [copyNote, setCopyNote] = useState("");

  useEffect(() => {
    if (blank) return;
    const facts = side === "before" ? PLANTED_BEFORE : PLANTED_AFTER;
    const ctl = new AbortController();
    setReview(null);
    setCopyNote("");
    (async () => {
      const key = `batatis-planted-${side}`;
      try {
        let id = sessionStorage.getItem(key);
        if (!id) {
          const created = await engine.createCase({ title: `Planted package · ${side}` });
          id = created.id;
          for (const fact of facts) await engine.addFact(id, fact);
          sessionStorage.setItem(key, id);
        }
        const gaps = await engine.gaps(id, ctl.signal);
        if (ctl.signal.aborted) return;
        setReview({
          side,
          source: "engine",
          note: "Online administrative review",
          gaps,
        });
      } catch (e) {
        if (ctl.signal.aborted) return;
        const message = e instanceof EngineError ? e.detail : e instanceof Error ? e.message : String(e);
        setReview({
          side,
          source: "browser",
          note: message,
          gaps: browserPlantedGaps(facts),
        });
      }
    })();
    return () => ctl.abort();
  }, [side, attempt, blank]);

  const openQuestions = c.questions.filter((q) => q.id.startsWith("q-scope-") && !q.answer);

  if (blank) {
    return (
      <>
        <PanelHeader title="Officer review" meta="Administrative completeness" />
        <div className="pane scroll-body">
          <div className="content-col stack">
            {openQuestions.length > 0 && (
              <section aria-labelledby="open-questions">
                <h2 id="open-questions" className="section-title">
                  Open questions
                </h2>
                <ul className="plain-list">
                  {openQuestions.map((q) => (
                    <li key={q.id}>
                      {q.text}
                      <div className="meta">{q.why}</div>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <p>Your application is blank. This screen does not open the sample package.</p>
            <a className="btn" href="#/describe">
              Return to application
            </a>
          </div>
        </div>
      </>
    );
  }

  const current = review && review.side === side ? review : null;
  const pending = !current;
  const letter = current ? requestText(current.gaps, side, current.source) : "";
  const version = side === "before" ? "Original example" : "Updated example";

  async function copy() {
    if (!current) return;
    try {
      await navigator.clipboard.writeText(letter);
      setCopyNote("Example information request copied.");
    } catch {
      setCopyNote("Copy was unavailable. Select the request text below and copy it.");
    }
  }

  function choose(next: Side) {
    setCopyNote("");
    setSide(next);
  }

  const n = current?.gaps.length ?? 0;
  const allClear = current != null && n === 0;

  return (
    <>
      <PanelHeader title="Officer review" meta="Administrative completeness" />
      <div className="pane scroll-body">
        <div className="content-col stack">
          <p className="meta intro">Compare two versions of an example package. Both may still have missing administrative items.</p>
          {openQuestions.length > 0 && (
            <section aria-labelledby="open-questions">
              <h2 id="open-questions" className="section-title">
                Open questions from this application
              </h2>
              <ul className="plain-list">
                {openQuestions.map((q) => (
                  <li key={q.id}>
                    {q.text}
                    <div className="meta">{q.why}</div>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <div className="toolbar" role="group" aria-label="Package version">
            <button type="button" className="pill" data-active={side === "before"} aria-pressed={side === "before"} onClick={() => choose("before")}>
              Original example
            </button>
            <button type="button" className="pill" data-active={side === "after"} aria-pressed={side === "after"} onClick={() => choose("after")}>
              Updated example
            </button>
          </div>
          <p className="meta" role="status">
            {pending ? "Reviewing the example package…" : current.source === "engine" ? "Online administrative review" : "Online review unavailable"}
          </p>
          {pending && (
            <div aria-busy="true">
              <p>
                <span className="status-dot pending" /> Missing items will appear here when the review finishes.
              </p>
              <progress aria-label="Reviewing the example package" />
            </div>
          )}
          {current?.source === "browser" && (
            <>
              <h2 className="section-title">Online review unavailable</h2>
              <p>
                <span className="status-dot warning" /> Showing a limited check of the example’s fields in this browser. The online review may find more missing items.
              </p>
              <button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>
                Retry review
              </button>
              <details>
                <summary>Technical detail</summary>
                <p>{current.note}</p>
              </details>
            </>
          )}
          {current && (
            <div>
              {current.source === "engine" && (
                <p>
                  {allClear
                    ? "No missing administrative items found in this review."
                    : `Review finished. ${n} administrative item${n === 1 ? "" : "s"} need attention.`}
                </p>
              )}
              {current.source === "browser" && allClear && (
                <p>No missing fields found by this browser check. The online review has not completed.</p>
              )}
              {allClear && current.source === "engine" && (
                <p>This review checks whether information is present. It does not decide whether the design complies or is safe.</p>
              )}
              {SECTION_ORDER.map((section) => {
                const group = current.gaps.filter((g) => g.section === section);
                return (
                  <section key={section} aria-labelledby={`sec-${section}`}>
                    <h2 id={`sec-${section}`} className="sub-title">
                      {SECTION_LABEL[section]}
                    </h2>
                    {group.length === 0 ? (
                      <p className="empty">
                        {current.source === "engine"
                          ? "No missing administrative items found in this section."
                          : "No missing fields found by this limited browser check. Online review is still needed."}
                      </p>
                    ) : (
                      <ul className="plain-list">
                        {group.map((g) => (
                          <li key={g.id}>
                            <span className={`status-dot ${g.severity}`} /> {g.message}
                            {g.fix_hint && <div className="meta">Reviewer note: {g.fix_hint}</div>}
                            {g.citation && <div className="mono meta">{g.citation}</div>}
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                );
              })}
              {allClear && (
                <a className="btn" href="#/describe">
                  Return to application
                </a>
              )}
            </div>
          )}
          <section aria-labelledby="request-title">
            <h2 id="request-title" className="section-title">
              Information request
            </h2>
            {current && (
              <div className="field request-field">
                <label htmlFor="request-text">{version}</label>
                <textarea id="request-text" className="mono" readOnly rows={10} value={letter} />
              </div>
            )}
            <div className="btn-row">
              <button type="button" className="btn btn-primary" disabled={pending} onClick={() => void copy()}>
                Copy example request
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
