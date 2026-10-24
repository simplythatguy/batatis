/**
 * While the officer still has the application (in review), a sent information request shows as
 * the one-line notice; the request itself is on the comments page. Drafts never reach the
 * applicant (the server returns sent requests only).
 */
import { useEffect, useState } from "react";
import type { ApplicationSummary } from "../../api/accounts";
import { packageReview } from "../../api/packageReview";
import { NoticeLine } from "./ReturnedBanner";

export function RequestBanner({ app }: { app: ApplicationSummary }) {
  const [sent, setSent] = useState<{ id: string; any: boolean } | null>(null);

  useEffect(() => {
    let live = true;
    packageReview.sent(app.id).then(
      (r) => { if (live) setSent({ id: app.id, any: r.requests.length > 0 }); },
      () => undefined,
    );
    return () => { live = false; };
  }, [app.id]);

  if (!sent || sent.id !== app.id || !sent.any) return null;
  return <NoticeLine app={app} />;
}
