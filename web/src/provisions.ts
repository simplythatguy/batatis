import type { Case, SectionCRow } from "./types";

/** Normalize punctuation only. IDs still have to come from CodeDB. */
export const canonicalProvision = (id: string) => id.trim().replace(/\s+/g, "").replace(/\.$/, "");
export const isProvision = (id: string) => /^\d+(?:\.\d+){3}\.?/.test(id);
export const withinProvision = (row: string, parent: string) => {
  const r = canonicalProvision(row), p = canonicalProvision(parent);
  return r === p || r.startsWith(`${p}.(`) || r.startsWith(`${p}(`);
};

/** Expand an article once, preserving only decisions about that exact sentence.
 * Overlapping article/child lookup must not duplicate rows or inherit a parent Yes. */
export function reconcileSectionC(c: Case, rows: SectionCRow[]): Case {
  const unique = [...new Map(rows.map(r => [canonicalProvision(r.provision), r])).values()];
  const candidates = c.candidates.filter(a => !unique.some(r => withinProvision(r.provision, a.provision)));
  const sectionC: SectionCRow[] = [];
  for (const row of unique) {
    const exact = c.candidates.find(a => canonicalProvision(a.provision) === canonicalProvision(row.provision));
    const parent = exact ?? c.candidates.find(a => withinProvision(row.provision, a.provision));
    if (!parent) continue; // A stale lookup cannot reintroduce a removed reference.
    const candidate = exact ?? {
      ...parent, id: `provision-${row.provision}`, provision: row.provision,
      answer: null, benchmark: false,
      quote: { text: "", citation: row.citation, source: "code" as const },
    };
    candidates.push(candidate);
    sectionC.push({ ...row, candidateId: candidate.id });
  }
  const next = { ...c, candidates, sectionC,
    questions: c.questions.filter(q => !q.cardId || candidates.some(a => a.id === q.cardId)),
  };
  return JSON.stringify(next) === JSON.stringify(c) ? c : next;
}

/** Article-level answers cannot be submitted before deterministic expansion. A Yes still waiting
 * for the engine (pending) is not confirmed yet: it stays a card until its decision is acknowledged. */
export function confirmedProvisions(c: Case): string[] {
  return [...new Set(c.candidates.filter(a => a.answer === "yes" && !a.pending && isProvision(a.provision)
    && c.sectionC.some(r => canonicalProvision(r.provision) === canonicalProvision(a.provision)))
    .map(a => a.provision))];
}

/** The same cards with the same answers, in any order (a lookup that only re-orders is not an edit). */
export function sameCards(a: Case["candidates"], b: Case["candidates"]): boolean {
  if (a.length !== b.length) return false;
  const key = (list: Case["candidates"]) => JSON.stringify([...list].sort((x, y) => (x.id < y.id ? -1 : x.id > y.id ? 1 : 0)));
  return key(a) === key(b);
}
