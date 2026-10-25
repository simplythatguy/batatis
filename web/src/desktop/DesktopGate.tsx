/**
 * In the desktop app the page waits for the local service; on the web this renders its children unchanged.
 * Once the app has opened, a later stop keeps the screen (and its unsaved text) and offers Restart.
 */
import { useState, type ReactNode } from "react";
import { desktop, isDesktop, useDesktop } from "./host";
import "./desktop.css";

let opened = false;

function Restart() {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  return (
    <>
      <button type="button" className="cf-btn is-sm is-primary" disabled={busy} onClick={async () => {
        setBusy(true);
        const outcome = await desktop.restart();
        if (!outcome.ok) setNote(outcome.message);
        setBusy(false);
      }}>{busy ? "Restarting…" : "Restart"}</button>
      {note && <p className="ac-error" role="alert">{note}</p>}
    </>
  );
}

function Status({ title, detail, restart }: { title: string; detail?: string | null; restart?: boolean }) {
  return (
    <main className="dk-status" aria-live="polite">
      <span className="cf-mark" aria-hidden="true" />
      <p className="dk-status-title">{title}</p>
      {detail && <p className="dk-status-detail">{detail}</p>}
      {restart && <Restart />}
    </main>
  );
}

export function DesktopGate({ children }: { children: ReactNode }) {
  const info = useDesktop();
  if (!isDesktop()) return <>{children}</>;
  const state = info?.service.state ?? "starting";
  if (state === "ready") opened = true;
  if (!opened) {
    return state === "failed"
      ? <Status title="Batatis couldn’t start" detail={info?.service.detail} restart />
      : <Status title={info?.service.detail ?? "Starting…"} />;
  }
  return (
    <>
      {children}
      {state === "failed" && (
        <div className="dk-banner" role="alert">
          <span>{info?.service.detail ?? "The local service stopped."}</span>
          <Restart />
        </div>
      )}
      {(state === "busy" || state === "starting") && (
        <div className="dk-veil" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />{info?.service.detail ?? "One moment…"}</div>
      )}
    </>
  );
}
