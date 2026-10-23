/**
 * Search over the offices an applicant can pick as the reviewing authority. Pure and
 * order-stable so the picker stays quick with hundreds of entries: every typed word must appear
 * in the name or id; names that start with the first word, then words that start with it, come first.
 */
export type AuthorityOption = { id: string; name: string };

/** How many matches the list renders at once; the rest wait behind "keep typing". */
export const AUTHORITY_LIST_LIMIT = 50;

function fold(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function filterAuthorities(options: readonly AuthorityOption[], query: string, limit = AUTHORITY_LIST_LIMIT): { shown: AuthorityOption[]; total: number } {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (!words.length) return { shown: options.slice(0, limit), total: options.length };
  const ranked: { o: AuthorityOption; rank: number; at: number }[] = [];
  options.forEach((o, at) => {
    const name = fold(o.name);
    const hay = `${name} ${fold(o.id)}`;
    if (!words.every((w) => hay.includes(w))) return;
    const first = words[0];
    const rank = name.startsWith(first) ? 0 : name.split(/[\s\-/(),.]+/).some((p) => p.startsWith(first)) ? 1 : 2;
    ranked.push({ o, rank, at });
  });
  ranked.sort((a, b) => a.rank - b.rank || a.at - b.at);
  return { shown: ranked.slice(0, limit).map((r) => r.o), total: ranked.length };
}
