import { useEffect, useState } from "react";
import { engine, failureText, type StoredFile } from "./api/client";
import { EvidenceFileLink } from "./EvidenceFileLink";
import { useCaseFileRequest } from "./useCaseFileRequest";

/** Read-only storage inventory, independent of current bindings and application status. */
export function RetainedSourceFiles({ caseId }: { caseId: string | null }) {
  const { scope, start, cancel } = useCaseFileRequest(caseId ?? "");
  const [open, setOpen] = useState(false);
  const [load, setLoad] = useState<{ scope: typeof scope; files: StoredFile[] | null; note: string } | null>(null);
  useEffect(() => {
    if (!caseId || !open) return;
    const request = start();
    setLoad({ scope, files: null, note: "" });
    engine.files(caseId, request.signal).then(files => {
      if (request.current()) setLoad({ scope, files, note: "" });
    }).catch(error => {
      if (request.current()) setLoad({ scope, files: [], note: failureText(error) });
    });
    return cancel;
  }, [caseId, open, scope, start, cancel]);
  if (!caseId) return null;
  const shown = load?.scope === scope ? load : null;
  return <details className="cf-sheet-sources" open={open} onToggle={e => {
    cancel();
    setLoad(null);
    setOpen(e.currentTarget.open);
  }}>
    <summary>Saved source PDFs{shown?.files && !shown.note ? ` (${shown.files.length})` : ""}</summary>
    {open && <>
      <p className="cf-sheet-note">Includes earlier and unlinked source PDFs. Removing or replacing a binding keeps its source file.</p>
      {!shown?.files ? <p className="cf-sheet-note" role="status">Loading source PDFs…</p>
        : shown.note ? <p className="cf-sheet-note" role="status">Source PDFs are unavailable. {shown.note} Close and reopen this list to try again.</p>
        : shown.files.length ? <ul className="plain-list">{shown.files.map(file => <li key={file.id}>
          <span>{file.name}</span>{" · "}<EvidenceFileLink caseId={caseId} fileId={file.id} name={file.name}
            onUnavailable={() => setLoad({ scope, files: [], note: "Access changed or this application is no longer available." })} />
        </li>)}</ul> : <p className="cf-sheet-note">No source PDFs are stored in this application.</p>}
    </>}
  </details>;
}
