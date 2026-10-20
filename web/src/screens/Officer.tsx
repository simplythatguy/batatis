import { useEffect, useState } from "react";
import { engine, type EngineGap } from "../api/client";
import { PanelHeader } from "../components";
import { browserPlantedGaps, PLANTED_AFTER, PLANTED_BEFORE, SECTION_LABEL, SECTION_ORDER } from "../planted";

type Side = "before" | "after";

interface Review {
  side: Side;
  source: "engine" | "browser";
  note: string;
  gaps: EngineGap[];
}

function requestText(gaps: EngineGap[]): string {
  const lines = [
    "Information request",
    "Planted example. Not a real application.",
    "This asks for missing administrative items. It is not a decision on the variance, and it does not say the design complies or is safe.",
    "",
  ];
  for (const section of SECTION_ORDER) {
    const group = gaps.filter((g) => g.section === section);
    if (!group.length) continue;
    lines.push(SECTION_LABEL[section]);
    for (const g of group) lines.push(`- ${g.message}`);
    lines.push("");
  }
  if (gaps.length === 0) lines.push("No administrative gaps are open on this version of the package.");
  return lines.join("\n");
}

export function Officer() {
  const [side, setSide] = useState<Side>("before");
  const [review, setReview] = useState<Review | null>(null);
  const [copyNote, setCopyNote] = useState("");

  useEffect(() => {
    const facts = side === "before" ? PLANTED_BEFORE : PLANTED_AFTER;
    const ctl = new AbortController();
    setReview(null);
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
          note: "Administrative completeness for this planted example. This does not certify the design.",
          gaps,
        });
      } catch (e) {
        if (ctl.signal.aborted) return;
        const message = e instanceof Error ? e.message : String(e);
        setReview({
          side,
          source: "browser",
          note: `The engine's check did not return (${message}). This list is the browser check for the planted example, not a code review.`,
          gaps: browserPlantedGaps(facts),
        });
      }
    })();
    return () => ctl.abort();
  }, [side]);

  const gaps = review?.gaps ?? [];
  const letter = requestText(gaps);

  async function copy() {
    try {
      await navigator.clipboard.writeText(letter);
      setCopyNote("Copied the information request.");
    } catch {
      setCopyNote("Clipboard was blocked. The request is in the box below. Select it and copy.");
    }
  }

  return (
    <>
      <PanelHeader title="Officer review" meta="Administrative completeness" />
      <div className="pane scroll-body">
        <div className="content-col stack">
          <p className="example-banner" role="status">
            Planted example. Not a real application.
          </p>
          <p className="meta intro">
            One planted package, before and after the missing items are filled. This does not certify the design.
          </p>
          <div className="toolbar" role="group" aria-label="Package version">
            <button type="button" className="pill" data-active={side === "before"} aria-pressed={side === "before"} onClick={() => setSide("before")}>
              Before fixes
            </button>
            <button type="button" className="pill" data-active={side === "after"} aria-pressed={side === "after"} onClick={() => setSide("after")}>
              After fixes
            </button>
          </div>
          <p className="meta" role="status">
            {review ? review.note : "Loading the package…"}
          </p>
          {SECTION_ORDER.map((section) => {
            const group = gaps.filter((g) => g.section === section);
            return (
              <section key={section} aria-labelledby={`sec-${section}`}>
                <h2 id={`sec-${section}`} className="sub-title">
                  {SECTION_LABEL[section]}
                </h2>
                {group.length === 0 ? (
                  <p className="empty">Nothing open in this section.</p>
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
          <section aria-labelledby="request-title">
            <h2 id="request-title" className="section-title">
              Information request
            </h2>
            <label htmlFor="request-text" className="meta">
              Request text
            </label>
            <textarea id="request-text" readOnly rows={10} value={letter} />
            <div className="btn-row">
              <button type="button" className="btn btn-primary" onClick={() => void copy()}>
                Copy request
              </button>
              <a className="btn btn-ghost" href="#/describe">
                Back to the application
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
