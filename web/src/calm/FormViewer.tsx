/**
 * The application as the actual PDF the engine fills (GET /cases/{id}/export/preview, a draft export), shown
 * as its own pages on light paper. The browser's PDF viewer would frame them in a dark backdrop this page
 * cannot restyle. The page images are drawn from the same bytes the open-in-new-tab link opens: what the
 * applicant sees is the file they download. The draft is saved first so the PDF shows the current answers;
 * after an answer changes, Update makes a new one. Read-only applications are shown as saved. Nothing here
 * unlocks the official PDF; that gate stays in the download panel.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { engine, EngineError, ExportBlockedError } from "../api/client";
import type { PreviewPage } from "../api/types.gen";
import { useCase } from "../store";
import { CIcon } from "./ui";

type View =
  | { state: "idle" | "loading" }
  | { state: "ready"; url: string; key: string; pages: PreviewPage[]; total: number }
  | { state: "failed"; message: string; reasons: string[] };

function failure(e: unknown): { message: string; reasons: string[] } {
  if (e instanceof ExportBlockedError) return { message: "The form can’t be filled yet.", reasons: e.reasons };
  if (e instanceof EngineError && e.status === 0) return { message: "The form didn’t load: the server didn’t respond.", reasons: [] };
  if (e instanceof EngineError && e.status === 503) return { message: "The form isn’t available on this server.", reasons: [] };
  return { message: "The form didn’t load.", reasons: [] };
}

/** The PDF bytes of a `data:` URL, for the open-in-new-tab link. */
function pdfFile(dataUrl: string): Blob {
  const bytes = atob(dataUrl.slice(dataUrl.indexOf(",") + 1));
  return new Blob([Uint8Array.from(bytes, (c) => c.charCodeAt(0))], { type: "application/pdf" });
}

/**
 * `status`: a sent or closed application's own status ("Sent", "Accepted"). The file on screen is
 * always the draft export, whatever the application's status, and is labelled as such.
 */
export function FormViewer({ locked, status }: { locked: boolean; status?: string }) {
  const { c, engineId, saveDraft } = useCase();
  // What the PDF is filled from: the answers, the applicant's own case, the authority and Section C.
  const key = useMemo(() => JSON.stringify([c.facts.map((f) => [f.field, f.value, f.status]), c.process, c.authority, c.sectionC.map((r) => r.provision)]), [c.facts, c.process, c.authority, c.sectionC]);
  const keyNow = useRef(key);
  keyNow.current = key;
  const [view, setView] = useState<View>({ state: "idle" });
  const run = useRef<AbortController | null>(null);
  const url = useRef<string | null>(null);

  const load = useCallback(async () => {
    run.current?.abort();
    const ctl = new AbortController();
    run.current = ctl;
    const filledFrom = keyNow.current;
    setView({ state: "loading" });
    try {
      // The PDF is filled from the saved case, so this visit's answers are saved first.
      const id = locked ? engineId : (await saveDraft()) ?? engineId;
      if (ctl.signal.aborted) return;
      if (!id) { setView({ state: "failed", message: "Save your application to see the form.", reasons: [] }); return; }
      const preview = await engine.exportPreview(id, ctl.signal);
      if (ctl.signal.aborted) return;
      if (url.current) URL.revokeObjectURL(url.current);
      url.current = URL.createObjectURL(pdfFile(preview.pdf));
      setView({ state: "ready", url: url.current, key: filledFrom, pages: preview.pages, total: preview.page_count });
    } catch (e) {
      if (!ctl.signal.aborted) setView({ state: "failed", ...failure(e) });
    }
  }, [engineId, locked, saveDraft]);

  // Once per opened application; a later answer marks it out of date instead of refetching.
  useEffect(() => {
    if (engineId) void load();
    return () => run.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engineId]);
  useEffect(() => () => { if (url.current) URL.revokeObjectURL(url.current); }, []);

  const stale = view.state === "ready" && view.key !== key && !locked;
  const title = status ? `Application form (${status.toLowerCase()}), draft PDF` : "Application form, draft PDF";
  return (
    <section className="cf-form-view" aria-label="Application form">
      <div className="cf-form-bar">
        {status && <span className="cf-form-status">{status}</span>}
        <span className="cf-form-tag" title="Filled from your answers. Not the official PDF.">Draft PDF</span>
        {view.state === "loading" && <span className="cf-faint cf-small" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" /> Filling the form…</span>}
        {stale && <button type="button" className="cf-btn is-xs" onClick={() => void load()}><CIcon name="retry" size={13} />Update</button>}
        {view.state === "ready" && <a className="cf-icon-btn is-plain" href={view.url} target="_blank" rel="noreferrer" aria-label="Open the draft PDF in a new tab" title="Open the draft PDF in a new tab"><CIcon name="external" size={15} /></a>}
      </div>
      {view.state === "ready" ? (
        // A focusable scroll region, so the pages scroll from the keyboard too.
        <div className="cf-form-pages" role="region" aria-label={title} tabIndex={0}>
          {view.pages.map((page, i) => (
            <img key={i} className="cf-form-page" src={page.image} width={page.width} height={page.height}
              alt={`Page ${i + 1} of ${view.total}`} loading={i < 2 ? "eager" : "lazy"} decoding="async" />
          ))}
          {view.pages.length < view.total && (
            <a className="cf-inline-link cf-form-more" href={view.url} target="_blank" rel="noreferrer">
              {view.total - view.pages.length} more {view.total - view.pages.length === 1 ? "page" : "pages"} in the PDF
            </a>
          )}
        </div>
      ) : view.state === "failed" ? (
        <div className="cf-form-empty" role="alert">
          <p>{view.message}</p>
          {view.reasons.length > 0 && <ul className="cf-small">{view.reasons.slice(0, 5).map((r) => <li key={r}>{r}</li>)}</ul>}
          {engineId && <button type="button" className="cf-btn is-sm" onClick={() => void load()}>Try again</button>}
        </div>
      ) : (
        <div className="cf-form-empty" aria-hidden={view.state === "loading" ? "true" : undefined}><div className="cf-form-ghost" /></div>
      )}
    </section>
  );
}

/** Before an application exists there is nothing to fill: a blank page where the form will be. */
export function FormPlaceholder() {
  return (
    <section className="cf-form-view" aria-label="Application form">
      <div className="cf-form-empty" aria-hidden="true"><div className="cf-form-ghost" /></div>
    </section>
  );
}
