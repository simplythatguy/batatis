import { useCallback, useEffect, useRef, useState } from "react";
import { useCase } from "../../store";
import { useCurrentApplication } from "../begin";
import { CIcon } from "../ui";
import { workspaceApi, workspaceFailure, type PackagePreview as Preview, type PreviewPage } from "./api";

type View = { phase: "loading" } | { phase: "failed"; note: string } | { phase: "ready"; id: string; preview: Preview; basis: string };

/** One image per visible page. Leaving the viewport releases its base64 pixels. */
function Page({ id, index, total, official, root, seed, width, height }: {
  id: string; index: number; total: number; official: boolean; root: HTMLDivElement | null; seed?: PreviewPage; width: number; height: number;
}) {
  const ref = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(index < 2);
  const [page, setPage] = useState<PreviewPage | null>(null);
  const [note, setNote] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") { setVisible(true); return; }
    const observer = new IntersectionObserver(entries => setVisible(entries.some(e => e.isIntersecting)), { root, rootMargin: "400px 0px" });
    observer.observe(el);
    return () => observer.disconnect();
  }, [root]);
  useEffect(() => {
    if (!visible) { setPage(null); return; }
    if (seed) { setPage(seed); return; }
    const ctl = new AbortController();
    setNote("");
    void workspaceApi.preview(id, index, 1, official, ctl.signal).then(response => {
      if (!ctl.signal.aborted) {
        const page = response.start === index ? response.pages[0] : undefined;
        if (page) setPage(page);
        else setNote("This page didn’t load.");
      }
    }).catch(e => { if (!ctl.signal.aborted) setNote(workspaceFailure(e, "Package preview")); });
    return () => ctl.abort();
  }, [id, index, official, visible, seed, attempt]);
  return <figure className="aw-preview-page" ref={ref} style={{ aspectRatio: `${page?.width ?? width} / ${page?.height ?? height}` }} aria-label={`Package page ${index + 1} of ${total}`}>
    {page && visible ? <img src={page.image} width={page.width} height={page.height} alt={`Page ${index + 1} of ${total}`} decoding="async" />
      : <div className="aw-page-placeholder">{note ? <><p role="status">{note}</p><button type="button" className="cf-btn is-sm" onClick={() => { setVisible(true); setAttempt(n => n + 1); }}>Try again</button></> : <span className="cf-faint cf-small">Page {index + 1}{visible ? " · Loading…" : ""}</span>}</div>}
  </figure>;
}

export function PackagePreview({ official, versionKey, zoom }: { official: boolean; versionKey: string; zoom: number }) {
  const { engineId, saveDraft, readSync, applicationStatus } = useCase();
  const { locked, app } = useCurrentApplication();
  const accepted = (app?.status ?? applicationStatus) === "accepted";
  const [view, setView] = useState<View>({ phase: "loading" });
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [root, setRoot] = useState<HTMLDivElement | null>(null);
  const pending = useRef<AbortController | null>(null);
  const key = useRef(versionKey); key.current = versionKey;
  const load = useCallback(async () => {
    pending.current?.abort();
    const ctl = new AbortController(); pending.current = ctl;
    const basis = key.current; setView({ phase: "loading" });
    try {
      const id = locked ? engineId : await saveDraft();
      if (ctl.signal.aborted) return;
      if (!id || !locked && !readSync().saved) { setView({ phase: "failed", note: "Save your application to see the package." }); return; }
      const preview = await workspaceApi.preview(id, 0, 3, official, ctl.signal);
      if (!ctl.signal.aborted) setView({ phase: "ready", id, preview, basis });
    } catch (e) { if (!ctl.signal.aborted) setView({ phase: "failed", note: workspaceFailure(e, "Package preview") }); }
  }, [engineId, locked, official]);
  useEffect(() => { void load(); return () => pending.current?.abort(); }, [load]);
  useEffect(() => {
    if (view.phase !== "ready" || !view.preview.pdf) { setPdfUrl(null); return; }
    let url: string | null = null;
    try {
      const bytes = atob(view.preview.pdf.slice(view.preview.pdf.indexOf(",") + 1));
      url = URL.createObjectURL(new Blob([Uint8Array.from(bytes, c => c.charCodeAt(0))], { type: "application/pdf" }));
      setPdfUrl(url);
    } catch { setPdfUrl(null); }
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [view]);
  const first = view.phase === "ready" ? view.preview.pages[0] : undefined;
  const stale = view.phase === "ready" && view.basis !== versionKey;
  return <section className="aw-package-preview" aria-label="Officer view">
    <div className="aw-preview-bar">
      <span>{official ? accepted ? "Accepted application" : "What the officer receives" : "Draft package"}{view.phase === "ready" ? <span className="aw-meta"> · {view.preview.page_count} pages</span> : null}</span>
      {stale && <button type="button" className="cf-btn is-xs" onClick={() => void load()}><CIcon name="retry" size={12} />Update</button>}
      {pdfUrl && <a className="cf-icon-btn is-plain" href={pdfUrl} target="_blank" rel="noreferrer" title="Open the PDF in a new tab" aria-label="Open the PDF in a new tab"><CIcon name="external" size={14} /></a>}
    </div>
    {view.phase === "ready" ? <div className="aw-package-pages" ref={setRoot} role="region" tabIndex={0} aria-label={official ? "Pages the officer receives" : "Draft PDF pages"}>
      <div className="aw-preview-scale" style={{ width: `${zoom}%`, maxWidth: `${650 * zoom / 100}px` }}>{Array.from({ length: view.preview.page_count }, (_, index) => <Page key={`${view.id}:${view.basis}:${official}:${index}`} id={view.id} index={index} total={view.preview.page_count} official={official} root={root}
        seed={index < view.preview.pages.length ? view.preview.pages[index] : undefined} width={first?.width ?? 612} height={first?.height ?? 792} />)}</div>
    </div> : <div className="aw-preview-empty" role="status">{view.phase === "loading" ? "Preparing the package…" : <><p>{view.note}</p><button type="button" className="cf-btn is-sm" onClick={() => void load()}>Try again</button></>}</div>}
  </section>;
}
