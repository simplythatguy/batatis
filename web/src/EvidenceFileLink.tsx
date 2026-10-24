import { useState } from "react";
import { engine, EngineError, failureText } from "./api/client";
import { useCaseFileRequest } from "./useCaseFileRequest";

/** Both roles use the same authorized download, including visible failure and retry. */
export function EvidenceFileLink({ caseId, fileId, name, className, onUnavailable }: { caseId: string; fileId: string; name: string; className?: string; onUnavailable?: () => void }) {
  const { scope, start } = useCaseFileRequest(caseId, fileId);
  const [state, setState] = useState({ scope, busy: false, note: "" });
  const { busy, note } = state.scope === scope ? state : { busy: false, note: "" };
  async function download() {
    if (busy) return;
    const request = start();
    setState({ scope, busy: true, note: "" });
    try {
      const blob = await engine.downloadFile(caseId, fileId, request.signal);
      if (!request.current()) return;
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: name });
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setState({ scope, busy: false, note: "" });
    } catch (error) {
      if (!request.current()) return;
      setState({ scope, busy: false, note: failureText(error) });
      if (error instanceof EngineError && [401, 403, 404].includes(error.status)) onUnavailable?.();
    }
  }
  return <span>
    <a className={className} href={engine.fileUrl(caseId, fileId)} aria-label={`Download ${name}`} aria-disabled={busy}
      onClick={(e) => { e.preventDefault(); void download(); }}>{busy ? "Downloading…" : "Download PDF"}</a>
    {note && <span className="field-note" role="status">{note} Try the download again.</span>}
  </span>;
}
