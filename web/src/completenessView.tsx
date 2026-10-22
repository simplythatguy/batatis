import { GROUP_LABEL, groupGaps, type CompletenessRecord } from "./humanReview";
import type { Gap } from "./types";

const ORDER = ["A", "B", "C", "D", "process", "facts"];

/** The same missing-item record the completeness dialog and the officer both show. */
export function MissingItems({
  gaps,
  sectionById,
  onFollow,
}: {
  gaps: Gap[];
  sectionById?: ReadonlyMap<string, string>;
  onFollow?: (gap: Gap) => void;
}) {
  const groups = groupGaps(gaps, sectionById);
  if (!gaps.length) return <p className="empty">No missing items in this record.</p>;
  return (
    <div className="stack">
      <h3 className="sub-title">Current missing items</h3>
      {ORDER.map((key) => {
        const items = groups.get(key);
        if (!items?.length) return null;
        return (
          <section key={key}>
            <h4 className="sub-title">{GROUP_LABEL[key]}</h4>
            <ul className="plain-list">
              {items.map((gap) => (
                <li key={gap.id}>
                  {onFollow ? (
                    <a
                      href={gap.href}
                      onClick={(e) => {
                        e.preventDefault();
                        onFollow(gap);
                      }}
                    >
                      {gap.label}
                    </a>
                  ) : (
                    <a href={gap.href}>{gap.label}</a>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

export function RecordHeading({ record }: { record: CompletenessRecord | null }) {
  if (!record) return <p className="meta">No export has been requested yet.</p>;
  return (
    <section aria-labelledby="completeness-record">
      <h3 id="completeness-record" className="sub-title">
        {record.label}
      </h3>
      <p>{record.note}</p>
      {record.reasons.length > 0 && (
        <ul className="plain-list">
          {record.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
