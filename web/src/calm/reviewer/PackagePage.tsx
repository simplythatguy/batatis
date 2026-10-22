/**
 * #/review/package: review a third-party package (no Batatis case). Drop the SCC variance form
 * (fillable or flattened) and its attachments; the review is scoped to the officer's authority and
 * kept for seven days. #/review/package/<id> shows it, takes re-uploads (with the diff) and drafts the
 * information request, which the officer copies out (there is no applicant account to send to).
 */
import { useCallback, useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { AccountsError } from "../../api/accounts";
import { packageReview, type ReviewTarget } from "../../api/packageReview";
import type { PackageReviewIndex, ReviewSession } from "../../api/types.gen";
import { PageHead } from "../auth/bits";
import { CIcon } from "../ui";
import { InfoRequest } from "./InfoRequest";
import { PackageReview } from "./PackageReview";
import { sentLabel } from "./queue";
import "./review.css";

const RECENT = "batatis.recentPackages";
const MAX_FILES = 12;
const MAX_BYTES = 4 * 1024 * 1024;

/** Package ids this browser opened (ids only), newest first. */
function recent(): { id: string; at: string }[] {
  try {
    const v = JSON.parse(localStorage.getItem(RECENT) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x?.id === "string" && /^pkg_[a-z0-9]+$/.test(x.id)).slice(0, 8) : [];
  } catch {
    return [];
  }
}
function remember(id: string) {
  try {
    localStorage.setItem(RECENT, JSON.stringify([{ id, at: new Date().toISOString() }, ...recent().filter((r) => r.id !== id)].slice(0, 8)));
  } catch {
    /* private mode: nothing to remember */
  }
}

/** Why a set of files can't be sent, or "". Mirrors the server limits. */
export function filesProblem(files: File[]): string {
  if (!files.length) return "";
  if (files.some((f) => !/\.pdf$/i.test(f.name) && f.type !== "application/pdf")) return "Only PDF files can be reviewed.";
  if (files.length > MAX_FILES) return `At most ${MAX_FILES} files at once.`;
  if (files.reduce((n, f) => n + f.size, 0) > MAX_BYTES) return "At most 4 MB in total.";
  return "";
}

function errorText(e: unknown): string {
  if (e instanceof AccountsError) {
    if (e.status === 413) return "Those files are too large: at most 12 PDFs and 4 MB in total.";
    if (e.status === 404) return "This package isn’t available. Packages are kept for seven days, for your authority only.";
    return e.detail;
  }
  return "The review didn’t run. Try again.";
}

function DropZone({ busy, label, onFiles, children }: { busy: boolean; label: string; onFiles: (f: File[]) => void; children?: ReactNode }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    if (busy) return; // one review at a time
    const files = [...e.dataTransfer.files];
    if (files.length) onFiles(files);
  };
  return (
    <div className={`pr-drop${over ? " is-over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
      {children}
      <input ref={input} className="pr-file-input" type="file" accept="application/pdf,.pdf" multiple tabIndex={-1} aria-hidden="true"
        onChange={(e) => { const f = [...(e.target.files ?? [])]; e.target.value = ""; if (f.length) onFiles(f); }} />
      <button type="button" className="cf-btn is-sm is-primary" disabled={busy} onClick={() => input.current?.click()}>
        <CIcon name="upload" size={14} />{busy ? "Reviewing…" : label}
      </button>
      <p className="pr-faint pr-small">PDFs only · up to 12 files, 4 MB in total · or drop them here</p>
    </div>
  );
}

export function PackagePage({ packageId, phoneTools }: { packageId: string | null; phoneTools?: ReactNode }) {
  const [index, setIndex] = useState<PackageReviewIndex | null>(null);
  const [shown, setShown] = useState<ReviewSession | null>(null);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  // A ref, not state: a second drop in the same tick must see the first one as pending.
  const pending = useRef(false);
  const [error, setError] = useState("");
  const [view, setView] = useState<"review" | "request">("review");
  const target: ReviewTarget | null = packageId ? { kind: "package", id: packageId } : null;

  const load = useCallback(async (keep = false) => {
    if (!packageId) return;
    try {
      const ix = await packageReview.index({ kind: "package", id: packageId });
      setIndex(ix);
      if (!keep) setShown(ix.latest);
      setLoadError("");
      setError("");
      remember(packageId);
    } catch (e) {
      // With a review on screen, a failed refresh is a note, not a page that hides it.
      if (keep) setError(`The version list didn’t refresh: ${errorText(e)}`);
      else setLoadError(errorText(e));
    }
  }, [packageId]);

  useEffect(() => { void load(); }, [load]);

  async function upload(files: File[]) {
    if (pending.current) return;
    const problem = filesProblem(files);
    if (problem) return setError(problem);
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      if (!target) {
        const s = await packageReview.start(files);
        remember(s.package_id);
        location.hash = `#/review/package/${encodeURIComponent(s.package_id)}`;
        return;
      }
      setShown(await packageReview.run(target, files));
      setView("review");
      await load(true);
    } catch (e) {
      setError(errorText(e));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  const head = (
    <PageHead
      title={<><a className="ac-crumb" href="#/review">Queue</a><span className="ac-crumb-sep" aria-hidden="true">/</span>{packageId ? "PDF package" : "Review a PDF package"}</>}
      meta={shown ? `· ${shown.files.map((f) => f.name).join(", ")}` : undefined}
      phoneTools={phoneTools}
    />
  );

  if (!packageId) {
    const list = recent();
    return (
      <div className="ac-page">
        {head}
        <div className="ac-page-body is-narrow">
          <h2 className="pr-title">Review a package from outside Batatis</h2>
          <p className="pr-lede">Add the SCC variance form (fillable or a flattened scan with a text layer) and its attachments. The review lists what is present, blank or not found, with where each was read. Nothing is filled in, and the files themselves aren’t kept.</p>
          <DropZone busy={busy} label="Choose PDFs" onFiles={(f) => void upload(f)} />
          {error && <p className="ac-error" role="alert">{error}</p>}
          {list.length > 0 && (
            <section className="pr-group" aria-label="Recent packages">
              <h3 className="pr-group-h">Opened on this device</h3>
              <ul className="pr-list">
                {list.map((r) => (
                  <li key={r.id} className="pr-item"><span className="cf-dot is-pending" aria-hidden="true" /><div className="pr-item-body"><a className="ac-link pr-mono" href={`#/review/package/${r.id}`}>{r.id}</a><p className="pr-item-meta">{sentLabel(r.at)}</p></div></li>
                ))}
              </ul>
            </section>
          )}
          <p className="pr-fine">Packages are kept for seven days and only officers of your authority can open them.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ac-page">
      {head}
      {loadError ? (
        <div className="ac-page-body is-narrow"><p className="ac-empty">{loadError} <a className="ac-link" href="#/review/package">Review another package</a></p></div>
      ) : !shown || !target ? (
        <div className="ac-page-body is-narrow"><p className="ac-empty">Loading the package review…</p></div>
      ) : (
        <div className="ac-page-body pr-page">
          <div className="pr-view" role="group" aria-label="Show">
            <button type="button" className="ac-tab" aria-pressed={view === "review"} onClick={() => setView("review")}>Package review</button>
            <button type="button" className="ac-tab" aria-pressed={view === "request"} onClick={() => setView("request")}>Information request</button>
          </div>
          {error && <p className="ac-error pr-empty" role="alert">{error}</p>}
          {view === "review" ? (
            <PackageReview
              session={shown}
              versions={index?.sessions ?? []}
              onPickVersion={(v) => void packageReview.version(target, v).then(setShown, (e) => setError(errorText(e)))}
              actions={<DropZoneButton busy={busy} onFiles={(f) => void upload(f)} />}
              finish={{ label: "Information request", onClick: () => setView("request") }}
            />
          ) : (
            <InfoRequest
              target={target}
              session={shown}
              latest={!index?.latest || shown.version === index.latest.version}
              canEdit
              applicant="the applicant"
              onChange={(s) => { setShown(s); void load(true); }}
            />
          )}
        </div>
      )}
    </div>
  );
}

/** "Upload a new version": a compact file button for the review header. */
function DropZoneButton({ busy, onFiles }: { busy: boolean; onFiles: (f: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input ref={input} className="pr-file-input" type="file" accept="application/pdf,.pdf" multiple tabIndex={-1} aria-hidden="true"
        onChange={(e) => { const f = [...(e.target.files ?? [])]; e.target.value = ""; if (f.length) onFiles(f); }} />
      <button type="button" className="cf-btn is-xs" disabled={busy} onClick={() => input.current?.click()}><CIcon name="upload" size={13} />{busy ? "Reviewing…" : "Upload a new version"}</button>
    </>
  );
}
