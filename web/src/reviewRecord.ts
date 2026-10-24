/** A saved administrative record, separate from the applicant's source-form PDF. */
import type { Case, Decision } from "./api/types.gen";

const decisionLabel = (outcome: Decision["outcome"]) => ({
  accept: "Accepted as administratively complete", return: "Returned for information", refuse: "Administrative refusal",
})[outcome];

function decisionLines(decision: Decision): string[] {
  return [decisionLabel(decision.outcome), `Officer: ${decision.by_name} (${decision.by_id})`,
    `Decision date: ${decision.at}`, decision.message,
    ...decision.items.map(item => `Requested item (${item.field || item.gap_id}): ${item.note}`)];
}

export function savedReviewRecord(saved: Case, downloadedAt = new Date()): string {
  const history = [...saved.decision_history];
  if (saved.decision && !history.some(d => d.at === saved.decision!.at && d.by_id === saved.decision!.by_id
    && d.outcome === saved.decision!.outcome && d.message === saved.decision!.message)) history.push(saved.decision);
  return [
    "Administrative review record — saved application",
    `Application: ${saved.title || saved.id}`, `Application ID: ${saved.id}`,
    `Saved content/workflow version: ${saved.version}`, `Status: ${saved.status}`,
    `Reviewing authority: ${saved.authority || 'Not recorded'}`, `Downloaded: ${downloadedAt.toISOString()}`,
    `Stored until: ${saved.expires_at || 'Not recorded'}`,
    "Administrative completeness only. This record does not assess design compliance or safety.",
    "This text is not the Safety Codes Council form. Keep original supporting attachments separately.",
    "", "Current decision", ...(saved.decision ? decisionLines(saved.decision) : ["No decision recorded."]),
    "", "Decision history", ...(history.length ? history.flatMap(d => [...decisionLines(d), ""]) : ["No decisions recorded."]),
    "", "Submission history", ...saved.submissions.flatMap(s => [
      `Submission ${s.number} · ${s.at} · applicant ${s.by_id} · authority ${s.authority}`,
      ...(s.changes.length ? s.changes.map(change => `${change.field}: ${change.before ?? '(not recorded)'} → ${change.after ?? '(not recorded)'}`)
        : [s.comparison_available ? "No saved value changes." : "No comparison available for this submission."]),
    ]),
    "", "Status history", ...saved.status_history.map(s => `${s.at} · ${s.by_name} (${s.by_id}) · ${s.from_status} → ${s.to_status}${s.note ? `\n${s.note}` : ''}`),
    "", "Messages and history", ...(saved.messages.length ? saved.messages.flatMap(m => [
      `${m.created_at} · ${m.author.name} (${m.author.id}, ${m.author.role || 'role not recorded'}) · ${m.kind}`,
      m.body, ...m.items.map(item => `Requested item (${item.field || item.gap_id}): ${item.note}`), "",
    ]) : ["No messages recorded."]),
  ].join("\n");
}
