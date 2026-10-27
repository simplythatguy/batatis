/** Open retained case bytes through the same authorized download as EvidenceFileLink. */
import { useEffect, useRef, useState } from "react";
import { engine, failureText } from "../../api/client";
import { useCaseFileRequest } from "../../useCaseFileRequest";
import { Icon24 } from "../icons";

export function OpenFileLink({ caseId, fileId, page, name, label }: { caseId: string; fileId: string; page?: number | null; name: string; /** Chip text; defaults to "Open page N". */ label?: string }) {
  const { scope, start } = useCaseFileRequest(caseId, fileId);
  const [state, setState] = useState({ scope, busy: false, error: "" });
  const url = useRef("");
  useEffect(() => () => { if (url.current) URL.revokeObjectURL(url.current); }, [scope]);
  const current = state.scope === scope ? state : { busy: false, error: "" };
  async function open() {
    if (current.busy) return;
    const popup = window.open("about:blank", "_blank");
    if (popup) popup.opener = null;
    const request = start();
    setState({ scope, busy: true, error: "" });
    try {
      const blob = await engine.downloadFile(caseId, fileId, request.signal);
      if (!request.current()) { popup?.close(); return; }
      if (url.current) URL.revokeObjectURL(url.current);
      url.current = URL.createObjectURL(blob);
      const href = `${url.current}${page ? `#page=${page}` : ""}`;
      if (popup) popup.location.replace(href);
      else throw new Error("Allow a new tab, then try Open again.");
      setState({ scope, busy: false, error: "" });
    } catch (error) {
      popup?.close();
      if (request.current()) setState({ scope, busy: false, error: failureText(error) });
    }
  }
  return <span className="rw-file-link">
    <a className="cf-cite" href={`${engine.fileUrl(caseId, fileId)}${page ? `#page=${page}` : ""}`} target="_blank" rel="noopener noreferrer"
      aria-label={`Open ${name}${page ? `, page ${page}` : ""}`} aria-disabled={current.busy}
      onClick={event => { event.preventDefault(); void open(); }}>
      <Icon24 name="file" size={14} />{current.busy ? "Opening…" : label || (page ? `Open page ${page}` : "Open")}
    </a>
    {current.error && <span className="rw-hint" role="alert">{current.error}</span>}
  </span>;
}
