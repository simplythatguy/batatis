import type { Case } from "./types";

type EvidenceContext = { provision_id?: string; provision?: { provision_id: string } | null; function?: string | null; objective?: string | null };

/** Compact choices retain sentence, function and objective identity. Full source
 * wording stays in the guidance; these labels are navigation, not code quotations. */
export function evidenceTask(c: Case, item: EvidenceContext): string {
  const provision = item.provision?.provision_id ?? item.provision_id;
  const row = c.sectionC.find(r => r.provision === provision);
  const text = item.function ? row?.terms?.[item.function] : undefined;
  if (!text) return provision ? `${provision} · Identify benchmark` : "Choose a code reference first";
  const article = provision?.split("(")[0];
  const singleArticle = new Set(c.sectionC.map(r => r.provision.split("(")[0])).size === 1;
  const sentence = provision?.match(/\((\d+)\)(.*)$/);
  const context = singleArticle && sentence ? `${sentence[1]}${sentence[2]}` : provision;
  const scope = item.objective?.startsWith("OS") ? "People"
    : item.objective?.startsWith("OP3") ? "Nearby buildings"
    : item.objective?.startsWith("OP") ? "Building" : "Performance";
  const purpose = text.replace(/^To\s+/i, "").split(/[.;]/)[0];
  const task = item.function === "F03" ? "fire spread" : item.function === "F04" ? "fire collapse" : purpose;
  const label = `${context ?? article} · ${scope}: ${task}`;
  // Other objectives can share a short meaning. Retain their exact identity rather
  // than silently presenting two tasks as the same choice.
  const sameMeaning = row?.pairs.flatMap(p => p.functions.includes(item.function ?? "") ? p.objectives : [])
    .filter(o => o !== item.objective && o.slice(0, 3) === item.objective?.slice(0, 3));
  return sameMeaning?.length ? `${label} · ${item.objective}` : label;
}
