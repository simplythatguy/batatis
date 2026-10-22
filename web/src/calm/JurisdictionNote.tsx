/**
 * The calm confirmation under "Who will review your application?" (docs/api/jurisdictions.md):
 * the pack's authority and how to reach it, the office's own process notes with their sources, any
 * older package that is not offered, and, when the applicant is not sure yet, what Batatis covers
 * elsewhere. Everything comes from the packs; nothing here names an office by itself.
 */
import { useEffect } from "react";
import type { JurisdictionDetail, PackSource } from "../api/types.gen";
import { loadDirectory, loadJurisdiction, retryExtras, type CaseExtras } from "./caseExtras";

/** Loading or failed: say so, with Try again on failure. */
function Pending({ failed, what }: { failed: boolean; what: string }) {
  return (
    <div className="cf-juris" role="status">
      {failed ? (
        <p className="cf-note"><Dot tone="warning" />{what} didn’t load. <button type="button" className="cf-link-btn" onClick={retryExtras}>Try again</button></p>
      ) : (
        <p className="cf-faint">Loading {what.toLowerCase()}…</p>
      )}
    </div>
  );
}
import { CIcon, Dot } from "./ui";

function Sources({ sources }: { sources: PackSource[] }) {
  if (!sources.length) return null;
  return (
    <span className="cf-juris-src">
      {sources.map((s, i) => (
        <span key={`${s.url}-${i}`}>
          {i > 0 && " · "}
          <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>{s.pages ? `, ${s.pages}` : ""}
          {s.status === "unverified" && " (not verified)"}
        </span>
      ))}
    </span>
  );
}

function PackDetail({ pack, extras }: { pack: JurisdictionDetail; extras: CaseExtras }) {
  const local = pack.process_notes.filter((n) => n.scope === "local");
  const historical = extras.checklists?.jurisdiction === pack.id ? extras.checklists.historical : [];
  const current = pack.standing_packages.filter((p) => p.status === "current");
  return (
    <div className="cf-juris" role="note">
      <p className="cf-juris-h"><Dot tone="done" />{pack.authority.name} reviews it.</p>
      {pack.authority.contact && <p>{pack.authority.contact}</p>}
      {current.length > 0 && (
        <p className="cf-faint">
          This office publishes {current.length === 1 ? "one pre-reviewed path" : `${current.length} pre-reviewed paths`} (standing {current.length === 1 ? "package" : "packages"} {current.map((p) => p.code).join(", ")}). Batatis offers one if your project fits.
        </p>
      )}
      {local.length > 0 && (
        <details>
          <summary>How this office handles a variance ({local.length})</summary>
          <ul className="cf-juris-notes">
            {local.map((n) => (
              <li key={n.id}>
                <span>{n.text}</span>
                <Sources sources={n.sources} />
              </li>
            ))}
          </ul>
        </details>
      )}
      {historical.length > 0 && (
        <details>
          <summary>Older packages, not offered ({historical.length})</summary>
          <ul className="cf-juris-notes">
            {historical.map((h) => (
              <li key={h.id}>
                <span>{h.code} {h.title}. {h.historical_reason}</span>
                <Sources sources={[h.source]} />
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="cf-faint cf-small">{pack.disclaimer}</p>
    </div>
  );
}

/** Not sure yet: who reviews elsewhere in the province, and what Batatis covers where. */
function Elsewhere({ extras }: { extras: CaseExtras }) {
  useEffect(() => { void loadDirectory(); }, []);
  const dir = extras.directory;
  const fallback = dir?.jurisdictions.find((j) => j.fallback);
  useEffect(() => { if (fallback) void loadJurisdiction(fallback.id); }, [fallback?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!dir || !fallback) return <Pending failed={Boolean(extras.failed.directory)} what="Where else applications go" />;
  const finder = extras.details[fallback.id]?.authority.sources[0];
  const preview = dir.coverage.filter((c) => c.coverage === "preview").length;
  return (
    <div className="cf-juris" role="note">
      <p className="cf-juris-h"><Dot tone="pending" />Somewhere else in {dir.coverage.find((c) => c.id === fallback.province)?.name ?? "the province"}?</p>
      <p>{fallback.authority} reviews it. Batatis has no local pack for that office yet, so ask it about its own forms and steps.</p>
      <p className="cf-faint">{dir.levels.full}</p>
      {preview > 0 && <p className="cf-faint">Outside {dir.coverage.find((c) => c.id === fallback.province)?.name ?? "this province"}, Batatis is a preview only: {dir.levels.preview.charAt(0).toLowerCase()}{dir.levels.preview.slice(1)}</p>}
      {finder ? (
        <a className="cf-inline-link cf-small" href={finder.url} target="_blank" rel="noreferrer">{finder.title} <CIcon name="external" size={12} /></a>
      ) : extras.failed.details[fallback.id] ? (
        <p className="cf-note cf-small"><Dot tone="warning" />The office’s contact link didn’t load. <button type="button" className="cf-link-btn" onClick={retryExtras}>Try again</button></p>
      ) : !extras.details[fallback.id] ? (
        <p className="cf-faint cf-small" role="status">Loading the office’s contact link…</p>
      ) : null}
    </div>
  );
}

export function JurisdictionNote({ authority, unsure, extras }: { authority: string; unsure: boolean; extras: CaseExtras }) {
  useEffect(() => { if (authority) void loadJurisdiction(authority); }, [authority]);
  if (authority) {
    const pack = extras.details[authority];
    return pack ? <PackDetail pack={pack} extras={extras} /> : <Pending failed={Boolean(extras.failed.details[authority])} what="The office’s notes" />;
  }
  return unsure ? <Elsewhere extras={extras} /> : null;
}
