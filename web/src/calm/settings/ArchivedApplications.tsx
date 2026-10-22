/**
 * Settings → Archived: the owner's archived applications, each with Restore. Archiving only files an
 * application away in this account (it never changes the case or its status), so every row keeps its
 * real workflow line. The pattern of T3 Code's Archived panel and Irsal's archive-in-Settings.
 */
import { useState } from "react";
import type { ApplicationSummary } from "../../api/accounts";
import { setApplicationPreferences, useAccount } from "../account";
import { statusLine } from "../applications";
import { Icon24 } from "../icons";
import "./archived.css";

function ArchivedRow({ a }: { a: ApplicationSummary }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const name = a.title || "Untitled application";
  async function restore() {
    setBusy(true);
    setError("");
    const failed = await setApplicationPreferences(a.id, { archived: false });
    // On success the row leaves with the server's answer; on failure it stays and says why.
    if (failed) { setError(failed); setBusy(false); }
  }
  return (
    <li className="cf-arch-row">
      <span className="cf-arch-text">
        <span className="cf-arch-title">{name}</span>
        <span className="cf-arch-line">{statusLine(a).text}</span>
      </span>
      <button type="button" className="cf-btn is-xs cf-arch-restore" disabled={busy} aria-label={`Restore ${name}`} onClick={() => void restore()}>
        <Icon24 name="restore" size={14} />Restore
      </button>
      {error && <span className="cf-arch-error" role="alert">Couldn’t restore it. {error}</span>}
    </li>
  );
}

export function ArchivedApplications() {
  const { applications, loadingList, listError } = useAccount();
  const archived = (applications ?? []).filter((a) => a.archived).sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  return (
    <section className="ac-section" aria-labelledby="ac-s-archived">
      <h2 id="ac-s-archived" className="ac-section-title">Archived</h2>
      {archived.length > 0 ? (
        <ul className="cf-arch-rows">{archived.map((a) => <ArchivedRow key={a.id} a={a} />)}</ul>
      ) : (
        <p className="cf-arch-empty" role="status">
          <Icon24 name="archive" size={15} />
          {applications === null && loadingList ? "Loading…" : listError ? `Couldn’t load your applications. ${listError}` : "Nothing archived"}
        </p>
      )}
    </section>
  );
}
