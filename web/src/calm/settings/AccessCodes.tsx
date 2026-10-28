/** Settings → Access codes, for the site admin only: make a code, see who is using it, cap its seats, switch it off. */
import { useEffect, useState } from "react";
import { AccountsError, adminCodes, type AccessCodeInfo } from "../../api/accounts";
import { Row } from "./rows";

const message = (e: unknown) => (e instanceof AccountsError && e.detail ? e.detail : "That didn’t work. Try again.");
const seats = (text: string): number | null => (text.trim() === "" ? null : Math.max(1, Math.floor(Number(text))));
const validSeats = (text: string) => text.trim() === "" || (Number.isFinite(Number(text)) && Number(text) >= 1);

function CodeRow({ info, onChange, onError }: { info: AccessCodeInfo; onChange: (next: AccessCodeInfo) => void; onError: (text: string) => void }) {
  const [limit, setLimit] = useState(info.max_users === null ? "" : String(info.max_users));
  const [busy, setBusy] = useState(false);
  const dirty = limit.trim() !== (info.max_users === null ? "" : String(info.max_users));
  async function save(patch: { max_users?: number | null; revoked?: boolean }) {
    setBusy(true);
    onError("");
    try {
      const next = await adminCodes.change(info.name, patch);
      onChange(next);
      setLimit(next.max_users === null ? "" : String(next.max_users));
    } catch (e) {
      onError(message(e));
    } finally {
      setBusy(false);
    }
  }
  const tally = info.max_users === null ? `${info.in_use} in use` : `${info.in_use} of ${info.max_users} in use`;
  return (
    <div className="ac-row">
      <span className="ac-row-label">{info.name}</span>
      <span className="ac-row-value">
        <span>{tally}</span>
        {info.revoked && <span className="ac-faint-tag">Off</span>}
        <input className="ac-in ac-in-short" inputMode="numeric" aria-label={`Seat limit for ${info.name}`} placeholder="No limit" value={limit} maxLength={6}
          onChange={(e) => setLimit(e.target.value.replace(/[^\d]/g, ""))}
          onKeyDown={(e) => { if (e.key === "Enter" && dirty && validSeats(limit) && !busy) void save({ max_users: seats(limit) }); }} />
      </span>
      <span className="ac-row-action">
        {dirty && <button type="button" className="cf-btn is-xs is-primary" disabled={busy || !validSeats(limit)} onClick={() => void save({ max_users: seats(limit) })}>Save</button>}
        <button type="button" className="cf-btn is-xs is-ghost" disabled={busy} onClick={() => void save({ revoked: !info.revoked })}>{info.revoked ? "Turn on" : "Turn off"}</button>
      </span>
    </div>
  );
}

export function AccessCodesSection() {
  const [codes, setCodes] = useState<AccessCodeInfo[] | null>(null);
  const [name, setName] = useState("");
  const [limit, setLimit] = useState("");
  const [made, setMade] = useState<{ name: string; code: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    adminCodes.list().then((next) => { if (live) setCodes(next); }, () => {});
    return () => { live = false; };
  }, []);

  // Not the admin (403) or no such route: the section isn't there at all.
  if (codes === null) return null;

  async function make() {
    if (!name.trim() || busy || !validSeats(limit)) return;
    setBusy(true);
    setError("");
    try {
      const created = await adminCodes.create(name.trim(), seats(limit));
      setCodes(await adminCodes.list());
      setMade({ name: created.info.name, code: created.code });
      setCopied(false);
      setName("");
      setLimit("");
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ac-section" aria-labelledby="ac-s-codes">
      <h2 id="ac-s-codes" className="ac-section-title">Access codes</h2>
      {codes.length === 0 && <p className="ac-help">No codes yet.</p>}
      {codes.map((info) => (
        <CodeRow key={info.name} info={info} onError={setError}
          onChange={(next) => setCodes((all) => all && all.map((item) => (item.name === next.name ? next : item)))} />
      ))}
      <form className="ac-row" onSubmit={(e) => { e.preventDefault(); void make(); }}>
        <label className="ac-row-label" htmlFor="ac-code-name">New code</label>
        <span className="ac-row-value">
          <input id="ac-code-name" className="ac-in" placeholder="Name" autoComplete="off" spellCheck={false} maxLength={40} value={name}
            onChange={(e) => { setName(e.target.value); setError(""); }} />
          <input className="ac-in ac-in-short" inputMode="numeric" aria-label="Seat limit" placeholder="No limit" maxLength={6} value={limit}
            onChange={(e) => setLimit(e.target.value.replace(/[^\d]/g, ""))} />
        </span>
        <span className="ac-row-action">
          <button type="submit" className="cf-btn is-xs is-primary" disabled={!name.trim() || busy || !validSeats(limit)}>Make</button>
        </span>
      </form>
      {made && (
        <Row label={made.name} action={
          <button type="button" className="cf-btn is-xs" onClick={() => { void navigator.clipboard?.writeText(made.code).then(() => setCopied(true), () => {}); }}>{copied ? "Copied" : "Copy"}</button>
        }>
          <code className="ac-code" data-testid="new-access-code">{made.code}</code>
          <span className="ac-faint-tag">Shown once</span>
        </Row>
      )}
      {error && <p className="ac-error is-row" role="alert">{error}</p>}
    </section>
  );
}
