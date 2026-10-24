/** A cited provision as a quiet chip; its verbatim code text stays hidden until the officer asks. */
import { useState } from "react";
import { engine } from "../../api/client";
import { NrcCredit } from "../../components";
import { parseCitation } from "./packageView";

export function CodeRef({ citation }: { citation: string }) {
  const parsed = parseCitation(citation);
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<{ phase: "idle" | "loading" | "ready" | "error"; text: string }>({ phase: "idle", text: "" });

  function toggle() {
    const next = !open;
    setOpen(next);
    if (!next || !parsed || state.phase === "ready" || state.phase === "loading") return;
    setState({ phase: "loading", text: "" });
    engine.provision(parsed.id, parsed.division).then(
      (r) => setState({ phase: "ready", text: r.text.replace(/\s+/g, " ").trim() }),
      () => setState({ phase: "error", text: "" }),
    );
  }

  const short = parsed ? `Div ${parsed.division} ${parsed.id}` : citation;
  return (
    <span className="pr-code">
      <button type="button" className="pr-code-chip" aria-expanded={open} onClick={toggle}>
        <span className="pr-mono">{short}</span>
        <span className="pr-code-act">{open ? "Hide the code" : "Show the code"}</span>
      </button>
      {open && (
        <span className="pr-code-box" role="region" aria-label={`Code text, ${short}`}>
          <span className="pr-code-label">Code text · verbatim</span>
          {state.phase === "loading" && <span className="pr-faint">Loading…</span>}
          {state.phase === "error" && <span className="pr-faint">The code text didn’t load. {citation}</span>}
          {state.phase === "ready" && <q className="pr-code-q">{state.text}</q>}
          {!parsed && <span className="pr-faint">{citation}</span>}
          {parsed && <span className="pr-code-cite">{citation}</span>}
          {state.phase === "ready" && <NrcCredit />}
        </span>
      )}
    </span>
  );
}
