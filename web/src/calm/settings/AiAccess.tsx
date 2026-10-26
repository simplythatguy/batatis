/** Settings → AI access: on a server that needs one, an access code turns on AI for this account. */
import { useEffect, useState } from "react";
import { AccountsError, aiAccess, type AiAccess } from "../../api/accounts";
import { useCountdown } from "../auth/bits";
import { Row } from "./rows";

export function AiAccessSection() {
  const [state, setState] = useState<AiAccess | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [wait, startWait] = useCountdown();

  useEffect(() => {
    let live = true;
    aiAccess.read().then((next) => { if (live) setState(next); }, () => {});
    return () => { live = false; };
  }, []);

  if (!state?.required) return null;

  async function run(work: () => Promise<AiAccess>) {
    setBusy(true);
    setError("");
    try {
      setState(await work());
      setCode("");
    } catch (e) {
      if (e instanceof AccountsError && e.status === 429) startWait(e.retryAfter);
      else setError(e instanceof AccountsError && e.detail ? e.detail : "That didn’t work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ac-section" aria-labelledby="ac-s-ai">
      <h2 id="ac-s-ai" className="ac-section-title">AI access</h2>
      {state.granted ? (
        <Row label="AI" action={<button type="button" className="cf-btn is-xs is-ghost" disabled={busy} onClick={() => void run(aiAccess.remove)}>Remove code</button>}>
          <span className="ac-saved">On</span>
        </Row>
      ) : (
        <form className="ac-row" onSubmit={(e) => { e.preventDefault(); if (code.trim() && !busy && wait === 0) void run(() => aiAccess.enter(code.trim())); }}>
          <label className="ac-row-label" htmlFor="ac-ai-code">Access code</label>
          <span className="ac-row-value">
            <input id="ac-ai-code" className="ac-in" type="password" autoComplete="off" spellCheck={false} value={code} maxLength={200}
              onChange={(e) => { setCode(e.target.value); setError(""); }} />
          </span>
          <span className="ac-row-action">
            <button type="submit" className="cf-btn is-xs is-primary" disabled={!code.trim() || busy || wait > 0}>{wait > 0 ? `Wait ${wait}s` : "Turn on AI"}</button>
          </span>
        </form>
      )}
      {error && <p className="ac-error is-row" role="alert">{error}</p>}
      {!state.granted && <p className="ac-help">AI features are off until you enter an access code. Everything else works without one.</p>}
    </section>
  );
}
