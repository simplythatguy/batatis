/**
 * While the officer still has the application (in review), an information request they sent shows
 * here: who asked, when, and the numbered items. Drafts never reach the applicant (the server
 * returns sent requests only). The applicant answers in Messages; the officer returns the
 * application when they need edits to it.
 */
import { useEffect, useState } from "react";
import type { ApplicationSummary } from "../../api/accounts";
import { packageReview } from "../../api/packageReview";
import type { SentInformationRequest } from "../../api/types.gen";
import { initials } from "../account";
import { authorityName } from "../applications";

const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

export function RequestBanner({ app }: { app: ApplicationSummary }) {
  const [latest, setLatest] = useState<SentInformationRequest | null>(null);

  useEffect(() => {
    let live = true;
    setLatest(null);
    packageReview.sent(app.id).then(
      (r) => { if (live) setLatest(r.requests[r.requests.length - 1] ?? null); },
      () => undefined,
    );
    return () => { live = false; };
  }, [app.id]);

  if (!latest) return null;
  const who = latest.sent_by_name || app.reviewer?.name || "The officer";
  const where = authorityName(app.authority);
  return (
    <section className="cf-returned" aria-labelledby="cf-request-who">
      <span className="cf-returned-av" aria-hidden="true">{initials(who) || "?"}</span>
      <div className="cf-returned-body">
        <h2 className="cf-returned-who" id="cf-request-who">
          {who} <span>· {where ? `Safety Codes Officer, ${where} · ` : ""}asked for more information {when(latest.sent_at)}</span>
        </h2>
        <p className="cf-returned-msg">{latest.intro}</p>
        <ol className="cf-request-items">
          {latest.items.map((t, i) => <li key={i}>{t}</li>)}
        </ol>
        <p className="cf-faint cf-small">Reply with the information in Messages. If the officer needs changes to the application itself, they’ll send it back to you to edit.</p>
      </div>
    </section>
  );
}
