/** Listbox typeahead: a typed letter moves to the next option, wrapping past the end. */
const words = (label: string) => label.toLowerCase().split(/[\s·/,()-]+/).filter(Boolean);

/** The next option after `from` (wrapping) with a word starting with `key`, else one containing it; -1 for none. */
export function typeahead(labels: string[], from: number, key: string): number {
  const k = key.toLowerCase(), n = labels.length;
  const order = Array.from({ length: n }, (_, i) => (from + 1 + i) % n);
  const hit = order.find((i) => words(labels[i]).some((w) => w.startsWith(k)));
  return hit ?? order.find((i) => labels[i].toLowerCase().includes(k)) ?? -1;
}
