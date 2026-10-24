/**
 * `#/comments`: everything the Safety Codes Officer wrote about the open application, on its own
 * page. The current decision leads (a return with each requested item and its live state, or a
 * refusal with its reasons and appeal notice); any information request sent while the officer still
 * has the file follows; the messages and history sit below. Messages are one way: the applicant
 * answers a return by fixing and resending, never by replying here.
 *
 * Only what this page shows, in a visible tab, is acknowledged (by message id). Late answers for
 * another application or account are dropped and their requests aborted.
 */
import { useEffect, useState } from "react";
import type { ApplicationSummary } from "../../api/accounts";
import { packageReview } from "../../api/packageReview";
import type { SentInformationRequest } from "../../api/types.gen";
import { useCase } from "../../store";
import { useAccount } from "../account";
import { Icon24 } from "../icons";
import { lastStageHash } from "../routes";
import { ApplicationConversation } from "../shell/ApplicationConversation";
import { CIcon, Dot } from "../ui";
import { useOpenProblem } from "./opening";
import "./comments.css";

/** A closed file's state, in a few words; acceptance keeps its boundary (not a design approval). */
const SETTLED_LINE: Partial<Record<ApplicationSummary["status"], { label: string; note?: string; tone: "done" | "blocking" | "pending" }>> = {
  refused: { label: "Refused · read-only", tone: "blocking" },
  accepted: { label: "Accepted · administratively complete", note: "not a design approval", tone: "done" },
  withdrawn: { label: "Withdrawn · read-only", tone: "pending" },
};

export function Comments({ caseParam }: { caseParam: string | null }) {
  const { engineId } = useCase();
  const account = useAccount();
  const problem = useOpenProblem();
  const accountId = account.user?.id ?? null;
  // A link for another application waits for the shell's guarded switch; it never shows this one's thread.
  const waiting = Boolean(caseParam && caseParam !== engineId);
  const app: ApplicationSummary | null = (!waiting && engineId && account.applications?.find((a) => a.id === engineId)) || null;
  const key = app ? `${accountId}:${app.id}` : null;
  const [requests, setRequests] = useState<{ key: string; list: SentInformationRequest[] } | null>(null);

  // A sent information request reaches the applicant while the officer still has the file.
  useEffect(() => {
    if (!app || !key || app.status !== "in_review") return;
    const ctl = new AbortController();
    packageReview.sent(app.id, ctl.signal).then((r) => { if (!ctl.signal.aborted) setRequests({ key, list: r.requests }); }, () => undefined);
    return () => ctl.abort();
  }, [key, app?.status, app?.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const back = lastStageHash();
  const head = (
    <div className="cf-comments-head">
      <a className="cf-comments-back" href={back} aria-label="Back to the application"><CIcon name="back" size={15} /><span>Back</span></a>
      <h1 className="cf-comments-title"><Icon24 name="msg" size={18} />Comments</h1>
    </div>
  );

  if (waiting) {
    return (
      <div className="cf-comments">
        {head}
        {problem && problem.id === caseParam
          ? <p className="cf-comments-note" role="alert"><Dot tone="blocking" />{problem.text}</p>
          : <p className="cf-comments-note" role="status">Opening…</p>}
      </div>
    );
  }
  if (!app) {
    return (
      <div className="cf-comments">
        {head}
        <p className="cf-comments-empty">No comments yet</p>
      </div>
    );
  }

  const status = SETTLED_LINE[app.status] ?? null;
  return (
    <div className="cf-comments" data-application-id={app.id}>
      {head}
      {status && <p className="cf-comments-state"><Dot tone={status.tone} /><span>{status.label}</span>{status.note && <span className="cf-faint"> · {status.note}</span>}</p>}
      <ApplicationConversation app={app} sent={requests && requests.key === key && app.status === "in_review" ? requests.list : []} />
    </div>
  );
}
