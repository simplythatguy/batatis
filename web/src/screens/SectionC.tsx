import { useRef, useState } from "react";
import { engine, EngineError, type CodeHit } from "../api/client";
import { CodeQuote } from "../components";
import { useCase } from "../store";
import type { Candidate } from "../types";
import { useCurrentApplication } from "../calm/begin";

const SUGGESTED = "Confirm before using";

/** The code-check card a looked-up provision becomes (search here, the code library elsewhere). */
export function provisionCandidate(h: { id: string; article_title?: string | null; title?: string | null; text: string; citation?: string | null }): Candidate {
  return {
    id: `search-${h.id}`,
    topic: h.article_title || h.title || h.id,
    provision: h.id,
    part: Number(h.id.split(".")[0]) || 0,
    benchmark: false,
    identified: true,
    suggestion: "search",
    quote: { text: h.text, citation: h.citation ?? "No citation returned", source: "code" },
    departure: "do something other than what this sentence requires",
    clarifyingQuestion: "Which part of this sentence does the design not follow?",
    answer: null,
  };
}

/** Manual code search. `onAdded` receives the new card id after "Use this provision". */
export function ProvisionSearch({ onAdded }: { onAdded?: (candidateId: string) => void } = {}) {
  const { c, dispatch, noteLookupFailure } = useCase();
  const { locked, readOnly } = useCurrentApplication();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<CodeHit[]>([]);
  const [note, setNote] = useState("");
  const [technical, setTechnical] = useState("");
  const searchSeq = useRef(0);

  async function runSearch(text: string) {
    setTechnical("");
    const q = text.trim();
    if (q.length < 3) {
      setNote("Enter code keywords or an article number.");
      setHits([]);
      return;
    }
    const seq = ++searchSeq.current;
    setNote("Searching the code…");
    try {
      const rows = await engine.search(q, { division: "B", limit: 8 });
      if (seq !== searchSeq.current) return;
      setHits(rows);
      setNote(rows.length ? `${rows.length} provisions. Pick the one that fits what you are proposing.` : "No provisions matched those words.");
    } catch (e) {
      if (seq !== searchSeq.current) return;
      setHits([]);
      setNote("Search unavailable. Try again when you’re ready.");
      setTechnical(e instanceof EngineError ? e.technical : String(e));
      noteLookupFailure(e instanceof Error ? e.message : String(e));
    }
  }

  if (readOnly) return <p className="meta">Your saved application is read-only. Read the code in the code library.</p>;

  return (
    <form
      className="field"
      onSubmit={(e) => {
        e.preventDefault();
        void runSearch(query);
      }}
    >
      <label htmlFor="section-c-search">Search the code for a provision</label>
      <input
        id="section-c-search"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
        }}
      />
      <button type="submit" className="btn">
        Search
      </button>
      {note && (
        <p className="field-note" role="status">
          {note}
        </p>
      )}
      {technical && <details><summary>Technical detail</summary><p>{technical}</p></details>}
      {hits.length > 0 && (
        <ul className="plain-list">
          {hits.map((h) => (
            <li key={h.id} className="card">
              <div className="card-head">
                <span className="article-id">{h.id}</span>
                {h.article_title && <span className="card-topic">{h.article_title}</span>}
                <span className="label-pill">Code text</span>
              </div>
              {h.text.trim() ? <CodeQuote text={h.text} /> : <p className="meta">Article heading. Its sentences are shown once the provision is in the table.</p>}
              <p className="mono meta">{h.citation ?? "No citation returned"}</p>
              <p className="meta">{SUGGESTED}</p>
              <button
                type="button"
                className="btn"
                disabled={locked}
                onClick={() => {
                  if (locked || c.candidates.some((x) => x.provision === h.id)) return;
                  dispatch({ type: "addCandidate", candidate: provisionCandidate(h) });
                  setNote(`${h.id} is in the table. Confirm it before you submit.`);
                  onAdded?.(`search-${h.id}`);
                }}
              >
                Use this provision
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
