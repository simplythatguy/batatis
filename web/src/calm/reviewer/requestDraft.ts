/** Draft transitions keep edits made while a PUT is in flight and adopt its canonical item IDs. */
import type { DispositionEdit, InformationRequestEdit, InformationRequestItem, RequestLimits, RequestTarget, ReviewSession } from "../../api/types.gen";

export interface DraftRequestItem extends InformationRequestItem { key: string; saved: boolean }
export interface RequestDraft { intro: string; items: DraftRequestItem[]; findings: DispositionEdit[] }
export type SaveState = { kind: "saved" } | { kind: "dirty" } | { kind: "saving"; snapshot: RequestDraft; revision: number } | { kind: "error"; message: string; conflict: boolean };
export interface DraftState { content: RequestDraft; revision: number; save: SaveState; savedAt: string | null }
export type DraftEvent =
  | { type: "intro"; value: string }
  | { type: "item"; key: string; patch: Partial<Pick<DraftRequestItem, "text" | "target" | "included">> }
  | { type: "add"; item: DraftRequestItem }
  | { type: "remove"; key: string }
  | { type: "finding"; edit: DispositionEdit }
  | { type: "start" }
  | { type: "saved"; session: ReviewSession; at: string }
  | { type: "failed"; message: string; conflict: boolean }
  | { type: "retry" }
  | { type: "reset"; session: ReviewSession };

export function draftFromSession(session: ReviewSession): RequestDraft {
  return { intro: session.information_request.intro, items: session.information_request.items.map(item => ({ ...item, key: item.id, saved: true })), findings: [] };
}
export function initialDraft(session: ReviewSession): DraftState {
  return { content: draftFromSession(session), revision: 0, save: { kind: "saved" }, savedAt: null };
}
export function editBody(draft: RequestDraft): InformationRequestEdit {
  return { intro: draft.intro, findings: draft.findings, items: draft.items.map(item => ({
    ...(item.saved ? { id: item.id } : {}), text: item.text, included: item.included, target: item.target,
  })) };
}

function adopt(current: RequestDraft, submitted: RequestDraft, session: ReviewSession): RequestDraft {
  const returned = session.information_request.items;
  const oldIds = new Set(submitted.items.filter(i => i.saved).map(i => i.id));
  const newItems = returned.filter(i => !oldIds.has(i.id));
  const ids = new Map<string, InformationRequestItem>();
  let next = 0;
  for (const item of submitted.items) {
    const saved = item.saved ? returned.find(i => i.id === item.id) : newItems[next++];
    if (saved) ids.set(item.key, saved);
  }
  const items = current.items.map(item => {
    const sent = submitted.items.find(i => i.key === item.key);
    const saved = ids.get(item.key);
    if (!sent || !saved) return item;
    return { ...saved, key: item.key, saved: true,
      text: item.text === sent.text ? saved.text : item.text,
      target: JSON.stringify(item.target) === JSON.stringify(sent.target) ? saved.target : item.target,
      included: item.included === sent.included ? saved.included : item.included,
    };
  });
  // The server may add linked rulebook items; retain them rather than losing them on the next PUT.
  for (const saved of returned) {
    if (![...ids.values()].some(i => i.id === saved.id) && !items.some(i => i.id === saved.id)) items.push({ ...saved, key: saved.id, saved: true });
  }
  return { intro: current.intro === submitted.intro ? session.information_request.intro : current.intro, items,
    findings: current.findings.filter(edit => JSON.stringify(edit) !== JSON.stringify(submitted.findings.find(e => e.key === edit.key))) };
}

export function draftReducer(state: DraftState, event: DraftEvent): DraftState {
  if (event.type === "reset") return initialDraft(event.session);
  if (event.type === "start") return { ...state, save: { kind: "saving", snapshot: state.content, revision: state.revision } };
  if (event.type === "failed") return { ...state, save: { kind: "error", message: event.message, conflict: event.conflict } };
  if (event.type === "retry") return { ...state, save: { kind: "dirty" } };
  if (event.type === "saved") {
    if (state.save.kind !== "saving") return state;
    return { ...state, content: adopt(state.content, state.save.snapshot, event.session), savedAt: event.at,
      save: { kind: state.revision === state.save.revision ? "saved" : "dirty" } };
  }
  let content = state.content;
  switch (event.type) {
    case "intro": content = { ...content, intro: event.value }; break;
    case "item": content = { ...content, items: content.items.map(i => i.key === event.key ? { ...i, ...event.patch } : i) }; break;
    case "add": content = { ...content, items: [...content.items, event.item] }; break;
    case "remove": content = { ...content, items: content.items.filter(i => i.key !== event.key || i.finding_key) }; break;
    case "finding": content = { ...content, findings: [...content.findings.filter(e => e.key !== event.edit.key), event.edit],
      items: content.items.map(i => i.finding_key === event.edit.key ? { ...i, included: event.edit.state === "ask" } : i) }; break;
  }
  return { ...state, content, revision: state.revision + 1, save: state.save.kind === "saving" ? state.save : state.save.kind === "error" && state.save.conflict ? state.save : { kind: "dirty" } };
}

export function draftProblem(draft: RequestDraft, session: ReviewSession, limits: RequestLimits): string {
  if (draft.intro.length > limits.intro) return `The opening line is limited to ${limits.intro} characters.`;
  if (draft.items.length > limits.items) return `At most ${limits.items} request items.`;
  for (const item of draft.items) {
    if (!item.text.trim()) return "Write the empty request item or remove it.";
    if (item.text.length > limits.item_text) return `Each item is limited to ${limits.item_text} characters.`;
    if (!item.finding_key && !item.target) return "Choose where the applicant answers your item.";
  }
  for (const edit of draft.findings) {
    if (edit.state !== "dismissed") continue;
    if (!edit.reason) return "Choose why you dismissed the finding.";
    if (session.findings.find(f => f.key === edit.key)?.severity === "blocking" && !edit.note?.trim()) return "Add a note for the required finding you dismissed.";
  }
  return "";
}
let sequence = 0;
export function officerItem(text: string, target: RequestTarget): DraftRequestItem {
  const key = `officer-${++sequence}`;
  return { key, id: key, saved: false, text, target, included: true, finding_key: null, field: target.field, section: target.section, authored_by: "officer", officer_check: false };
}
