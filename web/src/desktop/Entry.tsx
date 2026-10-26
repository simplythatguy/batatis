import { useState } from "react";
import { desktop, isDesktop, useDesktop } from "./host";

/** Fresh desktop installs can enter the shared test workspace without making an account. */
export function DesktopEntry() {
  const info = useDesktop();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!isDesktop() || info?.workspace !== "local") return null;
  return (
    <div className="dk-entry">
      <button type="button" className="cf-btn is-center" disabled={busy || info.service.state !== "ready"} onClick={async () => {
        setBusy(true); setError("");
        const outcome = await desktop.switchWorkspace("dev");
        if (!outcome.ok) { setError(outcome.message); setBusy(false); }
      }}>{busy ? "Opening…" : "Local development"}</button>
      <p className="ac-help">Test people, one shared database. No signup.</p>
      {error && <p className="ac-error" role="alert">{error}</p>}
    </div>
  );
}
