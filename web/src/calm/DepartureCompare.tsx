import type { DepartureComparison } from "./departure";

/** Three short lines: the code's words, the applicant's words, and the drafted difference. */
export function DepartureCompare({ lines, onEdit }: { lines: DepartureComparison; onEdit: () => void }) {
  const clipped = (t: string) => (t.length > 220 ? `${t.slice(0, 219).trimEnd()}…` : t);
  return (
    <>
      <dl className="cf-compare">
        {lines.code && <div><dt>Code</dt><dd><blockquote>{clipped(lines.code)}</blockquote></dd></div>}
        <div><dt>Your design</dt><dd><q>{clipped(lines.design)}</q></dd></div>
        {lines.gap && <div><dt>Difference</dt><dd className="cf-compare-gap"><span className="cf-sr">Drafted by Batatis, not code text: </span>{clipped(lines.gap)}</dd></div>}
      </dl>
      <button type="button" className="cf-link-btn" onClick={onEdit}>Edit</button>
    </>
  );
}
