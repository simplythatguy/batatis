/** The server's inactivity deadline, in the reader's local time with a zone. */
export function expiryLabel(iso: string | null | undefined): string | null {
  if (!iso || !Number.isFinite(Date.parse(iso))) return null;
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
  });
}

export function ExpiryNotice({ expiresAt, officer = false }: { expiresAt: string | null | undefined; officer?: boolean }) {
  const label = expiryLabel(expiresAt);
  if (!label) return null;
  return <p className="cf-faint cf-small" role="note">
    If inactive, stored until <time dateTime={expiresAt ?? undefined}>{label}</time>, then deleted with messages and attachments.
    {officer ? " Print or save this view and download attachments to your authority’s records before then." : " Download your application PDF, save the text record for decisions and messages, and keep your original attachments before then."}
    {" "}Saved changes and application messages extend this date.
  </p>;
}
